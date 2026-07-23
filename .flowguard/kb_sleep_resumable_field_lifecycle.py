"""FieldLifecycleMesh for resumable Sleep and generation-bound retrieval safety."""

from __future__ import annotations

import json
from dataclasses import replace

from flowguard import (
    FieldLifecycleGroup,
    FieldLifecyclePlan,
    FieldLifecycleRow,
    FieldProjection,
    review_field_lifecycle,
)


MODEL_OWNER = "kb_convergence_upgrade_model.LifecycleConvergenceBlock"
DESIGN_REF = "openspec:make-kb-sleep-resumable-and-nonblocking/design"
MODEL_REF = f"flowguard:{MODEL_OWNER}"


FIELD_GROUPS = {
    "group:sleep-batch-head": (
        "sleep_batch_head",
        "local_kb/sleep_batch.py",
        (
            "sleep_batch.head.schema_version",
            "sleep_batch.head.generation",
            "sleep_batch.head.batch_id",
            "sleep_batch.head.plan_ref",
            "sleep_batch.head.plan_digest",
            "sleep_batch.head.checkpoint_ref",
            "sleep_batch.head.checkpoint_digest",
            "sleep_batch.head.checkpoint_revision",
            "sleep_batch.head.settled",
            "sleep_batch.head.updated_at",
        ),
    ),
    "group:sleep-batch-plan": (
        "immutable_batch_plan",
        "local_kb/sleep_batch.py",
        (
            "sleep_batch.plan.schema_version",
            "sleep_batch.plan.batch_id",
            "sleep_batch.plan.created_at",
            "sleep_batch.plan.input_watermark",
            "sleep_batch.plan.prior_remaining_count",
            "sleep_batch.plan.prior_no_reduction_streak",
            "sleep_batch.plan.opening_remaining_count",
            "sleep_batch.plan.newly_eligible_count",
            "sleep_batch.plan.newly_eligible_item_ids",
            "sleep_batch.plan.min_items",
            "sleep_batch.plan.max_items",
            "sleep_batch.plan.target_formula",
            "sleep_batch.plan.target_item_count",
            "sleep_batch.plan.eligible_item_ids",
            "sleep_batch.plan.selected_item_ids",
            "sleep_batch.plan.deferred_item_ids",
            "sleep_batch.plan.deferred_item_count",
        ),
    ),
    "group:sleep-batch-checkpoint": (
        "derived_checkpoint",
        "local_kb/sleep_batch.py",
        (
            "sleep_batch.checkpoint.schema_version",
            "sleep_batch.checkpoint.batch_id",
            "sleep_batch.checkpoint.revision",
            "sleep_batch.checkpoint.created_at",
            "sleep_batch.checkpoint.updated_at",
            "sleep_batch.checkpoint.state",
            "sleep_batch.checkpoint.settled",
            "sleep_batch.checkpoint.completed_item_ids",
            "sleep_batch.checkpoint.blocked_item_ids",
            "sleep_batch.checkpoint.pending_item_ids",
            "sleep_batch.checkpoint.deferred_item_ids",
            "sleep_batch.checkpoint.completed_count",
            "sleep_batch.checkpoint.blocked_count",
            "sleep_batch.checkpoint.pending_count",
            "sleep_batch.checkpoint.processed_count",
            "sleep_batch.checkpoint.opening_remaining_count",
            "sleep_batch.checkpoint.closing_remaining_count",
            "sleep_batch.checkpoint.net_reduction",
            "sleep_batch.checkpoint.prior_remaining_count",
            "sleep_batch.checkpoint.remainder_delta_from_prior",
            "sleep_batch.checkpoint.remainder_trend",
            "sleep_batch.checkpoint.no_reduction_streak",
            "sleep_batch.checkpoint.backlog_growing",
        ),
    ),
    "group:sleep-batch-result": (
        "immutable_item_result",
        "local_kb/sleep_batch.py",
        (
            "sleep_batch.result.schema_version",
            "sleep_batch.result.batch_id",
            "sleep_batch.result.item_id",
            "sleep_batch.result.status",
            "sleep_batch.result.owner",
            "sleep_batch.result.reopen_condition",
            "sleep_batch.result.details",
            "sleep_batch.result.recorded_at",
        ),
    ),
    "group:active-index-pointer": (
        "serving_generation_pointer",
        "local_kb/active_index.py",
        (
            "active_index.pointer.schema_version",
            "active_index.pointer.activated_at",
            "active_index.pointer.generation",
            "active_index.pointer.artifact_path",
            "active_index.pointer.artifact_digest",
            "active_index.pointer.content_digest",
            "active_index.pointer.indexed_record_count",
            "active_index.pointer.authority_generation_id",
            "active_index.pointer.authority_generation_digest",
            "active_index.pointer.deny_path",
            "active_index.pointer.deny_digest",
            "active_index.pointer.pointer_digest",
        ),
    ),
    "group:active-index-deny": (
        "exact_subtractive_projection",
        "local_kb/active_index.py",
        (
            "active_index.deny.schema_version",
            "active_index.deny.index_generation",
            "active_index.deny.index_artifact_path",
            "active_index.deny.index_artifact_digest",
            "active_index.deny.authority_generation_id",
            "active_index.deny.denied_records[].entry_id",
            "active_index.deny.denied_records[].content_digest",
            "active_index.deny.denied_records[].denied_at",
            "active_index.deny.denied_records[].reason",
            "active_index.deny.denied_records[].event_type",
            "active_index.deny.denied_records[].item_id",
            "active_index.deny.deny_digest",
        ),
    ),
    "group:active-index-corruption": (
        "exact_current_corruption",
        "local_kb/active_index.py",
        (
            "active_index.corruption.schema_version",
            "active_index.corruption.marked_at",
            "active_index.corruption.pointer_digest",
            "active_index.corruption.artifact_digest",
            "active_index.corruption.reason",
            "active_index.corruption.evidence",
            "active_index.corruption.marker_digest",
        ),
    ),
    "group:retired-active-invalidated": (
        "retired_unscoped_authority",
        "kb/indexes/active-invalidated.json",
        (
            "retired.active-invalidated.schema_version",
            "retired.active-invalidated.reason",
            "retired.active-invalidated.token",
            "retired.active-invalidated.invalidated_at",
            "retired.active-invalidated.event_type",
            "retired.active-invalidated.item_id",
            "retired.active-invalidated.marker_digest",
        ),
    ),
    "group:migration-index-impact-deferral": (
        "upgrade_only_index_rebuild_handoff",
        "local_kb/maintenance_migration.py",
        (
            "migration.lifecycle_batch.defer_active_index_impacts_to_migration_rebuild",
            "migration.lifecycle_batch.retrieval_impacts[].status",
            "migration.lifecycle_batch.retrieval_impacts[].event_count",
        ),
    ),
    "group:authority-writer-recovery": (
        "explicit_current_store_crash_recovery",
        "local_kb/logicguard_models.py",
        (
            "authority_recovery.status",
            "authority_recovery.scopes[].scope",
            "authority_recovery.scopes[].status",
            "authority_recovery.scopes[].model_recovery_receipts",
            "authority_recovery.scopes[].mesh_recovery_receipts",
        ),
    ),
    "group:upgrade-automation-recovery-snapshot": (
        "pre_migration_user_intent_authority",
        "local_kb/install.py",
        (
            "upgrade_attempt.phase.automations_paused_migration_pending",
            "upgrade_attempt.automation_state_snapshot.states",
            "upgrade_attempt.automation_state_snapshot.user_paused",
            "upgrade_attempt.survivors_must_remain_paused",
        ),
    ),
}


