"""Close the real large-brain LogicGuard runtime performance model miss.

The earlier performance obligation passed only a three-card fixture.  A real
3427-card current generation then exceeded the catalog and exact-context
budgets.  This review reuses the existing retrieval commitment, preserves the
false-negative evidence, binds one generalized same-class case to the owner
code and tests, and requires current large-brain runtime evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from flowguard import (
    FALSE_NEGATIVE_CAUSE_SCOPE_OVERCLAIM,
    MODEL_MATURATION_SIGNAL_CODE_BOUNDARY_MISMATCH,
    MODEL_MATURATION_SIGNAL_SAME_CLASS_MISSING,
    MODEL_MISS_BACKFEED_REUSE_EXISTING,
    FalseNegativeBackpropagationPlan,
    FalseNegativeCase,
    FlowGuardClosureContractPlan,
    ModelMaturationPlan,
    ModelMaturationSignal,
    SameClassMissClosure,
    UIModelMissRecord,
    backfeed_model_miss_to_behavior_ledger,
    load_behavior_commitment_ledger,
    review_false_negative_backpropagation,
    review_flowguard_closure_contract,
    review_model_maturation_loop,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = REPO_ROOT / ".flowguard" / "behavior_commitment_ledger" / "ledger.json"
MISS_ID = "miss:khaos-logicguard-runtime:large-local-generation"
COMMITMENT_ID = "commitment:kb-retrieval-current-index"
OWNER_MODEL_ID = "kb_convergence_upgrade_model.LifecycleConvergenceBlock"
OBLIGATION_ID = "req.retrieval.performance"
GENERALIZED_CASE_ID = "case:retrieval:shared-current-mesh-across-distinct-cards"
OBSERVED_FAILURE_ID = "evidence:logicguard-runtime:3427-card-budget-failure"
RUNTIME_CLOSURE_ID = "evidence:logicguard-runtime:3427-card-budget-pass"
SAME_CLASS_TEST_ID = (
    "test:tests/test_khaos_model_native_retrieval.py::"
    "KhaosModelNativeRetrievalTests::"
    "test_current_mesh_view_is_reused_across_distinct_cards_in_one_generation"
)
MEASUREMENT_TEST_ID = (
    "test:tests/test_khaos_model_runtime_readiness.py::"
    "KhaosModelRuntimeReadinessTests::"
    "test_catalog_latency_is_measured_without_memory_instrumentation"
)


def build_report() -> dict[str, object]:
    ledger = load_behavior_commitment_ledger(LEDGER_PATH)
    miss = UIModelMissRecord(
        miss_id=MISS_ID,
        previous_claim_id=OBLIGATION_ID,
        previous_green_reason="The performance owner had only a three-card fixture.",
        observed_failure=(
            "The current 3427-card generation exceeded catalog and exact-context budgets."
        ),
        observed_failure_evidence_ref=OBSERVED_FAILURE_ID,
        miss_type="evidence_overclaimed",
        affected_capability_ids=("capability:exact-model-bound-retrieval",),
        same_class_capability_ids=(
            "capability:distinct-card-same-generation-mesh-reuse",
            "capability:catalog-latency-with-independent-memory-probe",
        ),
        required_test_ids=(SAME_CLASS_TEST_ID, MEASUREMENT_TEST_ID),
        required_implementation_evidence_ids=(RUNTIME_CLOSURE_ID,),
        affected_behavior_plane="product_runtime",
        affected_commitment_id=COMMITMENT_ID,
        primary_owner_model_id=OWNER_MODEL_ID,
        error_signatures=(
            "catalog-performance:30.620497>30.000000",
            "exact-context-p95:3.145622>2.000000",
        ),
        error_evidence_ids=(OBSERVED_FAILURE_ID,),
        root_cause_backpropagation=(
            "The benchmark timed memory instrumentation, and each distinct card reparsed "
            "the same immutable scope mesh three times. The small fixture did not expose scale."
        ),
        code_owner="local_kb.logicguard_models._cached_current_mesh_view",
        rationale="Reuse the existing retrieval commitment and close the scale class, not one card.",
    )
    backfeed = backfeed_model_miss_to_behavior_ledger(miss, ledger)

    false_negative = review_false_negative_backpropagation(
        FalseNegativeBackpropagationPlan(
            plan_id="plan:khaos-logicguard-runtime:false-negative",
            cases=(
                FalseNegativeCase(
                    case_id=MISS_ID,
                    previous_claim_id=OBLIGATION_ID,
                    observed_failure_id=OBSERVED_FAILURE_ID,
                    cause=FALSE_NEGATIVE_CAUSE_SCOPE_OVERCLAIM,
                    would_have_failed_if=(
                        "the performance gate had included the existing 3427-card generation",
                        "the same-class test had required distinct cards to share one mesh view",
                        "catalog timing had excluded memory instrumentation overhead",
                    ),
                    generalized_case_id=GENERALIZED_CASE_ID,
                    new_model_obligation_id=OBLIGATION_ID,
                    new_plan_item_ids=(SAME_CLASS_TEST_ID, MEASUREMENT_TEST_ID),
                    closure_evidence_ids=(RUNTIME_CLOSURE_ID,),
                    repair_evidence_ids=(
                        "code:local_kb/logicguard_models.py:_cached_current_mesh_view",
                        "code:scripts/check_khaos_logicguard_runtime.py:build_report",
                        SAME_CLASS_TEST_ID,
                        MEASUREMENT_TEST_ID,
                    ),
                    metadata={
                        "failed_entry_count": 3427,
                        "failed_catalog_seconds": 30.620497,
                        "failed_exact_context_p95_seconds": 3.145622,
                        "passed_catalog_seconds": 13.069128,
                        "passed_exact_context_p95_seconds": 0.052862,
                        "passed_search_p95_seconds": 0.551762,
                    },
                ),
            ),
            recurring_or_high_risk=False,
            allow_scoped_confidence=False,
        )
    )

    maturation = review_model_maturation_loop(
        ModelMaturationPlan(
            plan_id="plan:khaos-logicguard-runtime:maturation",
            model_id=OWNER_MODEL_ID,
            risk_id=MISS_ID,
            signals=(
                ModelMaturationSignal(
                    signal_id="signal:runtime-scale-code-boundary",
                    signal_type=MODEL_MATURATION_SIGNAL_CODE_BOUNDARY_MISMATCH,
                    source_route="model_miss_review",
                    model_id=OWNER_MODEL_ID,
                    risk_id=MISS_ID,
                    evidence_id=RUNTIME_CLOSURE_ID,
                    description="Distinct cards now reuse one exact current mesh view.",
                    resolved=True,
                    current=True,
                ),
                ModelMaturationSignal(
                    signal_id="signal:runtime-scale-same-class",
                    signal_type=MODEL_MATURATION_SIGNAL_SAME_CLASS_MISSING,
                    source_route="model_miss_review",
                    model_id=OWNER_MODEL_ID,
                    risk_id=MISS_ID,
                    evidence_id=SAME_CLASS_TEST_ID,
                    description="The generalized distinct-card same-generation case is current.",
                    resolved=True,
                    current=True,
                ),
            ),
            claim_scope="release",
            require_full_closure=True,
            allow_scoped_claim=False,
        )
    )

    same_class = SameClassMissClosure(
        miss_id=MISS_ID,
        observed_failure_evidence_id=OBSERVED_FAILURE_ID,
        same_class_proof_evidence_id=SAME_CLASS_TEST_ID,
        model_obligation_id=OBLIGATION_ID,
        defect_family_id=GENERALIZED_CASE_ID,
        current=True,
        result_status="passed",
        metadata={"runtime_closure_evidence_id": RUNTIME_CLOSURE_ID},
    )
    closure = review_flowguard_closure_contract(
        FlowGuardClosureContractPlan(
            claim_id="claim:khaos-logicguard-runtime-model-miss-closed",
            claim_scope="false_negative_closed",
            same_class_miss_closures=(same_class,),
            require_runtime_trace_mapping=False,
            require_artifact_freshness=False,
            require_model_quality_review=False,
            require_same_class_miss_closure=True,
            require_runtime_gateway_closure=False,
            require_risk_ledger=False,
            allow_scoped_confidence=False,
        )
    )

    ok = bool(
        backfeed.disposition == MODEL_MISS_BACKFEED_REUSE_EXISTING
        and backfeed.primary_context is not None
        and backfeed.primary_context.commitment_id == COMMITMENT_ID
        and false_negative.ok
        and maturation.ok
        and closure.ok
    )
    return {
        "artifact_type": "khaos_brain_logicguard_runtime_model_miss_review",
        "ok": ok,
        "miss_id": MISS_ID,
        "behavior_backfeed": backfeed.to_dict(),
        "false_negative": false_negative.to_dict(),
        "maturation": maturation.to_dict(),
        "same_class_closure": closure.to_dict(),
        "claim_boundary": (
            "This closes the observed 3427-card performance false negative and its "
            "declared same-class scale case for the current code and evidence identities. "
            "It does not replace the final aggregate release owner."
        ),
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
