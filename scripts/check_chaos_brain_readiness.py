"""Compose the current target-owned Chaos Brain upgrade gates.

The repository-wide regression is the sole owner of its test execution.
Author-side SkillGuard maintenance is a separate static contract audit and is
never part of the installed consumer runtime or proof chain.
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
from typing import Any, Iterable, Mapping, Sequence
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    # Direct file execution sets sys.path[0] to ``scripts``. Insert the owning
    # repository explicitly so sibling script modules cannot resolve through
    # an unrelated installed ``scripts`` namespace.
    sys.path.insert(0, str(REPO_ROOT))
from local_kb.transactional_install import tree_manifest  # noqa: E402
from local_kb.automation_contracts import (  # noqa: E402
    AGGREGATE_ASSURANCE_TIMEOUT_SECONDS,
)
from local_kb.process_control import run_with_timeout_cleanup  # noqa: E402

DEFAULT_RECEIPT = REPO_ROOT / ".local" / "assurance" / "chaos_brain_readiness.json"
DEFAULT_EVIDENCE_ROOT = REPO_ROOT / ".local" / "assurance" / "validation-evidence"
EVIDENCE_SCHEMA = "khaos-brain.validation-evidence.v2"
EVIDENCE_POLICY_VERSION = "khaos-brain.owner-scoped-receipt.v2"

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
        repo_root / "schemas",
        repo_root / ".github",
        repo_root / "docs",
        repo_root / "assets",
    )
    suffixes = {
        ".py",
        ".md",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".template",
        ".txt",
        ".html",
        ".css",
        ".js",
        ".svg",
        ".png",
        ".ico",
        ".csv",
    }
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
        "requirements.txt",
        "requirements-dev.txt",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "CODEX_PROJECT_SPEC_predictive_kb.md",
        ".gitignore",
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


_EXACT_SOURCE_COMPONENTS = {
    "scripts/check_chaos_brain_readiness.py": "readiness_planner",
    "tests/test_chaos_brain_readiness.py": "readiness_planner",
    "tests/test_chaos_brain_readiness_projection.py": "readiness_planner",
    "scripts/check_khaos_logicguard_runtime.py": "logicguard_runtime_check",
    "scripts/check_kb_skillguard.py": "author_contract_check",
    "scripts/build_kb_automation_skillguard_contracts.py": "author_contract_check",
    "scripts/check_kb_automation_skillguard_depth.py": "author_contract_check",
    "scripts/check_retired_kb_architect.py": "retired_architect_check",
    "scripts/check_current_runtime_only.py": "current_runtime_check",
    "scripts/evaluate_kb_retrieval.py": "retrieval_quality_check",
    "scripts/install_codex_kb.py": "installation_check",
    "scripts/check_consumer_install_assurance.py": "installation_check",
    "scripts/run_flowguard_suite.py": "flowguard_mesh_source",
    ".flowguard/kb_convergence_upgrade_model.py": "flowguard_convergence_source",
    ".flowguard/run_kb_convergence_checks.py": "flowguard_convergence_source",
    ".flowguard/kb_skill_contract_model_common.py": "flowguard_convergence_source",
    ".flowguard/kb_sleep_skill_contract_model.py": "flowguard_convergence_source",
    ".flowguard/kb_dream_skill_contract_model.py": "flowguard_convergence_source",
    ".flowguard/kb_org_contribute_skill_contract_model.py": "flowguard_convergence_source",
    ".flowguard/kb_org_maintenance_skill_contract_model.py": "flowguard_convergence_source",
    ".flowguard/khaos_brain_update_skill_contract_model.py": "flowguard_convergence_source",
    ".flowguard/khaos_brain_logicguard_authority_cutover.py": (
        "logicguard_authority_cutover_model"
    ),
    ".flowguard/khaos_brain_logicguard_field_lifecycle.py": (
        "logicguard_field_lifecycle_model"
    ),
    ".flowguard/khaos_brain_logicguard_model_mesh.py": "logicguard_model_mesh_model",
    ".flowguard/khaos_brain_logicguard_code_structure.py": (
        "logicguard_code_structure_model"
    ),
    ".flowguard/khaos_brain_logicguard_model_test_alignment.py": (
        "logicguard_model_test_surface"
    ),
    ".flowguard/khaos_brain_logicguard_test_mesh.py": (
        "logicguard_model_test_surface"
    ),
    ".flowguard/khaos_brain_logicguard_runtime_model_miss.py": (
        "logicguard_runtime_model_miss_model"
    ),
    "tests/fixtures/kb_retrieval_eval_cases.json": "retrieval_quality_cases",
    "tests/test_kb_automation_skillguard.py": "flowguard_contract_tests",
    "tests/test_kb_flowguard_execution_identity.py": "flowguard_contract_tests",
}

_SOURCE_COMPONENT_OWNER_EDGES: dict[str, frozenset[str]] = {
    "runtime_source": frozenset(
        {
            "full_regression",
            "flowguard_models",
            "flowguard_meshes",
            "logicguard_runtime",
            "logicguard_runtime_model_miss",
            "author_contract_assurance",
            "retired_architect_absence",
            "current_runtime_only",
            "retrieval_quality",
            "install_health",
        }
    ),
    "runtime_script_source": frozenset(
        {
            "full_regression",
            "flowguard_meshes",
            "retired_architect_absence",
            "current_runtime_only",
            "install_health",
        }
    ),
    "readiness_planner": frozenset(),
    "logicguard_runtime_check": frozenset(
        {"full_regression", "logicguard_runtime", "current_runtime_only"}
    ),
    "author_contract_check": frozenset(
        {"full_regression", "author_contract_assurance", "current_runtime_only"}
    ),
    "retired_architect_check": frozenset(
        {"full_regression", "retired_architect_absence"}
    ),
    "current_runtime_check": frozenset(
        {"full_regression", "flowguard_meshes", "current_runtime_only"}
    ),
    "retrieval_quality_check": frozenset(
        {"full_regression", "retrieval_quality", "current_runtime_only"}
    ),
    "installation_check": frozenset(
        {
            "full_regression",
            "flowguard_models",
            "flowguard_meshes",
            "retired_architect_absence",
            "current_runtime_only",
            "install_health",
        }
    ),
    "flowguard_convergence_source": frozenset(
        {
            "full_regression",
            "flowguard_models",
            "flowguard_meshes",
            "retired_architect_absence",
        }
    ),
    "flowguard_mesh_source": frozenset(
        {"full_regression", "flowguard_meshes", "retired_architect_absence"}
    ),
    "flowguard_other_source": frozenset(
        {"full_regression", "flowguard_meshes", "retired_architect_absence"}
    ),
    "logicguard_authority_cutover_model": frozenset(
        {
            "full_regression",
            "logicguard_authority_cutover_model",
            "retired_architect_absence",
        }
    ),
    "logicguard_field_lifecycle_model": frozenset(
        {
            "full_regression",
            "logicguard_field_lifecycle",
            "retired_architect_absence",
        }
    ),
    "logicguard_model_mesh_model": frozenset(
        {"full_regression", "logicguard_model_mesh", "retired_architect_absence"}
    ),
    "logicguard_code_structure_model": frozenset(
        {
            "full_regression",
            "logicguard_code_structure",
            "retired_architect_absence",
        }
    ),
    "logicguard_model_test_surface": frozenset(
        {
            "full_regression",
            "logicguard_model_test_contract",
            "logicguard_test_mesh",
            "retired_architect_absence",
        }
    ),
    "logicguard_runtime_model_miss_model": frozenset(
        {
            "full_regression",
            "logicguard_runtime_model_miss",
            "retired_architect_absence",
        }
    ),
    "consumer_skill_source": frozenset(
        {
            "full_regression",
            "flowguard_models",
            "author_contract_assurance",
            "retired_architect_absence",
            "current_runtime_only",
            "install_health",
        }
    ),
    "author_skill_contract": frozenset(
        {"full_regression", "author_contract_assurance"}
    ),
    "template_source": frozenset(
        {
            "full_regression",
            "retired_architect_absence",
            "install_health",
        }
    ),
    "product_asset": frozenset({"full_regression", "install_health"}),
    "runtime_dependency": frozenset(
        {
            "full_regression",
            "logicguard_runtime",
            "current_runtime_only",
            "install_health",
        }
    ),
    "test_source": frozenset({"full_regression"}),
    "flowguard_contract_tests": frozenset(
        {
            "full_regression",
            "flowguard_models",
            "flowguard_meshes",
            "author_contract_assurance",
        }
    ),
    "retrieval_quality_cases": frozenset({"full_regression", "retrieval_quality"}),
    "logicguard_openspec_contract": frozenset({"logicguard_openspec"}),
    "readiness_openspec_contract": frozenset(),
    "other_openspec_contract": frozenset(),
    "release_ci": frozenset(),
    "campaign_metadata": frozenset(),
    "runtime_authority_state": frozenset(
        {"logicguard_runtime", "retrieval_quality"}
    ),
    "installed_codex_state": frozenset(
        {"retired_architect_absence", "install_health"}
    ),
    "author_toolchain_state": frozenset({"author_contract_assurance"}),
}


def _classify_watched_source(relative: Path) -> str | None:
    text = relative.as_posix()
    exact = _EXACT_SOURCE_COMPONENTS.get(text)
    if exact:
        return exact
    if text.startswith("local_kb/"):
        return "runtime_source"
    if text.startswith("scripts/"):
        return "runtime_script_source"
    if text.startswith("tests/"):
        return "test_source"
    if text.startswith(".flowguard/"):
        return "flowguard_other_source"
    if text.startswith(".agents/skills/"):
        return (
            "author_skill_contract"
            if "/.skillguard/" in f"/{text}"
            else "consumer_skill_source"
        )
    if text.startswith("templates/"):
        return "template_source"
    if text.startswith("schemas/") or text.startswith("assets/"):
        return "product_asset"
    if text.startswith(
        "openspec/changes/make-khaos-brain-logicguard-native/"
    ):
        return "logicguard_openspec_contract"
    if text.startswith("openspec/changes/make-readiness-affected-only/"):
        return "readiness_openspec_contract"
    if text.startswith("openspec/"):
        return "other_openspec_contract"
    if text.startswith(".github/"):
        return "release_ci"
    if text.startswith("docs/"):
        return "campaign_metadata"
    if relative.name in {"requirements.txt", "requirements-dev.txt", "pyproject.toml"}:
        return "runtime_dependency"
    if "/" not in text:
        return "campaign_metadata"
    return None


def _digest_component_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    body = json.dumps(
        [dict(row) for row in rows],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _tree_component_row(label: str, path: Path) -> dict[str, Any]:
    resolved = Path(path).resolve()
    if not resolved.exists():
        return {"label": label, "kind": "missing", "digest": "", "file_count": 0}
    if resolved.is_file():
        return {
            "label": label,
            "kind": "file",
            "digest": hashlib.sha256(resolved.read_bytes()).hexdigest(),
            "file_count": 1,
        }
    manifest = tree_manifest(resolved)
    return {
        "label": label,
        "kind": "tree",
        "digest": str(manifest.get("digest") or ""),
        "file_count": int(manifest.get("file_count") or 0),
    }


def _tree_stat_component_row(label: str, path: Path) -> dict[str, Any]:
    """Bind a content-addressed authority tree to its observed file projection.

    The authority pointer and store manifests carry the cryptographic content
    identities. The stat projection detects an ordinary byte edit, addition,
    removal, or replacement without rereading multi-gigabyte immutable
    histories on every readiness plan.
    """

    resolved = Path(path).resolve()
    if not resolved.exists():
        return {"label": label, "kind": "missing", "digest": "", "file_count": 0}
    if resolved.is_file():
        stat = resolved.stat()
        rows = [
            {
                "path": resolved.name,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        ]
    else:
        rows = []
        for child in sorted(resolved.rglob("*")):
            if not child.is_file():
                continue
            stat = child.stat()
            rows.append(
                {
                    "path": child.relative_to(resolved).as_posix(),
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                }
            )
    return {
        "label": label,
        "kind": "content-authority-stat-projection",
        "digest": _digest_component_rows(rows),
        "file_count": len(rows),
    }


def _safe_current_ref(
    authority_root: Path,
    reference: Mapping[str, Any] | None,
) -> Path | None:
    relative = str((reference or {}).get("relative_path") or "")
    if not relative:
        return None
    root = authority_root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _runtime_authority_component(repo_root: Path) -> dict[str, Any]:
    rows = [
        _tree_stat_component_row("kb/public", repo_root / "kb" / "public"),
        _tree_stat_component_row("kb/private", repo_root / "kb" / "private"),
        _tree_stat_component_row("kb/candidates", repo_root / "kb" / "candidates"),
        _tree_component_row("kb/indexes", repo_root / "kb" / "indexes"),
        _tree_component_row("kb/taxonomy.yaml", repo_root / "kb" / "taxonomy.yaml"),
        _tree_component_row(
            ".local/khaos-brain/logicguard-authority/current-generation.json",
            repo_root
            / ".local"
            / "khaos-brain"
            / "logicguard-authority"
            / "current-generation.json",
        ),
        *(
            _tree_component_row(
                f".local/khaos-brain/logicguard-authority/{scope}/models/manifest.json",
                repo_root
                / ".local"
                / "khaos-brain"
                / "logicguard-authority"
                / scope
                / "models"
                / "manifest.json",
            )
            for scope in ("public", "private", "candidates")
        ),
        *(
            _tree_component_row(
                f".local/khaos-brain/logicguard-authority/{scope}/meshes/mesh-manifest.json",
                repo_root
                / ".local"
                / "khaos-brain"
                / "logicguard-authority"
                / scope
                / "meshes"
                / "mesh-manifest.json",
            )
            for scope in ("public", "private", "candidates")
        ),
        _tree_component_row(
            ".local/khaos-brain/logicguard-authority/generations",
            repo_root / ".local" / "khaos-brain" / "logicguard-authority",
        ),
    ]
    rows[-1] = _tree_stat_component_row(
        ".local/khaos-brain/logicguard-authority/current-store-projection",
        repo_root / ".local" / "khaos-brain" / "logicguard-authority",
    )
    return {
        "component_id": "runtime_authority_state",
        "digest": _digest_component_rows(rows),
        "file_count": sum(int(row["file_count"]) for row in rows),
    }


def _installed_codex_component(repo_root: Path, codex_home: Path) -> dict[str, Any]:
    from local_kb.install import (
        MAINTENANCE_SKILL_NAMES,
        REPO_AUTOMATION_SPECS,
        RETIRED_AUTOMATION_IDS,
        RETIRED_MAINTENANCE_SKILL_IDS,
    )

    skill_ids = (
        "predictive-kb-preflight",
        *MAINTENANCE_SKILL_NAMES,
        *RETIRED_MAINTENANCE_SKILL_IDS,
    )
    automation_ids = (
        *(str(item["id"]) for item in REPO_AUTOMATION_SPECS),
        *RETIRED_AUTOMATION_IDS,
    )
    install_authority_root = codex_home / ".khaos-brain-install"
    attempts_root = install_authority_root / "attempts"
    attempt_head_path = attempts_root / "HEAD.json"
    try:
        attempt_head = json.loads(attempt_head_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        attempt_head = {}
    attempt_current = _safe_current_ref(
        attempts_root,
        attempt_head.get("current_ref") if isinstance(attempt_head, Mapping) else {},
    )

    assurance_root = install_authority_root / "consumer-assurance"
    assurance_current_path = assurance_root / "current.json"
    try:
        assurance_current = json.loads(
            assurance_current_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        assurance_current = {}
    assurance_receipts = (
        assurance_current.get("owner_receipts")
        if isinstance(assurance_current, Mapping)
        and isinstance(assurance_current.get("owner_receipts"), Mapping)
        else {}
    )

    activation_root = install_authority_root / "operator-activation"
    activation_head_path = activation_root / "HEAD.json"
    try:
        activation_head = json.loads(
            activation_head_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        activation_head = {}
    activation_receipt = _safe_current_ref(
        activation_root,
        activation_head.get("receipt_ref")
        if isinstance(activation_head, Mapping)
        else {},
    )

    rows = [
        _tree_component_row("codex/AGENTS.md", codex_home / "AGENTS.md"),
        _tree_component_row(
            "codex/predictive-kb/install.json",
            codex_home / "predictive-kb" / "install.json",
        ),
        _tree_component_row("codex/install-attempt/HEAD.json", attempt_head_path),
        _tree_component_row(
            "codex/install-attempt/current.json",
            attempt_current
            if attempt_current is not None
            else attempts_root / "__missing_current__.json",
        ),
        _tree_component_row(
            "codex/consumer-assurance/current.json",
            assurance_current_path,
        ),
        _tree_component_row(
            "codex/operator-activation/HEAD.json",
            activation_head_path,
        ),
        _tree_component_row(
            "codex/operator-activation/current-receipt.json",
            activation_receipt
            if activation_receipt is not None
            else activation_root / "__missing_receipt__.json",
        ),
        _tree_component_row(
            "repo/.local/khaos_brain_update_state.json",
            repo_root / ".local" / "khaos_brain_update_state.json",
        ),
        _tree_component_row(
            "repo/kb/history/current-migration",
            repo_root
            / "kb"
            / "history"
            / "migrations"
            / "kb-maintenance-standard-v6-resumable-sleep-current-index",
        ),
    ]
    rows.extend(
        _tree_component_row(f"codex/skills/{skill_id}", codex_home / "skills" / skill_id)
        for skill_id in skill_ids
    )
    rows.extend(
        _tree_component_row(
            f"codex/automations/{automation_id}",
            codex_home / "automations" / automation_id,
        )
        for automation_id in automation_ids
    )
    rows.extend(
        _tree_component_row(
            f"codex/consumer-assurance/{owner}",
            current_ref
            if current_ref is not None
            else assurance_root / f"__missing_{owner}__.json",
        )
        for owner, reference in sorted(assurance_receipts.items())
        for current_ref in (
            _safe_current_ref(
                assurance_root,
                reference if isinstance(reference, Mapping) else {},
            ),
        )
    )
    return {
        "component_id": "installed_codex_state",
        "digest": _digest_component_rows(rows),
        "file_count": sum(int(row["file_count"]) for row in rows),
    }


def _author_toolchain_component() -> dict[str, Any]:
    configured = os.environ.get("SKILLGUARD_AUTHOR_COMPILER", "").strip()
    candidates = (
        Path(configured) if configured else None,
        Path.home()
        / ".codex"
        / "skills"
        / "skillguard"
        / "scripts"
        / "skillguard_compile.py",
        REPO_ROOT.parent
        / "SkillGuard_20260614"
        / ".agents"
        / "skills"
        / "skillguard"
        / "scripts"
        / "skillguard_compile.py",
    )
    selected = next(
        (candidate.resolve() for candidate in candidates if candidate and candidate.is_file()),
        None,
    )
    row = _tree_component_row(
        "skillguard-author-compiler",
        selected if selected is not None else Path("__missing_skillguard_compiler__"),
    )
    return {
        "component_id": "author_toolchain_state",
        "digest": _digest_component_rows([row]),
        "file_count": int(row["file_count"]),
    }


def _build_component_inventory(
    repo_root: Path,
    codex_home: Path,
) -> dict[str, Any]:
    component_rows: dict[str, list[dict[str, Any]]] = {}
    path_components: dict[str, set[str]] = {}
    for path in _watched_files(repo_root):
        relative = path.relative_to(repo_root)
        component = _classify_watched_source(relative)
        text = relative.as_posix()
        if component is not None:
            path_components.setdefault(text, set()).add(component)
            semantic = _semantic_bytes(path, relative)
            component_rows.setdefault(component, []).append(
                {
                    "path": text,
                    "semantic_sha256": hashlib.sha256(semantic).hexdigest(),
                }
            )
        else:
            path_components.setdefault(text, set())

    issues = [
        (
            f"unmapped-watched-input:{path}"
            if not components
            else f"ambiguous-watched-input:{path}:{','.join(sorted(components))}"
        )
        for path, components in sorted(path_components.items())
        if len(components) != 1
    ]
    unknown_components = sorted(
        component
        for component in component_rows
        if component not in _SOURCE_COMPONENT_OWNER_EDGES
    )
    issues.extend(f"unknown-component:{component}" for component in unknown_components)

    components: dict[str, dict[str, Any]] = {}
    for component, rows in sorted(component_rows.items()):
        ordered = sorted(rows, key=lambda row: str(row["path"]))
        components[component] = {
            "component_id": component,
            "digest": _digest_component_rows(ordered),
            "file_count": len(ordered),
        }
    for external in (
        _runtime_authority_component(repo_root),
        _installed_codex_component(repo_root, codex_home),
        _author_toolchain_component(),
    ):
        components[str(external["component_id"])] = external

    return {
        "schema_version": "khaos-brain.readiness-component-inventory.v1",
        "components": components,
        "watched_file_count": len(path_components),
        "issues": issues,
        "ok": not issues,
    }


def _owner_component_snapshots(
    commands: Mapping[str, Sequence[str]],
    inventory: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    available = (
        inventory.get("components")
        if isinstance(inventory.get("components"), Mapping)
        else {}
    )
    owners: dict[str, dict[str, Any]] = {}
    issues = list(inventory.get("issues") or [])
    for owner in sorted(commands):
        rows = [
            {
                "component_id": component_id,
                "digest": str(component.get("digest") or ""),
                "file_count": int(component.get("file_count") or 0),
            }
            for component_id, component in sorted(available.items())
            if owner in _SOURCE_COMPONENT_OWNER_EDGES.get(component_id, frozenset())
            and isinstance(component, Mapping)
        ]
        if not rows:
            issues.append(f"owner-without-components:{owner}")
            continue
        owners[owner] = {
            "owner": owner,
            "components": rows,
            "digest": _digest_component_rows(rows),
        }
    return owners, sorted(set(issues))


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


def _researchguard_logic_toolchain_identity(
    researchguard_module: Any,
    research_logic_module: Any,
) -> dict[str, Any]:
    configured = os.environ.get(
        "KHAOS_BRAIN_RESEARCHGUARD_LOGIC_VALIDATION_ROOT", ""
    ).strip()
    imported_root = Path(researchguard_module.__file__).resolve().parent
    imported_logic_root = Path(research_logic_module.__file__).resolve().parent
    root = Path(configured).resolve() if configured else imported_root
    try:
        imported_root.relative_to(root)
        imported_logic_root.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(
            "Imported ResearchGuard logic member resolved outside the frozen "
            "validation toolchain"
        ) from exc
    manifest = tree_manifest(root) if root.is_dir() else {}
    digest = str(manifest.get("digest") or "")
    expected = os.environ.get(
        "KHAOS_BRAIN_RESEARCHGUARD_LOGIC_VALIDATION_DIGEST", ""
    ).strip()
    required_symbols = (
        "FileModelStore",
        "FileModelMeshStore",
        "MeshNodeOverride",
        "simulate_mesh",
    )
    missing = [
        name
        for name in required_symbols
        if not hasattr(research_logic_module, name)
    ]
    if (
        not digest
        or not (root / "__init__.py").is_file()
        or missing
        or str(getattr(research_logic_module, "SCHEMA_VERSION", ""))
        != "researchguard.logic.model-store.v1"
        or str(getattr(research_logic_module, "MESH_SCHEMA_VERSION", ""))
        != "researchguard.logic.model-mesh.v1"
    ):
        raise RuntimeError(
            "Current ResearchGuard logic validation toolchain is unavailable"
        )
    if expected and digest != expected:
        raise RuntimeError(
            "Frozen ResearchGuard logic validation toolchain digest does not "
            "match its declared identity"
        )
    return {
        "digest": digest,
        "file_count": int(manifest.get("file_count") or 0),
        "root": str(root),
        "version": str(getattr(research_logic_module, "__version__", "")),
        "model_store_schema": str(
            getattr(research_logic_module, "SCHEMA_VERSION", "")
        ),
        "mesh_schema": str(
            getattr(research_logic_module, "MESH_SCHEMA_VERSION", "")
        ),
    }


def _verifier_fingerprint() -> dict[str, Any]:
    import flowguard
    import researchguard
    from researchguard import logic as research_logic

    flowguard_identity = _flowguard_toolchain_identity(flowguard)
    researchguard_logic_identity = _researchguard_logic_toolchain_identity(
        researchguard,
        research_logic,
    )
    payload = {
        "evidence_policy_version": EVIDENCE_POLICY_VERSION,
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pytest_version": _package_version("pytest"),
        "flowguard_schema_version": str(flowguard.SCHEMA_VERSION),
        "flowguard_package_digest": str(flowguard_identity["digest"]),
        "flowguard_toolchain": flowguard_identity,
        "researchguard_logic_toolchain": researchguard_logic_identity,
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["digest"] = hashlib.sha256(body).hexdigest()
    return payload


def _environment_contract(repo_root: Path) -> dict[str, str]:
    return {
        "cwd": str(repo_root.resolve()),
        "KHAOS_BRAIN_ASSURANCE_ACTIVE": "1",
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        "python_executable": str(Path(sys.executable).resolve()),
    }


_FLOWGUARD_TOOLCHAIN_OWNERS = frozenset(
    {
        "flowguard_models",
        "flowguard_meshes",
        "logicguard_authority_cutover_model",
        "logicguard_field_lifecycle",
        "logicguard_model_mesh",
        "logicguard_code_structure",
        "logicguard_model_test_contract",
        "logicguard_test_mesh",
        "logicguard_runtime_model_miss",
        "full_regression",
    }
)
_RESEARCHGUARD_TOOLCHAIN_OWNERS = frozenset(
    {
        "logicguard_runtime",
        "logicguard_runtime_model_miss",
        "retrieval_quality",
        "current_runtime_only",
        "install_health",
        "full_regression",
    }
)


def _owner_verifier_fingerprint(
    owner: str,
    verifier_fingerprint: Mapping[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "evidence_policy_version": EVIDENCE_POLICY_VERSION,
        "python_executable": str(verifier_fingerprint.get("python_executable") or ""),
        "python_version": str(verifier_fingerprint.get("python_version") or ""),
        "platform": str(verifier_fingerprint.get("platform") or ""),
    }
    if owner == "full_regression":
        payload["pytest_version"] = str(
            verifier_fingerprint.get("pytest_version") or ""
        )
    if owner in _FLOWGUARD_TOOLCHAIN_OWNERS:
        toolchain = verifier_fingerprint.get("flowguard_toolchain")
        payload["flowguard_toolchain"] = (
            {
                "digest": str(toolchain.get("digest") or ""),
                "file_count": int(toolchain.get("file_count") or 0),
            }
            if isinstance(toolchain, Mapping)
            else {}
        )
    if owner in _RESEARCHGUARD_TOOLCHAIN_OWNERS:
        toolchain = verifier_fingerprint.get("researchguard_logic_toolchain")
        payload["researchguard_logic_toolchain"] = (
            {
                "digest": str(toolchain.get("digest") or ""),
                "file_count": int(toolchain.get("file_count") or 0),
                "version": str(toolchain.get("version") or ""),
                "model_store_schema": str(
                    toolchain.get("model_store_schema") or ""
                ),
                "mesh_schema": str(toolchain.get("mesh_schema") or ""),
            }
            if isinstance(toolchain, Mapping)
            else {}
        )
    payload["digest"] = _digest_component_rows(
        [{"field": key, "value": value} for key, value in sorted(payload.items())]
    )
    return payload


def _semantic_argv(command: list[str]) -> list[str]:
    return [
        "--junitxml=<RESULT>" if str(part).startswith("--junitxml=") else str(part)
        for part in command
    ]


def _command_identity(
    command: list[str],
    *,
    owner_component_digest: str,
    verifier_digest: str,
    environment_contract: dict[str, str],
) -> str:
    payload = {
        "argv": _semantic_argv(command),
        "executable_identity": _executable_identity(command[0]),
        "owner_component_digest": owner_component_digest,
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
        "author_contract_assurance": [
            sys.executable,
            "scripts/check_kb_skillguard.py",
            "--json",
            "--source-only",
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
    owner_component_snapshot: dict[str, Any],
    owner_verifier_fingerprint: dict[str, Any],
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
        owner_component_digest=str(owner_component_snapshot["digest"]),
        verifier_digest=str(owner_verifier_fingerprint["digest"]),
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
    stdout_bytes = stdout.encode("utf-8")
    json_payload_limit_bytes = 1_048_576
    if len(stdout_bytes) > json_payload_limit_bytes:
        json_payload = None
        json_payload_projection = {
            "status": "omitted-oversize",
            "source_bytes": len(stdout_bytes),
            "limit_bytes": json_payload_limit_bytes,
        }
    else:
        try:
            json_payload = json.loads(stdout)
        except json.JSONDecodeError:
            json_payload = None
            json_payload_projection = {
                "status": "not-json",
                "source_bytes": len(stdout_bytes),
                "limit_bytes": json_payload_limit_bytes,
            }
        else:
            json_payload_projection = {
                "status": "embedded",
                "source_bytes": len(stdout_bytes),
                "limit_bytes": json_payload_limit_bytes,
            }
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
            "owner_components": owner_component_snapshot["digest"],
            "verifier": owner_verifier_fingerprint["digest"],
        },
        "owner_components": list(owner_component_snapshot.get("components") or []),
        "owner_verifier_fingerprint": owner_verifier_fingerprint,
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
        "stdout_sha256": hashlib.sha256(stdout_bytes).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
        "stdout_tail": stdout[-6000:],
        "stderr_tail": stderr[-6000:],
        "json_payload": json_payload,
        "json_payload_projection": json_payload_projection,
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


def _current_owner_receipt(
    current_manifest_path: Path | None,
    owner_name: str,
    command: list[str],
    repo_root: Path,
    *,
    owner_component_snapshot: dict[str, Any],
    owner_verifier_fingerprint: dict[str, Any],
    current_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return one exact immutable success receipt for the requested owner."""

    if current_manifest_path is None:
        return None
    current_manifest_path = Path(current_manifest_path).resolve()
    evidence_root = current_manifest_path.parent
    if current_manifest is None:
        try:
            manifest = json.loads(current_manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
    else:
        manifest = current_manifest
    if not isinstance(manifest, dict) or manifest.get("schema_version") != EVIDENCE_SCHEMA:
        return None
    entries = manifest.get("entries")
    entry = entries.get(owner_name) if isinstance(entries, dict) else None
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

    owner_component_digest = str(owner_component_snapshot.get("digest") or "")
    verifier_digest = str(owner_verifier_fingerprint.get("digest") or "")
    environment_contract = _environment_contract(repo_root)
    identity = _command_identity(
        command,
        owner_component_digest=owner_component_digest,
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
    if receipt.get("receipt_id") != f"validation:{owner_name}:{identity}":
        return None
    if stored_inputs != {
        "owner_components": owner_component_digest,
        "verifier": verifier_digest,
    }:
        return None
    if receipt.get("owner_components") != list(
        owner_component_snapshot.get("components") or []
    ):
        return None
    if receipt.get("owner_verifier_fingerprint") != owner_verifier_fingerprint:
        return None
    if receipt.get("environment_contract") != environment_contract:
        return None
    if receipt.get("executable_identity") != _executable_identity(command[0]):
        return None
    if receipt.get("cwd") != str(repo_root.resolve()):
        return None
    if not (
        receipt.get("schema_version") == EVIDENCE_SCHEMA
        and receipt.get("name") == owner_name
        and receipt.get("execution") == "executed"
        and receipt.get("terminal_status") == "passed"
        and receipt.get("ok") is True
        and receipt.get("timed_out") is False
        and receipt.get("cleanup_confirmed") is True
        and receipt.get("exit_code") == 0
    ):
        return None

    proof = receipt.get("proof_artifact_ref")
    if not isinstance(proof, dict):
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
    if owner_name == "full_regression":
        junit = receipt.get("junit")
        if not isinstance(junit, dict):
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


def _materialize_owner_reuse(
    reusable: dict[str, Any],
    *,
    owner_name: str,
    evidence_dir: Path,
    inventory_revision: str,
) -> dict[str, Any]:
    """Project an exact prior owner receipt into the current aggregate run."""

    source_path = Path(reusable["receipt_path"]).resolve()
    source_receipt = dict(reusable["receipt"])
    evidence_dir.mkdir(parents=True, exist_ok=True)
    projection_path = evidence_dir / f"{owner_name}.receipt.json"
    receipt = {
        key: value
        for key, value in source_receipt.items()
        if key
        not in {
            "json_payload",
            "json_payload_projection",
            "receipt_path",
            "receipt_sha256",
            "reuse_ticket",
        }
    }
    raw_json_payload = source_receipt.get("json_payload")
    if raw_json_payload is not None:
        encoded_payload = json.dumps(
            raw_json_payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded_payload) <= 1_048_576:
            receipt["json_payload"] = raw_json_payload
            receipt["json_payload_projection"] = {
                "status": "embedded",
                "source_bytes": len(encoded_payload),
                "limit_bytes": 1_048_576,
            }
        else:
            receipt["json_payload"] = None
            receipt["json_payload_projection"] = {
                "status": "omitted-oversize",
                "source_bytes": len(encoded_payload),
                "limit_bytes": 1_048_576,
            }
    else:
        receipt["json_payload"] = None
        receipt["json_payload_projection"] = dict(
            source_receipt.get("json_payload_projection")
            or {
                "status": "not-json",
                "source_bytes": 0,
                "limit_bytes": 1_048_576,
            }
        )
    receipt["compacted_from"] = {
        "receipt_path": str(source_path),
        "receipt_sha256": reusable["receipt_sha256"],
    }
    projection_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    projection_hash = hashlib.sha256(projection_path.read_bytes()).hexdigest()
    source_inventory = str(receipt.get("inventory_revision") or "")
    return {
        **receipt,
        "execution": "reused",
        "inventory_revision": inventory_revision,
        "receipt_path": str(projection_path.resolve()),
        "receipt_sha256": projection_hash,
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
    owner_component_snapshots: Mapping[str, dict[str, Any]],
    verifier_fingerprint: dict[str, Any],
    inventory_revision: str = "",
    current_manifest_path: Path | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    current_manifest: Mapping[str, Any] | None = None
    if current_manifest_path is not None:
        try:
            loaded_manifest = json.loads(
                Path(current_manifest_path).resolve().read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            pass
        else:
            if isinstance(loaded_manifest, Mapping):
                current_manifest = loaded_manifest
    env_contract = _environment_contract(repo_root)
    owner_by_identity: dict[str, str] = {}
    owners: dict[str, list[str]] = {}
    owner_verifiers: dict[str, dict[str, Any]] = {}
    for name, command in commands.items():
        snapshot = owner_component_snapshots.get(name)
        if not isinstance(snapshot, Mapping):
            raise RuntimeError(f"Readiness owner lacks a component snapshot: {name}")
        owner_verifier = _owner_verifier_fingerprint(name, verifier_fingerprint)
        owner_verifiers[name] = owner_verifier
        identity = _command_identity(
            command,
            owner_component_digest=str(snapshot["digest"]),
            verifier_digest=str(owner_verifier["digest"]),
            environment_contract=env_contract,
        )
        owner = owner_by_identity.setdefault(identity, name)
        if owner != name:
            raise RuntimeError(
                "Duplicate readiness execution identity has multiple owners: "
                f"{owner}, {name}"
            )
        owners[name] = command

    results: dict[str, dict[str, Any]] = {}
    pending: dict[str, list[str]] = {}
    for name, command in owners.items():
        reusable = _current_owner_receipt(
            current_manifest_path,
            name,
            command,
            repo_root,
            owner_component_snapshot=dict(owner_component_snapshots[name]),
            owner_verifier_fingerprint=owner_verifiers[name],
            current_manifest=current_manifest,
        )
        if reusable is None:
            pending[name] = command
        else:
            results[name] = _materialize_owner_reuse(
                reusable,
                owner_name=name,
                evidence_dir=evidence_dir,
                inventory_revision=inventory_revision,
            )
    current_manifest = None
    loaded_manifest = None

    # The repository-wide suite is the sole owner of capability pytest. Run it
    # first on its exclusive lane; no other maintenance unit consumes or
    # projects this receipt as its own evidence.
    if "full_regression" in pending:
        name, result = _run(
            ("full_regression", pending.pop("full_regression")),
            repo_root,
            evidence_dir=evidence_dir,
            owner_component_snapshot=dict(
                owner_component_snapshots["full_regression"]
            ),
            owner_verifier_fingerprint=owner_verifiers["full_regression"],
            inventory_revision=inventory_revision,
        )
        results[name] = result

    # Performance evidence and real scheduled production are both
    # resource-sensitive.  Keep them out of the ordinary parallel pool, then
    # run them in a fixed order: LogicGuard benchmarks first and installed
    # scheduled production last.  This prevents either owner from losing its
    # declared budget to sibling CPU or filesystem pressure.
    exclusive_sequence = ("logicguard_runtime",)
    exclusive_names = set(exclusive_sequence)
    parallel = {
        name: cmd
        for name, cmd in pending.items()
        if name not in exclusive_names
    }
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(parallel)))) as executor:
        results.update(
            executor.map(
                lambda item: _run(
                    item,
                    repo_root,
                    evidence_dir=evidence_dir,
                    owner_component_snapshot=dict(
                        owner_component_snapshots[item[0]]
                    ),
                    owner_verifier_fingerprint=owner_verifiers[item[0]],
                    inventory_revision=inventory_revision,
                    timeout_seconds=3600,
                ),
                parallel.items(),
            )
        )

    for name in exclusive_sequence:
        if name not in pending:
            continue
        owner_name, result = _run(
            (name, pending[name]),
            repo_root,
            evidence_dir=evidence_dir,
            owner_component_snapshot=dict(owner_component_snapshots[name]),
            owner_verifier_fingerprint=owner_verifiers[name],
            inventory_revision=inventory_revision,
            timeout_seconds=AGGREGATE_ASSURANCE_TIMEOUT_SECONDS,
        )
        results[owner_name] = result

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
    component_inventory_before = _build_component_inventory(repo_root, codex_home)
    owner_snapshots_before, planning_issues = _owner_component_snapshots(
        commands,
        component_inventory_before,
    )
    if planning_issues:
        planning_entry = {
            "schema_version": EVIDENCE_SCHEMA,
            "receipt_id": f"validation:owner_component_plan:{run_id}",
            "name": "owner_component_plan",
            "execution": "blocked",
            "terminal_status": "blocked",
            "timed_out": False,
            "cleanup_confirmed": True,
            "exit_code": 2,
            "ok": False,
            "issues": planning_issues,
        }
        blocked_manifest = {
            "schema_version": EVIDENCE_SCHEMA,
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repo_root": str(repo_root),
            "codex_home": str(codex_home),
            "pre_restore": pre_restore,
            "inventory_revision": inventory_revision,
            "source_snapshot_before": before,
            "component_inventory_before": component_inventory_before,
            "entries": {"owner_component_plan": planning_entry},
            "ok": False,
        }
        manifest_ref = _write_json(
            evidence_dir / "manifest.json",
            blocked_manifest,
        )
        return {
            "schema_version": 2,
            "check": "chaos-brain-aggregate-readiness",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repo_root": str(repo_root),
            "codex_home": str(codex_home),
            "pre_restore": pre_restore,
            "ok": False,
            "source_snapshot_before": before,
            "source_snapshot_after": before,
            "source_stable_during_checks": True,
            "owner_components_stable_during_checks": False,
            "component_planning_issues": planning_issues,
            "checks": {"owner_component_plan": planning_entry},
            "failed_checks": ["owner_component_plan"],
            "evidence_manifest": manifest_ref,
            "evidence_run_id": run_id,
            "exact_execution_identity_counts": {},
            "duplicate_exact_executions": [],
            "claim_boundary": (
                "Planning stopped before validation because the closed owner-component "
                "inventory was incomplete or ambiguous. No run-all route was selected."
            ),
        }
    results, identity_counts = _execute_plan(
        commands,
        repo_root,
        evidence_dir=evidence_dir,
        owner_component_snapshots=owner_snapshots_before,
        verifier_fingerprint=verifier,
        inventory_revision=inventory_revision,
        current_manifest_path=Path(evidence_root).resolve() / "current.json",
    )

    leaf_after = _source_snapshot(repo_root)
    component_inventory_after_leaf = _build_component_inventory(repo_root, codex_home)
    owner_snapshots_after_leaf, after_leaf_issues = _owner_component_snapshots(
        commands,
        component_inventory_after_leaf,
    )
    owner_components_stable_after_leaf = (
        not after_leaf_issues
        and {
            name: str(snapshot["digest"])
            for name, snapshot in owner_snapshots_before.items()
        }
        == {
            name: str(snapshot["digest"])
            for name, snapshot in owner_snapshots_after_leaf.items()
        }
    )
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
        "component_inventory_before": component_inventory_before,
        "component_inventory_after_leaf_execution": component_inventory_after_leaf,
        "owner_component_snapshots_before": owner_snapshots_before,
        "owner_component_snapshots_after_leaf_execution": owner_snapshots_after_leaf,
        "owner_components_stable_during_leaf_execution": (
            owner_components_stable_after_leaf
        ),
        "component_planning_issues_after_leaf_execution": after_leaf_issues,
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
    component_inventory_after = _build_component_inventory(repo_root, codex_home)
    owner_snapshots_after, after_issues = _owner_component_snapshots(
        commands,
        component_inventory_after,
    )
    owner_components_stable = (
        not after_issues
        and {
            name: str(snapshot["digest"])
            for name, snapshot in owner_snapshots_before.items()
        }
        == {
            name: str(snapshot["digest"])
            for name, snapshot in owner_snapshots_after.items()
        }
    )
    source_stable = (
        before["digest"] == after["digest"]
        and owner_components_stable
    )
    manifest["entries"] = results
    manifest["source_snapshot_after"] = after
    manifest["component_inventory_after"] = component_inventory_after
    manifest["owner_component_snapshots_after"] = owner_snapshots_after
    manifest["owner_components_stable"] = owner_components_stable
    manifest["component_planning_issues_after"] = after_issues
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
        "owner_components_stable_during_checks": owner_components_stable,
        "component_planning_issues": after_issues,
        "verifier_fingerprint": verifier,
        "checks": results,
        "failed_checks": [name for name, item in results.items() if not item.get("ok")],
        "evidence_manifest": manifest_ref,
        "evidence_run_id": run_id,
        "exact_execution_identity_counts": identity_counts,
        "duplicate_exact_executions": manifest["duplicate_exact_executions"],
        "claim_boundary": (
            "Current final-source LogicGuard authority/model/mesh/projection, FlowGuard, "
            "OpenSpec, author-side contract audit, retirement, install, retrieval, performance, "
            "and one repository-wide regression execution or exact current immutable owner "
            "receipt reuse. Each maintained skill owns distinct test evidence; Model-Test "
            "Alignment checks ownership without consuming another skill's receipt. "
            "OpenSpec archival and external release publication "
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