def _obligation(field_id: str) -> tuple[str, str]:
    if field_id.startswith("sleep_batch"):
        return "req.maintenance.resumable-batch", "contract.sleep-batch.current-authority"
    if field_id.startswith("active_index.pointer"):
        return "req.retrieval.immutable-pointer", "contract.index.pointer-bound-snapshot"
    if field_id.startswith("active_index.deny"):
        return "req.retrieval.exact-entry-deny", "contract.index.publish-exact-deny"
    if field_id.startswith("active_index.corruption"):
        return "req.retrieval.exact-current-corruption", "contract.index.mark-exact-current-corruption"
    if field_id.startswith("migration.lifecycle_batch"):
        return "req.migration.transactional", "contract.migration.final-index-rebuild-owner"
    if field_id.startswith("authority_recovery"):
        return "req.maintenance.writer-recovery", "contract.authority.explicit-crash-recovery"
    if field_id.startswith("upgrade_attempt"):
        return "req.migration.transactional", "contract.install.persist-intent-before-migration"
    return "req.retrieval.retire-global-invalidation", "contract.index.retire-active-invalidated"


def _row(group_id: str, location: str, field_id: str) -> FieldLifecycleRow:
    obligation, contract = _obligation(field_id)
    retired = field_id.startswith("retired.")
    replacement = ""
    disposition = "deleted"
    return FieldLifecycleRow(
        field_id=field_id,
        field_name=field_id.rsplit(".", 1)[-1],
        locations=(location,),
        group_id=group_id,
        role="routing" if any(token in field_id for token in ("status", "state", "path", "ref", "digest")) else "persisted",
        lifecycle="old" if retired else "current",
        behavior_impacts=("state", "routing", "side_effect", "external_contract"),
        reader_ids=(("versioned upgrade owner",) if retired else ("local_kb.lifecycle", "local_kb.active_index")),
        writer_ids=(() if retired else (MODEL_OWNER,)),
        replacement_field_id=replacement,
        old_field_ids=((field_id,) if retired else ()),
        disposition=(disposition if retired else "unknown"),
        disposition_evidence_refs=((DESIGN_REF, MODEL_REF) if retired else ()),
        projection=FieldProjection(
            projection_id=f"projection:{field_id}",
            field_id=field_id,
            model_obligation_id=obligation,
            code_contract_id=contract,
            required_test_kinds=("happy_path", "failure_path", "negative_path", "replay"),
            external_inputs=(field_id,),
            external_outputs=(replacement or field_id,),
            state_reads=("frozen Sleep batch or current serving generation",),
            state_writes=(() if retired else (field_id,)),
            side_effects=(("direct migration or deletion",) if retired else ("atomic current-format write",)),
            error_paths=("foreign identity", "digest mismatch", "unknown old authority", "over-broad invalidation"),
            risk_level="high",
            evidence_refs=(DESIGN_REF, MODEL_REF),
            rationale=f"{field_id} stays under the existing lifecycle convergence owner.",
        ),
    )


