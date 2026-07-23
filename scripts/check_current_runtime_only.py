"""Prove that retired compatibility and alternate-authority paths stay absent."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

RETIRED_FLOWGUARD_SHADOW_MEMBER_IDS = (
    "model-first-function-flow",
    "flowguard-agent-workflow-rehearsal",
    "flowguard-architecture-reduction",
    "flowguard-behavior-commitment-ledger",
    "flowguard-code-structure-recommendation",
    "flowguard-contract-exhaustion-mesh",
    "flowguard-development-process-flow",
    "flowguard-existing-model-preflight",
    "flowguard-field-lifecycle-mesh",
    "flowguard-model-mesh",
    "flowguard-model-miss-review",
    "flowguard-model-test-alignment",
    "flowguard-model-topology-hazard-review",
    "flowguard-plan-detailing-compiler",
    "flowguard-structure-mesh",
    "flowguard-test-mesh",
    "flowguard-ui-flow-structure",
)
REQUIRED_PROJECT_SKILL_IDS = (
    "kb-dream-pass",
    "kb-organization-contribute",
    "kb-organization-maintenance",
    "kb-sleep-maintenance",
    "khaos-brain-open-ui",
    "khaos-brain-update",
    "local-kb-retrieve",
    "organization-review",
)
RETIRED_FLOWGUARD_SHADOW_CONTROL_PATHS = (
    ".agents/skills/.flowguard-skill-suite-ownership.json",
    ".skillguard/flowguard-suite/suite-map.json",
    "scripts/verify_skill_suite_markers.py",
)


FORBIDDEN_BY_FILE: dict[str, tuple[str, ...]] = {
    "local_kb/logicguard_models.py": (
        "from logicguard",
        "import logicguard",
        'import_module("logicguard")',
        "import_module('logicguard')",
    ),
    "local_kb/dream.py": (
        "from logicguard",
        "import logicguard",
    ),
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
        "LOGICGUARD_VALIDATION_ROOT_ENV",
        "LOGICGUARD_VALIDATION_DIGEST_ENV",
        "_freeze_logicguard_validation_toolchain",
        "_require_live_logicguard_matches_snapshot",
        'import_module("logicguard")',
        'glob("*/current.json")',
        "compact_upgrade_attempt_projection",
        'UPGRADE_ATTEMPT_SCHEMA = "khaos-brain.upgrade-attempt.v1"',
        'UPGRADE_ATTEMPT_PROJECTION_SCHEMA = "khaos-brain.upgrade-attempt-projection.v1"',
    ),
    "local_kb/operator_activation.py": (
        'SCHEMA_VERSION = "khaos-brain.operator-automation-activation.v1"',
        "scheduled_production_refs",
    ),
    "local_kb/org_cleanup.py": ("kb/trusted", "kb/candidates", "legacy_compatibility"),
    "local_kb/org_maintenance.py": ("kb/trusted", "kb/candidates", "legacy_compatibility"),
    "local_kb/org_automation.py": ("kb/trusted", "kb/candidates", "legacy_compatibility"),
    "local_kb/org_checks.py": ("kb/trusted", "kb/candidates", "legacy_compatibility"),
    "scripts/run_kb_automation.py": (
        "SkillGuard",
        ".skillguard",
        "skillguard.py",
    ),
    "scripts/run_khaos_brain_manual_update.py": (
        "awaiting-skillguard",
        "final_skillguard",
        "staged-restoration-authorization",
    ),
    "templates/predictive-kb-preflight/kb_launch.py": ("--path-hint", "implicit_search"),
    ".agents/skills/local-kb-retrieve/scripts/kb_search.py": ("--path-hint",),
    "local_kb/feedback.py": (
        "admit_observation(",
        "replay_lifecycle(",
        "maintenance_standard_is_active",
    ),
    ".agents/skills/local-kb-retrieve/scripts/kb_feedback.py": (
        "from local_kb.lifecycle import admit_observation",
    ),
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
        'MIN_RESEARCHGUARD_VERSION = "0.1.1"',
        "researchguard_logic_dependency_preflight",
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
        "migrate_obsolete_update_state",
        "resolve_automation_runtime",
        'UPGRADE_ATTEMPT_SCHEMA = "khaos-brain.upgrade-attempt.v2"',
        'UPGRADE_ATTEMPT_PROJECTION_SCHEMA = "khaos-brain.upgrade-attempt-projection.v2"',
        'UPGRADE_ATTEMPT_HEAD_SCHEMA = "khaos-brain.upgrade-attempt-head.v1"',
        "def current_upgrade_attempt_authority(",
        '"history_files_scanned": 0',
    ),
    "local_kb/operator_activation.py": (
        'SCHEMA_VERSION = "khaos-brain.operator-automation-activation.v3"',
        "SKILL_INVENTORY_SCHEMA_VERSION",
        '"maintained_skill_ids"',
        '"scheduled_skill_ids"',
        '"manual_only_skill_ids"',
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
    "local_kb/feedback.py": (
        "POSTFLIGHT_RECEIPT_SCHEMA",
        "record_observation_result",
        "inspect_observation_postflight",
        "deferred_to_sleep_primary_path",
        '"timeout_unknown"',
    ),
    ".agents/skills/local-kb-retrieve/scripts/kb_feedback.py": (
        'parser.add_argument("--event-id"',
        'parser.add_argument("--inspect-event-id"',
        "record_observation_result",
        "inspect_observation_postflight",
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
        'MIGRATION_ID = "kb-maintenance-standard-v6-resumable-sleep-current-index"',
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
        "legacy_schema_found",
    ),
    "scripts/run_kb_automation.py": (
        "run_automation",
        "build_native_receipt",
        "validate_native_receipt",
    ),
    "scripts/run_khaos_brain_manual_update.py": (
        "run_manual_update",
        "apply_repo_automation_restoration_plan",
        "build_installation_check",
        '"status": "current-and-restored"',
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


def check_current_runtime_only(
    repo_root: Path = REPO_ROOT, *, consumer_install: bool = False
) -> dict[str, Any]:
    root = Path(repo_root)
    issues: list[str] = []
    rows: list[dict[str, Any]] = []
    governed_paths = sorted(set(FORBIDDEN_BY_FILE) | set(REQUIRED_BY_FILE))
    if consumer_install:
        governed_paths = [
            relative
            for relative in governed_paths
            if "skillguard" not in relative.lower()
        ]
    for relative in governed_paths:
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
        if "migrate_obsolete_update_state" in path.read_text(encoding="utf-8"):
            production_refs.append(path.relative_to(root).as_posix())
    for path in sorted((root / "scripts").rglob("*.py")):
        if path.name == Path(__file__).name:
            continue
        if "migrate_obsolete_update_state" in path.read_text(encoding="utf-8"):
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

    retired_standalone_logicguard_import_refs: list[str] = []
    retired_import_pattern = re.compile(
        r"(?m)^\s*(?:from\s+logicguard(?:\.|\s)|"
        r"import\s+logicguard(?:\.|\s|$))|"
        r"importlib(?:\.util)?\.import_module\(\s*['\"]logicguard['\"]"
    )
    for source_root in ("local_kb", "scripts"):
        for path in sorted((root / source_root).rglob("*.py")):
            if retired_import_pattern.search(path.read_text(encoding="utf-8")):
                retired_standalone_logicguard_import_refs.append(
                    path.relative_to(root).as_posix()
                )
    if retired_standalone_logicguard_import_refs:
        issues.append(
            "retired-standalone-logicguard-import-refs:"
            + ",".join(retired_standalone_logicguard_import_refs)
        )

    retired_standalone_logicguard_dependency_refs: list[str] = []
    for relative in ("requirements.txt", "requirements-dev.txt"):
        path = root / relative
        if not path.is_file():
            continue
        if any(
            re.match(
                r"(?i)^logicguard(?:\s|@|==|>=|<=|~=|!=|>|<|;|\[)",
                line.strip(),
            )
            for line in path.read_text(encoding="utf-8").splitlines()
        ):
            retired_standalone_logicguard_dependency_refs.append(relative)
    if retired_standalone_logicguard_dependency_refs:
        issues.append(
            "retired-standalone-logicguard-dependency-refs:"
            + ",".join(retired_standalone_logicguard_dependency_refs)
        )

    retired_flowguard_shadow_skill_residuals: list[str] = []
    missing_project_skill_surfaces: list[str] = []
    retired_flowguard_shadow_control_residuals: list[str] = []
    project_skills_root = root / ".agents" / "skills"
    if not consumer_install and project_skills_root.is_dir():
        retired_flowguard_shadow_skill_residuals = [
            f".agents/skills/{member_id}"
            for member_id in RETIRED_FLOWGUARD_SHADOW_MEMBER_IDS
            if (project_skills_root / member_id).exists()
        ]
        missing_project_skill_surfaces = [
            f".agents/skills/{skill_id}/SKILL.md"
            for skill_id in REQUIRED_PROJECT_SKILL_IDS
            if not (project_skills_root / skill_id / "SKILL.md").is_file()
        ]
        retired_flowguard_shadow_control_residuals = [
            relative
            for relative in RETIRED_FLOWGUARD_SHADOW_CONTROL_PATHS
            if (root / relative).exists()
        ]
        issues.extend(
            "retired-flowguard-shadow-skill-residual:" + relative
            for relative in retired_flowguard_shadow_skill_residuals
        )
        issues.extend(
            "missing-project-skill-surface:" + relative
            for relative in missing_project_skill_surfaces
        )
        issues.extend(
            "retired-flowguard-shadow-control-residual:" + relative
            for relative in retired_flowguard_shadow_control_residuals
        )

    return {
        "ok": not issues,
        "policy_id": "chaos-brain.current-runtime-only.v1",
        "consumer_install": consumer_install,
        "governed_file_count": len(rows),
        "governed_digest": _digest(rows),
        "obsolete_update_state_migrator_refs": production_refs,
        "normal_runtime_direct_card_store_readers": direct_card_store_readers,
        "retired_standalone_logicguard_import_refs": (
            retired_standalone_logicguard_import_refs
        ),
        "retired_standalone_logicguard_dependency_refs": (
            retired_standalone_logicguard_dependency_refs
        ),
        "retired_flowguard_shadow_skill_residuals": (
            retired_flowguard_shadow_skill_residuals
        ),
        "missing_project_skill_surfaces": missing_project_skill_surfaces,
        "retired_flowguard_shadow_control_residuals": (
            retired_flowguard_shadow_control_residuals
        ),
        "issues": issues,
        "files": rows,
        "claim_boundary": (
            "Static source gate for the enumerated retired runtime authorities "
            "and the ordinary-project skill surface. Migration behavior and "
            "installed-machine residual counts require their separate current "
            "receipts."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--consumer-install", action="store_true")
    args = parser.parse_args()
    report = check_current_runtime_only(
        Path(args.repo_root), consumer_install=args.consumer_install
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    else:
        print(f"ok: {report['ok']}")
        for issue in report["issues"]:
            print(f"- {issue}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
