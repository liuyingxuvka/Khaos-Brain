#!/usr/bin/env python3
"""Run or audit affected-only consumer installation assurance owners."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.install import MAINTENANCE_SKILL_SPECS, maintenance_skill_source_dir
from local_kb.process_control import run_with_timeout_cleanup
from local_kb.transactional_install import consumer_skill_manifest, tree_manifest


ASSURANCE_SCHEMA = "khaos-brain.consumer-install-assurance.v2"
OWNER_RECEIPT_SCHEMA = "khaos-brain.consumer-assurance-owner-receipt.v2"
OWNER_ORDER = (
    "consumer_projections",
    "flow_model",
    "reasoning_runtime",
    "retrieval_quality",
    "current_runtime",
)
OWNER_COMPONENTS = {
    "consumer_projections": (
        "consumer_source",
        "installed_projection",
    ),
    "flow_model": (
        "flow_model_source",
        "flowguard_toolchain",
    ),
    "reasoning_runtime": (
        "reasoning_source",
        "researchguard_toolchain",
        "runtime_authority",
    ),
    "retrieval_quality": (
        "retrieval_source",
        "runtime_authority",
    ),
    "current_runtime": (
        "current_runtime_source",
        "consumer_source",
        "installed_projection",
        "runtime_authority",
    ),
}
AUTHORITY_ONLY_COMPONENTS = ("planner_source",)
OWNER_TIMEOUT_SECONDS = 1800
MAX_STABILITY_PASSES = 3
AUTHOR_CONTROL_PATH_PART = "." + "skill" + "guard"


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _component_map_issues(snapshot: Mapping[str, Any]) -> list[str]:
    components = snapshot.get("components")
    if not isinstance(components, Mapping):
        return ["component-snapshot-missing"]
    declared = {
        *AUTHORITY_ONLY_COMPONENTS,
        *(
            component_id
            for component_ids in OWNER_COMPONENTS.values()
            for component_id in component_ids
        ),
    }
    actual = {str(component_id) for component_id in components}
    return [
        *(f"unknown-component:{component_id}" for component_id in sorted(actual - declared)),
        *(f"missing-component:{component_id}" for component_id in sorted(declared - actual)),
    ]


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _path_inventory(
    root: Path,
    paths: Iterable[Path],
    *,
    exclude_author_control: bool = False,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for candidate in paths:
        path = Path(candidate)
        if not path.is_absolute():
            path = root / path
        path = path.resolve()
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            if path.suffix == ".pyc" or "__pycache__" in path.parts:
                continue
            if exclude_author_control and AUTHOR_CONTROL_PATH_PART in path.parts:
                continue
            rows.append(
                {
                    "path": _relative_path(path, root),
                    "sha256": _file_sha256(path),
                    "size": path.stat().st_size,
                }
            )
            continue
        if path.is_dir():
            for item in sorted(path.rglob("*")):
                if not item.is_file():
                    continue
                if item.suffix == ".pyc" or "__pycache__" in item.parts:
                    continue
                if ".git" in item.parts:
                    continue
                if (
                    exclude_author_control
                    and AUTHOR_CONTROL_PATH_PART in item.parts
                ):
                    continue
                rows.append(
                    {
                        "path": _relative_path(item, root),
                        "sha256": _file_sha256(item),
                        "size": item.stat().st_size,
                    }
                )
            continue
        rows.append({"path": _relative_path(path, root), "missing": True})
    rows.sort(key=lambda row: str(row["path"]))
    return {
        "digest": _canonical_hash(rows),
        "file_count": sum(1 for row in rows if not row.get("missing")),
        "missing_count": sum(1 for row in rows if row.get("missing")),
    }


def _package_component(package_name: str) -> dict[str, Any]:
    spec = importlib.util.find_spec(package_name)
    if spec is None:
        return {"status": "missing", "digest": "missing"}
    locations = list(spec.submodule_search_locations or [])
    if locations:
        root = Path(locations[0]).resolve()
    elif spec.origin:
        root = Path(spec.origin).resolve().parent
    else:
        return {"status": "missing", "digest": "missing"}
    manifest = tree_manifest(root)
    return {
        "status": "current",
        "digest": str(manifest.get("digest") or ""),
        "file_count": int(manifest.get("file_count") or 0),
    }


def _bounded_payload_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Keep decision evidence without embedding an owner's full model trace."""

    summary: dict[str, Any] = {}
    for key in (
        "schema_version",
        "ok",
        "status",
        "policy_id",
        "claim_boundary",
        "error",
        "reason",
    ):
        value = payload.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            summary[key] = value
    for key, value in payload.items():
        if key in summary:
            continue
        if (
            isinstance(value, (str, int, float, bool))
            and (
                key.endswith("_count")
                or key.endswith("_digest")
                or key.endswith("_hash")
            )
        ):
            summary[key] = value
    for key in ("issues", "failed_checks", "errors", "warnings"):
        value = payload.get(key)
        if isinstance(value, list):
            summary[key] = [
                str(item)[:1000]
                for item in value[:50]
            ]
    checks = payload.get("checks")
    if isinstance(checks, list):
        failed_checks: list[dict[str, Any]] = []
        for row in checks:
            if not isinstance(row, Mapping) or row.get("ok") is True:
                continue
            failed_checks.append(
                {
                    str(key): value
                    for key, value in row.items()
                    if key in {
                        "id",
                        "name",
                        "ok",
                        "status",
                        "details",
                        "error",
                        "issues",
                    }
                }
            )
            if len(failed_checks) >= 50:
                break
        summary["checks"] = failed_checks
    skills = payload.get("skills")
    if isinstance(skills, Mapping):
        skill_rows: dict[str, dict[str, Any]] = {}
        for skill_id, row in list(skills.items())[:50]:
            if not isinstance(row, Mapping):
                continue
            skill_rows[str(skill_id)] = {
                str(key): value
                for key, value in row.items()
                if key in {
                    "ok",
                    "status",
                    "issues",
                    "failed_checks",
                    "error",
                }
            }
        summary["skills"] = skill_rows
    return summary


