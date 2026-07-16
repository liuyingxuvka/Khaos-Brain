"""Frozen Model-Test Alignment plan for LogicGuard-native Khaos Brain.

This is a planning artifact, not passing test evidence.  It proves that every
OpenSpec obligation has exactly one planned external code owner and one named
test-evidence slot.  All evidence is intentionally ``not_run`` until the
implementation exists and the frozen final execution owner runs it.
"""

from __future__ import annotations

import json
from dataclasses import replace

from flowguard.model_test_alignment import (
    CodeContract,
    ModelObligation,
    ModelTestAlignmentPlan,
    TestEvidence,
    review_model_test_alignment,
)


MODEL_ID = "khaos_brain_logicguard_authority_cutover"

# obligation id, code-contract id, path, symbol, primary test path
BINDINGS = (
    ("req.authority.exact-projection", "contract.projection.validate-exact-binding", "local_kb/model_projection.py", "validate_card_projection", "tests/test_khaos_model_projection.py"),
    ("req.authority.argument-block", "contract.models.build-argument-block", "local_kb/logicguard_models.py", "build_predictive_argument_model", "tests/test_khaos_logicguard_models.py"),
    ("req.authority.projection-only", "contract.projection.project-card", "local_kb/model_projection.py", "project_card", "tests/test_khaos_model_projection.py"),
    ("req.authority.atomic-publication", "contract.lifecycle.publish-complete-generation", "local_kb/lifecycle.py", "run_incremental_sleep", "tests/test_khaos_sleep_model_maintenance.py"),
    ("req.authority.privacy", "contract.models.validate-scope", "local_kb/logicguard_models.py", "normalize_authority_scope", "tests/test_khaos_logicguard_models.py"),
    ("req.maintenance.sleep-owner", "contract.lifecycle.sleep-owner", "local_kb/lifecycle.py", "run_incremental_sleep", "tests/test_khaos_sleep_model_maintenance.py"),
    ("req.maintenance.mesh-consolidation", "contract.maintenance.publish-model-generation", "local_kb/model_maintenance.py", "publish_sleep_model_generation", "tests/test_khaos_sleep_model_maintenance.py"),
    ("req.maintenance.gap-review", "contract.maintenance.summarize-model-gaps", "local_kb/model_maintenance.py", "_gap_summary", "tests/test_khaos_sleep_model_maintenance.py"),
    ("req.maintenance.dream-read-only", "contract.dream.run-read-only", "local_kb/dream.py", "run_dream_maintenance", "tests/test_kb_dream.py"),
    ("req.maintenance.dream-convergence", "contract.dream.fingerprint-experiment", "local_kb/dream.py", "_evidence_fingerprint", "tests/test_kb_dream.py"),
    ("req.retrieval.current-index", "contract.search.current-index-only", "local_kb/search.py", "search_with_receipt", "tests/test_khaos_model_native_retrieval.py"),
    ("req.retrieval.neighborhood", "contract.models.materialize-neighborhood", "local_kb/logicguard_models.py", "materialize_bound_neighborhood", "tests/test_khaos_model_native_retrieval.py"),
    ("req.retrieval.ranking", "contract.search.rank-entry-then-grounded-neighborhood", "local_kb/search.py", "search_model_bound_entries", "tests/test_khaos_model_native_retrieval.py"),
    ("req.retrieval.desktop", "contract.desktop.render-exact-model-detail", "local_kb/ui_data.py", "build_card_detail_payload", "tests/test_kb_desktop_ui.py"),
    ("req.retrieval.performance", "contract.readiness.measure-model-retrieval", "scripts/check_khaos_logicguard_runtime.py", "build_report", "tests/test_khaos_model_runtime_readiness.py"),
    ("req.migration.only-legacy-reader", "contract.migration.consume-legacy-direct", "local_kb/maintenance_migration.py", "plan_logicguard_native_migration", "tests/test_khaos_logicguard_migration.py"),
    ("req.migration.complete-conservative", "contract.migration.map-every-card", "local_kb/maintenance_migration.py", "migrate_legacy_card_generation", "tests/test_khaos_logicguard_migration.py"),
    ("req.migration.transactional", "contract.migration.cutover-or-rollback", "local_kb/maintenance_migration.py", "commit_logicguard_native_generation", "tests/test_khaos_logicguard_migration.py"),
    ("req.migration.install", "contract.installer.require-model-authority", "scripts/install_codex_kb.py", "main", "tests/test_codex_install.py"),
    ("req.assurance.flowguard", "contract.flowguard.authority-cutover-model", ".flowguard/khaos_brain_logicguard_authority_cutover.py", "main", "tests/test_khaos_logicguard_assurance.py"),
    ("req.assurance.alignment", "contract.flowguard.model-test-alignment", ".flowguard/khaos_brain_logicguard_model_test_alignment.py", "main", "tests/test_khaos_logicguard_assurance.py"),
    ("req.assurance.execution-owner", "contract.readiness.single-final-owner", "scripts/check_khaos_logicguard_native_readiness.py", "main", "tests/test_khaos_logicguard_readiness.py"),
    ("req.assurance.surface-parity", "contract.readiness.surface-parity", "scripts/check_kb_skillguard.py", "main", "tests/test_kb_automation_skillguard.py"),
    ("req.assurance.release-gates", "contract.readiness.release-gates", "scripts/check_khaos_logicguard_native_readiness.py", "build_report", "tests/test_khaos_logicguard_readiness.py"),
)

