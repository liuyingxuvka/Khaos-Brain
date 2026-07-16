"""Prove that retired compatibility and alternate-authority paths stay absent."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


FORBIDDEN_BY_FILE: dict[str, tuple[str, ...]] = {
    "local_kb/search.py": (
        "load_filtered_entries_scan",
        "from local_kb.store import load_entries",
        "_related_entry_ids",
    ),
    "local_kb/active_index.py": (
        "rebuild_if_stale",
        "load_filtered_entries_scan",
        "from local_kb.store import load_entries",
    ),
    "local_kb/install.py": (
        "AUTOMATION_FALLBACK_MODEL",
        "AUTOMATION_FALLBACK_REASONING_EFFORT",
    ),
    "local_kb/org_cleanup.py": ("kb/trusted", "kb/candidates", "legacy_compatibility"),
    "local_kb/org_maintenance.py": ("kb/trusted", "kb/candidates", "legacy_compatibility"),
    "local_kb/org_automation.py": ("kb/trusted", "kb/candidates", "legacy_compatibility"),
    "local_kb/org_checks.py": ("kb/trusted", "kb/candidates", "legacy_compatibility"),
    "scripts/run_kb_guarded_automation.py": (
        "recovered_update_identity_failure",
        "canonicalize_obsolete_update_state",
    ),
    "scripts/check_kb_skillguard.py": (
        'surface_kind.startswith("installed")',
    ),
    "scripts/run_installed_skillguard_supervision.py": (
        "skillguard_compile",
        "compile_skill_contract",
        "compiled_contract=None",
        "verified_installation_context=None",
    ),
    "templates/predictive-kb-preflight/kb_launch.py": ("--path-hint", "implicit_search"),
    ".agents/skills/local-kb-retrieve/scripts/kb_search.py": ("--path-hint",),
    "scripts/open_khaos_brain_ui.py": ("--prefer-python", "_exe_candidates", "prefer_python"),
    "scripts/install_desktop_shortcut.py": ("--prefer-python", "_exe_candidates", "prefer_python"),
    "local_kb/settings.py": (
        '"maintainer_mode_requested"',
        '"maintainer_validated"',
        '"maintainer_validation_status"',
        '"maintainer_validation_message"',
        "def maintainer_status_from_settings",
    ),
    "local_kb/desktop_app.py": (
        '"maintainer_mode_requested"',
        '"maintainer_mode"',
        '"maintainer_hint"',
    ),
    "local_kb/org_outbox.py": (
        'use.get("skill_fallback")',
        'use.get("fallback")',
        'use.get("without_skill")',
        'use.get("fallback_guidance")',
        '"unavailable-skill-fallback"',
    ),
    "templates/github/org_kb_check.py": (
        'if main_path else ("kb/trusted", "kb/candidates", "kb/imports")',
        '"kb/candidates/", "skills/candidates/"',
    ),
}

REQUIRED_BY_FILE: dict[str, tuple[str, ...]] = {
    "local_kb/search.py": (
        "maintenance_standard_is_active",
        "load_active_entries",
        "search_model_bound_entries",
        "read_bound_argument_context",
        "grounded-model-neighborhood",
    ),
    "local_kb/active_index.py": (
        "Active index is unavailable or stale",
        "logicguard_model_id",
        "logicguard_mesh_revision_id",
        "authority_generation_id",
    ),
    "local_kb/logicguard_models.py": (
        'MIN_LOGICGUARD_VERSION = "0.18.0"',
        "logicguard_dependency_preflight",
        "AUTHORITY_GENERATION_WRITERS",
        "read_exact_model",
        "read_exact_mesh",
        "simulate_bound_mesh",
    ),
    "local_kb/model_projection.py": (
        'CARD_PROJECTION_SCHEMA_VERSION = "khaos-brain.card-projection.v1"',
        "binding_from_projection",
        "validate_card_projection",
        "projection_digest",
    ),
    "local_kb/model_maintenance.py": (
        "publish_sleep_model_generation",
        "load_current_model_entries",
        "_restore_active_authority",
        "unresolved_relationships",
    ),
    "local_kb/dream.py": (
        "simulate_bound_mesh",
        "authority_generation_id",
        "Dream authority generation changed during the pinned simulation run",
    ),
    "local_kb/install.py": (
        "canonicalize_obsolete_update_state",
        "resolve_automation_runtime",
    ),
    "local_kb/org_sources.py": (
        "obsolete organization roots are forbidden",
        "migrate_organization_repo_to_current",
    ),
    "local_kb/store.py": (
        "Organization KB has obsolete runtime roots",
        "Run the direct organization-layout migration",
    ),
    "templates/github/org_kb_check.py": (
        "kb.main_path must be exactly kb/main",
        "obsolete organization roots are forbidden",
    ),
    "templates/predictive-kb-preflight/kb_launch.py": (
        'parser.add_argument("command"',
    ),
    ".agents/skills/local-kb-retrieve/scripts/kb_search.py": (
        'parser.add_argument("--route-hint"',
    ),
    "scripts/open_khaos_brain_ui.py": (
        '"--runtime"',
        "CURRENT_RELEASE_EXECUTABLE",
        "Selected release runtime is unavailable",
    ),
    "scripts/install_desktop_shortcut.py": (
        '"--runtime"',
        "Bind the shortcut to exactly one current runtime",
    ),
    "local_kb/settings.py": (
        "CURRENT_DESKTOP_SETTINGS_SCHEMA_VERSION",
        "current_desktop_settings_issues",
        '"organization_maintenance_requested"',
    ),
    "local_kb/settings_migration.py": (
        "migrate_desktop_settings_to_current",
        "residual_obsolete_field_count",
        '"ai-upgrade-owner"',
    ),
    "local_kb/card_schema_migration.py": (
        "migrate_skill_guidance_fields_to_current",
        'CURRENT_SKILL_GUIDANCE_FIELD = "unavailable_skill_guidance"',
        "residual_obsolete_field_count",
    ),
    "local_kb/org_outbox.py": (
        'use.get("unavailable_skill_guidance")',
        '"unavailable-skill-guidance"',
    ),
    "local_kb/maintenance_migration.py": (
        '"canonicalize-runtime"',
        'MIGRATION_ID = "kb-maintenance-standard-v4-logicguard-native"',
        '"migrate-logicguard-authority"',
        "migrate_legacy_card_generation",
        "validate_logicguard_native_authority",
        "canonicalize_runtime_state",
        "migrate_desktop_settings_to_current",
        "migrate_skill_guidance_fields_to_current",
    ),
    "local_kb/software_update.py": (
        "UPDATE_STATE_REQUIRED_FIELDS",
        "UPDATE_STATE_ALLOWED_FIELDS",
        "Update state is not current:",
        "retired_schema_found",
    ),
    "scripts/run_installed_skillguard_supervision.py": (
        "CURRENT_COMPILED_CONTRACT_PATH",
        "CURRENT_CHECK_MANIFEST_PATH",
        "_materialize_installed_control_projection",
        '"source_kind": "exact-installed-current-bytes"',
        '"projection_scope": "repository-local-content-addressed"',
        "_materialize_skillguard_runtime_projection",
        '"source_kind": "frozen-current-runtime-without-runtime-state"',
        '"projection_scope": "repository-local-content-addressed"',
        '"skillguard-global-router"',
        '".sg-runtime" in relative.parts',
        '"__pycache__" in relative.parts',
        "installed_authority",
        "projection_authority",
        "load_verified_installation_context",
        "self.compiled = _load_object(",
        "self.manifest = _load_object(",
        "compiled_contract=self.compiled",
        "check_manifest=self.manifest",
        "guard_runtime_identity=self.guard_runtime_identity",
        "verified_installation_context=self.verified_context",
        "_supervision_dynamic_environment",
        "dynamic_environment=dynamic_environment",
    ),
    "scripts/check_kb_skillguard.py": (
        "_supervision_target_authority",
        'target_authority == "installed"',
        "must be exactly one current managed root",
    ),
    "scripts/check_kb_automation_skillguard_depth.py": (
        "validate_completion_surface(",
        "build_fixture_payload(",
        '"positive_fixture": positive',
        '"shallow_fixture": shallow',
    ),
}


def _digest(rows: list[dict[str, Any]]) -> str:
    body = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def check_current_runtime_only(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    root = Path(repo_root)
    issues: list[str] = []
    rows: list[dict[str, Any]] = []
    for relative in sorted(set(FORBIDDEN_BY_FILE) | set(REQUIRED_BY_FILE)):
        path = root / relative
        if not path.is_file():
            issues.append(f"missing-governed-file:{relative}")
            continue
        text = path.read_text(encoding="utf-8")
        forbidden_hits = [token for token in FORBIDDEN_BY_FILE.get(relative, ()) if token in text]
        missing_required = [token for token in REQUIRED_BY_FILE.get(relative, ()) if token not in text]
        for token in forbidden_hits:
            issues.append(f"retired-runtime-authority:{relative}:{token}")
        for token in missing_required:
            issues.append(f"missing-current-runtime-authority:{relative}:{token}")
        rows.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "forbidden_hits": forbidden_hits,
                "missing_required": missing_required,
            }
        )

    production_refs: list[str] = []
    for path in sorted((root / "local_kb").rglob("*.py")):
        if "canonicalize_obsolete_update_state" in path.read_text(encoding="utf-8"):
            production_refs.append(path.relative_to(root).as_posix())
    for path in sorted((root / "scripts").rglob("*.py")):
        if path.name == Path(__file__).name:
            continue
        if "canonicalize_obsolete_update_state" in path.read_text(encoding="utf-8"):
            production_refs.append(path.relative_to(root).as_posix())
    expected_refs = ["local_kb/install.py", "local_kb/software_update.py"]
    if production_refs != expected_refs:
        issues.append(
            "obsolete-update-state-migrator-has-non-upgrade-callers:"
            + ",".join(production_refs)
        )

    direct_card_store_readers: list[str] = []
    for path in sorted((root / "local_kb").rglob("*.py")):
        if path.name == "store.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "from local_kb.store import load_entries" in text:
            direct_card_store_readers.append(path.relative_to(root).as_posix())
    if direct_card_store_readers:
        issues.append(
            "normal-runtime-direct-card-store-readers:"
            + ",".join(direct_card_store_readers)
        )

    return {
        "ok": not issues,
        "policy_id": "chaos-brain.current-runtime-only.v1",
        "governed_file_count": len(rows),
        "governed_digest": _digest(rows),
        "obsolete_update_state_migrator_refs": production_refs,
        "normal_runtime_direct_card_store_readers": direct_card_store_readers,
        "issues": issues,
        "files": rows,
        "claim_boundary": (
            "Static source gate for the enumerated retired runtime authorities. "
            "Migration behavior and installed-machine residual counts require their separate current receipts."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = check_current_runtime_only(Path(args.repo_root))
    if args.json:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    else:
        print(f"ok: {report['ok']}")
        for issue in report["issues"]:
            print(f"- {issue}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