def _consumer_source_component(repo_root: Path) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    for spec in MAINTENANCE_SKILL_SPECS:
        skill_id = str(spec["name"])
        source = maintenance_skill_source_dir(repo_root, skill_id)
        try:
            manifest = consumer_skill_manifest(source)
            rows[skill_id] = {
                "digest": str(manifest.get("digest") or ""),
                "file_count": int(manifest.get("file_count") or 0),
            }
        except (OSError, RuntimeError) as exc:
            rows[skill_id] = {
                "digest": "invalid",
                "error": f"{type(exc).__name__}: {exc}",
            }
    support = _path_inventory(
        repo_root,
        (
            repo_root / "local_kb" / "transactional_install.py",
            repo_root / "local_kb" / "install.py",
        ),
    )
    return {
        "digest": _canonical_hash({"skills": rows, "support": support}),
        "skills": rows,
        "support": support,
    }


def _installed_projection_component(
    repo_root: Path,
    codex_home: Path,
) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    for spec in MAINTENANCE_SKILL_SPECS:
        skill_id = str(spec["name"])
        install_root = codex_home / "skills" / skill_id
        manifest = tree_manifest(install_root) if install_root.is_dir() else {}
        rows[skill_id] = {
            "digest": str(manifest.get("digest") or "missing"),
            "file_count": int(manifest.get("file_count") or 0),
        }
    global_skill = codex_home / "skills" / "predictive-kb-preflight"
    global_manifest = (
        tree_manifest(global_skill) if global_skill.is_dir() else {}
    )
    return {
        "digest": _canonical_hash(
            {
                "skills": rows,
                "global_skill": {
                    "digest": str(global_manifest.get("digest") or "missing"),
                    "file_count": int(global_manifest.get("file_count") or 0),
                },
            }
        ),
        "skills": rows,
        "global_skill": {
            "digest": str(global_manifest.get("digest") or "missing"),
            "file_count": int(global_manifest.get("file_count") or 0),
        },
    }


def _runtime_authority_component(repo_root: Path) -> dict[str, Any]:
    return _path_inventory(
        repo_root,
        (
            repo_root
            / ".local"
            / "khaos-brain"
            / "logicguard-authority"
            / "current-generation.json",
            repo_root / "kb" / "indexes" / "active.json",
            repo_root / "kb" / "taxonomy.yaml",
            repo_root / "kb" / "public",
            repo_root / "kb" / "private",
            repo_root / "kb" / "candidates",
        ),
    )