KNOWN_BAD_TARGET_IDS = (
    "bad.standalone-yaml-authority",
    "bad.projection-before-model",
    "bad.index-before-projection",
    "bad.partial-migration-current",
    "bad.unowned-model-writer",
    "bad.duplicate-sleep-owner",
    "bad.duplicate-search-owner",
    "bad.dream-canonical-mutation",
    "bad.dream-handoff-without-simulation",
    "bad.flat-yaml-fallback",
    "bad.floating-head-substitution",
    "bad.projection-digest-mismatch",
    "bad.private-cross-scope-edge",
    "bad.retrieval-without-neighborhood",
)

EXPECTED_PLANNING_GAP_CODES = {
    "test_evidence_not_passing",
    "missing_test_evidence",
    "missing_code_contract_test_evidence",
    "missing_required_test_kind",
}


def _description(obligation_id: str) -> str:
    return "Frozen implementation and verification obligation imported from the LogicGuard-native Khaos Brain OpenSpec contract: " + obligation_id


def build_plan() -> ModelTestAlignmentPlan:
    obligations = tuple(
        ModelObligation(
            obligation_id=obligation_id,
            obligation_type="external_contract",
            description=_description(obligation_id),
            required=True,
            required_test_kinds=("happy_path",),
            risk_level="high",
            allow_shared_evidence=False,
            allow_shared_implementation=False,
            exact_external_contract=True,
        )
        for obligation_id, _contract_id, _path, _symbol, _test_path in BINDINGS
    )
    contracts = tuple(
        CodeContract(
            code_contract_id=contract_id,
            path=path,
            symbol=symbol,
            surface_type="function",
            role="owner",
            implements_obligations=(obligation_id,),
            required=True,
        )
        for obligation_id, contract_id, path, symbol, _test_path in BINDINGS
    )
    evidence = tuple(
        TestEvidence(
            evidence_id=f"evidence.planned.{obligation_id}",
            test_name=f"planned::{obligation_id}",
            path=test_path,
            command=f"python -m pytest -q {test_path}",
            result_status="not_run",
            evidence_current=True,
            test_kind="happy_path",
            covered_obligations=(obligation_id,),
            covered_code_contracts=(contract_id,),
            assertion_scope="external_contract",
            evidence_role="primary",
        )
        for obligation_id, contract_id, _path, _symbol, test_path in BINDINGS
    )
    return ModelTestAlignmentPlan(
        model_id=MODEL_ID,
        obligations=obligations,
        code_contracts=contracts,
        test_evidence=evidence,
        require_proof_artifacts=False,
        require_runtime_path_evidence=False,
        require_source_audit=False,
        allow_orphan_tests=False,
        allow_orphan_code_contracts=False,
    )


def build_known_bad_plan() -> ModelTestAlignmentPlan:
    current = build_plan()
    duplicate = CodeContract(
        code_contract_id="contract.parallel-controller.duplicate-sleep-owner",
        path="local_kb/logicguard_controller.py",
        symbol="commit_sleep_model_change",
        surface_type="function",
        role="owner",
        implements_obligations=("req.maintenance.sleep-owner",),
        required=True,
    )
    return replace(current, code_contracts=(*current.code_contracts, duplicate))


def main() -> int:
    current = review_model_test_alignment(build_plan())
    known_bad = review_model_test_alignment(build_known_bad_plan())
    current_codes = {finding.code for finding in current.findings}
    known_bad_codes = {finding.code for finding in known_bad.findings}
    rows_have_one_owner = all(
        len(row.owner_code_contract_ids) == 1 and row.status == "blocked"
        for row in current.binding_rows
    )
    payload = {
        "artifact_type": "khaos_brain_logicguard_native_model_test_alignment_plan",
        "current": current.to_dict(),
        "known_bad": known_bad.to_dict(),
        "obligation_count": len(build_plan().obligations),
        "code_contract_count": len(build_plan().code_contracts),
        "planned_test_evidence_count": len(build_plan().test_evidence),
        "known_bad_target_ids": list(KNOWN_BAD_TARGET_IDS),
        "planning_state": "frozen_not_run",
        "ok": (
            len(current.binding_rows) == len(BINDINGS)
            and rows_have_one_owner
            and current_codes
            and current_codes.issubset(EXPECTED_PLANNING_GAP_CODES)
            and "duplicate_code_contract_owner" in known_bad_codes
        ),
        "claim_boundary": (
            "This artifact freezes one planned code owner and one not-run evidence slot for every required OpenSpec "
            "obligation and rejects a duplicate Sleep code owner. Its blocked alignment status is intentional: no "
            "implementation or test is treated as passing until current external-contract evidence is produced."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
