"""Close the Sleep timeout / active-index recovery FlowGuard model miss."""

from __future__ import annotations

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

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = REPO_ROOT / ".flowguard" / "behavior_commitment_ledger" / "ledger.json"
MISS_ID = "miss:kb-sleep:timeout-after-lifecycle-invalidation"
COMMITMENT_ID = "commitment:sleep-no-delta-single-owner"
OWNER_MODEL_ID = "kb_convergence_upgrade_model.LifecycleConvergenceBlock"
OBLIGATION_ID = "obligation:sleep-bounded-lifecycle-index-recovery"
OBSERVED_FAILURE_ID = (
    "evidence:native-kb-sleep-maintenance-20260720T100219848122Z-58af370c"
)
GENERALIZED_CASE_ID = "case:sleep:same-cycle-lifecycle-batch-family"
MODEL_PROOF_ID = "evidence:flowguard:lifecycle-convergence-v2"
OBSERVED_TEST_ID = (
    "test:tests/test_kb_lifecycle.py::"
    "KbLifecycleTests::test_candidate_events_commit_in_one_bounded_batch"
)
SAME_CLASS_TEST_ID = (
    "test:tests/test_kb_lifecycle.py::"
    "KbLifecycleTests::test_candidate_transition_family_retry_is_bounded"
)
INDEX_AUTHORITY_TEST_ID = (
    "test:tests/test_kb_retrieval_calibration.py::"
    "KbRetrievalCalibrationTests::test_rebuild_requires_authorized_publisher"
)


