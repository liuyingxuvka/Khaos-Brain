"""Frozen TestMesh inventory for LogicGuard-native Khaos Brain.

The child suites are intentionally not executed here.  This artifact freezes
their disjoint obligation ownership, ordering, timeouts, freshness boundary,
persistent receipt root, and the sole final aggregate command before any
production implementation begins.
"""

from __future__ import annotations

import json
from dataclasses import replace

from flowguard.testmesh import (
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    review_test_mesh,
)

from khaos_brain_logicguard_model_test_alignment import BINDINGS


PARENT_SUITE_ID = "suite:khaos-logicguard-native:parent"
INVENTORY_REVISION = "khaos-logicguard-native-inventory-v4-resumable-sleep-pointer-safety"
RECEIPT_ROOT = ".local/verification/khaos-logicguard-native"
FINAL_COMMAND = "python scripts/check_khaos_logicguard_native_readiness.py --json"
RESUMABLE_SLEEP_OBLIGATION_IDS = (
    "req.maintenance.resumable-batch",
    "req.maintenance.item-checkpoint",
    "req.maintenance.remainder-movement",
    "req.maintenance.writer-recovery",
    "req.retrieval.immutable-pointer",
    "req.retrieval.exact-entry-deny",
    "req.retrieval.exact-current-corruption",
    "req.retrieval.retire-global-invalidation",
)

SUITE_SPECS = (
    (
        "suite:flowguard-assurance",
        "python .flowguard/khaos_brain_logicguard_authority_cutover.py && python .flowguard/khaos_brain_logicguard_field_lifecycle.py && python .flowguard/kb_sleep_resumable_field_lifecycle.py && python .flowguard/khaos_brain_logicguard_model_mesh.py && python .flowguard/khaos_brain_logicguard_code_structure.py && python .flowguard/khaos_brain_logicguard_model_test_alignment.py && python .flowguard/kb_sleep_resumable_model_test_alignment.py",
        ("req.assurance.flowguard", "req.assurance.alignment"),
        300,
        ("flowguard_alignment_state",),
        ("flowguard_child_receipt",),
    ),
    (
        "suite:model-authority-projection",
        "python -m pytest -q tests/test_khaos_logicguard_models.py tests/test_khaos_model_projection.py",
        (
            "req.authority.exact-projection",
            "req.authority.argument-block",
            "req.authority.projection-only",
            "req.authority.atomic-publication",
            "req.authority.privacy",
        ),
        900,
        ("model_projection_test_state",),
        ("model_projection_test_receipt",),
    ),
    (
        "suite:sleep-dream",
        "python -m pytest -q tests/test_sleep_batch.py tests/test_khaos_sleep_model_maintenance.py tests/test_kb_sleep_convergence.py tests/test_kb_lifecycle.py tests/test_kb_dream.py",
        (
            "req.maintenance.sleep-owner",
            "req.maintenance.lifecycle-batch",
            "req.maintenance.resumable-batch",
            "req.maintenance.item-checkpoint",
            "req.maintenance.remainder-movement",
            "req.maintenance.writer-recovery",
            "req.maintenance.mesh-consolidation",
            "req.maintenance.gap-review",
            "req.maintenance.dream-read-only",
            "req.maintenance.dream-convergence",
        ),
        1200,
        ("sleep_dream_test_state",),
        ("sleep_dream_test_receipt",),
    ),
    (
        "suite:retrieval-ui-performance",
        "python -m pytest -q tests/test_kb_active_index_generation.py tests/test_khaos_model_native_retrieval.py tests/test_kb_retrieval_calibration.py tests/test_kb_desktop_ui.py tests/test_khaos_model_runtime_readiness.py",
        (
            "req.retrieval.current-index",
            "req.retrieval.publisher-authority",
            "req.retrieval.immutable-pointer",
            "req.retrieval.exact-entry-deny",
            "req.retrieval.exact-current-corruption",
            "req.retrieval.retire-global-invalidation",
            "req.retrieval.neighborhood",
            "req.retrieval.ranking",
            "req.retrieval.desktop",
            "req.retrieval.performance",
        ),
        1200,
        ("retrieval_ui_performance_test_state",),
        ("retrieval_ui_performance_test_receipt",),
    ),
    (
        "suite:migration-installer",
        "python -m pytest -q tests/test_khaos_logicguard_migration.py tests/test_kb_history_migration.py tests/test_codex_install.py",
        (
            "req.migration.only-legacy-reader",
            "req.migration.complete-conservative",
            "req.migration.transactional",
            "req.migration.install",
        ),
        1800,
        ("migration_installer_test_state",),
        ("migration_installer_test_receipt",),
    ),
    (
        "suite:surface-skillguard",
        "python -m pytest -q tests/test_kb_automation_skillguard.py tests/test_kb_automation_native_receipts.py tests/test_codex_install.py",
        ("req.assurance.surface-parity",),
        1200,
        ("surface_skillguard_test_state",),
        ("surface_skillguard_test_receipt",),
    ),
    (
        "suite:existing-khaos-regressions",
        "python -m pytest -q tests --junitxml=work/verification/khaos-full-regression.xml",
        ("inventory.existing-khaos-regressions",),
        3600,
        ("existing_regression_test_state",),
        ("existing_regression_test_receipt",),
    ),
    (
        "suite:release-gate-contract",
        "openspec validate make-khaos-brain-logicguard-native --type change --strict --json --no-interactive",
        ("req.assurance.release-gates",),
        300,
        ("release_gate_contract_state",),
        ("release_gate_contract_receipt",),
    ),
    (
        "suite:final-aggregate-owner",
        FINAL_COMMAND,
        ("req.assurance.execution-owner", "inventory.final-aggregate-receipt"),
        7200,
        ("final_aggregate_execution_state",),
        ("final_aggregate_execution", "final_parent_receipt"),
    ),
)