def build_plan() -> FieldLifecyclePlan:
    groups = tuple(
        FieldLifecycleGroup(
            group_id=group_id,
            boundary_kind=boundary,
            field_ids=field_ids,
            owner_route="field_lifecycle_mesh",
            evidence_refs=(DESIGN_REF, MODEL_REF),
            rationale=f"Exact field boundary for {boundary}; no compatibility or fallback authority.",
        )
        for group_id, (boundary, _location, field_ids) in FIELD_GROUPS.items()
    )
    rows = tuple(
        _row(group_id, location, field_id)
        for group_id, (_boundary, location, field_ids) in FIELD_GROUPS.items()
        for field_id in field_ids
    )
    return FieldLifecyclePlan(
        mesh_id="kb-sleep-resumable-and-nonblocking-fields-v1",
        discovered_field_ids=tuple(row.field_id for row in rows),
        groups=groups,
        fields=rows,
        claim_scope="bounded",
        allow_scoped_confidence=False,
        notes=(
            "Complete changed-field inventory for frozen/resumable Sleep batches, pointer-bound immutable serving, "
            "exact denies, exact-current corruption, and direct retirement of active-invalidated.json."
        ),
    )


def build_known_bad_plan() -> FieldLifecyclePlan:
    plan = build_plan()
    rows = list(plan.fields)
    retired = next(row for row in rows if row.field_id == "retired.active-invalidated.token")
    rows[rows.index(retired)] = replace(
        retired,
        disposition="unknown",
        replacement_field_id="",
        disposition_evidence_refs=(),
    )
    return replace(plan, mesh_id="kb-sleep-resumable-fields-known-bad", fields=tuple(rows))


def build_report() -> dict[str, object]:
    current = review_field_lifecycle(build_plan())
    known_bad = review_field_lifecycle(build_known_bad_plan())
    return {
        "artifact_type": "kb_sleep_resumable_field_lifecycle_mesh",
        "primary_owner_model_id": MODEL_OWNER,
        "field_count": len(build_plan().fields),
        "group_count": len(build_plan().groups),
        "current_ok": current.ok,
        "current_finding_codes": sorted({finding.code for finding in current.findings}),
        "known_bad_ok": known_bad.ok,
        "known_bad_finding_codes": sorted({finding.code for finding in known_bad.findings}),
        "ok": current.ok and not known_bad.ok,
        "claim_boundary": (
            "Field inventory and retirement disposition only; behavior, source, runtime, tests, installation, and release stay separate."
        ),
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