def build_report() -> dict[str, object]:
    ledger = load_behavior_commitment_ledger(LEDGER_PATH)
    miss = UIModelMissRecord(
        miss_id=MISS_ID,
        previous_claim_id=COMMITMENT_ID,
        previous_green_reason=(
            "The prior model covered one final index owner and no-delta reuse, "
            "but represented lifecycle/index publication only through a consumer-block alias."
        ),
        observed_failure=(
            "Sleep committed candidate lifecycle events, durably invalidated the active "
            "index, then exhausted its 900-second native timeout before index/watermark closure."
        ),
        observed_failure_evidence_ref=OBSERVED_FAILURE_ID,
        miss_type="state_too_coarse",
        affected_capability_ids=(
            "capability:sleep-bounded-lifecycle-publication",
            "capability:active-index-timeout-recovery",
        ),
        same_class_capability_ids=(
            "capability:candidate-create-park-batch",
            "capability:candidate-reopen-promote-batch",
            "capability:candidate-downgrade-park-batch",
            "capability:candidate-calibration-batch",
            "capability:observation-disposition-batch",
        ),
        required_test_ids=(
            OBSERVED_TEST_ID,
            SAME_CLASS_TEST_ID,
            INDEX_AUTHORITY_TEST_ID,
        ),
        required_implementation_evidence_ids=(MODEL_PROOF_ID,),
        affected_behavior_plane="product_runtime",
        affected_commitment_id=COMMITMENT_ID,
        primary_owner_model_id=OWNER_MODEL_ID,
        error_signatures=(
            "native timeout after 900.0s",
            "active index is durably invalidated pending rebuild",
        ),
        error_evidence_ids=(OBSERVED_FAILURE_ID,),
        root_cause_backpropagation=(
            "Candidate creation and review committed transitions one event at a time. "
            "Each event replayed the complete lifecycle ledger before and after append, "
            "while the executable owner model lacked invalidated-pending-rebuild and timeout states."
        ),
        code_owner="local_kb.lifecycle._run_incremental_sleep_locked",
        rationale=(
            "Reuse the existing Sleep commitment and LifecycleConvergenceBlock; "
            "close every same-cycle transition family without adding another writer."
        ),
    )
    backfeed = backfeed_model_miss_to_behavior_ledger(miss, ledger)

    false_negative = review_false_negative_backpropagation(
        FalseNegativeBackpropagationPlan(
            plan_id="plan:kb-sleep-timeout:false-negative",
            cases=(
                FalseNegativeCase(
                    case_id=MISS_ID,
                    previous_claim_id=COMMITMENT_ID,
                    observed_failure_id=OBSERVED_FAILURE_ID,
                    cause=FALSE_NEGATIVE_CAUSE_SCOPE_OVERCLAIM,
                    would_have_failed_if=(
                        "the model had represented invalidated_pending_rebuild explicitly",
                        "the same-class test had counted complete-ledger replay per candidate",
                        "the prior green claim had required one real timeout/recovery trace",
                    ),
                    generalized_case_id=GENERALIZED_CASE_ID,
                    new_model_obligation_id=OBLIGATION_ID,
                    new_plan_item_ids=(
                        OBSERVED_TEST_ID,
                        SAME_CLASS_TEST_ID,
                        INDEX_AUTHORITY_TEST_ID,
                    ),
                    closure_evidence_ids=(MODEL_PROOF_ID,),
                    repair_evidence_ids=(
                        "code:local_kb/candidate_lifecycle.py",
                        "code:local_kb/lifecycle.py:commit_lifecycle_events",
                        "code:local_kb/active_index.py:rebuild_active_index",
                        OBSERVED_TEST_ID,
                        SAME_CLASS_TEST_ID,
                        INDEX_AUTHORITY_TEST_ID,
                    ),
                    metadata={
                        "native_timeout_seconds": 900,
                        "lifecycle_event_count_at_failure": 241990,
                        "candidate_count_in_failed_run": 14,
                    },
                ),
            ),
            recurring_or_high_risk=True,
            allow_scoped_confidence=False,
        )
    )

    maturation = review_model_maturation_loop(
        ModelMaturationPlan(
            plan_id="plan:kb-sleep-timeout:maturation",
            model_id=OWNER_MODEL_ID,
            risk_id=MISS_ID,
            signals=(
                ModelMaturationSignal(
                    signal_id="signal:sleep-timeout-state-boundary",
                    signal_type=MODEL_MATURATION_SIGNAL_CODE_BOUNDARY_MISMATCH,
                    source_route="model_miss_review",
                    model_id=OWNER_MODEL_ID,
                    risk_id=MISS_ID,
                    evidence_id=MODEL_PROOF_ID,
                    description=(
                        "LifecycleConvergenceBlock now models batch, invalidation, "
                        "timeout, authorized recovery, and watermark terminal states."
                    ),
                    resolved=True,
                    current=True,
                ),
                ModelMaturationSignal(
                    signal_id="signal:sleep-transition-family-same-class",
                    signal_type=MODEL_MATURATION_SIGNAL_SAME_CLASS_MISSING,
                    source_route="model_miss_review",
                    model_id=OWNER_MODEL_ID,
                    risk_id=MISS_ID,
                    evidence_id=SAME_CLASS_TEST_ID,
                    description=(
                        "Create, park, reopen, promote, downgrade, calibration, and "
                        "observation transitions share bounded batch evidence."
                    ),
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
        metadata={"model_proof_id": MODEL_PROOF_ID},
    )
    closure = review_flowguard_closure_contract(
        FlowGuardClosureContractPlan(
            claim_id="claim:kb-sleep-timeout-model-miss-closed",
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
        "artifact_type": "kb_sleep_timeout_model_miss_review",
        "ok": ok,
        "miss_id": MISS_ID,
        "miss_types": ["state_too_coarse", "evidence_overclaimed"],
        "observed_counterexample_id": OBSERVED_FAILURE_ID,
        "behavior_backfeed": backfeed.to_dict(),
        "false_negative": false_negative.to_dict(),
        "maturation": maturation.to_dict(),
        "same_class_closure": closure.to_dict(),
        "claim_boundary": (
            "This closes the modeled timeout/recovery and same-cycle lifecycle "
            "transition family for current code/test identities. Final runtime "
            "recovery and aggregate release evidence remain separate gates."
        ),
    }