DEPENDENCIES = {
    "suite:flowguard-assurance": (),
    "suite:model-authority-projection": ("suite:flowguard-assurance",),
    "suite:sleep-dream": ("suite:model-authority-projection",),
    "suite:retrieval-ui-performance": ("suite:model-authority-projection",),
    "suite:migration-installer": ("suite:model-authority-projection", "suite:sleep-dream", "suite:retrieval-ui-performance"),
    "suite:surface-skillguard": ("suite:model-authority-projection", "suite:sleep-dream", "suite:retrieval-ui-performance", "suite:migration-installer"),
    "suite:existing-khaos-regressions": ("suite:model-authority-projection", "suite:sleep-dream", "suite:retrieval-ui-performance", "suite:migration-installer"),
    "suite:release-gate-contract": (),
    "suite:final-aggregate-owner": (
        "suite:flowguard-assurance",
        "suite:model-authority-projection",
        "suite:sleep-dream",
        "suite:retrieval-ui-performance",
        "suite:migration-installer",
        "suite:surface-skillguard",
        "suite:existing-khaos-regressions",
        "suite:release-gate-contract",
    ),
}

FRESHNESS_SELECTORS = (
    "local_kb/**/*.py",
    "scripts/**/*.py",
    "tests/**/*.py",
    ".flowguard/**/*.py",
    ".flowguard/project.toml",
    ".agents/skills/**/SKILL.md",
    ".agents/skills/**/.skillguard/**/*.json",
    ".agents/skills/**/.skillguard/**/*.py",
    "templates/**/*.md",
    "templates/**/*.json",
    "openspec/changes/make-khaos-brain-logicguard-native/**",
    "openspec/changes/repair-sleep-active-index-recovery/**",
    "PROJECT_SPEC.md",
    "README.md",
    "AGENTS.md",
    "docs/**/*.md",
)

STRUCTURAL_BLOCKER_CODES = {
    "coverage_gap",
    "duplicate_partition_owner",
    "test_inventory_revision_missing",
    "test_inventory_required_items_missing",
    "test_inventory_revision_mismatch",
    "required_inventory_item_missing",
    "unexpected_test_inventory_item",
    "missing_target_split_derivation",
    "invalid_target_split_derivation",
    "missing_target_suites",
    "unknown_target_suite",
    "incomplete_target_suites",
    "incomplete_target_split_coverage",
    "missing_target_state_owner_map",
    "missing_target_side_effect_owner_map",
    "missing_target_split_rationale",
    "duplicate_state_owner",
    "duplicate_side_effect_owner",
}


def required_inventory_ids() -> tuple[str, ...]:
    return tuple(obligation_id for obligation_id, *_rest in BINDINGS) + RESUMABLE_SLEEP_OBLIGATION_IDS + (
        "inventory.existing-khaos-regressions",
        "inventory.final-aggregate-receipt",
    )


def owner_by_item() -> dict[str, str]:
    owners: dict[str, str] = {}
    for suite_id, _command, item_ids, _timeout, _state, _effects in SUITE_SPECS:
        for item_id in item_ids:
            if item_id in owners:
                raise ValueError(f"duplicate inventory owner for {item_id}: {owners[item_id]} and {suite_id}")
            owners[item_id] = suite_id
    return owners