def _current_runtime_source_paths(repo_root: Path) -> tuple[Path, ...]:
    from scripts import check_current_runtime_only as current_runtime

    declared = {
        *current_runtime.FORBIDDEN_BY_FILE,
        *current_runtime.REQUIRED_BY_FILE,
    }
    return (
        repo_root / "scripts" / "check_current_runtime_only.py",
        *(repo_root / relative for relative in sorted(declared)),
    )


def build_component_snapshot(
    repo_root: Path,
    codex_home: Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    home = Path(codex_home).resolve()
    planner_source = _path_inventory(
        root,
        (root / "scripts" / "check_consumer_install_assurance.py",),
    )
    flow_model_paths = tuple(
        path
        for path in sorted((root / ".flowguard").rglob("*.py"))
        if "__pycache__" not in path.parts
    )
    flow_model_source = _path_inventory(
        root,
        (
            *flow_model_paths,
            root / "local_kb" / "automation_contracts.py",
            root / "local_kb" / "install.py",
            root / "local_kb" / "transactional_install.py",
            root / "scripts" / "run_kb_automation.py",
            root / "scripts" / "run_khaos_brain_manual_update.py",
        ),
    )
    reasoning_source = _path_inventory(
        root,
        (
            root / "scripts" / "check_khaos_logicguard_runtime.py",
            root / "local_kb" / "logicguard_models.py",
            root / "local_kb" / "maintenance_migration.py",
            root / "local_kb" / "model_maintenance.py",
            root / "local_kb" / "model_projection.py",
            root / "local_kb" / "search.py",
            root / "local_kb" / "active_index.py",
            root / "local_kb" / "models.py",
            root / "local_kb" / "common.py",
        ),
    )
    retrieval_source = _path_inventory(
        root,
        (
            root / "scripts" / "evaluate_kb_retrieval.py",
            root / "tests" / "fixtures" / "kb_retrieval_eval_cases.json",
            root / "local_kb" / "active_index.py",
            root / "local_kb" / "maintenance_standard.py",
            root / "local_kb" / "search.py",
            root / "local_kb" / "model_maintenance.py",
            root / "local_kb" / "model_projection.py",
            root / "local_kb" / "logicguard_models.py",
            root / "local_kb" / "models.py",
            root / "local_kb" / "common.py",
        ),
    )
    current_runtime_source = _path_inventory(
        root,
        _current_runtime_source_paths(root),
    )
    components = {
        "planner_source": planner_source["digest"],
        "consumer_source": _consumer_source_component(root)["digest"],
        "installed_projection": _installed_projection_component(root, home)[
            "digest"
        ],
        "flow_model_source": flow_model_source["digest"],
        "flowguard_toolchain": _canonical_hash(_package_component("flowguard")),
        "reasoning_source": reasoning_source["digest"],
        "researchguard_toolchain": _canonical_hash(
            _package_component("researchguard")
        ),
        "runtime_authority": _runtime_authority_component(root)["digest"],
        "retrieval_source": retrieval_source["digest"],
        "current_runtime_source": current_runtime_source["digest"],
    }
    return {
        "schema_version": "khaos-brain.consumer-assurance-components.v1",
        "components": components,
        "digest": _canonical_hash(components),
    }


def _owner_commands(repo_root: Path) -> dict[str, list[str]]:
    root = Path(repo_root).resolve()
    return {
        "flow_model": [
            sys.executable,
            ".flowguard/run_kb_convergence_checks.py",
            "--json",
            "--no-write-evidence",
        ],
        "reasoning_runtime": [
            sys.executable,
            "scripts/check_khaos_logicguard_runtime.py",
            "--json",
            "--repo-root",
            str(root),
        ],
        "retrieval_quality": [
            sys.executable,
            "scripts/evaluate_kb_retrieval.py",
            "--json",
            "--require-thresholds",
            "--repo-root",
            str(root),
        ],
        "current_runtime": [
            sys.executable,
            "scripts/check_current_runtime_only.py",
            "--json",
            "--repo-root",
            str(root),
            "--consumer-install",
        ],
    }


def _environment_contract() -> dict[str, Any]:
    return {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }


def _owner_identity(
    owner_id: str,
    command: list[str],
    component_snapshot: Mapping[str, Any],
) -> tuple[str, dict[str, str]]:
    components = component_snapshot.get("components")
    if not isinstance(components, Mapping):
        raise RuntimeError("consumer assurance component snapshot is invalid")
    input_components = {
        component_id: str(components.get(component_id) or "")
        for component_id in OWNER_COMPONENTS[owner_id]
    }
    identity = _canonical_hash(
        {
            "owner_id": owner_id,
            "command": command,
            "input_components": input_components,
            "environment": _environment_contract(),
        }
    )
    return identity, input_components


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _receipt_path(
    evidence_root: Path,
    owner_id: str,
    identity: str,
) -> Path:
    digest = identity.removeprefix("sha256:")
    return evidence_root / "receipts" / owner_id / f"{digest}.json"


def _receipt_reference(
    receipt_path: Path,
    evidence_root: Path,
) -> dict[str, str]:
    return {
        "path": receipt_path.resolve().relative_to(
            evidence_root.resolve()
        ).as_posix(),
        "sha256": _file_sha256(receipt_path),
    }


def _load_receipt_reference(
    evidence_root: Path,
    reference: object,
    *,
    owner_id: str,
    identity: str,
) -> dict[str, Any] | None:
    if not isinstance(reference, Mapping):
        return None
    relative = str(reference.get("path") or "")
    expected_hash = str(reference.get("sha256") or "")
    if not relative or not expected_hash:
        return None
    path = (evidence_root / relative).resolve()
    try:
        path.relative_to(evidence_root.resolve())
        raw = path.read_bytes()
    except (OSError, ValueError):
        return None
    if "sha256:" + hashlib.sha256(raw).hexdigest() != expected_hash:
        return None
    try:
        receipt = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(receipt, dict):
        return None
    if not (
        receipt.get("schema_version") == OWNER_RECEIPT_SCHEMA
        and receipt.get("owner_id") == owner_id
        and receipt.get("identity") == identity
        and receipt.get("status") == "passed"
        and receipt.get("ok") is True
        and receipt.get("timed_out") is False
        and receipt.get("cleanup_confirmed") is True
    ):
        return None
    return {
        "receipt": receipt,
        "reference": dict(reference),
        "path": str(path),
    }


def _consumer_projection_report(
    repo_root: Path,
    codex_home: Path,
) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    issues: list[str] = []
    for spec in MAINTENANCE_SKILL_SPECS:
        skill_id = str(spec["name"])
        source = maintenance_skill_source_dir(repo_root, skill_id)
        installed = codex_home / "skills" / skill_id
        try:
            expected = consumer_skill_manifest(source)
        except (OSError, RuntimeError) as exc:
            issues.append(f"{skill_id}:source:{type(exc).__name__}:{exc}")
            continue
        actual = tree_manifest(installed) if installed.is_dir() else {}
        row = {
            "expected_digest": str(expected.get("digest") or ""),
            "actual_digest": str(actual.get("digest") or ""),
            "expected_file_count": int(expected.get("file_count") or 0),
            "actual_file_count": int(actual.get("file_count") or 0),
        }
        rows[skill_id] = row
        if (
            row["expected_digest"] != row["actual_digest"]
            or (installed / AUTHOR_CONTROL_PATH_PART).exists()
        ):
            issues.append(f"{skill_id}:installed-consumer-projection-stale")
    return {
        "ok": not issues and len(rows) == len(MAINTENANCE_SKILL_SPECS),
        "rows": rows,
        "issues": issues,
    }


def _execute_owner(
    owner_id: str,
    command: list[str],
    repo_root: Path,
    codex_home: Path,
) -> dict[str, Any]:
    if owner_id == "consumer_projections":
        payload = _consumer_projection_report(repo_root, codex_home)
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return {
            "ok": payload["ok"],
            "exit_code": 0 if payload["ok"] else 1,
            "payload": payload,
            "stdout_sha256": "sha256:" + hashlib.sha256(encoded).hexdigest(),
            "stdout_byte_count": len(encoded),
            "stdout_tail": "",
            "stderr_tail": "",
            "timed_out": False,
            "cleanup_confirmed": True,
            "cleanup_receipt": {},
        }
    try:
        process = run_with_timeout_cleanup(
            command,
            cwd=str(repo_root),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=OWNER_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception as exc:
        cleanup = dict(getattr(exc, "cleanup_receipt", {}) or {})
        return {
            "ok": False,
            "exit_code": None,
            "payload": {},
            "stdout_sha256": "sha256:" + hashlib.sha256(b"").hexdigest(),
            "stdout_byte_count": 0,
            "stdout_tail": "",
            "stderr_tail": f"{type(exc).__name__}: {exc}"[-2000:],
            "timed_out": isinstance(exc, TimeoutError)
            or type(exc).__name__ == "TimeoutExpired",
            "cleanup_confirmed": bool(
                cleanup.get("cleanup_confirmed") is True
                and int(cleanup.get("remaining_process_count") or 0) == 0
            ),
            "cleanup_receipt": cleanup,
        }
    payload: dict[str, Any] = {}
    try:
        decoded = json.loads(process.stdout)
        if isinstance(decoded, dict):
            payload = decoded
    except json.JSONDecodeError:
        pass
    return {
        "ok": process.returncode == 0
        and (payload.get("ok") is not False if payload else True),
        "exit_code": process.returncode,
        "payload": payload,
        "stdout_sha256": "sha256:"
        + hashlib.sha256(process.stdout.encode("utf-8")).hexdigest(),
        "stdout_byte_count": len(process.stdout.encode("utf-8")),
        "stdout_tail": process.stdout[-2000:],
        "stderr_tail": process.stderr[-2000:],
        "timed_out": False,
        "cleanup_confirmed": True,
        "cleanup_receipt": {},
    }


def _receipt_from_execution(
    owner_id: str,
    identity: str,
    command: list[str],
    input_components: Mapping[str, str],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    ok = bool(
        result.get("ok")
        and result.get("timed_out") is False
        and result.get("cleanup_confirmed") is True
    )
    return {
        "schema_version": OWNER_RECEIPT_SCHEMA,
        "owner_id": owner_id,
        "identity": identity,
        "status": "passed" if ok else "failed",
        "ok": ok,
        "command": command,
        "input_components": dict(input_components),
        "environment": _environment_contract(),
        "exit_code": result.get("exit_code"),
        "payload": _bounded_payload_summary(
            result.get("payload")
            if isinstance(result.get("payload"), Mapping)
            else {}
        ),
        "stdout_sha256": str(result.get("stdout_sha256") or ""),
        "stdout_byte_count": int(result.get("stdout_byte_count") or 0),
        "stdout_tail": str(result.get("stdout_tail") or "")[-2000:],
        "stderr_tail": str(result.get("stderr_tail") or "")[-2000:],
        "timed_out": bool(result.get("timed_out")),
        "cleanup_confirmed": bool(result.get("cleanup_confirmed")),
        "cleanup_receipt": dict(result.get("cleanup_receipt") or {}),
    }


def _load_current(evidence_root: Path) -> dict[str, Any]:
    path = evidence_root / "current.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or payload.get("schema_version") != ASSURANCE_SCHEMA:
        return {}
    unsigned = {key: value for key, value in payload.items() if key != "receipt_hash"}
    if str(payload.get("receipt_hash") or "") != _canonical_hash(unsigned):
        return {}
    return payload


def _current_references(payload: Mapping[str, Any]) -> dict[str, Any]:
    references = payload.get("owner_receipts")
    return dict(references) if isinstance(references, Mapping) else {}


def audit_current_assurance(
    repo_root: Path,
    codex_home: Path,
    *,
    evidence_root: Path | None = None,
    expected_receipt_hash: str = "",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    home = Path(codex_home).resolve()
    evidence = (
        Path(evidence_root).resolve()
        if evidence_root is not None
        else home / ".khaos-brain-install" / "consumer-assurance"
    )
    snapshot = build_component_snapshot(root, home)
    current = _load_current(evidence)
    issues: list[str] = _component_map_issues(snapshot)
    if not current:
        issues.append("current-assurance-authority-missing-or-invalid")
    elif expected_receipt_hash and current.get("receipt_hash") != expected_receipt_hash:
        issues.append("install-state-assurance-receipt-hash-mismatch")
    if (
        current
        and str((current.get("component_snapshot") or {}).get("digest") or "")
        != str(snapshot.get("digest") or "")
    ):
        issues.append("current-assurance-component-snapshot-stale")
    commands = _owner_commands(root)
    references = _current_references(current)
    owners: dict[str, dict[str, Any]] = {}
    for owner_id in OWNER_ORDER:
        command = commands.get(owner_id, [])
        identity, input_components = _owner_identity(
            owner_id,
            command,
            snapshot,
        )
        loaded = _load_receipt_reference(
            evidence,
            references.get(owner_id),
            owner_id=owner_id,
            identity=identity,
        )
        owners[owner_id] = {
            "ok": loaded is not None,
            "identity": identity,
            "input_components": input_components,
            "execution": "audited",
        }
        if loaded is None:
            issues.append(f"{owner_id}:current-receipt-missing-or-stale")
    return {
        "schema_version": ASSURANCE_SCHEMA,
        "ok": not issues,
        "status": "current" if not issues else "stale",
        "repo_root": str(root),
        "codex_home": str(home),
        "evidence_root": str(evidence),
        "component_snapshot": snapshot,
        "owners": owners,
        "execution_count": 0,
        "issues": issues,
        "receipt_hash": str(current.get("receipt_hash") or ""),
        "claim_boundary": (
            "Read-only bounded currentness audit. It launches no validation owner "
            "and does not replace an affected-owner assurance execution."
        ),
    }


def build_report(
    repo_root: Path,
    codex_home: Path | None = None,
    *,
    evidence_root: Path | None = None,
    audit_only: bool = False,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    home = Path(codex_home or (Path.home() / ".codex")).resolve()
    evidence = (
        Path(evidence_root).resolve()
        if evidence_root is not None
        else home / ".khaos-brain-install" / "consumer-assurance"
    )
    if audit_only:
        return audit_current_assurance(
            root,
            home,
            evidence_root=evidence,
        )

    commands = _owner_commands(root)
    current = _load_current(evidence)
    candidate_references = _current_references(current)
    executed_owner_ids: list[str] = []
    reused_owner_ids: list[str] = []
    passes: list[dict[str, Any]] = []
    stable_snapshot: dict[str, Any] = {}
    stable_owner_rows: dict[str, dict[str, Any]] = {}
    stable_references: dict[str, Any] = {}
    failed_owner_ids: list[str] = []
    component_map_issues: list[str] = []

    for pass_index in range(1, MAX_STABILITY_PASSES + 1):
        before = build_component_snapshot(root, home)
        component_map_issues = _component_map_issues(before)
        if component_map_issues:
            stable_snapshot = before
            failed_owner_ids = ["component_map"]
            passes.append(
                {
                    "pass": pass_index,
                    "executed_owner_ids": [],
                    "reused_owner_ids": [],
                    "changed_component_ids": [],
                    "affected_owner_ids": [],
                }
            )
            break
        owner_rows: dict[str, dict[str, Any]] = {}
        next_references: dict[str, Any] = {}
        failed_owner_ids = []
        pass_executed: list[str] = []
        pass_reused: list[str] = []
        for owner_id in OWNER_ORDER:
            command = commands.get(owner_id, [])
            identity, input_components = _owner_identity(
                owner_id,
                command,
                before,
            )
            loaded = _load_receipt_reference(
                evidence,
                candidate_references.get(owner_id),
                owner_id=owner_id,
                identity=identity,
            )
            if loaded is not None:
                receipt = dict(loaded["receipt"])
                reference = dict(loaded["reference"])
                execution = "reused"
                pass_reused.append(owner_id)
                if owner_id not in reused_owner_ids:
                    reused_owner_ids.append(owner_id)
            else:
                result = _execute_owner(
                    owner_id,
                    command,
                    root,
                    home,
                )
                receipt = _receipt_from_execution(
                    owner_id,
                    identity,
                    command,
                    input_components,
                    result,
                )
                receipt_path = _receipt_path(evidence, owner_id, identity)
                if receipt.get("ok") is True:
                    if receipt_path.exists():
                        existing = json.loads(
                            receipt_path.read_text(encoding="utf-8")
                        )
                        if existing != receipt:
                            raise RuntimeError(
                                f"immutable assurance receipt collision for {owner_id}"
                            )
                    else:
                        _write_json_atomic(receipt_path, receipt)
                    reference = _receipt_reference(receipt_path, evidence)
                else:
                    reference = {}
                execution = "executed"
                pass_executed.append(owner_id)
                if owner_id not in executed_owner_ids:
                    executed_owner_ids.append(owner_id)
            next_references[owner_id] = reference
            owner_rows[owner_id] = {
                "ok": receipt.get("ok") is True,
                "status": str(receipt.get("status") or ""),
                "terminal_status": str(receipt.get("status") or ""),
                "identity": identity,
                "input_components": input_components,
                "execution": execution,
                "receipt": reference,
                "exit_code": receipt.get("exit_code"),
                "timed_out": bool(receipt.get("timed_out")),
                "cleanup_confirmed": bool(receipt.get("cleanup_confirmed")),
                "json_payload": receipt.get("payload") or {},
                "stdout_tail": str(receipt.get("stdout_tail") or "")[-2000:],
                "stderr_tail": str(receipt.get("stderr_tail") or "")[-2000:],
            }
            if receipt.get("ok") is not True:
                failed_owner_ids.append(owner_id)
        after = build_component_snapshot(root, home)
        before_components = dict(before.get("components") or {})
        after_components = dict(after.get("components") or {})
        changed_components = sorted(
            component_id
            for component_id in set(before_components) | set(after_components)
            if before_components.get(component_id) != after_components.get(component_id)
        )
        affected_after_change = sorted(
            owner_id
            for owner_id, component_ids in OWNER_COMPONENTS.items()
            if set(component_ids).intersection(changed_components)
        )
        passes.append(
            {
                "pass": pass_index,
                "executed_owner_ids": pass_executed,
                "reused_owner_ids": pass_reused,
                "changed_component_ids": changed_components,
                "affected_owner_ids": affected_after_change,
            }
        )
        if failed_owner_ids:
            stable_snapshot = after
            stable_owner_rows = owner_rows
            stable_references = next_references
            break
        if not changed_components:
            stable_snapshot = after
            stable_owner_rows = owner_rows
            stable_references = next_references
            break
        candidate_references = next_references
    else:
        failed_owner_ids = ["stability_limit"]

    ok = bool(not failed_owner_ids and passes and not passes[-1]["changed_component_ids"])
    current_payload: dict[str, Any] = {
        "schema_version": ASSURANCE_SCHEMA,
        "ok": ok,
        "status": "passed" if ok else "failed",
        "repo_root": str(root),
        "codex_home": str(home),
        "evidence_root": str(evidence),
        "component_snapshot": stable_snapshot,
        "owners": stable_owner_rows,
        "owner_receipts": stable_references,
        "executed_owner_ids": executed_owner_ids,
        "reused_owner_ids": reused_owner_ids,
        "execution_count": sum(
            len(item.get("executed_owner_ids") or []) for item in passes
        ),
        "failed_checks": failed_owner_ids,
        "issues": component_map_issues,
        "passes": passes,
        "claim_boundary": (
            "Exact component-to-owner consumer assurance. Unchanged immutable "
            "owner receipts are reused; only owners affected by changed declared "
            "inputs execute. There is no run-all fallback."
        ),
    }
    unsigned = dict(current_payload)
    current_payload["receipt_hash"] = _canonical_hash(unsigned)
    if ok:
        _write_json_atomic(evidence / "current.json", current_payload)
    return current_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=SCRIPT_REPO_ROOT)
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(
        args.repo_root,
        args.codex_home,
        evidence_root=args.evidence_root,
        audit_only=args.audit_only,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "Consumer install assurance:",
            "PASS" if report["ok"] else "FAIL",
        )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
