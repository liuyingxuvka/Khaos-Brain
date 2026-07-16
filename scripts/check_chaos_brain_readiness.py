"""Compose every current Chaos Brain upgrade gate into one hard receipt.

The release gate is the sole owner of expensive leaf execution.  Downstream
consumers (notably Model-Test Alignment and OpenSpec closure) consume the
immutable proof artifacts emitted here instead of recursively launching the
same commands again.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from typing import Any, Iterable
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    # Direct file execution sets sys.path[0] to ``scripts``. Insert the owning
    # repository explicitly so sibling script modules cannot resolve through
    # an unrelated installed ``scripts`` namespace.
    sys.path.insert(0, str(REPO_ROOT))
from local_kb.transactional_install import tree_manifest  # noqa: E402
from local_kb.automation_contracts import (  # noqa: E402
    AGGREGATE_SKILLGUARD_TIMEOUT_SECONDS,
)
from local_kb.process_control import run_with_timeout_cleanup  # noqa: E402

DEFAULT_RECEIPT = REPO_ROOT / ".local" / "assurance" / "chaos_brain_readiness.json"
DEFAULT_EVIDENCE_ROOT = REPO_ROOT / ".local" / "assurance" / "validation-evidence"
EVIDENCE_SCHEMA = "khaos-brain.validation-evidence.v1"

_CHECKBOX_RE = re.compile(r"(?m)^(\s*-\s*\[)[ xX](\])")


def _semantic_bytes(path: Path, relative: Path) -> bytes:
    """Return behavior-significant bytes for freshness decisions.

    OpenSpec task checkbox state is closure bookkeeping.  The task wording
    remains behavior-significant, but changing ``[ ]`` to ``[x]`` after a
    successful run must not invalidate the evidence that licensed the change.
    """

    raw = path.read_bytes()
    if (
        relative.name == "tasks.md"
        and len(relative.parts) >= 3
        and relative.parts[0] == "openspec"
        and relative.parts[1] == "changes"
    ):
        text = raw.decode("utf-8", errors="replace")
        return _CHECKBOX_RE.sub(r"\1 \2", text).encode("utf-8")
    return raw


def _watched_files(repo_root: Path) -> Iterable[Path]:
    roots = (
        repo_root / "local_kb",
        repo_root / "scripts",
        repo_root / "tests",
        repo_root / ".flowguard",
        repo_root / ".agents" / "skills",
        repo_root / "templates",
        repo_root / "openspec",
    )
    suffixes = {".py", ".md", ".json", ".yaml", ".yml", ".toml", ".template"}
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            relative = path.relative_to(repo_root)
            if any(
                part in {"__pycache__", "evidence", "runs", "test-results"}
                for part in relative.parts
            ):
                continue
            yield path
    for name in (
        "AGENTS.md",
        "PROJECT_SPEC.md",
        "README.md",
        "VERSION",
        "pyproject.toml",
    ):
        path = repo_root / name
        if path.is_file():
            yield path


def _source_snapshot(repo_root: Path) -> dict[str, Any]:
    rows = []
    for path in _watched_files(repo_root):
        relative = path.relative_to(repo_root)
        semantic = _semantic_bytes(path, relative)
        rows.append(
            {
                "path": relative.as_posix(),
                "semantic_sha256": hashlib.sha256(semantic).hexdigest(),
                "digest_policy": (
                    "openspec-task-checkbox-normalized"
                    if relative.name == "tasks.md"
                    and len(relative.parts) >= 3
                    and relative.parts[0] == "openspec"
                    and relative.parts[1] == "changes"
                    else "raw-bytes"
                ),
            }
        )
    body = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "file_count": len(rows),
        "digest": hashlib.sha256(body).hexdigest(),
        "files": rows,
    }


def _tree_python_digest(root: Path) -> str:
    if not root.exists():
        return "missing"
    rows = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or not path.is_file():
            continue
        rows.append(
            (
                path.relative_to(root).as_posix(),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "missing"


def _skillguard_toolchain_identity() -> dict[str, Any]:
    configured = os.environ.get(
        "KHAOS_BRAIN_SKILLGUARD_VALIDATION_ROOT", ""
    ).strip()
    root = (
        Path(configured).resolve()
        if configured
        else Path.home() / ".codex" / "skills" / "skillguard"
    )
    manifest = tree_manifest(root) if root.is_dir() else {}
    digest = str(manifest.get("digest") or "")
    expected = os.environ.get(
        "KHAOS_BRAIN_SKILLGUARD_VALIDATION_DIGEST", ""
    ).strip()
    if not (
        digest
        and (root / "scripts" / "skillguard_compile.py").is_file()
        and (root / "scripts" / "skillguard.py").is_file()
    ):
        raise RuntimeError("Current SkillGuard validation toolchain is unavailable")
    if expected and digest != expected:
        raise RuntimeError(
            "Frozen SkillGuard validation toolchain digest does not match its declared identity"
        )
    return {
        "digest": digest,
        "file_count": int(manifest.get("file_count") or 0),
        "compiler_sha256": hashlib.sha256(
            (root / "scripts" / "skillguard_compile.py").read_bytes()
        ).hexdigest(),
        "cli_sha256": hashlib.sha256(
            (root / "scripts" / "skillguard.py").read_bytes()
        ).hexdigest(),
    }


def _flowguard_toolchain_identity(flowguard_module: Any) -> dict[str, Any]:
    configured = os.environ.get(
        "KHAOS_BRAIN_FLOWGUARD_VALIDATION_ROOT", ""
    ).strip()
    imported_root = Path(flowguard_module.__file__).resolve().parent
    root = Path(configured).resolve() if configured else imported_root
    try:
        imported_root.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(
            "Imported FlowGuard resolved outside the frozen validation toolchain"
        ) from exc
    manifest = tree_manifest(root) if root.is_dir() else {}
    digest = str(manifest.get("digest") or "")
    expected = os.environ.get(
        "KHAOS_BRAIN_FLOWGUARD_VALIDATION_DIGEST", ""
    ).strip()
    if not digest or not (root / "__init__.py").is_file():
        raise RuntimeError("Current FlowGuard validation toolchain is unavailable")
    if expected and digest != expected:
        raise RuntimeError(
            "Frozen FlowGuard validation toolchain digest does not match its declared identity"
        )
    return {
        "digest": digest,
        "file_count": int(manifest.get("file_count") or 0),
        "root": str(root),
    }


def _logicguard_toolchain_identity(logicguard_module: Any) -> dict[str, Any]:
    configured = os.environ.get(
        "KHAOS_BRAIN_LOGICGUARD_VALIDATION_ROOT", ""
    ).strip()
    imported_root = Path(logicguard_module.__file__).resolve().parent
    root = Path(configured).resolve() if configured else imported_root
    try:
        imported_root.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(
            "Imported LogicGuard resolved outside the frozen validation toolchain"
        ) from exc
    manifest = tree_manifest(root) if root.is_dir() else {}
    digest = str(manifest.get("digest") or "")
    expected = os.environ.get(
        "KHAOS_BRAIN_LOGICGUARD_VALIDATION_DIGEST", ""
    ).strip()
    required_symbols = (
        "FileModelStore",
        "FileModelMeshStore",
        "MeshNodeOverride",
        "simulate_mesh",
    )
    missing = [name for name in required_symbols if not hasattr(logicguard_module, name)]
    if (
        not digest
        or not (root / "__init__.py").is_file()
        or missing
        or str(getattr(logicguard_module, "SCHEMA_VERSION", ""))
        != "logicguard.model-store.v1"
        or str(getattr(logicguard_module, "MESH_SCHEMA_VERSION", ""))
        != "logicguard.model-mesh.v1"
    ):
        raise RuntimeError("Current LogicGuard validation toolchain is unavailable")
    if expected and digest != expected:
        raise RuntimeError(
            "Frozen LogicGuard validation toolchain digest does not match its declared identity"
        )
    return {
        "digest": digest,
        "file_count": int(manifest.get("file_count") or 0),
        "root": str(root),
        "version": str(getattr(logicguard_module, "__version__", "")),
        "model_store_schema": str(getattr(logicguard_module, "SCHEMA_VERSION", "")),
        "mesh_schema": str(getattr(logicguard_module, "MESH_SCHEMA_VERSION", "")),
    }


def _verifier_fingerprint() -> dict[str, Any]:
    import flowguard
    import logicguard

    flowguard_identity = _flowguard_toolchain_identity(flowguard)
    logicguard_identity = _logicguard_toolchain_identity(logicguard)
    payload = {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pytest_version": _package_version("pytest"),
        "flowguard_schema_version": str(flowguard.SCHEMA_VERSION),
        "flowguard_package_digest": str(flowguard_identity["digest"]),
        "flowguard_toolchain": flowguard_identity,
        "logicguard_toolchain": logicguard_identity,
        "skillguard_toolchain": _skillguard_toolchain_identity(),
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["digest"] = hashlib.sha256(body).hexdigest()
    return payload


def _environment_contract(repo_root: Path) -> dict[str, str]:
    import flowguard
    import logicguard

    skillguard_identity = _skillguard_toolchain_identity()
    flowguard_identity = _flowguard_toolchain_identity(flowguard)
    logicguard_identity = _logicguard_toolchain_identity(logicguard)
    return {
        "cwd": str(repo_root.resolve()),
        "KHAOS_BRAIN_ASSURANCE_ACTIVE": "1",
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        "python_executable": str(Path(sys.executable).resolve()),
        "skillguard_toolchain_digest": str(skillguard_identity["digest"]),
        "flowguard_toolchain_digest": str(flowguard_identity["digest"]),
        "logicguard_toolchain_digest": str(logicguard_identity["digest"]),
    }


def _semantic_argv(command: list[str]) -> list[str]:
    return [
        "--junitxml=<RESULT>" if str(part).startswith("--junitxml=") else str(part)
        for part in command
    ]


def _command_identity(
    command: list[str],
    *,
    source_digest: str,
    verifier_digest: str,
    environment_contract: dict[str, str],
) -> str:
    payload = {
        "argv": _semantic_argv(command),
        "executable_identity": _executable_identity(command[0]),
        "source_digest": source_digest,
        "verifier_digest": verifier_digest,
        "environment_contract": environment_contract,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@lru_cache(maxsize=32)
def _resolved_executable_identity(requested: str) -> dict[str, Any]:
    resolved = shutil.which(str(requested))
    if resolved is None:
        candidate = Path(str(requested)).expanduser()
        if candidate.is_file():
            resolved = str(candidate.resolve())
    path = Path(resolved).resolve() if resolved else None
    content_digest = ""
    content_identity_status = "unavailable"
    if path and path.is_file():
        try:
            content_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            content_identity_status = "unreadable-system-launcher"
        else:
            content_identity_status = "sha256"
    return {
        "requested": str(requested),
        "available": bool(path and path.is_file()),
        "resolved_path": str(path) if path else "",
        "sha256": content_digest,
        "content_identity_status": content_identity_status,
    }


def _executable_identity(requested: str) -> dict[str, Any]:
    return dict(_resolved_executable_identity(str(requested)))


def _commands(
    repo_root: Path,
    codex_home: Path,
    *,
    pre_restore: bool,
    junit_path: Path | None = None,
) -> dict[str, list[str]]:
    junit_path = junit_path or (
        DEFAULT_EVIDENCE_ROOT / "adhoc" / "full-regression.junit.xml"
    )
    capability_receipt = junit_path.parent / "full_regression.receipt.json"
    commands = {
        "flowguard_models": [
            sys.executable,
            ".flowguard/run_kb_convergence_checks.py",
        ],
        "flowguard_meshes": [
            sys.executable,
            "scripts/run_flowguard_suite.py",
            "--json",
            "--no-write-receipt",
        ],
        "logicguard_authority_cutover_model": [
            sys.executable,
            ".flowguard/khaos_brain_logicguard_authority_cutover.py",
        ],
        "logicguard_field_lifecycle": [
            sys.executable,
            ".flowguard/khaos_brain_logicguard_field_lifecycle.py",
        ],
        "logicguard_model_mesh": [
            sys.executable,
            ".flowguard/khaos_brain_logicguard_model_mesh.py",
        ],
        "logicguard_code_structure": [
            sys.executable,
            ".flowguard/khaos_brain_logicguard_code_structure.py",
        ],
        "logicguard_model_test_contract": [
            sys.executable,
            ".flowguard/khaos_brain_logicguard_model_test_alignment.py",
        ],
        "logicguard_test_mesh": [
            sys.executable,
            ".flowguard/khaos_brain_logicguard_test_mesh.py",
        ],
        "logicguard_runtime_model_miss": [
            sys.executable,
            ".flowguard/khaos_brain_logicguard_runtime_model_miss.py",
        ],
        "logicguard_runtime": [
            sys.executable,
            "scripts/check_khaos_logicguard_runtime.py",
            "--json",
            "--repo-root",
            str(repo_root),
        ],
        "logicguard_openspec": [
            "openspec",
            "validate",
            "make-khaos-brain-logicguard-native",
            "--type",
            "change",
            "--strict",
            "--json",
            "--no-interactive",
        ],
        "skillguard_source_install_parity": [
            sys.executable,
            "scripts/check_kb_skillguard.py",
            "--json",
            "--execute-checks",
            "--capability-receipt",
            str(capability_receipt),
            "--codex-home",
            str(codex_home),
        ],
        "skillguard_source_assurance": [
            sys.executable,
            "scripts/check_kb_skillguard.py",
            "--json",
            "--source-only",
            "--execute-checks",
            "--capability-receipt",
            str(capability_receipt),
            "--codex-home",
            str(codex_home),
        ],
        "retired_architect_absence": [
            sys.executable,
            "scripts/check_retired_kb_architect.py",
            "--json",
            "--codex-home",
            str(codex_home),
        ],
        "current_runtime_only": [
            sys.executable,
            "scripts/check_current_runtime_only.py",
            "--json",
            "--repo-root",
            str(repo_root),
        ],
        "retrieval_quality": [
            sys.executable,
            "scripts/evaluate_kb_retrieval.py",
            "--json",
            "--require-thresholds",
            "--repo-root",
            str(repo_root),
        ],
        "full_regression": [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests",
            f"--junitxml={junit_path}",
        ],
    }
    if not pre_restore:
        commands["install_health"] = [
            sys.executable,
            "scripts/install_codex_kb.py",
            "--check",
            "--json",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
        ]
    return commands


def _test_modules(repo_root: Path) -> dict[str, str]:
    modules: dict[str, str] = {}
    tests_root = repo_root / "tests"
    if not tests_root.exists():
        return modules
    for path in tests_root.rglob("*.py"):
        relative = path.relative_to(repo_root).as_posix()
        module = relative.removesuffix(".py").replace("/", ".")
        modules[module] = relative
    return modules


def _unique_test_module_aliases(modules: Mapping[str, str]) -> dict[str, str]:
    """Return only unambiguous pytest JUnit module aliases.

    Pytest may emit ``tests.test_sample`` on one platform and ``test_sample``
    on another for the same collected file.  Both are valid JUnit projections
    of the canonical repository node.  Short aliases are admitted only when
    they identify exactly one repository test module, so a receipt can never
    gain coverage by guessing between duplicate basenames.
    """

    candidates: dict[str, set[str]] = {}
    for module in modules:
        parts = module.split(".")
        aliases = {module}
        if parts and parts[0] == "tests":
            aliases.update(".".join(parts[index:]) for index in range(1, len(parts)))
        for alias in aliases:
            if alias:
                candidates.setdefault(alias, set()).add(module)
    return {
        alias: next(iter(owners))
        for alias, owners in candidates.items()
        if len(owners) == 1
    }


def _junit_summary(path: Path, repo_root: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": str(path.resolve()),
        "present": path.is_file(),
        "sha256": "",
        "testcase_count": 0,
        "passed_node_ids": [],
        "skipped_node_ids": [],
        "failed_node_ids": [],
        "errored_node_ids": [],
        "unparsed_cases": [],
        "parse_error": "",
    }
    if not path.is_file():
        return summary
    summary["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    modules = _test_modules(repo_root)
    module_aliases = _unique_test_module_aliases(modules)
    ordered_aliases = sorted(module_aliases, key=len, reverse=True)
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        summary["parse_error"] = f"{type(exc).__name__}:{exc}"
        return summary
    for case in root.iter("testcase"):
        summary["testcase_count"] += 1
        classname = str(case.get("classname") or "")
        name = str(case.get("name") or "")
        alias = next(
            (
                candidate
                for candidate in ordered_aliases
                if classname == candidate or classname.startswith(candidate + ".")
            ),
            "",
        )
        if not alias or not name:
            summary["unparsed_cases"].append(
                {"classname": classname, "name": name}
            )
            continue
        module = module_aliases[alias]
        class_suffix = classname[len(alias) :].lstrip(".")
        parts = [modules[module]]
        if class_suffix:
            parts.extend(part for part in class_suffix.split(".") if part)
        parts.append(name)
        node_id = "::".join(parts)
        if case.find("skipped") is not None:
            summary["skipped_node_ids"].append(node_id)
        elif case.find("failure") is not None:
            summary["failed_node_ids"].append(node_id)
        elif case.find("error") is not None:
            summary["errored_node_ids"].append(node_id)
        else:
            summary["passed_node_ids"].append(node_id)
    summary["covered_node_ids"] = sorted(
        {
            *summary["passed_node_ids"],
            *summary["skipped_node_ids"],
            *summary["failed_node_ids"],
            *summary["errored_node_ids"],
        }
    )
    return summary


def _proof_ref(path: Path) -> dict[str, Any]:
    present = path.is_file()
    return {
        "path": str(path.resolve()),
        "present": present,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if present else "",
    }


def _run(
    item: tuple[str, list[str]],
    repo_root: Path,
    *,
    evidence_dir: Path,
    source_snapshot: dict[str, Any],
    verifier_fingerprint: dict[str, Any],
    inventory_revision: str = "",
    timeout_seconds: int = 3600,
) -> tuple[str, dict[str, Any]]:
    name, command = item
    executable_identity = _executable_identity(command[0])
    execution_command = [
        str(executable_identity.get("resolved_path") or command[0]),
        *command[1:],
    ]
    started = datetime.now(timezone.utc)
    environment = os.environ.copy()
    environment["KHAOS_BRAIN_ASSURANCE_ACTIVE"] = "1"
    env_contract = _environment_contract(repo_root)
    identity = _command_identity(
        command,
        source_digest=str(source_snapshot["digest"]),
        verifier_digest=str(verifier_fingerprint["digest"]),
        environment_contract=env_contract,
    )
    timed_out = False
    if not executable_identity.get("available"):
        exit_code = 127
        stdout = ""
        stderr = f"Executable is unavailable: {command[0]}"
        timeout_cleanup = {}
    else:
        try:
            completed = run_with_timeout_cleanup(
                execution_command,
                cwd=repo_root,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=timeout_seconds,
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            stdout = str(exc.stdout or "")
            stderr = str(exc.stderr or "")
            timeout_cleanup = dict(getattr(exc, "cleanup_receipt", {}) or {})
        except OSError as exc:
            exit_code = 127
            stdout = ""
            stderr = f"{type(exc).__name__}: {exc}"
            timeout_cleanup = {}
        else:
            timeout_cleanup = {}
    finished = datetime.now(timezone.utc)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = evidence_dir / f"{name}.stdout.txt"
    stderr_path = evidence_dir / f"{name}.stderr.txt"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    junit_path = next(
        (
            Path(part.split("=", 1)[1])
            for part in command
            if str(part).startswith("--junitxml=")
        ),
        None,
    )
    junit = _junit_summary(junit_path, repo_root) if junit_path else {}
    terminal_status = (
        "timeout" if timed_out else "passed" if exit_code == 0 else "failed"
    )
    try:
        json_payload = json.loads(stdout)
    except json.JSONDecodeError:
        json_payload = None
    proof_path = junit_path if junit_path and junit_path.is_file() else stdout_path
    receipt = {
        "schema_version": EVIDENCE_SCHEMA,
        "receipt_id": f"validation:{name}:{identity}",
        "name": name,
        "execution": "executed",
        "identity_fingerprint": identity,
        "command": command,
        "execution_command": execution_command,
        "executable_identity": executable_identity,
        "semantic_argv": _semantic_argv(command),
        "cwd": str(repo_root.resolve()),
        "environment_contract": env_contract,
        "input_fingerprints": {
            "source": source_snapshot["digest"],
            "verifier": verifier_fingerprint["digest"],
        },
        "inventory_revision": inventory_revision,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "terminal_status": terminal_status,
        "timed_out": timed_out,
        "timeout_cleanup": timeout_cleanup,
        "cleanup_confirmed": (
            timeout_cleanup.get("cleanup_confirmed") is True
            if timed_out
            else True
        ),
        "exit_code": exit_code,
        "ok": exit_code == 0 and not timed_out,
        "stdout_path": str(stdout_path.resolve()),
        "stderr_path": str(stderr_path.resolve()),
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
        "stdout_tail": stdout[-6000:],
        "stderr_tail": stderr[-6000:],
        "json_payload": json_payload,
        "junit": junit,
        "covered_node_ids": list(junit.get("covered_node_ids", [])),
        "skipped_node_ids": list(junit.get("skipped_node_ids", [])),
        "proof_artifact_ref": _proof_ref(proof_path),
    }
    receipt_path = evidence_dir / f"{name}.receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    receipt["receipt_path"] = str(receipt_path.resolve())
    receipt["receipt_sha256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    return name, receipt


def _current_full_regression_receipt(
    current_manifest_path: Path | None,
    command: list[str],
    repo_root: Path,
    *,
    source_snapshot: dict[str, Any],
    verifier_fingerprint: dict[str, Any],
) -> dict[str, Any] | None:
    """Return one still-current immutable full-regression owner receipt.

    Only the expensive repository-wide pytest owner is eligible. The receipt
    is reusable only when its canonical bytes, proof artifact, JUnit inventory,
    owner inputs, command semantics, and execution environment all still match.
    An unrelated aggregate sibling being added or removed does not stale this
    owner receipt; any owner input change does.
    """

    if current_manifest_path is None:
        return None
    current_manifest_path = Path(current_manifest_path).resolve()
    evidence_root = current_manifest_path.parent
    try:
        manifest = json.loads(current_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(manifest, dict) or manifest.get("schema_version") != EVIDENCE_SCHEMA:
        return None
    entries = manifest.get("entries")
    entry = entries.get("full_regression") if isinstance(entries, dict) else None
    if not isinstance(entry, dict):
        return None
    raw_receipt_path = str(entry.get("receipt_path") or "")
    expected_receipt_hash = str(entry.get("receipt_sha256") or "")
    if not raw_receipt_path or not expected_receipt_hash:
        return None
    receipt_path = Path(raw_receipt_path).resolve()
    try:
        receipt_path.relative_to(evidence_root)
        receipt_bytes = receipt_path.read_bytes()
    except (OSError, ValueError):
        return None
    receipt_hash = hashlib.sha256(receipt_bytes).hexdigest()
    if receipt_hash != expected_receipt_hash:
        return None
    try:
        receipt = json.loads(receipt_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(receipt, dict):
        return None

    source_digest = str(source_snapshot.get("digest") or "")
    verifier_digest = str(verifier_fingerprint.get("digest") or "")
    environment_contract = _environment_contract(repo_root)
    identity = _command_identity(
        command,
        source_digest=source_digest,
        verifier_digest=verifier_digest,
        environment_contract=environment_contract,
    )
    stored_command = receipt.get("command")
    stored_inputs = receipt.get("input_fingerprints")
    if not isinstance(stored_command, list) or not isinstance(stored_inputs, dict):
        return None
    if _semantic_argv([str(item) for item in stored_command]) != _semantic_argv(command):
        return None
    if receipt.get("semantic_argv") != _semantic_argv(command):
        return None
    if receipt.get("identity_fingerprint") != identity:
        return None
    if receipt.get("receipt_id") != f"validation:full_regression:{identity}":
        return None
    if stored_inputs != {"source": source_digest, "verifier": verifier_digest}:
        return None
    if receipt.get("environment_contract") != environment_contract:
        return None
    if receipt.get("cwd") != str(repo_root.resolve()):
        return None
    if not (
        receipt.get("schema_version") == EVIDENCE_SCHEMA
        and receipt.get("name") == "full_regression"
        and receipt.get("execution") == "executed"
        and receipt.get("terminal_status") == "passed"
        and receipt.get("ok") is True
        and receipt.get("timed_out") is False
        and receipt.get("exit_code") == 0
    ):
        return None

    proof = receipt.get("proof_artifact_ref")
    junit = receipt.get("junit")
    if not isinstance(proof, dict) or not isinstance(junit, dict):
        return None
    raw_proof_path = str(proof.get("path") or "")
    if not raw_proof_path or not str(proof.get("sha256") or ""):
        return None
    proof_path = Path(raw_proof_path).resolve()
    try:
        proof_path.relative_to(evidence_root)
        proof_bytes = proof_path.read_bytes()
    except (OSError, ValueError):
        return None
    if hashlib.sha256(proof_bytes).hexdigest() != str(proof["sha256"]):
        return None
    observed_junit = _junit_summary(proof_path, repo_root)
    if not (
        observed_junit == junit
        and junit.get("present") is True
        and not junit.get("parse_error")
        and int(junit.get("testcase_count") or 0) > 0
    ):
        return None
    return {
        "receipt": receipt,
        "receipt_path": receipt_path,
        "receipt_sha256": receipt_hash,
        "current_manifest_path": current_manifest_path,
    }


def _materialize_full_regression_reuse(
    reusable: dict[str, Any],
    *,
    evidence_dir: Path,
    inventory_revision: str,
) -> dict[str, Any]:
    """Project an exact prior owner receipt into the current aggregate run."""

    source_path = Path(reusable["receipt_path"]).resolve()
    receipt = dict(reusable["receipt"])
    evidence_dir.mkdir(parents=True, exist_ok=True)
    alias_path = evidence_dir / "full_regression.receipt.json"
    shutil.copyfile(source_path, alias_path)
    alias_hash = hashlib.sha256(alias_path.read_bytes()).hexdigest()
    if alias_hash != reusable["receipt_sha256"]:
        raise RuntimeError("materialized full-regression receipt hash changed")
    source_inventory = str(receipt.get("inventory_revision") or "")
    return {
        **receipt,
        "execution": "reused",
        "inventory_revision": inventory_revision,
        "receipt_path": str(alias_path.resolve()),
        "receipt_sha256": alias_hash,
        "reuse_ticket": {
            "source_receipt_id": receipt["receipt_id"],
            "source_identity_fingerprint": receipt["identity_fingerprint"],
            "source_receipt_path": str(source_path),
            "source_receipt_sha256": reusable["receipt_sha256"],
            "source_manifest_path": str(reusable["current_manifest_path"]),
            "source_inventory_revision": source_inventory,
            "consumer_inventory_revision": inventory_revision,
            "scope_relation": "exact-owner-inputs; aggregate-sibling-inventory-independent",
            "current": True,
        },
    }


def _execute_plan(
    commands: dict[str, list[str]],
    repo_root: Path,
    *,
    evidence_dir: Path,
    source_snapshot: dict[str, Any],
    verifier_fingerprint: dict[str, Any],
    inventory_revision: str = "",
    current_manifest_path: Path | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    env_contract = _environment_contract(repo_root)
    owner_by_identity: dict[str, str] = {}
    owners: dict[str, list[str]] = {}
    aliases: dict[str, str] = {}
    for name, command in commands.items():
        identity = _command_identity(
            command,
            source_digest=str(source_snapshot["digest"]),
            verifier_digest=str(verifier_fingerprint["digest"]),
            environment_contract=env_contract,
        )
        owner = owner_by_identity.setdefault(identity, name)
        if owner == name:
            owners[name] = command
        else:
            aliases[name] = owner

    results: dict[str, dict[str, Any]] = {}
    # The repository-wide suite is the sole owner of capability pytest.  Run
    # it first on its exclusive lane so later SkillGuard source/install checks
    # can consume its exact JUnit receipt instead of launching nested copies.
    if "full_regression" in owners:
        reusable = _current_full_regression_receipt(
            current_manifest_path,
            owners["full_regression"],
            repo_root,
            source_snapshot=source_snapshot,
            verifier_fingerprint=verifier_fingerprint,
        )
        if reusable is not None:
            results["full_regression"] = _materialize_full_regression_reuse(
                reusable,
                evidence_dir=evidence_dir,
                inventory_revision=inventory_revision,
            )
        else:
            name, result = _run(
                ("full_regression", owners["full_regression"]),
                repo_root,
                evidence_dir=evidence_dir,
                source_snapshot=source_snapshot,
                verifier_fingerprint=verifier_fingerprint,
                inventory_revision=inventory_revision,
            )
            results[name] = result

    # Performance evidence and real scheduled production are both
    # resource-sensitive.  Keep them out of the ordinary parallel pool, then
    # run them in a fixed order: LogicGuard benchmarks first and installed
    # scheduled production last.  This prevents either owner from losing its
    # declared budget to sibling CPU or filesystem pressure.
    exclusive_sequence = (
        "logicguard_runtime",
        "skillguard_source_install_parity",
    )
    exclusive_names = set(exclusive_sequence)
    parallel = {
        name: cmd
        for name, cmd in owners.items()
        if name != "full_regression" and name not in exclusive_names
    }
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(parallel)))) as executor:
        results.update(
            executor.map(
                lambda item: _run(
                    item,
                    repo_root,
                    evidence_dir=evidence_dir,
                    source_snapshot=source_snapshot,
                    verifier_fingerprint=verifier_fingerprint,
                    inventory_revision=inventory_revision,
                    timeout_seconds=(
                        AGGREGATE_SKILLGUARD_TIMEOUT_SECONDS
                        if item[0] == "skillguard_source_install_parity"
                        else 3600
                    ),
                ),
                parallel.items(),
            )
        )

    for name in exclusive_sequence:
        if name not in owners:
            continue
        owner_name, result = _run(
            (name, owners[name]),
            repo_root,
            evidence_dir=evidence_dir,
            source_snapshot=source_snapshot,
            verifier_fingerprint=verifier_fingerprint,
            inventory_revision=inventory_revision,
            timeout_seconds=AGGREGATE_SKILLGUARD_TIMEOUT_SECONDS,
        )
        results[owner_name] = result

    for alias, owner in aliases.items():
        source = results[owner]
        results[alias] = {
            **source,
            "name": alias,
            "execution": "reused",
            "reuse_ticket": {
                "source_receipt_id": source["receipt_id"],
                "source_identity_fingerprint": source["identity_fingerprint"],
                "scope_relation": "exact-command-identity",
                "current": True,
            },
        }
    counts = Counter(
        row["identity_fingerprint"]
        for row in results.values()
        if row.get("execution") == "executed"
    )
    return results, dict(counts)


def _write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _inventory_revision(repo_root: Path, commands: dict[str, list[str]]) -> str:
    current_contract = (
        repo_root
        / "openspec"
        / "changes"
        / "make-khaos-brain-logicguard-native"
        / "verification-contract.yaml"
    )
    legacy_contract = (
        repo_root
        / "openspec"
        / "changes"
        / "converge-kb-learning-and-upgrade-migration"
        / "verification-contract.yaml"
    )
    contract = current_contract if current_contract.is_file() else legacy_contract
    payload = {
        "leaf_commands": {
            name: _semantic_argv(command) for name, command in sorted(commands.items())
        },
        "verification_contract_sha256": (
            hashlib.sha256(contract.read_bytes()).hexdigest()
            if contract.is_file()
            else "missing"
        ),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _alignment_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    from scripts import check_kb_model_test_alignment as alignment

    return alignment.build_report(evidence_manifest=manifest, run_missing=False)


def build_report(
    repo_root: Path,
    codex_home: Path,
    *,
    pre_restore: bool = False,
    evidence_root: Path = DEFAULT_EVIDENCE_ROOT,
) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    codex_home = Path(codex_home).resolve()
    before = _source_snapshot(repo_root)
    verifier = _verifier_fingerprint()
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + before["digest"][:12]
    )
    evidence_dir = Path(evidence_root).resolve() / run_id
    junit_path = evidence_dir / "full-regression.junit.xml"
    commands = _commands(
        repo_root,
        codex_home,
        pre_restore=pre_restore,
        junit_path=junit_path,
    )
    inventory_revision = _inventory_revision(repo_root, commands)
    results, identity_counts = _execute_plan(
        commands,
        repo_root,
        evidence_dir=evidence_dir,
        source_snapshot=before,
        verifier_fingerprint=verifier,
        inventory_revision=inventory_revision,
        current_manifest_path=Path(evidence_root).resolve() / "current.json",
    )

    leaf_after = _source_snapshot(repo_root)
    manifest: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "codex_home": str(codex_home),
        "pre_restore": pre_restore,
        "inventory_revision": inventory_revision,
        "source_snapshot_before": before,
        "source_snapshot_after_leaf_execution": leaf_after,
        "source_stable_during_leaf_execution": before["digest"] == leaf_after["digest"],
        "verifier_fingerprint": verifier,
        "entries": results,
        "exact_execution_identity_counts": identity_counts,
        "duplicate_exact_executions": [
            identity for identity, count in identity_counts.items() if count > 1
        ],
    }
    alignment_report = _alignment_from_manifest(manifest)
    alignment_ref = _write_json(evidence_dir / "model-test-alignment.json", alignment_report)
    results["model_code_test_alignment"] = {
        "schema_version": EVIDENCE_SCHEMA,
        "receipt_id": f"validation:model_code_test_alignment:{run_id}",
        "name": "model_code_test_alignment",
        "execution": "consumed",
        "identity_fingerprint": hashlib.sha256(
            json.dumps(
                sorted(
                    row["receipt_id"]
                    for row in results.values()
                    if row.get("receipt_id")
                ),
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "command": [
            sys.executable,
            "scripts/check_kb_model_test_alignment.py",
            "--evidence-manifest",
            str(evidence_dir / "manifest.json"),
        ],
        "terminal_status": "passed" if alignment_report.get("ok") else "failed",
        "timed_out": False,
        "exit_code": 0 if alignment_report.get("ok") else 1,
        "ok": alignment_report.get("ok") is True,
        "consumed_receipt_ids": sorted(
            row["receipt_id"] for row in results.values() if row.get("receipt_id")
        ),
        "proof_artifact_ref": alignment_ref,
        "report": alignment_report,
    }

    after = _source_snapshot(repo_root)
    source_stable = before["digest"] == after["digest"]
    manifest["entries"] = results
    manifest["source_snapshot_after"] = after
    manifest["source_stable"] = source_stable
    manifest["ok"] = (
        source_stable
        and not manifest["duplicate_exact_executions"]
        and all(item.get("ok") is True for item in results.values())
    )
    manifest_ref = _write_json(evidence_dir / "manifest.json", manifest)
    _write_json(Path(evidence_root).resolve() / "current.json", manifest)
    all_passed = all(item.get("ok") is True for item in results.values())
    return {
        "schema_version": 2,
        "check": "chaos-brain-aggregate-readiness",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "codex_home": str(codex_home),
        "pre_restore": pre_restore,
        "ok": all_passed and source_stable and not manifest["duplicate_exact_executions"],
        "source_snapshot_before": before,
        "source_snapshot_after": after,
        "source_stable_during_checks": source_stable,
        "verifier_fingerprint": verifier,
        "checks": results,
        "failed_checks": [name for name, item in results.items() if not item.get("ok")],
        "evidence_manifest": manifest_ref,
        "evidence_run_id": run_id,
        "exact_execution_identity_counts": identity_counts,
        "duplicate_exact_executions": manifest["duplicate_exact_executions"],
        "claim_boundary": (
            "Current final-source LogicGuard authority/model/mesh/projection, FlowGuard, "
            "OpenSpec, SkillGuard, retirement, install, retrieval, performance, "
            "and one repository-wide regression execution or exact current immutable owner "
            "receipt reuse. Model-Test Alignment consumes "
            "the exact leaf receipts; OpenSpec archival and external release publication "
            "remain separate explicit operations. Installer calls inside the aggregate "
            "regression are isolated fixtures; the outer upgrade owns real migration and "
            "restoration gates."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--no-write-receipt", action="store_true")
    parser.add_argument("--pre-restore", action="store_true")
    args = parser.parse_args()
    report = build_report(
        args.repo_root,
        args.codex_home,
        pre_restore=args.pre_restore,
        evidence_root=args.evidence_root,
    )
    if not args.no_write_receipt:
        _write_json(args.receipt, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Chaos Brain readiness:", "PASS" if report["ok"] else "FAIL")
        for name, item in report["checks"].items():
            print(("PASS" if item.get("ok") else "FAIL"), name, item.get("duration_seconds", 0))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
