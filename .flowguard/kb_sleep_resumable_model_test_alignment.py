"""Model-Test Alignment for resumable Sleep and scoped active-index safety."""

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


MODEL_ID = "kb_convergence_upgrade_model.LifecycleConvergenceBlock"
BUSINESS_INTENT_ID = "intent:converge-sleep-without-duplicate-work"
COMMITMENT_ID = "commitment:sleep-no-delta-single-owner"
FIELD_LIFECYCLE_SOURCE = ".flowguard/kb_sleep_resumable_field_lifecycle.py"

# obligation, contract, path, symbol, test path, required test kinds
BINDINGS = (
    (
        "req.maintenance.resumable-batch",
        "contract.sleep-batch.freeze-or-resume",
        "local_kb/sleep_batch.py",
        "start_or_resume_sleep_batch",
        "tests/test_sleep_batch.py",
        ("happy_path", "failure_path", "negative_path", "replay"),
    ),
    (
        "req.maintenance.item-checkpoint",
        "contract.sleep-batch.record-item-result",
        "local_kb/sleep_batch.py",
        "record_sleep_batch_item_result",
        "tests/test_sleep_batch.py",
        ("happy_path", "failure_path", "negative_path", "replay"),
    ),
    (
        "req.maintenance.remainder-movement",
        "contract.sleep-batch.compare-remainder",
        "local_kb/sleep_batch.py",
        "record_sleep_batch_item_result",
        "tests/test_sleep_batch.py",
        ("happy_path", "same_class"),
    ),
    (
        "req.maintenance.writer-recovery",
        "contract.authority.explicit-crash-recovery",
        "local_kb/logicguard_models.py",
        "recover_authority_scopes",
        "tests/test_khaos_sleep_model_maintenance.py",
        ("happy_path", "failure_path", "replay"),
    ),
    (
        "req.retrieval.immutable-pointer",
        "contract.index.pointer-bound-snapshot",
        "local_kb/active_index.py",
        "load_active_index",
        "tests/test_kb_active_index_generation.py",
        ("happy_path", "negative_path", "replay"),
    ),
    (
        "req.retrieval.exact-entry-deny",
        "contract.index.publish-exact-deny",
        "local_kb/active_index.py",
        "publish_active_index_deny",
        "tests/test_kb_active_index_generation.py",
        ("happy_path", "failure_path", "negative_path"),
    ),
    (
        "req.retrieval.exact-current-corruption",
        "contract.index.mark-exact-current-corruption",
        "local_kb/active_index.py",
        "mark_active_index_corruption",
        "tests/test_kb_active_index_generation.py",
        ("happy_path", "failure_path", "negative_path", "replay"),
    ),
    (
        "req.retrieval.retire-global-invalidation",
        "contract.index.retire-active-invalidated",
        "local_kb/active_index.py",
        "rebuild_active_index",
        "tests/test_kb_active_index_generation.py",
        ("happy_path", "negative_path", "replay"),
    ),
)

EXPECTED_PLANNING_GAPS = {
    "test_evidence_not_passing",
    "missing_test_evidence",
    "missing_code_contract_test_evidence",
    "missing_required_test_kind",
}


def build_plan() -> ModelTestAlignmentPlan:
    obligations = tuple(
        ModelObligation(
            obligation_id=obligation_id,
            obligation_type="external_contract",
            description=f"LifecycleConvergenceBlock obligation: {obligation_id}",
            required=True,
            required_test_kinds=required_kinds,
            risk_level="high",
            allow_shared_evidence=False,
            allow_shared_implementation=False,
            exact_external_contract=True,
            model_miss_origin=True,
            requires_same_class_test_evidence=("same_class" in required_kinds),
        )
        for obligation_id, _contract_id, _path, _symbol, _test_path, required_kinds in BINDINGS
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
        for obligation_id, contract_id, path, symbol, _test_path, _required_kinds in BINDINGS
    )
    evidence = tuple(
        TestEvidence(
            evidence_id=f"evidence.planned.{obligation_id}.{test_kind}",
            test_name=f"planned::{obligation_id}::{test_kind}",
            path=test_path,
            command=f"python -m pytest -q {test_path}",
            result_status="not_run",
            evidence_current=True,
            test_kind=test_kind,
            covered_obligations=(obligation_id,),
            covered_code_contracts=(contract_id,),
            assertion_scope="external_contract",
            evidence_role="primary",
        )
        for obligation_id, contract_id, _path, _symbol, test_path, required_kinds in BINDINGS
        for test_kind in required_kinds
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
        # The existing commitment is explicitly not path-sensitive in the
        # BehaviorCommitmentLedger, so no invented primary_path_id is allowed.
        require_stable_authority_ids=False,
        require_behavior_plane_binding=False,
    )


def build_known_bad_plan() -> ModelTestAlignmentPlan:
    plan = build_plan()
    duplicate = CodeContract(
        code_contract_id="contract.parallel-controller.duplicate-sleep-owner",
        path="local_kb/logicguard_controller.py",
        symbol="commit_sleep_model_change",
        role="owner",
        implements_obligations=("req.maintenance.resumable-batch",),
        required=True,
    )
    return replace(plan, code_contracts=(*plan.code_contracts, duplicate))


def build_report() -> dict[str, object]:
    current = review_model_test_alignment(build_plan())
    known_bad = review_model_test_alignment(build_known_bad_plan())
    current_codes = {finding.code for finding in current.findings}
    known_bad_codes = {finding.code for finding in known_bad.findings}
    one_owner = all(
        len(row.owner_code_contract_ids) == 1 and row.status == "blocked"
        for row in current.binding_rows
    )
    return {
        "artifact_type": "kb_sleep_resumable_model_test_alignment",
        "primary_owner_model_id": MODEL_ID,
        "business_intent_id": BUSINESS_INTENT_ID,
        "behavior_commitment_id": COMMITMENT_ID,
        "field_lifecycle_source": FIELD_LIFECYCLE_SOURCE,
        "obligation_count": len(build_plan().obligations),
        "planned_evidence_count": len(build_plan().test_evidence),
        "current_finding_codes": sorted(current_codes),
        "known_bad_finding_codes": sorted(known_bad_codes),
        "planning_state": "frozen_not_run",
        "ok": (
            len(current.binding_rows) == len(BINDINGS)
            and one_owner
            and current_codes
            and current_codes.issubset(EXPECTED_PLANNING_GAPS)
            and "duplicate_code_contract_owner" in known_bad_codes
        ),
        "claim_boundary": (
            "Alignment structure only. Tests remain explicitly not-run here and require current external execution evidence."
        ),
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