def build_plan() -> TestMeshPlan:
    owners = owner_by_item()
    inventory = required_inventory_ids()
    partitions = tuple(
        TestPartitionItem(
            item_id=item_id,
            item_type="verification_obligation",
            owner_suite_id=owners[item_id],
            ownership="child",
            description="Frozen current verification inventory item.",
            inventory_revision=INVENTORY_REVISION,
        )
        for item_id in inventory
    )
    suites = tuple(
        TestSuiteEvidence(
            suite_id=suite_id,
            command=command,
            layer="child",
            result_status="not_run",
            evidence_tier="candidate_only",
            evidence_current=True,
            test_count=0,
            selected_count=0,
            skipped_count=0,
            planned_count=1,
            executed_count=0,
            failed_count=0,
            not_run_count=1,
            diagnostic_boundary="Frozen planning inventory; final evidence is owned only by the declared aggregate command.",
            diagnostic_campaign_id=f"campaign:{INVENTORY_REVISION}:{suite_id}",
            skipped_visible=True,
            timeout_seconds=float(timeout),
            result_path=f"{RECEIPT_ROOT}/{suite_id.replace(':', '_')}.json",
            log_root=f"{RECEIPT_ROOT}/logs/{suite_id.replace(':', '_')}",
            background=False,
            has_exit_artifact=False,
            has_result_artifact=False,
            progress_only=False,
            release_required=True,
            owns_state=state,
            owns_side_effects=effects,
            not_run_reason="Implementation phase has not produced a frozen execution snapshot.",
            inventory_revision=INVENTORY_REVISION,
            owned_inventory_item_ids=item_ids,
            covered_obligation_ids=item_ids,
            terminal_status="not_run",
        )
        for suite_id, command, item_ids, timeout, state, effects in SUITE_SPECS
    )
    return TestMeshPlan(
        parent_suite_id=PARENT_SUITE_ID,
        partition_items=partitions,
        child_suites=suites,
        target_split_derivation=TestTargetSplitDerivation(
            source_model_id="khaos_brain_logicguard_model_mesh",
            source_model_path=".flowguard/khaos_brain_logicguard_model_mesh.py",
            target_suite_ids=tuple(suite.suite_id for suite in suites),
            covered_partition_item_ids=inventory,
            state_owner_fields=tuple(value for suite in suites for value in suite.owns_state),
            side_effect_owner_fields=tuple(value for suite in suites for value in suite.owns_side_effects),
            rationale=(
                "The child suites follow the FlowGuard ownership split: authority/projection, Sleep/Dream, "
            "resumable Sleep/checkpoint/remainder behavior, pointer/deny/corruption retrieval safety, migration/install, "
            "surfaces/SkillGuard, regressions, contract, and one final owner."
            ),
            derived_from_flowguard_model=True,
        ),
        required_evidence_tier="candidate_only",
        require_proof_artifacts=False,
        decision_scope="release",
        release_deferred_allowed=False,
        inventory_revision=INVENTORY_REVISION,
        required_inventory_item_ids=inventory,
        require_complete_inventory=True,
        require_final_receipts=True,
    )


def build_known_bad_plan() -> TestMeshPlan:
    current = build_plan()
    duplicate_final = TestSuiteEvidence(
        suite_id="suite:parallel-final-aggregate-owner",
        command=FINAL_COMMAND,
        result_status="not_run",
        evidence_tier="candidate_only",
        timeout_seconds=7200,
        owns_state=("parallel_final_state",),
        owns_side_effects=("final_aggregate_execution",),
        not_run_reason="Known bad: a second owner attempts to run the same final aggregate.",
        inventory_revision=INVENTORY_REVISION,
    )
    derivation = replace(
        current.target_split_derivation,
        target_suite_ids=(*current.target_split_derivation.target_suite_ids, duplicate_final.suite_id),
        state_owner_fields=(*current.target_split_derivation.state_owner_fields, "parallel_final_state"),
    )
    return replace(current, child_suites=(*current.child_suites, duplicate_final), target_split_derivation=derivation)


def dependency_graph_is_closed() -> bool:
    suite_ids = {suite_id for suite_id, *_rest in SUITE_SPECS}
    if set(DEPENDENCIES) != suite_ids:
        return False
    if any(dependency not in suite_ids for values in DEPENDENCIES.values() for dependency in values):
        return False
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return False
        if node in visited:
            return True
        visiting.add(node)
        if not all(visit(dependency) for dependency in DEPENDENCIES[node]):
            return False
        visiting.remove(node)
        visited.add(node)
        return True

    return all(visit(node) for node in sorted(suite_ids))


def main() -> int:
    current_plan = build_plan()
    current = review_test_mesh(current_plan)
    known_bad = review_test_mesh(build_known_bad_plan())
    current_codes = {finding.code for finding in current.findings}
    known_bad_codes = {finding.code for finding in known_bad.findings}
    final_owners = tuple(suite for suite in current_plan.child_suites if suite.command == FINAL_COMMAND)
    payload = {
        "artifact_type": "khaos_brain_logicguard_native_frozen_test_mesh",
        "planning_state": "frozen_not_run",
        "inventory_revision": INVENTORY_REVISION,
        "receipt_root": RECEIPT_ROOT,
        "freshness_selectors": list(FRESHNESS_SELECTORS),
        "dependencies": {key: list(value) for key, value in DEPENDENCIES.items()},
        "current": current.to_dict(),
        "known_bad": known_bad.to_dict(),
        "final_execution_owner": final_owners[0].suite_id if len(final_owners) == 1 else "",
        "final_command": FINAL_COMMAND,
        "ok": (
            len(current_plan.required_inventory_item_ids) == len(owner_by_item())
            and not (current_codes & STRUCTURAL_BLOCKER_CODES)
            and len(final_owners) == 1
            and dependency_graph_is_closed()
            and "duplicate_side_effect_owner" in known_bad_codes
        ),
        "claim_boundary": (
            "This artifact freezes a complete disjoint inventory, DAG, timeouts, freshness selectors, receipt root, "
            "and exactly one final aggregate command. Its release decision remains blocked because every suite is "
            "explicitly not run; no planned receipt is represented as current terminal evidence."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
