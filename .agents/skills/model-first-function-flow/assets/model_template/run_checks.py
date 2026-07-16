"""Run the formal minimum model_template checks."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    for parent in Path(__file__).resolve().parents:
        if (parent / "flowguard").is_dir():
            sys.path.insert(0, str(parent))
            break

from flowguard import (  # noqa: E402
    FlowGuardCheckPlan,
    KnownBadProof,
    MinimumModelContract,
    RiskIntent,
    RiskProfile,
    TemplateHarvestReview,
    TemplateReuseReview,
    run_model_first_checks,
)
import model  # noqa: E402


def build_plan(workflow, *, known_bad_proofs=()):
    return FlowGuardCheckPlan(
        workflow=workflow,
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=("stored", "rejected_duplicate"),
        risk_profile=RiskProfile(
            modeled_boundary="model template item acceptance",
            risk_classes=("deduplication", "side_effect"),
            risk_intent=RiskIntent(
                failure_modes=("duplicate item store", "store without accepted source"),
                protected_error_classes=("duplicate_side_effect", "source_trace_loss"),
                protected_harms=("downstream workflow acts on a duplicate or unsourced item",),
                must_model_state=("seen_ids", "stored_ids"),
                must_model_side_effects=("storage_write",),
                completion_evidence=("stored_ids",),
                adversarial_inputs=("same item repeated", "invalid item"),
                hard_invariants=("one store per item", "stored items trace to accepted outputs"),
                known_bad_cases=("duplicate_item_store",),
                used_template_ids=("side_effect_at_most_once",),
                blindspots=("real storage adapter replay is outside this starter template",),
            ),
            confidence_goal="model_level",
        ),
        template_reuse_review=TemplateReuseReview(
            used_template_ids=("side_effect_at_most_once",),
            searched_layers=("public", "local"),
        ),
        minimum_model_contract=MinimumModelContract(
            protected_error_classes=("duplicate_side_effect", "source_trace_loss"),
            modeled_state=("seen_ids", "stored_ids"),
            modeled_side_effects=("storage_write",),
            completion_evidence=("stored_ids",),
            known_bad_cases=("duplicate_item_store",),
        ),
        known_bad_proofs=known_bad_proofs,
        template_harvest_review=TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        scenario_matrix_config={"enabled": False},
    )


def known_bad_proof_from_summary(summary):
    sections = {section.name: section for section in summary.sections}
    caught = sections["model_check"].status == "failed"
    return KnownBadProof(
        "duplicate_item_store",
        protected_error_class="duplicate_side_effect",
        method="broken_workflow_variant",
        expected_failure="failed",
        observed_status="failed" if caught else "passed",
        observed_failure=(
            "duplicate store variant violates no_duplicate_stores"
            if caught
            else "duplicate store variant unexpectedly passed"
        ),
        evidence_id="model-template:duplicate_item_store",
    )


def main() -> int:
    broken_summary = run_model_first_checks(build_plan(model.broken_workflow()))
    proof = known_bad_proof_from_summary(broken_summary)
    report = run_model_first_checks(
        build_plan(model.build_workflow(), known_bad_proofs=(proof,))
    )
    sections = {section.name: section for section in report.sections}
    print(report.format_text())
    print(f"known_bad_duplicate_store_rejected: {'yes' if proof.observed_status == 'failed' else 'no'}")
    model_report = dict(report.metadata)["model_check_report"]
    labels = sorted({label for trace in model_report.traces for label in trace.labels})
    print("labels: " + ",".join(labels))
    expected_labels = {"stored", "rejected_duplicate"}
    return 0 if (
        sections["model_check"].status == "pass"
        and sections["known_bad_proof"].status == "pass"
        and proof.observed_status == "failed"
        and expected_labels.issubset(labels)
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
