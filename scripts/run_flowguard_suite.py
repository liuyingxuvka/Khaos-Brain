"""Run the release-facing FlowGuard assurance suite for Chaos Brain.

This suite complements the executable state models with two finite meshes:
field lifecycle ownership and Cartesian bad-case coverage.  It writes a
current machine-readable receipt so later readiness checks can reject stale or
missing assurance instead of trusting an old green report.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
FLOWGUARD_MODEL_ROOT = REPO_ROOT / ".flowguard"
if str(FLOWGUARD_MODEL_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_MODEL_ROOT))

import flowguard  # noqa: E402
import kb_convergence_upgrade_model as convergence_model  # noqa: E402


RECEIPT_PATH = REPO_ROOT / ".flowguard" / "evidence" / "kb_convergence_suite.json"
FLOWGUARD_SUITE_MAP_PATH = (
    REPO_ROOT / ".skillguard" / "flowguard-suite" / "suite-map.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _flowguard_route_for_owner(owner: str) -> str:
    """Resolve one canonical route from the sole suite inventory."""

    payload = json.loads(FLOWGUARD_SUITE_MAP_PATH.read_text(encoding="utf-8"))
    members = [
        row
        for row in payload.get("included_skills", [])
        if isinstance(row, dict) and str(row.get("owner") or "") == owner
    ]
    owner_slug = owner.replace("_", "-")
    exact_names = [
        str(row.get("name") or "")
        for row in members
        if str(row.get("name") or "")
        in {owner_slug, f"flowguard-{owner_slug}"}
    ]
    if len(exact_names) != 1:
        raise RuntimeError(
            f"FlowGuard suite owner {owner!r} does not resolve to one canonical route"
        )
    return exact_names[0]


def _flowguard_verifier_fingerprint() -> dict[str, Any]:
    """Bind a reusable suite receipt to the exact installed verifier code."""

    package_root = Path(flowguard.__file__).resolve().parent
    rows = [
        {
            "path": path.relative_to(package_root).as_posix(),
            "sha256": _sha256(path),
        }
        for path in sorted(package_root.rglob("*.py"))
        if "__pycache__" not in path.parts and path.is_file()
    ]
    digest = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": str(flowguard.SCHEMA_VERSION),
        "package_root": str(package_root),
        "python_file_count": len(rows),
        "package_digest": digest,
    }


def _projection(
    field_id: str,
    *,
    code_contract: str,
    inputs: tuple[str, ...] = (),
    outputs: tuple[str, ...] = (),
    reads: tuple[str, ...] = (),
    writes: tuple[str, ...] = (),
    effects: tuple[str, ...] = (),
) -> flowguard.FieldProjection:
    slug = field_id.replace(".", "-").replace("_", "-")
    return flowguard.FieldProjection(
        f"projection:{slug}",
        field_id,
        model_obligation_id=f"field:{slug}:obligation",
        code_contract_id=code_contract,
        required_test_kinds=(
            flowguard.TEST_KIND_HAPPY_PATH,
            flowguard.TEST_KIND_FAILURE_PATH,
        ),
        external_inputs=inputs,
        external_outputs=outputs,
        state_reads=reads,
        state_writes=writes,
        side_effects=effects,
        rationale=f"{field_id} controls a declared lifecycle or upgrade boundary",
    )


def _active_field(
    field_id: str,
    group_id: str,
    *,
    role: str,
    impacts: tuple[str, ...],
    readers: tuple[str, ...],
    writers: tuple[str, ...],
    contract: str,
) -> flowguard.FieldLifecycleRow:
    return flowguard.FieldLifecycleRow(
        field_id,
        group_id=group_id,
        role=role,
        lifecycle=flowguard.FIELD_LIFECYCLE_NEW,
        behavior_impacts=impacts,
        reader_ids=readers,
        writer_ids=writers,
        projection=_projection(
            field_id,
            code_contract=contract,
            inputs=(field_id,),
            outputs=(f"{field_id}:decision",),
            reads=(field_id,),
            writes=(field_id,),
        ),
    )


def _retired_field(
    field_id: str,
    *,
    replacement: str = "",
    disposition: str = flowguard.FIELD_DISPOSITION_DELETED,
    group_id: str = "architect-retirement",
    evidence_refs: tuple[str, ...] = (
        "tests/test_kb_upgrade_migration.py",
        "scripts/check_retired_kb_architect.py",
    ),
) -> flowguard.FieldLifecycleRow:
    slug = field_id.replace(".", "-").replace("_", "-")
    return flowguard.FieldLifecycleRow(
        field_id,
        group_id=group_id,
        role=flowguard.FIELD_ROLE_ROUTING,
        lifecycle=(
            flowguard.FIELD_LIFECYCLE_REPLACED
            if replacement
            else flowguard.FIELD_LIFECYCLE_OLD
        ),
        behavior_impacts=(
            flowguard.FIELD_IMPACT_ROUTING,
            flowguard.FIELD_IMPACT_STATE,
            flowguard.FIELD_IMPACT_SIDE_EFFECT,
        ),
        reader_ids=("legacy-upgrade-reader",),
        writer_ids=("retirement-migration",),
        replacement_field_id=replacement,
        disposition=disposition,
        disposition_evidence_refs=evidence_refs,
        projection=_projection(
            field_id,
            code_contract=f"retirement.{slug}",
            inputs=(field_id,),
            outputs=("retired-tombstone",),
            reads=(field_id,),
            writes=(replacement or "retired-id-set",),
            effects=("exact-managed-surface-removal",),
        ),
    )


def field_lifecycle_report() -> flowguard.FieldLifecycleReport:
    active_specs = (
        (
            "lifecycle.schema_version",
            "experience-lifecycle",
            flowguard.FIELD_ROLE_SCHEMA_VERSION,
            (flowguard.FIELD_IMPACT_SCHEMA,),
            "local_kb.lifecycle.replay_lifecycle",
        ),
        (
            "lifecycle.observation_id",
            "experience-lifecycle",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE,),
            "local_kb.lifecycle.admit_observation",
        ),
        (
            "lifecycle.disposition",
            "experience-lifecycle",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_ROUTING),
            "local_kb.lifecycle.dispose_observation",
        ),
        (
            "lifecycle.evidence_grade",
            "experience-lifecycle",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING,),
            "local_kb.lifecycle.classify_observation",
        ),
        (
            "lifecycle.entry_status",
            "retrieval-index",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_ROUTING),
            "local_kb.lifecycle.transition_entry",
        ),
        (
            "lifecycle.reopen_condition",
            "experience-lifecycle",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE,),
            "local_kb.candidate_lifecycle.review_entry_lifecycles",
        ),
        (
            "lifecycle.retrieval_eligible",
            "retrieval-index",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING,),
            "local_kb.lifecycle.entry_is_retrieval_eligible",
        ),
        (
            "retrieval.source_boundary",
            "retrieval-index",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING,),
            "local_kb.search.search_multi_source_entries",
        ),
        (
            "retrieval.authority_validation_mode",
            "retrieval-index",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING, flowguard.FIELD_IMPACT_STATE),
            "local_kb.active_index.load_active_entries",
        ),
        (
            "retrieval.current_index_required",
            "retrieval-index",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING, flowguard.FIELD_IMPACT_STATE),
            "local_kb.active_index.load_active_entries",
        ),
        (
            "organization.main_path",
            "current-only-runtime",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING, flowguard.FIELD_IMPACT_SCHEMA),
            "local_kb.org_sources.validate_organization_repo",
        ),
        (
            "organization.imports_path",
            "current-only-runtime",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING, flowguard.FIELD_IMPACT_SCHEMA),
            "local_kb.org_sources.validate_organization_repo",
        ),
        (
            "automation.current_model_policy",
            "current-only-runtime",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING, flowguard.FIELD_IMPACT_STATE),
            "local_kb.install.resolve_automation_runtime",
        ),
        (
            "launcher.explicit_command",
            "current-only-runtime",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING,),
            "templates.predictive-kb-preflight.kb_launch.main",
        ),
        (
            "launcher.route_hint",
            "current-only-runtime",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING,),
            "local-kb-retrieve.kb_search.main",
        ),
        (
            "desktop_launcher.selected_runtime",
            "current-only-runtime",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING,),
            "scripts.open_khaos_brain_ui._launch_command",
        ),
        (
            "desktop_settings.organization_maintenance_requested",
            "current-only-runtime",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_SCHEMA),
            "local_kb.settings.load_desktop_settings",
        ),
        (
            "card.use.unavailable_skill_guidance",
            "current-only-runtime",
            flowguard.FIELD_ROLE_SCHEMA_VERSION,
            (flowguard.FIELD_IMPACT_SCHEMA, flowguard.FIELD_IMPACT_ROUTING),
            "local_kb.org_outbox.skill_dependency_evidence",
        ),
        (
            "update.schema_version",
            "current-only-runtime",
            flowguard.FIELD_ROLE_SCHEMA_VERSION,
            (flowguard.FIELD_IMPACT_SCHEMA, flowguard.FIELD_IMPACT_STATE),
            "local_kb.software_update.load_update_state",
        ),
        (
            "sleep.watermark",
            "sleep-dream",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE,),
            "local_kb.lifecycle.run_incremental_sleep",
        ),
        (
            "lifecycle.writer_lock_owner",
            "experience-lifecycle",
            flowguard.FIELD_ROLE_STATE,
            (
                flowguard.FIELD_IMPACT_STATE,
                flowguard.FIELD_IMPACT_SIDE_EFFECT,
            ),
            "local_kb.lifecycle._lifecycle_lock",
        ),
        (
            "lifecycle.entry_calibration_watermark",
            "experience-lifecycle",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE,),
            "local_kb.candidate_lifecycle.review_entry_lifecycles",
        ),
        (
            "sleep.model_publication_owner",
            "sleep-dream",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_SIDE_EFFECT),
            "local_kb.lifecycle.run_incremental_sleep",
        ),
        (
            "sleep.actionable_backlog",
            "sleep-dream",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE,),
            "local_kb.lifecycle.run_incremental_sleep",
        ),
        (
            "dream.evidence_fingerprint",
            "sleep-dream",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_SIDE_EFFECT),
            "local_kb.dream.run_dream_maintenance",
        ),
        (
            "dream.pending_handoff",
            "sleep-dream",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_SIDE_EFFECT),
            "local_kb.lifecycle.record_dream_handoff",
        ),
        (
            "dream.handoff_commit_ack",
            "sleep-dream",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_SIDE_EFFECT),
            "local_kb.lifecycle.acknowledge_dream_handoff",
        ),
        (
            "migration.schema_version",
            "upgrade-migration",
            flowguard.FIELD_ROLE_SCHEMA_VERSION,
            (flowguard.FIELD_IMPACT_SCHEMA, flowguard.FIELD_IMPACT_MIGRATION),
            "local_kb.maintenance_migration.run_maintenance_migration",
        ),
        (
            "migration.phase",
            "upgrade-migration",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_MIGRATION),
            "local_kb.maintenance_migration.run_maintenance_migration",
        ),
        (
            "migration.canonicalization_receipt",
            "upgrade-migration",
            flowguard.FIELD_ROLE_PERSISTED,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_MIGRATION),
            "local_kb.maintenance_migration.canonicalize_runtime_state",
        ),
        (
            "migration.failure_state",
            "upgrade-migration",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_MIGRATION),
            "local_kb.maintenance_migration.run_maintenance_migration",
        ),
        (
            "migration.reconciliation_receipt",
            "upgrade-migration",
            flowguard.FIELD_ROLE_PERSISTED,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_MIGRATION),
            "local_kb.maintenance_migration.reconcile_managed_surface",
        ),
        (
            "migration.path_representation",
            "upgrade-migration",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_MIGRATION),
            "local_kb.maintenance_migration._fs_path",
        ),
        (
            "migration.logical_reconciliation_receipt",
            "upgrade-migration",
            flowguard.FIELD_ROLE_PERSISTED,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_MIGRATION),
            "local_kb.maintenance_migration.settle_knowledge_debt",
        ),
        (
            "migration.archive_manifest",
            "upgrade-migration",
            flowguard.FIELD_ROLE_PERSISTED,
            (flowguard.FIELD_IMPACT_MIGRATION, flowguard.FIELD_IMPACT_SIDE_EFFECT),
            "local_kb.maintenance_migration.archive_inventory",
        ),
        (
            "migration.prune_receipt",
            "upgrade-migration",
            flowguard.FIELD_ROLE_PERSISTED,
            (flowguard.FIELD_IMPACT_MIGRATION, flowguard.FIELD_IMPACT_SIDE_EFFECT),
            "local_kb.maintenance_migration.prune_inventory",
        ),
        (
            "migration.prune_file_mode",
            "upgrade-migration",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_SIDE_EFFECT),
            "local_kb.maintenance_migration._unlink_verified_managed_file",
        ),
        (
            "migration.prune_resume_accounting",
            "upgrade-migration",
            flowguard.FIELD_ROLE_PERSISTED,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_MIGRATION),
            "local_kb.maintenance_migration.prune_inventory",
        ),
        (
            "migration.install_transaction",
            "upgrade-migration",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_SIDE_EFFECT),
            "local_kb.transactional_install.install_managed_runtime",
        ),
        (
            "migration.prior_automation_states",
            "upgrade-migration",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_SIDE_EFFECT),
            "local_kb.transactional_install.install_managed_runtime",
        ),
        (
            "migration.settlement_mode",
            "upgrade-migration",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_MIGRATION),
            "local_kb.maintenance_migration.settle_knowledge_debt",
        ),
        (
            "migration.settlement_event_count",
            "upgrade-migration",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_MIGRATION),
            "local_kb.maintenance_migration.settle_knowledge_debt",
        ),
        (
            "migration.settlement_replay_pass_count",
            "upgrade-migration",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_MIGRATION),
            "local_kb.lifecycle.commit_lifecycle_events",
        ),
        (
            "migration.settlement_batch_count",
            "upgrade-migration",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_MIGRATION),
            "local_kb.lifecycle.commit_lifecycle_events",
        ),
        (
            "migration.settlement_reused_count",
            "upgrade-migration",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_MIGRATION),
            "local_kb.lifecycle.commit_lifecycle_events",
        ),
        (
            "install.assurance_context",
            "upgrade-migration",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING, flowguard.FIELD_IMPACT_SIDE_EFFECT),
            "scripts.install_codex_kb.main",
        ),
        (
            "install.router_refresh_receipt",
            "upgrade-migration",
            flowguard.FIELD_ROLE_PERSISTED,
            (
                flowguard.FIELD_IMPACT_STATE,
                flowguard.FIELD_IMPACT_MIGRATION,
                flowguard.FIELD_IMPACT_SIDE_EFFECT,
            ),
            "local_kb.install._record_upgrade_attempt",
        ),
        (
            "install.skillguard_router_surface_fingerprint",
            "upgrade-migration",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_MIGRATION),
            "local_kb.install._skillguard_router_surface",
        ),
        (
            "install.router_registry_freshness",
            "upgrade-migration",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_ROUTING),
            "local_kb.install._verify_skillguard_global_router",
        ),
        (
            "install.router_prompt_freshness",
            "upgrade-migration",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_ROUTING),
            "local_kb.install._verify_skillguard_global_router",
        ),
        (
            "install.post_commit_assurance_failure",
            "upgrade-migration",
            flowguard.FIELD_ROLE_PERSISTED,
            (
                flowguard.FIELD_IMPACT_STATE,
                flowguard.FIELD_IMPACT_MIGRATION,
                flowguard.FIELD_IMPACT_SIDE_EFFECT,
            ),
            "local_kb.install._record_upgrade_attempt",
        ),
        (
            "automation.native_run_receipt",
            "automation-assurance",
            flowguard.FIELD_ROLE_PERSISTED,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_SIDE_EFFECT),
            "local_kb.automation_runtime.build_native_receipt",
        ),
        (
            "automation.skillguard_execution_depth",
            "automation-assurance",
            flowguard.FIELD_ROLE_STATE,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_ROUTING),
            "scripts.check_kb_skillguard._execute_supervision",
        ),
        (
            "automation.skillguard_closure_profile",
            "automation-assurance",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING,),
            "scripts.check_kb_skillguard._execute_supervision",
        ),
        (
            "automation.capability_junit_receipt",
            "automation-assurance",
            flowguard.FIELD_ROLE_PERSISTED,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_ROUTING),
            "scripts.check_kb_skillguard._run_capability_regression",
        ),
        (
            "automation.restoration_plan",
            "automation-assurance",
            flowguard.FIELD_ROLE_PERSISTED,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_SIDE_EFFECT),
            "local_kb.install.plan_repo_automation_restoration",
        ),
        (
            "automation.finalization_receipt",
            "automation-assurance",
            flowguard.FIELD_ROLE_PERSISTED,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_ROUTING),
            "local_kb.automation_runtime.build_update_finalization_receipt",
        ),
        (
            "automation.activation_receipt",
            "automation-assurance",
            flowguard.FIELD_ROLE_PERSISTED,
            (flowguard.FIELD_IMPACT_STATE, flowguard.FIELD_IMPACT_SIDE_EFFECT),
            "local_kb.automation_runtime.build_update_activation_receipt",
        ),
        (
            "retirement.active_registry_path",
            "architect-retirement",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING,),
            "local_kb.codex_registry.discover_active_registry",
        ),
        (
            "retirement.registry_scope",
            "architect-retirement",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING, flowguard.FIELD_IMPACT_STATE),
            "local_kb.codex_registry.discover_active_registry",
        ),
        (
            "system_update_check",
            "system-maintenance",
            flowguard.FIELD_ROLE_ROUTING,
            (flowguard.FIELD_IMPACT_ROUTING,),
            "local_kb.software_update.system_update_check",
        ),
    )
    active_rows = tuple(
        _active_field(
            field_id,
            group_id,
            role=role,
            impacts=impacts,
            readers=(contract,),
            writers=(contract,),
            contract=contract,
        )
        for field_id, group_id, role, impacts, contract in active_specs
    )
    retired_rows = (
        _retired_field("architect.skill_id"),
        _retired_field("architect.automation_id"),
        _retired_field(
            "architect.queue", replacement="lifecycle.disposition",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
        ),
        _retired_field(
            "architect.handoff", replacement="dream.pending_handoff",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
        ),
        _retired_field(
            "architect_update_check", replacement="system_update_check",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
        ),
        _retired_field(
            "architect.readiness_gate", replacement="migration.install_transaction",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
        ),
        _retired_field(
            "retrieval.filtered_scan",
            replacement="retrieval.current_index_required",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_kb_retrieval_calibration.py",),
        ),
        _retired_field(
            "retrieval.unindexed_directory_scan",
            replacement="retrieval.current_index_required",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_kb_retrieval_calibration.py",),
        ),
        _retired_field(
            "organization.trusted_path",
            replacement="organization.main_path",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_org_sources.py",),
        ),
        _retired_field(
            "organization.candidates_path",
            replacement="organization.main_path",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_org_sources.py",),
        ),
        _retired_field(
            "automation.fixed_model_fallback",
            replacement="automation.current_model_policy",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_codex_install.py",),
        ),
        _retired_field(
            "automation.fixed_reasoning_fallback",
            replacement="automation.current_model_policy",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_codex_install.py",),
        ),
        _retired_field(
            "launcher.implicit_search",
            replacement="launcher.explicit_command",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_kb_preflight_entry_compat.py",),
        ),
        _retired_field(
            "launcher.path_hint_alias",
            replacement="launcher.route_hint",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_kb_preflight_entry_compat.py",),
        ),
        _retired_field(
            "desktop_launcher.prefer_python",
            replacement="desktop_launcher.selected_runtime",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_desktop_launcher_current_runtime.py",),
        ),
        _retired_field(
            "desktop_launcher.exe_candidates",
            replacement="desktop_launcher.selected_runtime",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_desktop_launcher_current_runtime.py",),
        ),
        _retired_field(
            "desktop_settings.maintainer_mode_requested",
            replacement="desktop_settings.organization_maintenance_requested",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_desktop_settings.py",),
        ),
        _retired_field(
            "desktop_settings.maintainer_validation_fields",
            replacement="desktop_settings.organization_maintenance_requested",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_desktop_settings.py",),
        ),
        _retired_field(
            "card.use.skill_guidance_aliases",
            replacement="card.use.unavailable_skill_guidance",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_card_schema_migration.py",),
        ),
        _retired_field(
            "update.runtime_identity_failure_repair",
            replacement="migration.canonicalization_receipt",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_software_update.py",),
        ),
        _retired_field(
            "update.pre_schema_document",
            replacement="update.schema_version",
            disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
            group_id="current-only-runtime",
            evidence_refs=("tests/test_software_update.py",),
        ),
    )
    rows = active_rows + retired_rows
    kernel_route = _flowguard_route_for_owner("model_first_function_flow")
    field_lifecycle_route = _flowguard_route_for_owner("field_lifecycle_mesh")
    development_process_route = _flowguard_route_for_owner(
        "development_process_flow"
    )
    model_test_alignment_route = _flowguard_route_for_owner(
        "model_test_alignment"
    )
    groups = (
        flowguard.FieldLifecycleGroup(
            "experience-lifecycle",
            boundary_kind="durable_ledger",
            field_ids=tuple(row.field_id for row in rows if row.group_id == "experience-lifecycle"),
            owner_route=kernel_route,
        ),
        flowguard.FieldLifecycleGroup(
            "retrieval-index",
            boundary_kind="derived_index",
            field_ids=tuple(row.field_id for row in rows if row.group_id == "retrieval-index"),
            owner_route=field_lifecycle_route,
        ),
        flowguard.FieldLifecycleGroup(
            "sleep-dream",
            boundary_kind="maintenance_handoff",
            field_ids=tuple(row.field_id for row in rows if row.group_id == "sleep-dream"),
            owner_route=kernel_route,
        ),
        flowguard.FieldLifecycleGroup(
            "upgrade-migration",
            boundary_kind="versioned_migration",
            field_ids=tuple(row.field_id for row in rows if row.group_id == "upgrade-migration"),
            owner_route=development_process_route,
        ),
        flowguard.FieldLifecycleGroup(
            "automation-assurance",
            boundary_kind="scheduled_run_receipt",
            field_ids=tuple(row.field_id for row in rows if row.group_id == "automation-assurance"),
            owner_route=model_test_alignment_route,
        ),
        flowguard.FieldLifecycleGroup(
            "system-maintenance",
            boundary_kind="system_update",
            field_ids=tuple(row.field_id for row in rows if row.group_id == "system-maintenance"),
            owner_route=field_lifecycle_route,
        ),
        flowguard.FieldLifecycleGroup(
            "architect-retirement",
            boundary_kind="retired_surface",
            field_ids=tuple(row.field_id for row in rows if row.group_id == "architect-retirement"),
            owner_route=field_lifecycle_route,
        ),
        flowguard.FieldLifecycleGroup(
            "current-only-runtime",
            boundary_kind="direct_to_current_migration",
            field_ids=tuple(row.field_id for row in rows if row.group_id == "current-only-runtime"),
            owner_route=field_lifecycle_route,
        ),
    )
    return flowguard.review_field_lifecycle(
        flowguard.FieldLifecyclePlan(
            "chaos-brain-lifecycle-fields-v1",
            discovered_field_ids=tuple(row.field_id for row in rows),
            groups=groups,
            fields=rows,
            claim_scope="bounded",
            allow_scoped_confidence=False,
        )
    )


def contract_exhaustion_report() -> flowguard.ContractExhaustionReport:
    axes = (
        flowguard.ContractAxis(
            "machine_history",
            model_id="kb-upgrade-migration",
            values=(
                "fresh",
                "legacy-active",
                "legacy-paused",
                "missing-manifest",
                "interrupted",
                "repeated",
            ),
        ),
        flowguard.ContractAxis(
            "install_integrity",
            model_id="kb-upgrade-migration",
            values=("current", "source-drift", "downgrade", "rollback-missing"),
        ),
        flowguard.ContractAxis(
            "prior_pause_state",
            model_id="kb-upgrade-migration",
            values=("active", "paused"),
        ),
        flowguard.ContractAxis(
            "aggregate_gate",
            model_id="kb-upgrade-migration",
            values=("pass", "fail"),
        ),
        flowguard.ContractAxis(
            "automation_completion_surface",
            model_id="kb-automation-runtime-assurance",
            values=("prompt-or-plan", "capability-regression", "native-terminal-receipt"),
        ),
        flowguard.ContractAxis(
            "automation_depth_receipt",
            model_id="kb-automation-runtime-assurance",
            values=("missing", "stale", "shallow-blocked", "execution-depth-pass"),
        ),
        flowguard.ContractAxis(
            "automation_semantic_depth_surface",
            model_id="kb-automation-runtime-assurance",
            values=(
                "target-native-per-obligation-receipts",
                "single-source-mechanical-expansion",
                "generic-obligation-calibration",
            ),
        ),
        flowguard.ContractAxis(
            "automation_native_lane_semantics",
            model_id="kb-automation-runtime-assurance",
            values=(
                "lane-lock-real-review-closed",
                "active-dream-lane-skipped",
                "sleep-lock-unheld",
                "fixture-masks-real-lifecycle-failure",
            ),
        ),
        flowguard.ContractAxis(
            "automation_noop_semantics",
            model_id="kb-automation-runtime-assurance",
            values=(
                "not-noop",
                "gate-scoped-functional-executed",
                "broad-all-obligations-passed",
                "update-authorization-only",
            ),
        ),
        flowguard.ContractAxis(
            "update_skillguard_stage",
            model_id="kb-automation-runtime-assurance",
            values=("authorization-only", "finalization-pass", "finalization-fail"),
        ),
        flowguard.ContractAxis(
            "restoration_source_state",
            model_id="kb-automation-runtime-assurance",
            values=("all-paused-current", "active-before-final", "hash-drift"),
        ),
        flowguard.ContractAxis(
            "activation_readback",
            model_id="kb-automation-runtime-assurance",
            values=("exact", "apply-fail", "readback-mismatch"),
        ),
        flowguard.ContractAxis(
            "retirement_registry_scope",
            model_id="kb-upgrade-migration",
            values=("active-codex-home", "unrelated-external"),
        ),
        flowguard.ContractAxis(
            "active_registry_state",
            model_id="kb-upgrade-migration",
            values=("clean", "architect-present", "unreadable"),
        ),
        flowguard.ContractAxis(
            "dream_evidence_delta",
            model_id="kb-lifecycle-convergence",
            values=("unchanged", "changed"),
        ),
        flowguard.ContractAxis(
            "dream_prior_outcome",
            model_id="kb-lifecycle-convergence",
            values=("passed", "failed", "weak", "inconclusive"),
        ),
        flowguard.ContractAxis(
            "index_state",
            model_id="kb-lifecycle-convergence",
            values=("current", "stale", "missing"),
        ),
        flowguard.ContractAxis(
            "query_authority_mode",
            model_id="kb-lifecycle-convergence",
            values=("fast-authority", "full-manifest-replay"),
        ),
        flowguard.ContractAxis(
            "entry_lifecycle",
            model_id="kb-lifecycle-convergence",
            values=("trusted", "candidate-ineligible", "rejected", "parked"),
        ),
        flowguard.ContractAxis(
            "candidate_source_boundary",
            model_id="kb-lifecycle-convergence",
            values=("local-active-index", "organization-read-only"),
        ),
        flowguard.ContractAxis(
            "organization_layout_consumer",
            model_id="kb-upgrade-migration",
            values=(
                "runtime-reader",
                "outbox-dedupe",
                "adoption",
                "github-check",
            ),
        ),
        flowguard.ContractAxis(
            "organization_layout_state",
            model_id="kb-upgrade-migration",
            values=("current-main-imports", "obsolete-root-present", "main-missing"),
        ),
        flowguard.ContractAxis(
            "organization_decision_identity",
            model_id="kb-upgrade-migration",
            values=("unique-stable", "duplicate-collision", "count-mismatch"),
        ),
        flowguard.ContractAxis(
            "installed_skillguard_contract_authority",
            model_id="kb-automation-runtime-assurance",
            values=(
                "verified-repository-local-installed-byte-projection",
                "installed-root-outside-repository",
                "installed-recompiled-as-repository",
                "source-execution-substitute",
            ),
        ),
        flowguard.ContractAxis(
            "skillguard_runtime_projection_authority",
            model_id="kb-automation-runtime-assurance",
            values=(
                "verified-short-root-behavior-and-router-projection",
                "runtime-state-or-cache-included",
                "global-router-sibling-missing",
                "installed-runtime-identity-mismatch",
                "deep-run-root-path-dependent",
            ),
        ),
        flowguard.ContractAxis(
            "target_fixture_check_binding",
            model_id="kb-automation-runtime-assurance",
            values=(
                "exact-manifest-and-readiness-binding",
                "positive-or-shallow-check-missing",
                "fixture-check-duplicated-or-misowned",
            ),
        ),
        flowguard.ContractAxis(
            "update_state_migration_phase",
            model_id="kb-upgrade-migration",
            values=("before-aggregate-assurance", "after-assurance", "daily-runtime"),
        ),
        flowguard.ContractAxis(
            "alignment_validation_owner_binding",
            model_id="kb-upgrade-migration",
            values=(
                "declared-logical-owner",
                "raw-receipt-owner-name",
                "unknown-owner-name",
            ),
        ),
        flowguard.ContractAxis(
            "candidate_evidence",
            model_id="kb-lifecycle-convergence",
            values=("eligible", "ineligible"),
        ),
        flowguard.ContractAxis(
            "history_scale",
            model_id="kb-upgrade-migration",
            values=("small", "large", "partial-resume"),
        ),
        flowguard.ContractAxis(
            "settlement_mode",
            model_id="kb-upgrade-migration",
            values=("atomic-batch", "per-item-replay"),
        ),
        flowguard.ContractAxis(
            "managed_file_attribute",
            model_id="kb-upgrade-migration",
            values=("writable", "read-only", "acl-denied"),
        ),
        flowguard.ContractAxis(
            "prune_resume_state",
            model_id="kb-upgrade-migration",
            values=("fresh", "partial"),
        ),
        flowguard.ContractAxis(
            "journal_failure_state",
            model_id="kb-upgrade-migration",
            values=("none", "active-paused", "resolved-history", "stale-committed"),
        ),
        flowguard.ContractAxis(
            "managed_surface_drift",
            model_id="kb-upgrade-migration",
            values=("none", "during-validation", "after-commit"),
        ),
        flowguard.ContractAxis(
            "managed_path_length",
            model_id="kb-upgrade-migration",
            values=("normal", "legacy-limit", "extended-length"),
        ),
        flowguard.ContractAxis(
            "post_commit_logical_drift",
            model_id="kb-upgrade-migration",
            values=("none", "one-observation", "continuous-observations"),
        ),
        flowguard.ContractAxis(
            "assurance_invocation",
            model_id="kb-upgrade-migration",
            values=("outer-upgrade", "aggregate-child", "isolated-fixture"),
        ),
        flowguard.ContractAxis(
            "router_refresh_receipt_state",
            model_id="kb-upgrade-migration",
            values=("final-durable", "missing", "pre-assurance-only"),
        ),
        flowguard.ContractAxis(
            "router_surface_after_refresh",
            model_id="kb-upgrade-migration",
            values=("stable", "drifted"),
        ),
        flowguard.ContractAxis(
            "router_registry_freshness",
            model_id="kb-upgrade-migration",
            values=("current-to-surface", "stale-to-surface", "unreadable"),
        ),
        flowguard.ContractAxis(
            "router_prompt_freshness",
            model_id="kb-upgrade-migration",
            values=("current-to-registry", "matches-old-registry", "unreadable"),
        ),
        flowguard.ContractAxis(
            "post_commit_assurance_outcome",
            model_id="kb-upgrade-migration",
            values=("pass", "failed-paused-retryable", "failed-ignored"),
        ),
    )
    groups = (
        flowguard.ContractInteractionGroup(
            "automation-run-depth-closure",
            model_id="kb-automation-runtime-assurance",
            axis_ids=("automation_completion_surface", "automation_depth_receipt"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "automation-native-semantic-depth",
            model_id="kb-automation-runtime-assurance",
            axis_ids=(
                "automation_semantic_depth_surface",
                "automation_native_lane_semantics",
                "automation_noop_semantics",
            ),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "staged-update-restoration",
            model_id="kb-automation-runtime-assurance",
            axis_ids=(
                "update_skillguard_stage",
                "restoration_source_state",
                "activation_readback",
            ),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "architect-active-registry-scope",
            model_id="kb-upgrade-migration",
            axis_ids=("retirement_registry_scope", "active_registry_state"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "legacy-upgrade-integrity",
            model_id="kb-upgrade-migration",
            axis_ids=("machine_history", "install_integrity"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "restore-preserves-user-state",
            model_id="kb-upgrade-migration",
            axis_ids=("prior_pause_state", "aggregate_gate"),
            required_routes=(flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "resume-journal-coherence",
            model_id="kb-upgrade-migration",
            axis_ids=("machine_history", "journal_failure_state"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "managed-surface-convergence",
            model_id="kb-upgrade-migration",
            axis_ids=("machine_history", "managed_surface_drift"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "managed-path-visibility",
            model_id="kb-upgrade-migration",
            axis_ids=("managed_file_attribute", "managed_path_length"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "post-commit-logical-convergence",
            model_id="kb-upgrade-migration",
            axis_ids=("machine_history", "post_commit_logical_drift"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "dream-convergence",
            model_id="kb-lifecycle-convergence",
            axis_ids=("dream_evidence_delta", "dream_prior_outcome"),
            required_routes=(flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "retrieval-current-authority",
            model_id="kb-lifecycle-convergence",
            axis_ids=("index_state", "entry_lifecycle"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_FIELD_LIFECYCLE,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "foreground-query-authority",
            model_id="kb-lifecycle-convergence",
            axis_ids=("index_state", "query_authority_mode"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "candidate-source-boundary",
            model_id="kb-lifecycle-convergence",
            axis_ids=("candidate_source_boundary", "candidate_evidence"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_FIELD_LIFECYCLE,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "organization-current-layout-consumer-radius",
            model_id="kb-upgrade-migration",
            axis_ids=("organization_layout_consumer", "organization_layout_state"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_FIELD_LIFECYCLE,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "organization-decision-identity",
            model_id="kb-upgrade-migration",
            axis_ids=("organization_decision_identity", "organization_layout_state"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "installed-skillguard-deployment-projection",
            model_id="kb-automation-runtime-assurance",
            axis_ids=(
                "installed_skillguard_contract_authority",
                "automation_completion_surface",
            ),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "skillguard-runtime-projection-currentness",
            model_id="kb-automation-runtime-assurance",
            axis_ids=(
                "skillguard_runtime_projection_authority",
                "automation_completion_surface",
            ),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "target-owned-fixture-check-binding",
            model_id="kb-automation-runtime-assurance",
            axis_ids=(
                "target_fixture_check_binding",
                "automation_completion_surface",
            ),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "update-state-pre-assurance-canonicalization",
            model_id="kb-upgrade-migration",
            axis_ids=("update_state_migration_phase", "assurance_invocation"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_FIELD_LIFECYCLE,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "model-test-logical-owner-binding",
            model_id="kb-upgrade-migration",
            axis_ids=(
                "alignment_validation_owner_binding",
                "assurance_invocation",
            ),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "history-settlement-scale",
            model_id="kb-upgrade-migration",
            axis_ids=("history_scale", "settlement_mode"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_FIELD_LIFECYCLE,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "prune-permission-and-resume",
            model_id="kb-upgrade-migration",
            axis_ids=("managed_file_attribute", "prune_resume_state"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_FIELD_LIFECYCLE,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "assurance-recursion-safety",
            model_id="kb-upgrade-migration",
            axis_ids=("assurance_invocation", "aggregate_gate"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "router-refresh-durability-and-freshness",
            model_id="kb-upgrade-migration",
            axis_ids=(
                "router_refresh_receipt_state",
                "router_surface_after_refresh",
                "router_registry_freshness",
                "router_prompt_freshness",
            ),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
                flowguard.CONTRACT_ROUTE_FIELD_LIFECYCLE,
            ),
            oracle_id="block-with-repair",
        ),
        flowguard.ContractInteractionGroup(
            "post-commit-assurance-failure-retry",
            model_id="kb-upgrade-migration",
            axis_ids=("post_commit_assurance_outcome", "prior_pause_state"),
            required_routes=(
                flowguard.CONTRACT_ROUTE_MODEL_MISS_REVIEW,
                flowguard.CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
                flowguard.CONTRACT_ROUTE_TEST_MESH,
            ),
            oracle_id="block-with-repair",
        ),
    )
    return flowguard.review_contract_exhaustion(
        flowguard.ContractExhaustionPlan(
            "chaos-brain-finite-boundaries-v1",
            model_id="kb-convergence-upgrade",
            axes=axes,
            interaction_groups=groups,
            oracles=(
                flowguard.ContractOracle(
                    "block-with-repair",
                    flowguard.CONTRACT_ORACLE_BLOCK_BEFORE_DOWNSTREAM,
                    expected_message_fields=("failed_axis", "failure_reason"),
                    required_repair_fields=("failed_axis", "required_action"),
                    forbidden_downstream_steps=("commit", "restore-survivors"),
                    disallowed_side_effects=("unverified-commit",),
                    description="Block the unsafe combination and name the exact repair.",
                ),
            ),
            require_model_coverage_receipt=True,
            cartesian_case_limit=72,
            claim_scope="release",
            allow_unbounded_scoped=False,
            coverage_universe=flowguard.ContractCoverageUniverse(
                "chaos-brain-upgrade-universe-v1",
                claim_scope="release",
                source_refs=(
                    "openspec/changes/converge-kb-learning-and-upgrade-migration/verification-contract.yaml",
                    ".flowguard/kb_convergence_upgrade_model.py",
                ),
                required_axis_ids=tuple(axis.axis_id for axis in axes),
                required_interaction_group_ids=tuple(group.group_id for group in groups),
                required_coverage_receipt_ids=(
                    "contract_coverage:kb-convergence-upgrade",
                ),
                require_full_product=True,
            ),
            require_coverage_universe=True,
            require_actionable_oracle_feedback=True,
        )
    )


def model_miss_backpropagation_report() -> flowguard.FalseNegativeBackpropagationReport:
    return flowguard.review_false_negative_backpropagation(
        flowguard.FalseNegativeBackpropagationPlan(
            "chaos-brain-post-green-misses-v1",
            recurring_or_high_risk=True,
            allow_scoped_confidence=False,
            cases=(
                flowguard.FalseNegativeCase(
                    "miss-assurance-recursive-install",
                    previous_claim_id="flowguard:kb-convergence-upgrade:green-before-full-regression",
                    observed_failure_id="pytest:test_installer_and_check_json_are_safe_under_cp1252:lock-timeout",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "assurance invocation context and nested upgrade depth had been modeled",
                    ),
                    generalized_case_id="contract:assurance-recursion-safety",
                    new_model_obligation_id="req.assurance.no-recursive-install",
                    new_plan_item_ids=(
                        "field:install.assurance_context",
                        "known-bad:recursive_assurance",
                    ),
                    closure_evidence_ids=(
                        "test:aggregate-assurance-child-isolation",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "scripts/install_codex_kb.py:assurance-child-fixture-boundary",
                    ),
                    metadata={
                        "miss_type": "input_branch_missing",
                        "owner_code_contract": "scripts.install_codex_kb.main",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-per-item-lifecycle-replay",
                    previous_claim_id="flowguard:kb-convergence-upgrade:green-before-live-scale-migration",
                    observed_failure_id="live-migration:463639-files:per-item-replay-nonprogress",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_INVARIANT_TOO_WEAK,
                    would_have_failed_if=(
                        "historical item count, settlement mode, replay passes, and batch count had been modeled",
                    ),
                    generalized_case_id="contract:history-settlement-scale",
                    new_model_obligation_id="req.history.scale-bounded-settlement",
                    new_plan_item_ids=(
                        "field:migration.settlement_mode",
                        "field:migration.settlement_replay_pass_count",
                        "known-bad:per_item_replay",
                    ),
                    closure_evidence_ids=(
                        "test:large-lifecycle-batch-two-replays",
                        "test:large-history-settlement-resume",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/lifecycle.py:commit_lifecycle_events",
                        "local_kb/maintenance_migration.py:settle_knowledge_debt",
                    ),
                    metadata={
                        "miss_type": "progress_state_missing",
                        "owner_code_contract": "local_kb.maintenance_migration.settle_knowledge_debt",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-windows-read-only-prune-resume",
                    previous_claim_id="flowguard:kb-convergence-upgrade:green-before-live-prune",
                    observed_failure_id="live-migration:read-only-git-object:permission-error",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "verified read-only versus ACL-denied file state and partial prune accounting had been crossed",
                    ),
                    generalized_case_id="contract:prune-permission-and-resume",
                    new_model_obligation_id="req.history.archive-prune-index",
                    new_plan_item_ids=(
                        "field:migration.prune_file_mode",
                        "field:migration.prune_resume_accounting",
                        "known-bad:read_only_prune_unhandled",
                    ),
                    closure_evidence_ids=(
                        "test:verified-read-only-managed-file",
                        "test:partial-prune-manifest-resume",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/maintenance_migration.py:_unlink_verified_managed_file",
                        "local_kb/maintenance_migration.py:prune_inventory",
                    ),
                    metadata={
                        "miss_type": "input_branch_missing",
                        "owner_code_contract": "local_kb.maintenance_migration.prune_inventory",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-stale-committed-failure",
                    previous_claim_id="flowguard:kb-convergence-upgrade:green-before-live-resume-commit",
                    observed_failure_id="live-migration:committed-journal-retained-permission-error",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_INVARIANT_TOO_WEAK,
                    would_have_failed_if=(
                        "active versus resolved journal failure state had been modeled across resume and commit",
                    ),
                    generalized_case_id="contract:migration-failure-state-coherence",
                    new_model_obligation_id="req.history.versioned-migration",
                    new_plan_item_ids=(
                        "field:migration.failure_state",
                        "known-bad:stale_committed_failure",
                    ),
                    closure_evidence_ids=(
                        "test:resolved-failure-moves-to-history",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/maintenance_migration.py:_resolve_active_failure",
                        "local_kb/maintenance_migration.py:check_migration",
                    ),
                    metadata={
                        "miss_type": "state_too_coarse",
                        "owner_code_contract": "local_kb.maintenance_migration.run_maintenance_migration",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-late-managed-surface-reintroduction",
                    previous_claim_id="flowguard:kb-convergence-upgrade:green-before-live-install-gate",
                    observed_failure_id="live-install:87709-managed-files-reappeared-after-validation-start",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "managed-surface drift had been checked after archive verification and again after commit",
                    ),
                    generalized_case_id="contract:managed-surface-convergence",
                    new_model_obligation_id="req.history.versioned-migration",
                    new_plan_item_ids=(
                        "field:migration.reconciliation_receipt",
                        "known-bad:late_managed_debt_unchecked",
                    ),
                    closure_evidence_ids=(
                        "test:post-commit-reintroduced-managed-debt",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/maintenance_migration.py:reconcile_managed_surface",
                        "local_kb/maintenance_migration.py:validate_migration",
                    ),
                    metadata={
                        "miss_type": "temporal_observation_missing",
                        "owner_code_contract": "local_kb.maintenance_migration.run_maintenance_migration",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-windows-extended-length-managed-paths",
                    previous_claim_id="flowguard:kb-convergence-upgrade:green-before-powershell-cross-check",
                    observed_failure_id="live-migration:87709-files-visible-to-powershell-invisible-to-pathlib",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "managed path representation and the legacy Win32 length boundary had been modeled",
                    ),
                    generalized_case_id="contract:managed-long-path-visibility",
                    new_model_obligation_id="req.history.archive-prune-index",
                    new_plan_item_ids=(
                        "field:migration.path_representation",
                        "known-bad:long_path_invisible",
                    ),
                    closure_evidence_ids=(
                        "test:windows-long-managed-path-pruned",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/maintenance_migration.py:_fs_path",
                        "local_kb/maintenance_migration.py:_managed_files",
                    ),
                    metadata={
                        "miss_type": "boundary_input_missing",
                        "owner_code_contract": "local_kb.maintenance_migration.build_inventory",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-post-commit-observation-debt",
                    previous_claim_id="flowguard:kb-convergence-upgrade:green-before-concurrent-ai-search",
                    observed_failure_id="live-install:6-observations-admitted-during-long-reconciliation",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "observation admission during and after physical reconciliation had been modeled",
                    ),
                    generalized_case_id="contract:post-commit-logical-convergence",
                    new_model_obligation_id="req.history.logical-settlement",
                    new_plan_item_ids=(
                        "field:migration.logical_reconciliation_receipt",
                        "known-bad:post_commit_logical_debt_unchecked",
                    ),
                    closure_evidence_ids=(
                        "test:post-commit-observation-debt-reconciled",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/maintenance_migration.py:settle_knowledge_debt",
                        "local_kb/maintenance_migration.py:run_maintenance_migration",
                    ),
                    metadata={
                        "miss_type": "temporal_input_missing",
                        "owner_code_contract": "local_kb.maintenance_migration.run_maintenance_migration",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-foreground-full-authority-replay",
                    previous_claim_id="flowguard:kb-convergence-upgrade:green-before-real-retrieval-timing",
                    observed_failure_id="live-retrieval:active-index-generation-zero:51-second-query",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_INVARIANT_TOO_WEAK,
                    would_have_failed_if=(
                        "foreground authority-validation mode and full manifest/lifecycle replay count had been modeled",
                    ),
                    generalized_case_id="contract:foreground-query-authority",
                    new_model_obligation_id="req.retrieval.fast-authority",
                    new_plan_item_ids=(
                        "field:retrieval.authority_validation_mode",
                        "known-bad:foreground_full_replay",
                    ),
                    closure_evidence_ids=(
                        "test:fast-authority-avoids-full-replay",
                        "live-eval:retrieval-p95-below-budget",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/active_index.py:validate_active_index_fast",
                        "local_kb/active_index.py:invalidate_active_index",
                        "local_kb/lifecycle.py:commit_lifecycle_event",
                    ),
                    metadata={
                        "miss_type": "performance_and_temporal_invariant_missing",
                        "owner_code_contract": "local_kb.active_index.load_active_entries",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-candidate-source-boundary",
                    previous_claim_id="flowguard:kb-convergence-upgrade:green-before-full-regression",
                    observed_failure_id="pytest:test_machine_b_syncs_org_cache:organization-entry-not-found",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "candidate eligibility had been crossed with local versus read-only organization source",
                    ),
                    generalized_case_id="contract:candidate-source-boundary",
                    new_model_obligation_id="req.retrieval.source-boundary",
                    new_plan_item_ids=(
                        "field:retrieval.source_boundary",
                        "known-bad:candidate_source_collapse",
                    ),
                    closure_evidence_ids=(
                        "test:organization-candidate-boundary",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/search.py:search_multi_source_entries",
                    ),
                    metadata={
                        "miss_type": "state_too_coarse",
                        "owner_code_contract": "local_kb.search.search_multi_source_entries",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-organization-current-layout-consumer-radius",
                    previous_claim_id="flowguard:organization-current-layout:green-before-full-regression",
                    observed_failure_id="full-regression:organization-consumers-retained-obsolete-layout-assumptions",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "every normal organization consumer and repository checker had been registered and crossed with current, obsolete-root, and missing-main layouts",
                    ),
                    generalized_case_id="contract:organization-current-layout-consumer-radius",
                    new_model_obligation_id="req.organization.current-layout-all-consumers",
                    new_plan_item_ids=(
                        "field:organization.layout_consumer",
                        "field:organization.layout_state",
                        "known-bad:obsolete_organization_consumer",
                    ),
                    closure_evidence_ids=(
                        "test:organization-runtime-obsolete-root-blocked",
                        "test:organization-github-check-obsolete-root-blocked",
                        "test:organization-outbox-current-layout",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/store.py:_organization_scope_targets",
                        "local_kb/org_outbox.py:_organization_existing_hashes",
                        "local_kb/adoption.py:adopt_organization_entry",
                        "templates/github/org_kb_check.py:check_manifest",
                        ".flowguard/behavior_commitment_ledger/ledger.json:commitment:organization-current-layout",
                    ),
                    metadata={
                        "miss_type": "boundary_missing",
                        "owner_code_contract": "local_kb.store._organization_scope_targets",
                        "analogous_consumer_scan": "closed",
                        "old_path_disposition": "upgrade-only-migrated-or-runtime-blocked",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-installed-skillguard-repository-boundary",
                    previous_claim_id="skillguard:installed-content-parity:current-before-production-depth",
                    observed_failure_id="aggregate-readiness:installed-skill-root-outside-canonical-repository",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "installed Skill deployment authority had required a repository-local content-addressed projection of exact installed bytes, target-root run ownership, and explicit blocks for direct outside-root execution and source substitution"
                    ),
                    generalized_case_id="contract:installed-skillguard-deployment-projection",
                    new_model_obligation_id="req.skillguard.installed-current-projection",
                    new_plan_item_ids=(
                        "field:installed_skillguard.contract_authority",
                        "known-bad:installed_root_executed_outside_repository",
                        "known-bad:installed_skill_recompiled_as_repository",
                        "known-bad:source_execution_substitutes_installed_target",
                    ),
                    closure_evidence_ids=(
                        "test:installed-supervision-consumes-current-v2-pair-through-exact-byte-local-projection",
                        "test:update-stage-run-root-owned-by-target",
                        "receipt:installed-scheduled-execution-depth",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "scripts/run_installed_skillguard_supervision.py",
                        "scripts/check_kb_skillguard.py:_execute_supervision",
                        ".flowguard/behavior_commitment_ledger/ledger.json:surface:installed-skillguard-current-supervision",
                    ),
                    metadata={
                        "miss_type": "boundary_missing",
                        "owner_code_contract": "scripts.run_installed_skillguard_supervision.main",
                        "source_execution_substitution": "forbidden",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-skillguard-runtime-state-and-path-boundary",
                    previous_claim_id="skillguard:installed-runtime-currentness-replayed",
                    observed_failure_id="installed-supervision:portable-runtime-fingerprint-or-windows-path-blocked",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "installed supervision had required one short repository-local content-addressed projection of the frozen SkillGuard behavior bytes plus the exact global-router sibling, excluded .sg-runtime and interpreter caches, and compared the official projection fingerprint to the verified installed runtime identity"
                    ),
                    generalized_case_id="contract:skillguard-runtime-projection-currentness",
                    new_model_obligation_id="req.skillguard.runtime-projection-currentness",
                    new_plan_item_ids=(
                        "field:skillguard_runtime_projection.authority",
                        "known-bad:runtime_state_in_behavior_projection",
                        "known-bad:router_missing_from_runtime_fingerprint",
                        "known-bad:deep_run_root_makes_runtime_path_dependent",
                    ),
                    closure_evidence_ids=(
                        "test:skillguard-runtime-projection-excludes-receipts-and-caches",
                        "test:skillguard-runtime-projection-uses-short-repository-root",
                        "receipt:verified-installed-runtime-fingerprint-match",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "scripts/run_installed_skillguard_supervision.py:_materialize_skillguard_runtime_projection",
                        "scripts/check_current_runtime_only.py",
                    ),
                    metadata={
                        "miss_type": "execution_environment_boundary_missing",
                        "runtime_state": "forbidden-from-behavior-projection",
                        "projection_placement": "short-repository-local-content-addressed",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-supervision-display-label-authority",
                    previous_claim_id="skillguard:installed-projection-entrypoint-current",
                    observed_failure_id="aggregate-readiness:scheduled-display-label-routed-installed-root-as-source",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "supervision target-root class and display surface label had been modeled independently, with execution authority restricted to the exact canonical source root or exact active installed root"
                    ),
                    generalized_case_id="contract:skillguard-supervision-exact-root-authority",
                    new_model_obligation_id="req.skillguard.supervision-exact-root-authority",
                    new_plan_item_ids=(
                        "field:automation.supervision_target_root_class",
                        "field:automation.supervision_surface_label",
                        "known-bad:surface_label_selects_supervision_authority",
                    ),
                    closure_evidence_ids=(
                        "test:scheduled-display-label-still-selects-exact-installed-root",
                        "test:source-and-installed-authority-derived-from-exact-root",
                        "test:unknown-supervision-root-blocked",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "scripts/check_kb_skillguard.py:_supervision_target_authority",
                        "scripts/check_current_runtime_only.py",
                        ".flowguard/behavior_commitment_ledger/ledger.json:surface:installed-skillguard-current-supervision",
                    ),
                    metadata={
                        "miss_type": "authority_input_conflated_with_display_projection",
                        "owner_code_contract": "scripts.check_kb_skillguard._execute_supervision",
                        "unknown_or_ambiguous_root": "blocked",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-native-disposition-proof-boundary",
                    previous_claim_id="skillguard:target-native-phase-depth-current",
                    observed_failure_id="installed-supervision:completed-native-receipt-lost-branch-obligation-at-depth-projection",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "every target-owned obligation disposition had been modeled as either performed with exact branch-local source fields or not_applicable with exact applicability and non-mutation proof, while absent fields from an inapplicable branch were forbidden as performed-path requirements"
                    ),
                    generalized_case_id="contract:automation-native-disposition-proof",
                    new_model_obligation_id="req.skillguard.native-disposition-proof",
                    new_plan_item_ids=(
                        "field:automation.native_disposition_proofs_current",
                        "known-bad:not_applicable_without_gate_proof",
                        "known-bad:branch_projection_requires_inapplicable_fields",
                    ),
                    closure_evidence_ids=(
                        "test:organization-empty-branch-emits-proven-not-applicable",
                        "test:maintenance-empty-branch-projects-only-evaluated-readiness-fields",
                        "test:forged-not-applicable-disposition-is-rejected",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/automation_runtime.py:_not_applicable_evidence",
                        "scripts/check_kb_automation_skillguard_depth.py:_phase_obligation_projections",
                        "tests/test_kb_automation_native_receipts.py",
                    ),
                    metadata={
                        "miss_type": "branch_disposition_and_source_projection_conflated",
                        "performed": "exact-current-branch-fields-required",
                        "not_applicable": "gate-plus-non-mutation-proof-required",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-conditional-finalize-depth-cycle",
                    previous_claim_id="skillguard:update-two-stage-terminal-builder-current",
                    observed_failure_id="installed-supervision:no-op-stage-depth-required-finalize-before-terminal-applicability",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "the independent conditional finalization check had been kept outside the generic production-depth denominator, while release closure still required the obligation and allowed a no-op disposition only through the terminal-bound applicability verifier"
                    ),
                    generalized_case_id="contract:update-conditional-finalize-ownership",
                    new_model_obligation_id="req.skillguard.conditional-finalize-independent-owner",
                    new_plan_item_ids=(
                        "field:automation.depth_required_obligation_ids",
                        "known-bad:conditional_finalize_in_generic_depth_denominator",
                    ),
                    closure_evidence_ids=(
                        "test:update-finalize-check-remains-required-but-not-depth-producing",
                        "test:update-noop-stage-depth-can-build-terminal-before-close",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "scripts/build_kb_automation_skillguard_contracts.py",
                        "local_kb/automation_contracts.py:validate_compiled_automation_contract",
                        "tests/test_kb_skillguard_contract_generation.py",
                    ),
                    metadata={
                        "miss_type": "cyclic_evidence_ownership",
                        "independent_finalization_check": "required-by-closure-not-depth-producer",
                        "noop_applicability_authority": "target-native-terminal-verifier",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-target-owned-fixture-check-binding",
                    previous_claim_id="skillguard:target-owned-positive-and-shallow-fixtures-current",
                    observed_failure_id="installed-supervision:fixture-check-missing-from-declared-inventory",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "each target-owned positive and shallow fixture check had been required exactly once in the manifest, native check inventory, and provider readiness inventory"
                    ),
                    generalized_case_id="contract:target-owned-fixture-check-binding",
                    new_model_obligation_id="req.skillguard.target-owned-fixture-check-binding",
                    new_plan_item_ids=(
                        "field:depth_profile.native_check_ids",
                        "field:provider_runtime.readiness_check_ids",
                        "known-bad:fixture-check-missing-duplicated-or-misowned",
                    ),
                    closure_evidence_ids=(
                        "test:target-owned-positive-and-shallow-fixtures-executable",
                        "receipt:declared-fixture-check-inventory-validated",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "scripts/check_kb_automation_skillguard_depth.py:build_report",
                        "scripts/build_kb_automation_skillguard_contracts.py:build_contract_source",
                        "tests/test_kb_skillguard_contract_generation.py",
                    ),
                    metadata={
                        "miss_type": "declared_check_inventory_binding_missing",
                        "identity_relation": "manifest_check_id=native_check_id=readiness_check_id",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-anti-downgrade-check-id-monotonicity",
                    previous_claim_id="install:current-to-current-semantic-anti-downgrade",
                    observed_failure_id="upgrade-1784030689727-6f8b719267:depth-profile-lost-native-check-ids",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "current-to-current anti-downgrade had projected checks onto obligations, evidence classes, and mandatory owners, allowing check or conditional-owner reorganization only when semantic hard authority remained a proven superset"
                    ),
                    generalized_case_id="contract:skillguard-semantic-anti-downgrade",
                    new_model_obligation_id="req.install.semantic-native-coverage-anti-downgrade",
                    new_plan_item_ids=(
                        "field:install.anti_downgrade_comparison_basis",
                        "field:install.semantic_hard_authority_preserved",
                        "known-bad:anti_downgrade_check_id_monotonicity",
                    ),
                    closure_evidence_ids=(
                        "test:native-check-reorganization-preserved-coverage-allowed",
                        "test:native-check-reorganization-lost-coverage-blocked",
                        "model:anti-downgrade-check-id-monotonicity-invariant-fails",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/transactional_install.py:_native_check_coverage",
                        "local_kb/transactional_install.py:_current_semantic_downgrade_reasons",
                        "tests/test_transactional_install_hardening.py",
                    ),
                    metadata={
                        "miss_type": "identity_monotonicity_confused_with_semantic_coverage",
                        "allowed_change": "check-merge-or-owner-reorganization-with-obligation-evidence-owner-superset",
                        "blocked_change": "lost-obligation-evidence-class-or-independent-hard-owner",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-model-test-logical-owner-binding",
                    previous_claim_id="assurance:model-test-alignment-consumes-current-leaf-receipts",
                    observed_failure_id="aggregate-readiness:model-test-alignment-raw-owner-keyerror",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "every alignment obligation had been restricted to the declared logical validation-owner registry and unknown names had produced explicit failed evidence instead of direct dictionary indexing"
                    ),
                    generalized_case_id="contract:model-test-logical-owner-binding",
                    new_model_obligation_id="req.assurance.logical-validation-owner-binding",
                    new_plan_item_ids=(
                        "field:alignment.validation_owner_binding",
                        "known-bad:raw-receipt-owner-name",
                        "known-bad:unknown-validation-owner-name",
                    ),
                    closure_evidence_ids=(
                        "test:unknown-alignment-run-is-failed-gate-not-exception",
                        "test:alignment-consumes-declared-logical-leaf-receipts",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "scripts/check_kb_model_test_alignment.py:_missing_alignment_run",
                        "tests/test_kb_validation_evidence_reuse.py",
                    ),
                    metadata={
                        "miss_type": "validation_owner_namespace_missing",
                        "raw_receipt_names": "not-logical-owner-keys",
                        "unknown_owner_disposition": "failed-gate",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-update-state-pre-assurance-order",
                    previous_claim_id="install:update-state-migrated-after-final-transaction",
                    observed_failure_id="aggregate-readiness:update-native-owner-observed-retired-failed-state",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "update-state migration phase had been crossed with aggregate assurance entry and rollback byte identity"
                    ),
                    generalized_case_id="contract:update-state-pre-assurance-canonicalization",
                    new_model_obligation_id="req.upgrade.update-state-current-before-assurance",
                    new_plan_item_ids=(
                        "field:update_state.migration_phase",
                        "known-bad:post-assurance-update-state-migration",
                        "known-bad:migration-failure-without-byte-rollback",
                    ),
                    closure_evidence_ids=(
                        "test:update-state-current-before-aggregate-assurance",
                        "test:update-state-exact-byte-rollback",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/install.py:_committed_install_receipt_projection",
                        "local_kb/install.py:_install_codex_integration_impl",
                        ".flowguard/behavior_commitment_ledger/ledger.json:surface:update-state-pre-assurance-migration",
                    ),
                    metadata={
                        "miss_type": "transition_missing",
                        "owner_code_contract": "local_kb.install.install_codex_integration",
                        "normal_runtime_compatibility": "forbidden",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-organization-decision-id-collision",
                    previous_claim_id="organization-maintenance:merge-split-checkpoint-complete",
                    observed_failure_id="scheduled-production:duplicate-merge-decision-id",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "distinct organization decisions had been crossed with stable id uniqueness and exact proposal counts"
                    ),
                    generalized_case_id="contract:organization-decision-identity",
                    new_model_obligation_id="req.organization.decision-id-unique",
                    new_plan_item_ids=(
                        "field:organization.decision_identity",
                        "known-bad:distinct_actions_share_receipt_id",
                        "known-bad:decision_count_identity_mismatch",
                    ),
                    closure_evidence_ids=(
                        "test:organization-merge-split-id-uniqueness",
                        "receipt:organization-maintenance-native-terminal",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/org_cleanup.py:_action",
                        "local_kb/automation_runtime.py:organization-maintenance-evidence",
                        ".flowguard/behavior_commitment_ledger/ledger.json:surface:organization-decision-identity",
                    ),
                    metadata={
                        "miss_type": "identity_collision",
                        "owner_code_contract": "local_kb.org_cleanup.build_organization_cleanup_proposal",
                        "exact_count_required": "true",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-shallow-automation-skillguard-contract",
                    previous_claim_id="skillguard:generic-three-phase-contract-green",
                    observed_failure_id="user-correction:background-task-may-stop-after-first-two-steps",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_INVARIANT_TOO_WEAK,
                    would_have_failed_if=(
                        "concrete native run receipt, exact run id/hash, target obligation depth, and closure consumption had been modeled separately from regression capability",
                    ),
                    generalized_case_id="contract:automation-run-depth-closure",
                    new_model_obligation_id="req.assurance.automation-skillguard-depth",
                    new_plan_item_ids=(
                        "field:automation.native_run_receipt",
                        "field:automation.skillguard_execution_depth",
                        "field:automation.skillguard_closure_profile",
                        "field:automation.capability_junit_receipt",
                        "known-bad:shallow_automation_completion",
                    ),
                    closure_evidence_ids=(
                        "test:partial-native-run-receipt-blocked",
                        "skillguard:five-enforced-depth-receipts",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/automation_runtime.py:validate_native_receipt",
                        "scripts/run_kb_guarded_automation.py:run_guarded_automation",
                        "scripts/check_kb_skillguard.py:_execute_supervision",
                    ),
                    metadata={
                        "miss_type": "completion_evidence_too_shallow",
                        "owner_code_contract": "scripts.run_kb_guarded_automation.run_guarded_automation",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-automation-native-semantic-depth-overclaim",
                    previous_claim_id="skillguard:phase-count-and-generic-calibration-green",
                    observed_failure_id="independent-audit:seven-automation-semantic-false-greens",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_INVARIANT_TOO_WEAK,
                    would_have_failed_if=(
                        "active lanes, shared locks, real lifecycle results, per-obligation semantic receipts, five target calibrations, and no-op scope had been modeled as separate evidence",
                    ),
                    generalized_case_id="contract:automation-native-semantic-depth",
                    new_model_obligation_id="req.assurance.automation-native-semantic-depth",
                    new_plan_item_ids=(
                        "known-bad:dream_active_lane_skipped",
                        "known-bad:phase_single_source_overclaims_full_semantics",
                        "known-bad:update_noop_authorization_only",
                        "known-bad:generic_fixture_targets_substitute_exact_obligations",
                        "known-bad:sleep_shared_lock_unheld",
                        "known-bad:sleep_fixture_masks_real_lifecycle_failure",
                        "known-bad:gated_noop_overclaims_obligations",
                    ),
                    closure_evidence_ids=(
                        "model:automation-native-semantics-require-target-receipts",
                        "known-bad-replay:seven-automation-semantic-false-greens",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        ".flowguard/kb_convergence_upgrade_model.py:automation_native_semantics_require_target_receipts",
                        ".flowguard/run_kb_convergence_checks.py:_automation_known_bad_plan",
                    ),
                    metadata={
                        "behavior_plane": "development-process",
                        "miss_type": "evidence_overclaimed",
                        "primary_owner_model": "kb-automation-runtime-assurance",
                        "owner_code_contract": "local_kb.automation_runtime.evaluate_native_payload",
                        "error_signature": (
                            "count-shaped or gate-shaped evidence declared full automation completion "
                            "without target-native semantic closure"
                        ),
                        "same_class_case_ids": [
                            "dream_active_lane_skipped",
                            "phase_single_source_overclaims_full_semantics",
                            "update_noop_authorization_only",
                            "generic_fixture_targets_substitute_exact_obligations",
                            "sleep_shared_lock_unheld",
                            "sleep_fixture_masks_real_lifecycle_failure",
                            "gated_noop_overclaims_obligations",
                        ],
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-update-restored-before-final-skillguard",
                    previous_claim_id="update:native-and-aggregate-gates-green",
                    observed_failure_id="design-review:live-automations-restored-before-final-composed-closure",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_INVARIANT_TOO_WEAK,
                    would_have_failed_if=(
                        "the five-task paused source state, hash-bound staged plan, final composed closure, exact apply/readback, and CURRENT transition had been modeled as separate ordered states",
                    ),
                    generalized_case_id="contract:staged-update-restoration",
                    new_model_obligation_id="req.assurance.automation-skillguard-depth",
                    new_plan_item_ids=(
                        "field:automation.restoration_plan",
                        "field:automation.finalization_receipt",
                        "field:automation.activation_receipt",
                        "known-bad:restore_before_final_skillguard",
                    ),
                    closure_evidence_ids=(
                        "test:restoration-plan-does-not-activate-live-tasks",
                        "test:source-drift-blocks-activation",
                        "test:activation-receipt-binds-both-prior-receipts",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/install.py:plan_repo_automation_restoration",
                        "local_kb/install.py:apply_repo_automation_restoration_plan",
                        "local_kb/automation_runtime.py:build_update_activation_receipt",
                        "scripts/run_kb_guarded_automation.py:run_guarded_automation",
                    ),
                    metadata={
                        "miss_type": "premature_live_side_effect",
                        "owner_code_contract": "scripts.run_kb_guarded_automation.run_guarded_automation",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-unscoped-architect-registry",
                    previous_claim_id="install:architect-retirement-source-and-installed-clean",
                    observed_failure_id="live-install:unrelated-stale-flowguard-registry-false-blocker",
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "active Codex registry scope had been crossed with unrelated external registry state",
                    ),
                    generalized_case_id="contract:architect-active-registry-scope",
                    new_model_obligation_id="req.upgrade.architect-active-registry-scope",
                    new_plan_item_ids=(
                        "field:retirement.active_registry_path",
                        "field:retirement.registry_scope",
                        "known-bad:unrelated_registry_false_blocker",
                    ),
                    closure_evidence_ids=(
                        "test:active-registry-clean-external-stale",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/codex_registry.py:discover_active_registry",
                        "scripts/check_retired_kb_architect.py:build_report",
                    ),
                    metadata={
                        "miss_type": "scope_boundary_missing",
                        "owner_code_contract": "local_kb.codex_registry.discover_active_registry",
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-router-refresh-receipt-and-live-freshness",
                    previous_claim_id="flowguard:kb-convergence-upgrade:green-before-live-install",
                    observed_failure_id=(
                        "live-install:2026-07-12:refresh-receipt-lost-then-skillguard-surface-drifted"
                    ),
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
                    would_have_failed_if=(
                        "final refresh receipt durability, active SkillGuard surface fingerprint, live registry freshness, and live prompt freshness had been modeled as separate post-transaction gates",
                    ),
                    generalized_case_id=(
                        "contract:router-refresh-durability-and-freshness"
                    ),
                    new_model_obligation_id="req.upgrade.transactional",
                    new_plan_item_ids=(
                        "field:install.router_refresh_receipt",
                        "field:install.skillguard_router_surface_fingerprint",
                        "field:install.router_registry_freshness",
                        "field:install.router_prompt_freshness",
                        "known-bad:router_refresh_receipt_missing",
                        "known-bad:router_surface_drift_after_refresh",
                        "known-bad:router_prompt_matches_old_registry",
                    ),
                    closure_evidence_ids=(
                        "model:durable_current_router_refresh",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/install.py:_record_upgrade_attempt",
                        "local_kb/install.py:_refresh_and_verify_skillguard_global_router",
                        ".flowguard/kb_convergence_upgrade_model.py:UpgradeMigrationBlock",
                    ),
                    metadata={
                        "behavior_plane": "development-process",
                        "miss_type": "boundary_missing",
                        "primary_owner_model": "kb-upgrade-migration",
                        "owner_code_contract": (
                            "local_kb.install._refresh_and_verify_skillguard_global_router"
                        ),
                        "error_signature": (
                            "refresh receipt existed only in memory; later SkillGuard tree replacement "
                            "left the saved registry stale while the prompt still matched that old registry"
                        ),
                        "same_class_case_ids": [
                            "router_refresh_receipt_missing",
                            "router_surface_drift_after_refresh",
                            "router_prompt_matches_old_registry",
                        ],
                    },
                ),
                flowguard.FalseNegativeCase(
                    "miss-post-commit-assurance-failure-ignored",
                    previous_claim_id="flowguard:kb-convergence-upgrade:commit-treated-as-terminal",
                    observed_failure_id=(
                        "live-install:2026-07-12:aggregate-assurance-failed-after-install-commit"
                    ),
                    cause=flowguard.FALSE_NEGATIVE_CAUSE_INVARIANT_TOO_WEAK,
                    would_have_failed_if=(
                        "committed-but-not-assured, paused-failed, and resumed-for-assurance states had been distinct and failure input remained legal after commit",
                    ),
                    generalized_case_id=(
                        "contract:post-commit-assurance-failure-retry"
                    ),
                    new_model_obligation_id="req.assurance.final-gate",
                    new_plan_item_ids=(
                        "field:install.post_commit_assurance_failure",
                        "known-bad:post_commit_assurance_failure_ignored",
                    ),
                    closure_evidence_ids=(
                        "model:post_commit_assurance_failure_is_retryable",
                        "contract_coverage:kb-convergence-upgrade",
                    ),
                    repair_evidence_ids=(
                        "local_kb/install.py:_record_upgrade_attempt",
                        ".flowguard/kb_convergence_upgrade_model.py:UpgradeMigrationBlock",
                    ),
                    metadata={
                        "behavior_plane": "development-process",
                        "miss_type": "state_too_coarse",
                        "primary_owner_model": "kb-upgrade-migration",
                        "owner_code_contract": "local_kb.install.install_codex_integration",
                        "error_signature": (
                            "aggregate assurance failed after the install transaction committed, "
                            "but the old model ignored failure in committed phase"
                        ),
                        "same_class_case_ids": [
                            "post_commit_assurance_failure_ignored",
                            "post_commit_assurance_failure_paused_retry",
                        ],
                    },
                ),
            ),
        )
    )


def build_report() -> dict[str, Any]:
    field_report = field_lifecycle_report()
    contract_report = contract_exhaustion_report()
    model_miss_report = model_miss_backpropagation_report()
    maturation_report = flowguard.review_model_maturation_loop(
        flowguard.ModelMaturationPlan(
            plan_id="chaos-brain-model-miss-maturation-v1",
            model_id="kb-convergence-upgrade",
            require_full_closure=True,
            allow_scoped_claim=False,
        )
    )
    watched = (
        REPO_ROOT / ".flowguard" / "kb_convergence_upgrade_model.py",
        Path(__file__).resolve(),
        REPO_ROOT
        / "openspec"
        / "changes"
        / "converge-kb-learning-and-upgrade-migration"
        / "verification-contract.yaml",
        REPO_ROOT / "local_kb" / "lifecycle.py",
        REPO_ROOT / "local_kb" / "maintenance_migration.py",
        REPO_ROOT / "local_kb" / "active_index.py",
        REPO_ROOT / "local_kb" / "org_migration.py",
        REPO_ROOT / "local_kb" / "org_sources.py",
        REPO_ROOT / "local_kb" / "settings.py",
        REPO_ROOT / "local_kb" / "settings_migration.py",
        REPO_ROOT / "local_kb" / "card_schema_migration.py",
        REPO_ROOT / "local_kb" / "transactional_install.py",
        REPO_ROOT / "local_kb" / "install.py",
        REPO_ROOT / "local_kb" / "automation_contracts.py",
        REPO_ROOT / "local_kb" / "automation_runtime.py",
        REPO_ROOT / "local_kb" / "codex_registry.py",
        REPO_ROOT / "local_kb" / "dream.py",
        REPO_ROOT / "local_kb" / "org_automation.py",
        REPO_ROOT / "local_kb" / "org_outbox.py",
        REPO_ROOT / "local_kb" / "org_maintenance.py",
        REPO_ROOT / "local_kb" / "search.py",
        REPO_ROOT / "local_kb" / "software_update.py",
        REPO_ROOT / ".flowguard" / "kb_skill_contract_model_common.py",
        REPO_ROOT / ".flowguard" / "kb_sleep_skill_contract_model.py",
        REPO_ROOT / ".flowguard" / "kb_dream_skill_contract_model.py",
        REPO_ROOT / ".flowguard" / "kb_org_contribute_skill_contract_model.py",
        REPO_ROOT / ".flowguard" / "kb_org_maintenance_skill_contract_model.py",
        REPO_ROOT / ".flowguard" / "khaos_brain_update_skill_contract_model.py",
        REPO_ROOT / "scripts" / "install_codex_kb.py",
        REPO_ROOT / "scripts" / "check_kb_automation_run_receipt.py",
        REPO_ROOT / "scripts" / "check_kb_skillguard.py",
        REPO_ROOT / "scripts" / "run_kb_guarded_automation.py",
        REPO_ROOT / "scripts" / "check_retired_kb_architect.py",
        REPO_ROOT / "scripts" / "check_current_runtime_only.py",
        REPO_ROOT / "scripts" / "check_chaos_brain_readiness.py",
        REPO_ROOT / "scripts" / "open_khaos_brain_ui.py",
        REPO_ROOT / "scripts" / "install_desktop_shortcut.py",
        REPO_ROOT / "scripts" / "kb_org_outbox.py",
        REPO_ROOT / "scripts" / "kb_org_maintainer.py",
        REPO_ROOT / "scripts" / "run_khaos_brain_system_update.py",
        REPO_ROOT / ".agents" / "skills" / "local-kb-retrieve" / "scripts" / "kb_sleep.py",
        REPO_ROOT / ".agents" / "skills" / "local-kb-retrieve" / "scripts" / "kb_dream.py",
        REPO_ROOT / "tests" / "test_kb_automation_activation.py",
        REPO_ROOT / "tests" / "test_kb_automation_skillguard.py",
        REPO_ROOT / "tests" / "test_kb_dream.py",
        REPO_ROOT / "tests" / "test_kb_sleep_convergence.py",
        REPO_ROOT / "tests" / "test_org_automation.py",
        REPO_ROOT / "tests" / "test_org_outbox.py",
        REPO_ROOT / "tests" / "test_org_maintenance.py",
        REPO_ROOT / "tests" / "test_software_update.py",
        REPO_ROOT / "tests" / "test_current_runtime_only.py",
        REPO_ROOT / "tests" / "test_desktop_launcher_current_runtime.py",
        REPO_ROOT / "tests" / "test_org_sources.py",
        REPO_ROOT / "tests" / "test_desktop_settings.py",
        REPO_ROOT / "tests" / "test_card_schema_migration.py",
    )
    verifier_fingerprint = _flowguard_verifier_fingerprint()
    watched_fingerprints = {
        str(path.relative_to(REPO_ROOT)).replace("\\", "/"): _sha256(path)
        for path in watched
    }
    input_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "watched": watched_fingerprints,
                "verifier": verifier_fingerprint,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    ok = (
        field_report.ok
        and contract_report.ok
        and model_miss_report.ok
        and maturation_report.ok
    )
    return {
        "schema_version": 1,
        "suite": "chaos-brain-flowguard-assurance",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "flowguard_schema_version": flowguard.SCHEMA_VERSION,
        "verifier_fingerprint": verifier_fingerprint,
        "input_fingerprint": input_fingerprint,
        "receipt_id": f"flowguard-suite:{input_fingerprint}",
        "ok": ok,
        "field_lifecycle": field_report.to_dict(),
        "contract_exhaustion": contract_report.to_dict(),
        "model_miss_backpropagation": model_miss_report.to_dict(),
        "model_maturation": maturation_report.to_dict(),
        "coverage": {
            "field_rows": len(field_report.projections),
            "field_projections": len(field_report.projections),
            "generated_bad_cases": len(contract_report.generated_cases),
            "combination_cases": len(contract_report.combination_cases),
            "coverage_receipts": list(
                flowguard.contract_exhaustion_to_coverage_receipt_ids(contract_report)
            ),
        },
        "watched_fingerprints": watched_fingerprints,
        "claim_boundary": (
            "Current executable field and finite-contract evidence; production test "
            "alignment, observed/same-class regression evidence, and filesystem "
            "migration receipts are separate hard gates."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write-receipt", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if not args.no_write_receipt:
        RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT_PATH.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("FlowGuard suite:", "PASS" if report["ok"] else "FAIL")
        print("Field lifecycle:", report["field_lifecycle"]["decision"])
        print("Contract exhaustion:", report["contract_exhaustion"]["decision"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
