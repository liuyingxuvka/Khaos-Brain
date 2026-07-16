"""FlowGuard child models for the Chaos Brain convergence upgrade.

The existing Khaos Brain models retain parent ownership.  This module narrows
the new behavior to two finite children: knowledge convergence and versioned
upgrade migration.  Every block implements ``Input x State -> Set(Output x
State)`` through ``FunctionResult``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow

from local_kb.automation_contracts import (
    AUTOMATION_COMPLETION_CONTRACTS,
    expected_obligation_ids,
)


ACTIVE_STATUSES = frozenset({"trusted", "candidate"})
TERMINAL_STATUSES = frozenset(
    {"merged", "rejected", "superseded", "parked", "retired", "history_only"}
)


@dataclass(frozen=True)
class LifecycleInput:
    kind: str
    item_id: str = ""
    disposition: str = "history_only"
    fingerprint: str = ""
    status: str = "candidate"
    retrieval_eligible: bool = False
    source_boundary: str = "local-active-index"
    row_count: int = 0
    terminal_count: int = 0
    processing_mode: str = "atomic-batch"
    owner_alive: bool = True
    owner_recorded: bool = True
    same_thread_active: bool = False
    release_succeeds: bool = True
    process_tree_count: int = 0
    cleanup_confirmed: bool = True
    child_timeout_seconds: int = 0
    parent_timeout_seconds: int = 0
    contains_yaml_date: bool = False
    scanner_definition_only: bool = False
    index_delta: bool = False
    parked_count: int = 0
    parked_evidence_delta_count: int = 0


@dataclass(frozen=True)
class LifecycleOutput:
    label: str
    item_id: str = ""
    fingerprint: str = ""


@dataclass(frozen=True)
class LifecycleState:
    admitted: tuple[str, ...] = ()
    dispositions: tuple[str, ...] = ()
    entry_statuses: tuple[str, ...] = ()
    candidate_eligible: tuple[str, ...] = ()
    candidate_eligibility_evidence: tuple[str, ...] = ()
    organization_candidates: tuple[str, ...] = ()
    active_index: tuple[str, ...] = ()
    actionable_backlog: int = 0
    watermark: int = 0
    index_generation: int = 0
    foreground_full_replays: int = 0
    dream_closed: tuple[str, ...] = ()
    dream_writes: tuple[str, ...] = ()
    sleep_handoffs: tuple[str, ...] = ()
    pending_handoffs: tuple[str, ...] = ()
    handoff_model_commits: tuple[str, ...] = ()
    handoff_acks: tuple[str, ...] = ()
    cooldown_closed: tuple[str, ...] = ()
    sleep_resume_pending_count: int = 0
    sleep_resume_replay_passes: int = 0
    sleep_resume_batch_count: int = 0
    lifecycle_replay_event_count: int = 0
    lifecycle_replay_membership_checks: int = 0
    dead_lane_lock_observed: bool = False
    dead_lane_lock_recovered: bool = False
    lifecycle_writer_orphan_observed: bool = False
    lifecycle_writer_orphan_recovered: bool = False
    lifecycle_writer_reentrant_observed: bool = False
    lifecycle_writer_reentrant_safe: bool = False
    lifecycle_writer_release_attempted: bool = False
    lifecycle_writer_release_succeeded: bool = False
    lifecycle_writer_release_failure_visible: bool = False
    validation_timeout_observed: bool = False
    validation_child_timeout_seconds: int = 0
    validation_parent_timeout_seconds: int = 0
    remaining_process_count: int = 0
    candidate_review_count: int = 0
    calibration_evidence_load_count: int = 0
    parked_review_count: int = 0
    parked_recalibration_count: int = 0
    parked_evidence_delta_count: int = 0
    parked_calibration_snapshot_count: int = 0
    shareability_serialization_ok: bool = True
    privacy_false_positive_count: int = 0
    sleep_model_publication_count: int = 0
    sleep_index_rebuild_count: int = 0
    sleep_index_validation_count: int = 0


def _append_unique(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    return values if value in values else values + (value,)


def _pairs(values: tuple[str, ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        key, separator, item = value.partition("=")
        if separator:
            result[key] = item
    return result


def _replace_pair(values: tuple[str, ...], key: str, value: str) -> tuple[str, ...]:
    pairs = _pairs(values)
    pairs[key] = value
    return tuple(f"{item_key}={pairs[item_key]}" for item_key in sorted(pairs))


def _eligible_index(
    entry_statuses: tuple[str, ...], candidate_eligible: tuple[str, ...] = ()
) -> tuple[str, ...]:
    pairs = _pairs(entry_statuses)
    eligible_candidates = set(candidate_eligible)
    return tuple(
        sorted(
            key
            for key, value in pairs.items()
            if value == "trusted" or (value == "candidate" and key in eligible_candidates)
        )
    )


class LifecycleConvergenceBlock:
    name = "LifecycleConvergenceBlock"
    reads = (
        "admitted",
        "dispositions",
        "entry_statuses",
        "candidate_eligible",
        "candidate_eligibility_evidence",
        "organization_candidates",
        "active_index",
        "actionable_backlog",
        "watermark",
        "foreground_full_replays",
        "dream_closed",
        "dream_writes",
        "sleep_handoffs",
        "pending_handoffs",
        "handoff_model_commits",
        "handoff_acks",
        "sleep_resume_pending_count",
        "sleep_resume_replay_passes",
        "sleep_resume_batch_count",
        "lifecycle_replay_event_count",
        "lifecycle_replay_membership_checks",
        "dead_lane_lock_observed",
        "dead_lane_lock_recovered",
        "lifecycle_writer_orphan_observed",
        "lifecycle_writer_orphan_recovered",
        "lifecycle_writer_reentrant_observed",
        "lifecycle_writer_reentrant_safe",
        "lifecycle_writer_release_attempted",
        "lifecycle_writer_release_succeeded",
        "lifecycle_writer_release_failure_visible",
        "validation_timeout_observed",
        "validation_child_timeout_seconds",
        "validation_parent_timeout_seconds",
        "remaining_process_count",
        "candidate_review_count",
        "calibration_evidence_load_count",
        "parked_review_count",
        "parked_recalibration_count",
        "parked_evidence_delta_count",
        "parked_calibration_snapshot_count",
        "shareability_serialization_ok",
        "privacy_false_positive_count",
        "sleep_model_publication_count",
        "sleep_index_rebuild_count",
        "sleep_index_validation_count",
    )
    writes = (
        "admitted",
        "dispositions",
        "entry_statuses",
        "candidate_eligible",
        "candidate_eligibility_evidence",
        "organization_candidates",
        "active_index",
        "actionable_backlog",
        "watermark",
        "index_generation",
        "foreground_full_replays",
        "dream_closed",
        "dream_writes",
        "sleep_handoffs",
        "pending_handoffs",
        "handoff_model_commits",
        "handoff_acks",
        "cooldown_closed",
        "sleep_resume_pending_count",
        "sleep_resume_replay_passes",
        "sleep_resume_batch_count",
        "lifecycle_replay_event_count",
        "lifecycle_replay_membership_checks",
        "dead_lane_lock_observed",
        "dead_lane_lock_recovered",
        "lifecycle_writer_orphan_observed",
        "lifecycle_writer_orphan_recovered",
        "lifecycle_writer_reentrant_observed",
        "lifecycle_writer_reentrant_safe",
        "lifecycle_writer_release_attempted",
        "lifecycle_writer_release_succeeded",
        "lifecycle_writer_release_failure_visible",
        "validation_timeout_observed",
        "validation_child_timeout_seconds",
        "validation_parent_timeout_seconds",
        "remaining_process_count",
        "candidate_review_count",
        "calibration_evidence_load_count",
        "parked_review_count",
        "parked_recalibration_count",
        "parked_evidence_delta_count",
        "parked_calibration_snapshot_count",
        "shareability_serialization_ok",
        "privacy_false_positive_count",
        "sleep_model_publication_count",
        "sleep_index_rebuild_count",
        "sleep_index_validation_count",
    )
    accepted_input_type = LifecycleInput
    input_description = "lifecycle, Sleep, Dream, or index event"
    output_description = "one convergence decision"
    idempotency = (
        "Observation ids, dispositions, Dream fingerprints, and handoff ids are "
        "stable; replay returns an existing decision without another mutation."
    )

    def __init__(self, *, broken_mode: str = "") -> None:
        self.broken_mode = broken_mode

    def apply(
        self, input_obj: LifecycleInput, state: LifecycleState
    ) -> Iterable[FunctionResult]:
        if input_obj.kind == "admit":
            if input_obj.item_id in state.admitted:
                yield FunctionResult(
                    LifecycleOutput("observation_already_admitted", input_obj.item_id),
                    state,
                    "observation_already_admitted",
                )
                return
            yield FunctionResult(
                LifecycleOutput("observation_admitted", input_obj.item_id),
                replace(
                    state,
                    admitted=state.admitted + (input_obj.item_id,),
                    actionable_backlog=state.actionable_backlog + 1,
                ),
                "observation_admitted",
            )
            return

        if input_obj.kind == "lifecycle_replay":
            event_count = max(0, input_obj.row_count)
            membership_checks = (
                event_count * event_count
                if self.broken_mode == "quadratic_lifecycle_idempotency_lookup"
                else event_count
            )
            yield FunctionResult(
                LifecycleOutput("lifecycle_replay_linear_idempotency_index"),
                replace(
                    state,
                    lifecycle_replay_event_count=event_count,
                    lifecycle_replay_membership_checks=membership_checks,
                ),
                "lifecycle_replay_linear_idempotency_index",
            )
            return

        if input_obj.kind == "sleep_resume":
            row_count = max(0, input_obj.row_count)
            terminal_count = max(0, input_obj.terminal_count)
            if terminal_count > row_count or terminal_count > len(state.dispositions):
                yield FunctionResult(
                    LifecycleOutput("sleep_blocked_missing_terminal_evidence"),
                    state,
                    "sleep_blocked_missing_terminal_evidence",
                )
                return
            pending_count = row_count - terminal_count
            admitted = state.admitted
            dispositions = state.dispositions
            for index in range(pending_count):
                item_id = f"resume-{state.watermark}-{index}"
                admitted = _append_unique(admitted, item_id)
                dispositions = _append_unique(
                    dispositions, f"{item_id}=history_only"
                )
            processing_mode = (
                "per-item-replay"
                if self.broken_mode in {
                    "sleep_per_item_replay",
                    "dream_handoff_per_item_replay",
                }
                else input_obj.processing_mode
            )
            replay_passes = (
                0
                if pending_count == 0
                else pending_count * 2
                if processing_mode == "per-item-replay"
                else 2
            )
            batch_count = (
                0
                if pending_count == 0
                else pending_count
                if processing_mode == "per-item-replay"
                else 1
            )
            label = (
                "sleep_resume_terminal_fast_path"
                if pending_count == 0
                else "sleep_resume_atomic_batch"
            )
            yield FunctionResult(
                LifecycleOutput(label),
                replace(
                    state,
                    admitted=admitted,
                    dispositions=dispositions,
                    actionable_backlog=max(0, len(admitted) - len(dispositions)),
                    watermark=len(dispositions),
                    sleep_resume_pending_count=pending_count,
                    sleep_resume_replay_passes=replay_passes,
                    sleep_resume_batch_count=batch_count,
                ),
                label,
            )
            return

        if input_obj.kind == "candidate_review":
            review_count = max(0, input_obj.row_count)
            parked_count = min(review_count, max(0, input_obj.parked_count))
            parked_delta_count = min(
                parked_count,
                max(0, input_obj.parked_evidence_delta_count),
            )
            evidence_load_count = (
                review_count
                if self.broken_mode == "candidate_per_item_calibration_reload"
                else 1
                if review_count
                else 0
            )
            yield FunctionResult(
                LifecycleOutput("candidate_review_shared_evidence_index"),
                replace(
                    state,
                    candidate_review_count=review_count,
                    calibration_evidence_load_count=evidence_load_count,
                    parked_review_count=parked_count,
                    parked_recalibration_count=(
                        parked_count
                        if self.broken_mode
                        == "parked_recalibrated_without_evidence_delta"
                        else parked_delta_count
                    ),
                    parked_evidence_delta_count=parked_delta_count,
                    parked_calibration_snapshot_count=(
                        0
                        if self.broken_mode == "parked_delta_not_checkpointed"
                        else parked_delta_count
                    ),
                ),
                "candidate_review_shared_evidence_index",
            )
            return

        if input_obj.kind == "sleep_index_finalize":
            rebuild_count = 1 if input_obj.index_delta else 0
            validation_count = 1
            publication_count = 1
            if self.broken_mode == "duplicate_sleep_index_validation":
                rebuild_count += 1
                validation_count += 1
            if self.broken_mode == "duplicate_sleep_model_publication":
                publication_count += 1
            yield FunctionResult(
                LifecycleOutput("sleep_index_finalized_once"),
                replace(
                    state,
                    sleep_model_publication_count=publication_count,
                    sleep_index_rebuild_count=rebuild_count,
                    sleep_index_validation_count=validation_count,
                ),
                "sleep_index_finalized_once",
            )
            return

        if input_obj.kind == "shareability_check":
            serialization_ok = not (
                input_obj.contains_yaml_date
                and self.broken_mode == "date_serialization_failure"
            )
            false_positive_count = (
                1
                if input_obj.scanner_definition_only
                and self.broken_mode == "scanner_self_match"
                else 0
            )
            yield FunctionResult(
                LifecycleOutput(
                    "shareability_check_passed"
                    if serialization_ok and not false_positive_count
                    else "shareability_check_failed"
                ),
                replace(
                    state,
                    shareability_serialization_ok=serialization_ok,
                    privacy_false_positive_count=false_positive_count,
                ),
                (
                    "shareability_check_passed"
                    if serialization_ok and not false_positive_count
                    else "shareability_check_failed"
                ),
            )
            return

        if input_obj.kind == "acquire_lane_lock":
            if input_obj.owner_alive:
                yield FunctionResult(
                    LifecycleOutput("lane_lock_blocked_live_owner"),
                    state,
                    "lane_lock_blocked_live_owner",
                )
                return
            recovered = self.broken_mode != "dead_lane_lock_retained"
            yield FunctionResult(
                LifecycleOutput(
                    "dead_lane_lock_recovered"
                    if recovered
                    else "dead_lane_lock_retained"
                ),
                replace(
                    state,
                    dead_lane_lock_observed=True,
                    dead_lane_lock_recovered=recovered,
                ),
                (
                    "dead_lane_lock_recovered"
                    if recovered
                    else "dead_lane_lock_retained"
                ),
            )
            return

        if input_obj.kind == "lifecycle_writer_lock":
            reentrant = input_obj.owner_alive and input_obj.same_thread_active
            orphaned = not input_obj.owner_alive or not input_obj.owner_recorded
            if input_obj.owner_alive and not reentrant:
                yield FunctionResult(
                    LifecycleOutput("lifecycle_writer_blocked_live_owner"),
                    state,
                    "lifecycle_writer_blocked_live_owner",
                )
                return
            reentrant_safe = (
                reentrant
                and self.broken_mode != "lifecycle_writer_self_deadlock"
            )
            recovered = (
                orphaned
                and self.broken_mode != "lifecycle_writer_orphan_retained"
            )
            if orphaned and not recovered:
                yield FunctionResult(
                    LifecycleOutput("lifecycle_writer_orphan_retained"),
                    replace(
                        state,
                        lifecycle_writer_orphan_observed=True,
                        lifecycle_writer_orphan_recovered=False,
                    ),
                    "lifecycle_writer_orphan_retained",
                )
                return
            if reentrant and not reentrant_safe:
                yield FunctionResult(
                    LifecycleOutput("lifecycle_writer_self_deadlock"),
                    replace(
                        state,
                        lifecycle_writer_reentrant_observed=True,
                        lifecycle_writer_reentrant_safe=False,
                    ),
                    "lifecycle_writer_self_deadlock",
                )
                return
            release_attempted = not reentrant
            release_succeeded = (
                release_attempted
                and input_obj.release_succeeds
            )
            release_failure_visible = (
                release_attempted
                and not release_succeeded
                and self.broken_mode
                != "lifecycle_writer_release_failure_hidden"
            )
            yield FunctionResult(
                LifecycleOutput(
                    "lifecycle_writer_reentrant_safe"
                    if reentrant
                    else "lifecycle_writer_released"
                    if release_succeeded
                    else "lifecycle_writer_release_failed_visible"
                    if release_failure_visible
                    else "lifecycle_writer_release_failure_hidden"
                ),
                replace(
                    state,
                    lifecycle_writer_orphan_observed=(
                        state.lifecycle_writer_orphan_observed or orphaned
                    ),
                    lifecycle_writer_orphan_recovered=(
                        state.lifecycle_writer_orphan_recovered or recovered
                    ),
                    lifecycle_writer_reentrant_observed=(
                        state.lifecycle_writer_reentrant_observed or reentrant
                    ),
                    lifecycle_writer_reentrant_safe=(
                        state.lifecycle_writer_reentrant_safe or reentrant_safe
                    ),
                    lifecycle_writer_release_attempted=(
                        state.lifecycle_writer_release_attempted
                        or release_attempted
                    ),
                    lifecycle_writer_release_succeeded=(
                        state.lifecycle_writer_release_succeeded
                        or release_succeeded
                    ),
                    lifecycle_writer_release_failure_visible=(
                        state.lifecycle_writer_release_failure_visible
                        or release_failure_visible
                    ),
                ),
                (
                    "lifecycle_writer_reentrant_safe"
                    if reentrant
                    else "lifecycle_writer_released"
                    if release_succeeded
                    else "lifecycle_writer_release_failed_visible"
                    if release_failure_visible
                    else "lifecycle_writer_release_failure_hidden"
                ),
            )
            return

        if input_obj.kind == "validation_timeout":
            child_timeout = max(0, input_obj.child_timeout_seconds)
            parent_timeout = max(0, input_obj.parent_timeout_seconds)
            if self.broken_mode == "timeout_hierarchy_collapse":
                parent_timeout = child_timeout
            remaining = (
                input_obj.process_tree_count
                if self.broken_mode == "orphan_process_tree"
                else 0
                if input_obj.cleanup_confirmed
                else input_obj.process_tree_count
            )
            yield FunctionResult(
                LifecycleOutput(
                    "timed_out_process_tree_cleaned"
                    if remaining == 0
                    else "timed_out_process_tree_orphaned"
                ),
                replace(
                    state,
                    validation_timeout_observed=True,
                    validation_child_timeout_seconds=child_timeout,
                    validation_parent_timeout_seconds=parent_timeout,
                    remaining_process_count=remaining,
                ),
                (
                    "timed_out_process_tree_cleaned"
                    if remaining == 0
                    else "timed_out_process_tree_orphaned"
                ),
            )
            return

        if input_obj.kind == "sleep_fail":
            failed_state = state
            if self.broken_mode == "premature_watermark":
                failed_state = replace(state, watermark=state.watermark + 1)
            yield FunctionResult(
                LifecycleOutput("sleep_failed", input_obj.item_id),
                failed_state,
                "sleep_failed",
            )
            return

        if input_obj.kind == "sleep_commit":
            item_id = input_obj.item_id
            disposition_key = f"{item_id}={input_obj.disposition}"
            if item_id not in state.admitted:
                yield FunctionResult(
                    LifecycleOutput("sleep_blocked_unadmitted", item_id),
                    state,
                    "sleep_blocked_unadmitted",
                )
                return
            if any(value.startswith(f"{item_id}=") for value in state.dispositions):
                yield FunctionResult(
                    LifecycleOutput("sleep_disposition_reused", item_id),
                    state,
                    "sleep_disposition_reused",
                )
                return
            statuses = state.entry_statuses
            if input_obj.disposition in ACTIVE_STATUSES | TERMINAL_STATUSES:
                statuses = _replace_pair(statuses, item_id, input_obj.disposition)
            dispositions = state.dispositions + (disposition_key,)
            eligible = state.candidate_eligible
            eligibility_evidence = state.candidate_eligibility_evidence
            if input_obj.disposition != "candidate":
                eligible = tuple(item for item in eligible if item != item_id)
                eligibility_evidence = tuple(
                    item for item in eligibility_evidence if item != item_id
                )
            active_index = _eligible_index(statuses, eligible)
            yield FunctionResult(
                LifecycleOutput("sleep_committed", item_id),
                replace(
                    state,
                    dispositions=dispositions,
                    entry_statuses=statuses,
                    candidate_eligible=eligible,
                    candidate_eligibility_evidence=eligibility_evidence,
                    active_index=active_index,
                    actionable_backlog=max(0, state.actionable_backlog - 1),
                    watermark=len(dispositions),
                    index_generation=state.index_generation + 1,
                ),
                "sleep_committed",
            )
            return

        if input_obj.kind == "candidate_transition":
            statuses = _replace_pair(state.entry_statuses, input_obj.item_id, input_obj.status)
            eligible = tuple(item for item in state.candidate_eligible if item != input_obj.item_id)
            eligibility_evidence = tuple(
                item
                for item in state.candidate_eligibility_evidence
                if item != input_obj.item_id
            )
            if input_obj.status == "candidate" and input_obj.retrieval_eligible:
                eligible = _append_unique(eligible, input_obj.item_id)
                eligibility_evidence = _append_unique(
                    eligibility_evidence, input_obj.item_id
                )
            if self.broken_mode == "candidate_leak" and input_obj.status == "candidate":
                eligible = _append_unique(eligible, input_obj.item_id)
            label = f"candidate_set_{input_obj.status}"
            yield FunctionResult(
                LifecycleOutput(label, input_obj.item_id),
                replace(
                    state,
                    entry_statuses=statuses,
                    candidate_eligible=eligible,
                    candidate_eligibility_evidence=eligibility_evidence,
                    active_index=_eligible_index(statuses, eligible),
                    index_generation=state.index_generation + 1,
                ),
                label,
            )
            return

        if input_obj.kind == "candidate_observe":
            if input_obj.source_boundary != "organization-read-only":
                yield FunctionResult(
                    LifecycleOutput("local_candidate_observation_blocked", input_obj.item_id),
                    state,
                    "local_candidate_observation_blocked",
                )
                return
            active_index = state.active_index
            if self.broken_mode == "candidate_source_collapse":
                active_index = _append_unique(active_index, input_obj.item_id)
            yield FunctionResult(
                LifecycleOutput("organization_candidate_visible_untrusted", input_obj.item_id),
                replace(
                    state,
                    organization_candidates=_append_unique(
                        state.organization_candidates, input_obj.item_id
                    ),
                    active_index=active_index,
                ),
                "organization_candidate_visible_untrusted",
            )
            return

        if input_obj.kind == "index_rebuild":
            yield FunctionResult(
                LifecycleOutput("index_rebuilt"),
                replace(
                    state,
                    active_index=_eligible_index(state.entry_statuses, state.candidate_eligible),
                    index_generation=state.index_generation + 1,
                ),
                "index_rebuilt",
            )
            return

        if input_obj.kind == "query":
            full_replays = state.foreground_full_replays
            label = "query_fast_authority"
            if self.broken_mode == "foreground_full_replay":
                full_replays += 1
                label = "query_full_authority_replay"
            yield FunctionResult(
                LifecycleOutput(label),
                replace(state, foreground_full_replays=full_replays),
                label,
            )
            return

        if input_obj.kind == "dream_complete":
            fingerprint = input_obj.fingerprint
            if fingerprint in state.dream_closed:
                repeated = state
                if self.broken_mode == "repeat_dream_write":
                    repeated = replace(
                        state,
                        dream_writes=state.dream_writes + (fingerprint,),
                        sleep_handoffs=state.sleep_handoffs + (fingerprint,),
                    )
                yield FunctionResult(
                    LifecycleOutput("no_delta_closed", fingerprint=fingerprint),
                    replace(
                        repeated,
                        cooldown_closed=_append_unique(repeated.cooldown_closed, fingerprint),
                    ),
                    "no_delta_closed",
                )
                return
            yield FunctionResult(
                LifecycleOutput("dream_handoff_emitted", fingerprint=fingerprint),
                replace(
                    state,
                    dream_closed=state.dream_closed + (fingerprint,),
                    dream_writes=state.dream_writes + (fingerprint,),
                    sleep_handoffs=state.sleep_handoffs + (fingerprint,),
                    pending_handoffs=state.pending_handoffs + (fingerprint,),
                ),
                "dream_handoff_emitted",
            )
            return

        if input_obj.kind == "commit_handoff_model":
            fingerprint = input_obj.fingerprint
            if fingerprint not in state.pending_handoffs:
                yield FunctionResult(
                    LifecycleOutput("handoff_model_commit_blocked", fingerprint=fingerprint),
                    state,
                    "handoff_model_commit_blocked",
                )
                return
            yield FunctionResult(
                LifecycleOutput("handoff_model_committed", fingerprint=fingerprint),
                replace(
                    state,
                    handoff_model_commits=_append_unique(
                        state.handoff_model_commits,
                        fingerprint,
                    ),
                ),
                "handoff_model_committed",
            )
            return

        if input_obj.kind == "ack_handoff":
            fingerprint = input_obj.fingerprint
            if fingerprint not in state.pending_handoffs:
                yield FunctionResult(
                    LifecycleOutput("handoff_ack_blocked", fingerprint=fingerprint),
                    state,
                    "handoff_ack_blocked",
                )
                return
            if (
                fingerprint not in state.handoff_model_commits
                and self.broken_mode != "handoff_ack_before_model_publication"
            ):
                yield FunctionResult(
                    LifecycleOutput("handoff_ack_waits_for_model", fingerprint=fingerprint),
                    state,
                    "handoff_ack_waits_for_model",
                )
                return
            next_state = replace(
                state,
                pending_handoffs=tuple(item for item in state.pending_handoffs if item != fingerprint),
                handoff_acks=_append_unique(state.handoff_acks, fingerprint),
            )
            if self.broken_mode == "missing_ack":
                next_state = replace(next_state, handoff_acks=state.handoff_acks)
            yield FunctionResult(
                LifecycleOutput("handoff_acknowledged", fingerprint=fingerprint),
                next_state,
                "handoff_acknowledged",
            )


def lifecycle_terminal(output: object, state: LifecycleState, trace: object) -> bool:
    del state, trace
    return isinstance(output, LifecycleOutput) and output.label.startswith("sleep_blocked")


def lifecycle_watermark_is_committed(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    if state.watermark > len(state.dispositions):
        return InvariantResult.fail("watermark advanced beyond durable dispositions")
    disposed_ids = {value.partition("=")[0] for value in state.dispositions}
    if not disposed_ids.issubset(set(state.admitted)):
        return InvariantResult.fail("a disposition references an unadmitted observation")
    return InvariantResult.pass_()


def lifecycle_dream_is_at_most_once(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    for field in ("dream_closed", "dream_writes", "sleep_handoffs"):
        values = getattr(state, field)
        if len(values) != len(set(values)):
            return InvariantResult.fail(f"{field} contains duplicate evidence fingerprints")
    if set(state.dream_writes) != set(state.sleep_handoffs):
        return InvariantResult.fail("Dream writes and typed Sleep handoffs diverged")
    return InvariantResult.pass_()


def lifecycle_index_contains_only_eligible(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    unattested = set(state.candidate_eligible) - set(
        state.candidate_eligibility_evidence
    )
    if unattested:
        return InvariantResult.fail(
            "candidate retrieval eligibility lacks explicit evidence: "
            f"{tuple(sorted(unattested))!r}"
        )
    expected = _eligible_index(state.entry_statuses, state.candidate_eligible)
    if state.active_index != expected:
        return InvariantResult.fail(
            f"active index {state.active_index!r} does not equal eligible set {expected!r}"
        )
    statuses = _pairs(state.entry_statuses)
    leaked = tuple(
        item_id
        for item_id in state.active_index
        if statuses.get(item_id) in TERMINAL_STATUSES
    )
    if leaked:
        return InvariantResult.fail(f"terminal entries leaked into active index: {leaked!r}")
    source_leaks = set(state.organization_candidates) & set(state.active_index)
    if source_leaks:
        return InvariantResult.fail(
            "read-only organization candidates leaked into the local active index: "
            f"{tuple(sorted(source_leaks))!r}"
        )
    return InvariantResult.pass_()


def lifecycle_backlog_and_handoffs_progress(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    if state.actionable_backlog < 0:
        return InvariantResult.fail("actionable backlog became negative")
    disposed = len(state.dispositions)
    if state.actionable_backlog != max(0, len(state.admitted) - disposed):
        return InvariantResult.fail("actionable backlog does not match admitted minus disposed observations")
    if not set(state.handoff_acks).issubset(set(state.sleep_handoffs)):
        return InvariantResult.fail("a handoff acknowledgement lacks a Dream handoff")
    if not set(state.handoff_acks).issubset(set(state.handoff_model_commits)):
        return InvariantResult.fail(
            "a Dream handoff was acknowledged before its model publication committed"
        )
    if not set(state.handoff_model_commits).issubset(set(state.sleep_handoffs)):
        return InvariantResult.fail(
            "a handoff model commit lacks a Dream handoff"
        )
    if set(state.handoff_acks) & set(state.pending_handoffs):
        return InvariantResult.fail("a handoff is both pending and acknowledged")
    if set(state.sleep_handoffs) != set(state.pending_handoffs) | set(state.handoff_acks):
        return InvariantResult.fail("a Dream handoff is neither pending nor acknowledged")
    if len(state.handoff_acks) != len(set(state.handoff_acks)):
        return InvariantResult.fail("a Dream handoff was acknowledged more than once")
    return InvariantResult.pass_()


def lifecycle_query_does_not_replay_full_authority(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    if state.foreground_full_replays:
        return InvariantResult.fail(
            "foreground retrieval replayed the full card manifest or lifecycle authority"
        )
    return InvariantResult.pass_()


def lifecycle_sleep_resume_is_scale_bounded(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    if state.sleep_resume_pending_count == 0:
        if state.sleep_resume_replay_passes or state.sleep_resume_batch_count:
            return InvariantResult.fail(
                "terminal Sleep history replayed lifecycle authority instead of advancing the cursor"
            )
        return InvariantResult.pass_()
    if (
        state.sleep_resume_replay_passes != 2
        or state.sleep_resume_batch_count != 1
    ):
        return InvariantResult.fail(
            "Sleep resume used per-item lifecycle replay instead of one atomic batch"
        )
    return InvariantResult.pass_()


def lifecycle_replay_uses_linear_idempotency_index(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    if state.lifecycle_replay_membership_checks > state.lifecycle_replay_event_count:
        return InvariantResult.fail(
            "lifecycle replay used a quadratic duplicate-key scan instead of one indexed membership check per event"
        )
    return InvariantResult.pass_()


def lifecycle_runtime_recovery_is_bounded(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    if state.dead_lane_lock_observed and not state.dead_lane_lock_recovered:
        return InvariantResult.fail("a dead recorded lane-lock owner remained blocking")
    if (
        state.lifecycle_writer_orphan_observed
        and not state.lifecycle_writer_orphan_recovered
    ):
        return InvariantResult.fail(
            "a dead or interrupted lifecycle writer remained permanently blocking"
        )
    if (
        state.lifecycle_writer_reentrant_observed
        and not state.lifecycle_writer_reentrant_safe
    ):
        return InvariantResult.fail(
            "the active lifecycle writer deadlocked on its own lock"
        )
    if (
        state.lifecycle_writer_release_attempted
        and not state.lifecycle_writer_release_succeeded
        and not state.lifecycle_writer_release_failure_visible
    ):
        return InvariantResult.fail(
            "lifecycle writer release failed without a visible terminal failure"
        )
    if state.validation_timeout_observed:
        if state.remaining_process_count:
            return InvariantResult.fail("a timed-out validation left descendant processes")
        if (
            state.validation_parent_timeout_seconds
            <= state.validation_child_timeout_seconds
        ):
            return InvariantResult.fail(
                "parent validation timeout has no cleanup margin beyond its child"
            )
    return InvariantResult.pass_()


def lifecycle_candidate_review_uses_one_evidence_index(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    if state.candidate_review_count and state.calibration_evidence_load_count != 1:
        return InvariantResult.fail(
            "candidate review reloaded full calibration evidence once per entry"
        )
    if state.parked_recalibration_count != state.parked_evidence_delta_count:
        return InvariantResult.fail(
            "parked candidates were semantically re-reviewed without new evidence"
        )
    if state.parked_calibration_snapshot_count != state.parked_evidence_delta_count:
        return InvariantResult.fail(
            "a parked evidence delta was reviewed without persisting its calibration watermark"
        )
    return InvariantResult.pass_()


def lifecycle_sleep_index_has_one_final_owner(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    if state.sleep_model_publication_count > 1:
        return InvariantResult.fail(
            "one no-delta Sleep cycle republished the same model generation"
        )
    if state.sleep_index_rebuild_count > 1:
        return InvariantResult.fail(
            "one Sleep cycle rebuilt the same final active-index generation more than once"
        )
    if state.sleep_index_validation_count > 1:
        return InvariantResult.fail(
            "one Sleep cycle revalidated an unchanged final active-index receipt"
        )
    return InvariantResult.pass_()


def lifecycle_shareability_is_total(
    state: LifecycleState, trace: object
) -> InvariantResult:
    del trace
    if not state.shareability_serialization_ok:
        return InvariantResult.fail(
            "a standard YAML date crashed organization shareability validation"
        )
    if state.privacy_false_positive_count:
        return InvariantResult.fail(
            "the privacy scanner treated its own declared path patterns as leaked data"
        )
    return InvariantResult.pass_()


LIFECYCLE_INVARIANTS = (
    Invariant(
        "watermark_after_disposition_commit",
        "Sleep watermark never advances beyond committed dispositions",
        lifecycle_watermark_is_committed,
    ),
    Invariant(
        "dream_fingerprint_at_most_once",
        "Unchanged Dream evidence produces at most one write and one Sleep handoff",
        lifecycle_dream_is_at_most_once,
    ),
    Invariant(
        "active_index_status_safe",
        "Only current trusted or eligible candidate entries appear in the active index",
        lifecycle_index_contains_only_eligible,
    ),
    Invariant(
        "backlog_and_handoff_progress",
        "Actionable backlog decreases on dispositions and every Dream handoff has at most one acknowledgement",
        lifecycle_backlog_and_handoffs_progress,
    ),
    Invariant(
        "foreground_query_uses_fast_authority",
        "Routine retrieval validates a compact fail-closed authority snapshot instead of replaying full history",
        lifecycle_query_does_not_replay_full_authority,
    ),
    Invariant(
        "sleep_resume_uses_terminal_fast_path_or_atomic_batch",
        "Sleep skips already-terminal history and batches genuinely pending lifecycle events",
        lifecycle_sleep_resume_is_scale_bounded,
    ),
    Invariant(
        "lifecycle_replay_uses_linear_idempotency_index",
        "Lifecycle replay preserves ordered keys while duplicate detection remains linear in event count",
        lifecycle_replay_uses_linear_idempotency_index,
    ),
    Invariant(
        "runtime_timeout_and_dead_lock_recovery_are_bounded",
        "Dead lane owners are recovered, timeouts preserve cleanup margin, and descendants reach zero",
        lifecycle_runtime_recovery_is_bounded,
    ),
    Invariant(
        "candidate_review_reuses_one_evidence_index",
        "One Sleep review cycle loads calibration evidence once for all candidates",
        lifecycle_candidate_review_uses_one_evidence_index,
    ),
    Invariant(
        "sleep_index_has_one_final_owner",
        "One Sleep cycle rebuilds only after an index-affecting delta and validates the final generation once",
        lifecycle_sleep_index_has_one_final_owner,
    ),
    Invariant(
        "shareability_inputs_are_total",
        "Standard dates serialize and scanner pattern definitions do not self-match",
        lifecycle_shareability_is_total,
    ),
)

LIFECYCLE_INPUTS = (
    LifecycleInput("admit", item_id="obs-1"),
    LifecycleInput("sleep_commit", item_id="obs-1", disposition="candidate"),
    LifecycleInput("sleep_fail", item_id="obs-1"),
    LifecycleInput("candidate_transition", item_id="card-1", status="trusted"),
    LifecycleInput("candidate_transition", item_id="card-1", status="candidate", retrieval_eligible=False),
    LifecycleInput("candidate_transition", item_id="card-1", status="candidate", retrieval_eligible=True),
    LifecycleInput("candidate_transition", item_id="card-1", status="rejected"),
    LifecycleInput(
        "candidate_observe",
        item_id="org-card-1",
        status="candidate",
        retrieval_eligible=False,
        source_boundary="organization-read-only",
    ),
    LifecycleInput("index_rebuild"),
    LifecycleInput("query"),
    LifecycleInput(
        "sleep_resume",
        row_count=3,
        terminal_count=0,
        processing_mode="atomic-batch",
    ),
    LifecycleInput(
        "sleep_resume",
        row_count=3,
        terminal_count=3,
        processing_mode="atomic-batch",
    ),
    LifecycleInput("lifecycle_replay", row_count=73_680),
    LifecycleInput("acquire_lane_lock", owner_alive=False),
    LifecycleInput("acquire_lane_lock", owner_alive=True),
    LifecycleInput(
        "lifecycle_writer_lock",
        owner_alive=False,
        owner_recorded=True,
    ),
    LifecycleInput(
        "lifecycle_writer_lock",
        owner_alive=False,
        owner_recorded=False,
    ),
    LifecycleInput(
        "lifecycle_writer_lock",
        owner_alive=True,
        owner_recorded=True,
        same_thread_active=True,
    ),
    LifecycleInput(
        "lifecycle_writer_lock",
        owner_alive=False,
        owner_recorded=True,
        release_succeeds=False,
    ),
    LifecycleInput(
        "validation_timeout",
        process_tree_count=3,
        cleanup_confirmed=True,
        child_timeout_seconds=900,
        parent_timeout_seconds=1200,
    ),
    LifecycleInput(
        "candidate_review",
        row_count=3000,
        parked_count=2990,
        parked_evidence_delta_count=2,
    ),
    LifecycleInput("sleep_index_finalize", index_delta=False),
    LifecycleInput("sleep_index_finalize", index_delta=True),
    LifecycleInput("shareability_check", contains_yaml_date=True),
    LifecycleInput("shareability_check", scanner_definition_only=True),
    LifecycleInput("dream_complete", fingerprint="dream-fp-1"),
    LifecycleInput("commit_handoff_model", fingerprint="dream-fp-1"),
    LifecycleInput("ack_handoff", fingerprint="dream-fp-1"),
)

LIFECYCLE_INITIAL_STATES = (
    LifecycleState(),
    LifecycleState(admitted=("obs-1",), actionable_backlog=1),
    LifecycleState(
        entry_statuses=("card-1=candidate",),
        candidate_eligible=("card-1",),
        candidate_eligibility_evidence=("card-1",),
        active_index=("card-1",),
        index_generation=1,
    ),
    LifecycleState(
        dream_closed=("dream-fp-1",),
        dream_writes=("dream-fp-1",),
        sleep_handoffs=("dream-fp-1",),
        pending_handoffs=("dream-fp-1",),
    ),
    LifecycleState(
        admitted=("terminal-1", "terminal-2", "terminal-3"),
        dispositions=(
            "terminal-1=history_only",
            "terminal-2=history_only",
            "terminal-3=history_only",
        ),
    ),
)


def lifecycle_workflow(*, broken_mode: str = "") -> Workflow:
    return Workflow(
        (LifecycleConvergenceBlock(broken_mode=broken_mode),),
        name=f"kb_lifecycle_convergence{('_' + broken_mode) if broken_mode else ''}",
    )


@dataclass(frozen=True)
class MigrationInput:
    kind: str
    context: str = "outer-upgrade"
    item_count: int = 1
    replay_passes: int = 2
    batch_count: int = 1
    reused_count: int = 0


@dataclass(frozen=True)
class MigrationOutput:
    label: str


@dataclass(frozen=True)
class MigrationState:
    phase: str = "idle"
    checkpoint: str = "idle"
    automations_paused: bool = False
    architect_present: bool = True
    rollback_ref: str = ""
    classified: bool = False
    runtime_canonicalized: bool = False
    obsolete_runtime_residual_count: int = 0
    canonicalization_receipt_count: int = 0
    debt_settled: bool = False
    settlement_mode: str = "atomic-batch"
    settlement_event_count: int = 1
    settlement_replay_passes: int = 2
    settlement_batch_count: int = 1
    settlement_reused_count: int = 0
    archive_ready: bool = False
    pruned: bool = False
    prune_verified_read_only_count: int = 0
    prune_read_only_cleared_count: int = 0
    prune_resumed_deleted_count: int = 0
    prune_permission_blocker_count: int = 0
    index_ready: bool = False
    validation_passed: bool = False
    committed_version: int = 0
    active_failure: bool = False
    resolved_failure_count: int = 0
    migration_lock_recovery_receipt_count: int = 0
    migration_lock_recovery_reason: str = ""
    live_migration_lock_stolen: bool = False
    recent_ownerless_lock_stolen: bool = False
    managed_surface_reintroduced_count: int = 0
    managed_surface_residual_count: int = 0
    reconciliation_receipt_count: int = 0
    managed_long_path_count: int = 0
    managed_enumerated_path_count: int = 0
    post_commit_observation_debt_count: int = 0
    logical_reconciliation_receipt_count: int = 0
    prior_automation_states: tuple[str, ...] = (
        "kb-sleep=ACTIVE",
        "kb-dream=PAUSED",
        "khaos-brain-system-update=ACTIVE",
        "kb-org-contribute=ACTIVE",
        "kb-org-maintenance=PAUSED",
    )
    restored_automation_states: tuple[str, ...] = ()
    staged_manifests_match: bool = False
    source_fingerprint_current: bool = False
    authority_install_policy_id: str = ""
    incoming_current_compiler_validated: bool = False
    authority_validation_identity_stable: bool = False
    authority_validation_snapshot_current: bool = False
    authority_validation_toolchains: tuple[str, ...] = ()
    active_managed_tree_class: str = ""
    whole_tree_replacement_staged: bool = False
    active_semantic_comparison_performed: bool = False
    anti_downgrade_comparison_basis: str = ""
    semantic_hard_authority_preserved: bool = False
    current_to_current_anti_downgrade_passed: bool = False
    authority_install_receipt_replay_current: bool = False
    authority_install_member_count: int = 0
    rollback_verified: bool = False
    install_transaction_committed: bool = False
    skillguard_surface_fingerprint: str = ""
    router_refresh_receipt: str = ""
    router_refresh_receipt_durable: bool = False
    router_refresh_receipt_current: bool = False
    router_refresh_surface_fingerprint: str = ""
    live_registry_fingerprint: str = ""
    live_registry_surface_fingerprint: str = ""
    live_registry_current: bool = False
    live_prompt_registry_fingerprint: str = ""
    live_prompt_current: bool = False
    router_refresh_required: bool = False
    router_refresh_count: int = 0
    skillguard_surface_drift_count: int = 0
    assurance_context: str = ""
    assurance_depth: int = 0
    fixture_gates_skipped: bool = False
    fixture_shell_isolated: bool = False
    post_assurance_data_current: bool = False
    aggregate_assurance_passed: bool = False
    aggregate_assurance_current: bool = False
    aggregate_assurance_receipt: str = ""
    full_regression_execution_count: int = 0
    full_regression_reuse_count: int = 0
    full_regression_duplicate_current_execution_count: int = 0
    full_regression_receipt_current: bool = False
    aggregate_script_import_current: bool = True
    performance_validation_lane_exclusive: bool = False
    scheduled_production_validation_lane_exclusive: bool = False
    post_commit_assurance_failure_count: int = 0
    post_commit_assurance_retry_count: int = 0
    post_commit_assurance_failure_pending: bool = False
    side_effects: tuple[str, ...] = ()


SURVIVING_AUTOMATIONS = (
    "kb-sleep",
    "kb-dream",
    "khaos-brain-system-update",
    "kb-org-contribute",
    "kb-org-maintenance",
)

CURRENT_SKILLGUARD_SURFACE_FINGERPRINT = "skillguard-surface:managed-current"
AUTHORITY_INSTALL_POLICY_ID = "skillguard.managed-whole-tree-currentness.v1"
AUTHORITY_INSTALL_MEMBER_COUNT = 5
CURRENT_AUTHORITY_VALIDATION_TOOLCHAINS = (
    "skillguard",
    "flowguard",
    "logicguard",
)
CURRENT_AUTHORITY_INSTALL_BINDING: dict[str, object] = {
    "authority_install_policy_id": AUTHORITY_INSTALL_POLICY_ID,
    "incoming_current_compiler_validated": True,
    "authority_validation_identity_stable": True,
    "authority_validation_snapshot_current": True,
    "authority_validation_toolchains": CURRENT_AUTHORITY_VALIDATION_TOOLCHAINS,
    "active_managed_tree_class": "opaque-noncurrent",
    "whole_tree_replacement_staged": True,
    "active_semantic_comparison_performed": False,
    "anti_downgrade_comparison_basis": "",
    "semantic_hard_authority_preserved": False,
    "current_to_current_anti_downgrade_passed": False,
    "authority_install_receipt_replay_current": True,
    "authority_install_member_count": AUTHORITY_INSTALL_MEMBER_COUNT,
}
CURRENT_ROUTER_REGISTRY_FINGERPRINT = (
    f"router-registry:{CURRENT_SKILLGUARD_SURFACE_FINGERPRINT}:1"
)
CURRENT_ROUTER_REFRESH_RECEIPT = (
    f"router-refresh:{CURRENT_ROUTER_REGISTRY_FINGERPRINT}"
)
CURRENT_ROUTER_BINDING: dict[str, object] = {
    "skillguard_surface_fingerprint": CURRENT_SKILLGUARD_SURFACE_FINGERPRINT,
    "router_refresh_receipt": CURRENT_ROUTER_REFRESH_RECEIPT,
    "router_refresh_receipt_durable": True,
    "router_refresh_receipt_current": True,
    "router_refresh_surface_fingerprint": CURRENT_SKILLGUARD_SURFACE_FINGERPRINT,
    "live_registry_fingerprint": CURRENT_ROUTER_REGISTRY_FINGERPRINT,
    "live_registry_surface_fingerprint": CURRENT_SKILLGUARD_SURFACE_FINGERPRINT,
    "live_registry_current": True,
    "live_prompt_registry_fingerprint": CURRENT_ROUTER_REGISTRY_FINGERPRINT,
    "live_prompt_current": True,
    "router_refresh_required": False,
    "router_refresh_count": 1,
}


def _router_refresh_binding(
    state: MigrationState,
    *,
    surface_fingerprint: str | None = None,
    stale_prompt: bool = False,
    missing_receipt: bool = False,
) -> dict[str, object]:
    """Return one refresh receipt plus the two independent live freshness bindings."""

    surface = surface_fingerprint or state.skillguard_surface_fingerprint
    refresh_count = state.router_refresh_count + 1
    registry_fingerprint = f"router-registry:{surface}:{refresh_count}"
    prompt_registry_fingerprint = (
        state.live_registry_fingerprint or "router-registry:pre-refresh"
        if stale_prompt
        else registry_fingerprint
    )
    return {
        "skillguard_surface_fingerprint": surface,
        "router_refresh_receipt": (
            "" if missing_receipt else f"router-refresh:{registry_fingerprint}"
        ),
        "router_refresh_receipt_durable": not missing_receipt,
        "router_refresh_receipt_current": not missing_receipt,
        "router_refresh_surface_fingerprint": surface,
        "live_registry_fingerprint": registry_fingerprint,
        "live_registry_surface_fingerprint": surface,
        "live_registry_current": True,
        "live_prompt_registry_fingerprint": prompt_registry_fingerprint,
        "live_prompt_current": True,
        "router_refresh_required": False,
        "router_refresh_count": refresh_count,
    }


def _router_refresh_is_current(state: MigrationState) -> bool:
    return bool(
        state.skillguard_surface_fingerprint
        and state.router_refresh_receipt
        and state.router_refresh_receipt_durable
        and state.router_refresh_receipt_current
        and state.router_refresh_surface_fingerprint
        == state.skillguard_surface_fingerprint
        and state.live_registry_fingerprint
        and state.live_registry_surface_fingerprint
        == state.skillguard_surface_fingerprint
        and state.live_registry_current
        and state.live_prompt_registry_fingerprint
        == state.live_registry_fingerprint
        and state.live_prompt_current
        and not state.router_refresh_required
    )


class UpgradeMigrationBlock:
    name = "UpgradeMigrationBlock"
    reads = (
        "phase",
        "checkpoint",
        "automations_paused",
        "architect_present",
        "rollback_ref",
        "classified",
        "runtime_canonicalized",
        "obsolete_runtime_residual_count",
        "canonicalization_receipt_count",
        "debt_settled",
        "settlement_mode",
        "settlement_event_count",
        "settlement_replay_passes",
        "settlement_batch_count",
        "settlement_reused_count",
        "archive_ready",
        "pruned",
        "prune_verified_read_only_count",
        "prune_read_only_cleared_count",
        "prune_resumed_deleted_count",
        "prune_permission_blocker_count",
        "index_ready",
        "validation_passed",
        "committed_version",
        "active_failure",
        "resolved_failure_count",
        "migration_lock_recovery_receipt_count",
        "migration_lock_recovery_reason",
        "live_migration_lock_stolen",
        "recent_ownerless_lock_stolen",
        "managed_surface_reintroduced_count",
        "managed_surface_residual_count",
        "reconciliation_receipt_count",
        "managed_long_path_count",
        "managed_enumerated_path_count",
        "post_commit_observation_debt_count",
        "logical_reconciliation_receipt_count",
        "prior_automation_states",
        "staged_manifests_match",
        "source_fingerprint_current",
        "authority_install_policy_id",
        "incoming_current_compiler_validated",
        "authority_validation_identity_stable",
        "authority_validation_snapshot_current",
        "authority_validation_toolchains",
        "active_managed_tree_class",
        "whole_tree_replacement_staged",
        "active_semantic_comparison_performed",
        "anti_downgrade_comparison_basis",
        "semantic_hard_authority_preserved",
        "current_to_current_anti_downgrade_passed",
        "authority_install_receipt_replay_current",
        "authority_install_member_count",
        "rollback_verified",
        "install_transaction_committed",
        "skillguard_surface_fingerprint",
        "router_refresh_receipt",
        "router_refresh_receipt_durable",
        "router_refresh_receipt_current",
        "router_refresh_surface_fingerprint",
        "live_registry_fingerprint",
        "live_registry_surface_fingerprint",
        "live_registry_current",
        "live_prompt_registry_fingerprint",
        "live_prompt_current",
        "router_refresh_required",
        "router_refresh_count",
        "skillguard_surface_drift_count",
        "assurance_context",
        "assurance_depth",
        "fixture_gates_skipped",
        "fixture_shell_isolated",
        "post_assurance_data_current",
        "aggregate_assurance_passed",
        "aggregate_assurance_current",
        "aggregate_assurance_receipt",
        "full_regression_execution_count",
        "full_regression_reuse_count",
        "full_regression_duplicate_current_execution_count",
        "full_regression_receipt_current",
        "aggregate_script_import_current",
        "performance_validation_lane_exclusive",
        "scheduled_production_validation_lane_exclusive",
        "post_commit_assurance_failure_count",
        "post_commit_assurance_retry_count",
        "post_commit_assurance_failure_pending",
    )
    writes = reads + (
        "prior_automation_states",
        "restored_automation_states",
        "staged_manifests_match",
        "source_fingerprint_current",
        "rollback_verified",
        "install_transaction_committed",
        "assurance_context",
        "assurance_depth",
        "fixture_gates_skipped",
        "fixture_shell_isolated",
        "post_assurance_data_current",
        "side_effects",
    )
    accepted_input_type = MigrationInput
    input_description = "one versioned migration checkpoint event"
    output_description = "checkpoint, block, resume, rollback, or restore decision"
    idempotency = (
        "Each phase has one stable side-effect id; repeated events reuse the committed "
        "checkpoint and never duplicate deletion, archive, install, or restore effects."
    )

    def __init__(self, *, broken_mode: str = "") -> None:
        self.broken_mode = broken_mode

    def _emit(
        self, label: str, state: MigrationState, **changes: object
    ) -> Iterable[FunctionResult]:
        yield FunctionResult(
            MigrationOutput(label), replace(state, **changes), label
        )

    def apply(
        self, input_obj: MigrationInput, state: MigrationState
    ) -> Iterable[FunctionResult]:
        kind = input_obj.kind
        if kind == "recover_migration_lock":
            if input_obj.context == "live-owner":
                if self.broken_mode == "live_migration_lock_stolen":
                    yield from self._emit(
                        "live_migration_lock_wrongly_recovered",
                        state,
                        migration_lock_recovery_receipt_count=(
                            state.migration_lock_recovery_receipt_count + 1
                        ),
                        migration_lock_recovery_reason="live-owner",
                        live_migration_lock_stolen=True,
                    )
                    return
                yield from self._emit("migration_lock_live_owner_blocked", state)
                return
            if input_obj.context == "legacy-recent":
                if self.broken_mode == "recent_ownerless_lock_stolen":
                    yield from self._emit(
                        "recent_ownerless_lock_wrongly_recovered",
                        state,
                        migration_lock_recovery_receipt_count=(
                            state.migration_lock_recovery_receipt_count + 1
                        ),
                        migration_lock_recovery_reason="legacy-recent",
                        recent_ownerless_lock_stolen=True,
                    )
                    return
                yield from self._emit("migration_lock_recent_ownerless_blocked", state)
                return
            if input_obj.context not in {"dead-owner", "legacy-stale"}:
                yield from self._emit("migration_lock_unknown_owner_blocked", state)
                return
            yield from self._emit(
                "stale_migration_lock_recovered",
                state,
                migration_lock_recovery_receipt_count=(
                    state.migration_lock_recovery_receipt_count + 1
                ),
                migration_lock_recovery_reason=input_obj.context,
                side_effects=_append_unique(state.side_effects, "migration-lock-recovery"),
            )
            return
        if kind == "assurance_invoke":
            if input_obj.context in {"aggregate-child", "isolated-fixture"}:
                if state.phase != "idle":
                    yield from self._emit("assurance_child_context_blocked", state)
                    return
                recursive = self.broken_mode == "recursive_assurance"
                yield from self._emit(
                    "assurance_child_isolated",
                    state,
                    assurance_context=input_obj.context,
                    assurance_depth=state.assurance_depth + 1 if recursive else 0,
                    fixture_gates_skipped=not recursive,
                    fixture_shell_isolated=(
                        self.broken_mode != "fixture_global_shell_side_effect"
                    ),
                )
                return
            yield from self._emit(
                "assurance_outer_started",
                state,
                assurance_context="outer-upgrade",
                assurance_depth=max(1, state.assurance_depth),
                fixture_gates_skipped=False,
                fixture_shell_isolated=False,
            )
            return

        if kind == "begin":
            if state.fixture_gates_skipped:
                yield from self._emit("fixture_migration_blocked", state)
                return
            if state.phase != "idle":
                yield from self._emit("migration_begin_reused", state)
                return
            yield from self._emit(
                "migration_begun",
                state,
                phase="preflight",
                checkpoint="preflight",
                automations_paused=True,
                rollback_ref="snapshot:pre-upgrade",
            )
            return

        if kind == "inventory_managed_path":
            is_long = input_obj.context == "windows-long"
            invisible = is_long and self.broken_mode == "long_path_invisible"
            yield from self._emit(
                "managed_path_inventoried" if not invisible else "managed_long_path_missed",
                state,
                managed_long_path_count=(
                    state.managed_long_path_count + (1 if is_long else 0)
                ),
                managed_enumerated_path_count=(
                    state.managed_enumerated_path_count + (0 if invisible else 1)
                ),
            )
            return

        if kind == "snapshot":
            if state.phase != "preflight":
                yield from self._emit("snapshot_blocked", state)
                return
            yield from self._emit(
                "snapshot_committed", state, phase="snapshot", checkpoint="snapshot"
            )
            return

        if kind == "classify":
            if state.phase != "snapshot":
                yield from self._emit("classify_blocked", state)
                return
            yield from self._emit(
                "classification_committed",
                state,
                phase="classify",
                checkpoint="classify",
                classified=True,
            )
            return

        if kind == "canonicalize_runtime":
            if state.phase != "classify" or not state.classified:
                yield from self._emit("runtime_canonicalization_blocked", state)
                return
            residual_count = (
                max(1, int(input_obj.item_count))
                if self.broken_mode == "runtime_compatibility_residual"
                else 0
            )
            if residual_count:
                yield from self._emit(
                    "runtime_canonicalization_residual_blocked",
                    state,
                    obsolete_runtime_residual_count=residual_count,
                )
                return
            yield from self._emit(
                "runtime_canonicalization_committed",
                state,
                phase="canonicalize-runtime",
                checkpoint="canonicalize-runtime",
                runtime_canonicalized=True,
                obsolete_runtime_residual_count=0,
                canonicalization_receipt_count=(
                    state.canonicalization_receipt_count + 1
                ),
                side_effects=_append_unique(
                    state.side_effects, "runtime-canonicalization"
                ),
            )
            return

        if kind == "settle":
            if (
                state.phase != "canonicalize-runtime"
                or not state.classified
                or not state.runtime_canonicalized
                or state.obsolete_runtime_residual_count
            ):
                yield from self._emit("settlement_blocked", state)
                return
            mode = "atomic-batch"
            event_count = max(1, int(input_obj.item_count))
            replay_passes = max(0, int(input_obj.replay_passes))
            batch_count = max(1, int(input_obj.batch_count))
            if self.broken_mode == "per_item_replay":
                mode = "per-item-replay"
                replay_passes = event_count * 2
                batch_count = event_count
            yield from self._emit(
                "debt_settlement_committed",
                state,
                phase="settle-logical-debt",
                checkpoint="settle-logical-debt",
                debt_settled=True,
                settlement_mode=mode,
                settlement_event_count=event_count,
                settlement_replay_passes=replay_passes,
                settlement_batch_count=batch_count,
                settlement_reused_count=max(0, int(input_obj.reused_count)),
            )
            return

        if kind == "archive":
            if state.phase != "settle-logical-debt" or not state.debt_settled:
                yield from self._emit("archive_blocked", state)
                return
            yield from self._emit(
                "cold_archive_committed",
                state,
                phase="archive-cold-evidence",
                checkpoint="archive-cold-evidence",
                archive_ready=True,
                side_effects=_append_unique(state.side_effects, "cold-archive"),
            )
            return

        if kind == "repair_prune_permission":
            if (
                state.phase != "archive-cold-evidence"
                or not state.prune_permission_blocker_count
            ):
                yield from self._emit("prune_permission_repair_not_needed", state)
                return
            yield from self._emit(
                "prune_permission_repaired",
                state,
                prune_permission_blocker_count=0,
            )
            return

        if kind == "prune":
            if self.broken_mode == "prune_before_archive":
                yield from self._emit(
                    "derived_data_pruned",
                    state,
                    phase="prune-derived-data",
                    checkpoint="prune-derived-data",
                    pruned=True,
                    side_effects=state.side_effects + ("prune",),
                )
                return
            if state.phase != "archive-cold-evidence" or not state.archive_ready:
                yield from self._emit("prune_blocked", state)
                return
            if state.prune_permission_blocker_count:
                yield from self._emit("prune_permission_blocked", state)
                return
            if input_obj.context == "acl-denied":
                yield from self._emit(
                    "prune_permission_blocked",
                    state,
                    prune_permission_blocker_count=(
                        state.prune_permission_blocker_count + 1
                    ),
                )
                return
            verified_read_only = state.prune_verified_read_only_count
            cleared_read_only = state.prune_read_only_cleared_count
            resumed_deleted = state.prune_resumed_deleted_count
            if input_obj.context == "read-only-managed":
                verified_read_only += 1
                if self.broken_mode != "read_only_prune_unhandled":
                    cleared_read_only += 1
            if input_obj.context == "partial-prune-resume":
                resumed_deleted += 1
            yield from self._emit(
                "derived_data_pruned",
                state,
                phase="prune-derived-data",
                checkpoint="prune-derived-data",
                pruned=True,
                prune_verified_read_only_count=verified_read_only,
                prune_read_only_cleared_count=cleared_read_only,
                prune_resumed_deleted_count=resumed_deleted,
                side_effects=_append_unique(state.side_effects, "prune"),
            )
            return

        if kind == "rebuild":
            if state.phase != "prune-derived-data" or not state.pruned:
                yield from self._emit("index_rebuild_blocked", state)
                return
            yield from self._emit(
                "active_index_committed",
                state,
                phase="rebuild-index",
                checkpoint="rebuild-index",
                index_ready=True,
                side_effects=_append_unique(state.side_effects, "active-index"),
            )
            return

        if kind == "remove_architect":
            if not state.automations_paused:
                yield from self._emit("architect_removal_blocked", state)
                return
            if not state.architect_present:
                yield from self._emit("architect_absence_reused", state)
                return
            yield from self._emit(
                "architect_removed",
                state,
                architect_present=False,
                side_effects=_append_unique(state.side_effects, "architect-tombstone"),
            )
            return

        if kind == "stage_install":
            if state.phase != "rebuild-index" or not state.index_ready or state.architect_present:
                yield from self._emit("installation_stage_blocked", state)
                return
            manifests_match = self.broken_mode != "concurrent_drift"
            incoming_current = self.broken_mode != "incoming_authority_not_current"
            validation_identity_stable = (
                self.broken_mode != "authority_validation_identity_drift"
            )
            validation_snapshot_current = (
                self.broken_mode != "authority_validation_snapshot_missing"
            )
            validation_toolchains = (
                CURRENT_AUTHORITY_VALIDATION_TOOLCHAINS
                if validation_snapshot_current
                else ("skillguard", "flowguard")
            )
            active_tree_class = (
                "scan-failed"
                if self.broken_mode == "active_tree_scan_failed"
                else (
                    "current"
                    if self.broken_mode
                    in {
                        "install_downgrade",
                        "current_anti_downgrade_skipped",
                        "anti_downgrade_check_id_monotonicity",
                    }
                    else "opaque-noncurrent"
                )
            )
            whole_tree_staged = self.broken_mode != "partial_tree_overlay"
            comparison_performed = bool(
                (
                    active_tree_class == "current"
                    and self.broken_mode != "current_anti_downgrade_skipped"
                )
                or self.broken_mode == "opaque_noncurrent_interpreted"
            )
            comparison_basis = (
                "check-id-subset"
                if self.broken_mode == "anti_downgrade_check_id_monotonicity"
                else (
                    "obligation-evidence-owner-coverage"
                    if comparison_performed
                    else ""
                )
            )
            semantic_hard_authority_preserved = bool(
                active_tree_class == "current"
                and self.broken_mode != "install_downgrade"
            )
            comparison_passed = bool(
                comparison_performed
                and semantic_hard_authority_preserved
                and comparison_basis == "obligation-evidence-owner-coverage"
            )
            receipt_replay_current = (
                self.broken_mode != "authority_install_receipt_replay_mismatch"
            )
            install_member_count = (
                4
                if self.broken_mode == "authority_install_member_missing"
                else AUTHORITY_INSTALL_MEMBER_COUNT
            )
            yield from self._emit(
                "installation_staged",
                state,
                phase="stage-install",
                checkpoint="stage-install",
                staged_manifests_match=manifests_match,
                source_fingerprint_current=manifests_match,
                authority_install_policy_id=AUTHORITY_INSTALL_POLICY_ID,
                incoming_current_compiler_validated=incoming_current,
                authority_validation_identity_stable=validation_identity_stable,
                authority_validation_snapshot_current=validation_snapshot_current,
                authority_validation_toolchains=validation_toolchains,
                active_managed_tree_class=active_tree_class,
                whole_tree_replacement_staged=whole_tree_staged,
                active_semantic_comparison_performed=comparison_performed,
                anti_downgrade_comparison_basis=comparison_basis,
                semantic_hard_authority_preserved=semantic_hard_authority_preserved,
                current_to_current_anti_downgrade_passed=comparison_passed,
                authority_install_receipt_replay_current=receipt_replay_current,
                authority_install_member_count=install_member_count,
                rollback_verified=self.broken_mode != "rollback_missing",
            )
            return

        if kind == "activate_install":
            unsafe_bypass = self.broken_mode in {
                "concurrent_drift",
                "install_downgrade",
                "rollback_missing",
                "incoming_authority_not_current",
                "authority_validation_identity_drift",
                "authority_validation_snapshot_missing",
                "partial_tree_overlay",
                "current_anti_downgrade_skipped",
                "anti_downgrade_check_id_monotonicity",
                "opaque_noncurrent_interpreted",
                "active_tree_scan_failed",
                "authority_install_receipt_replay_mismatch",
                "authority_install_member_missing",
            }
            if not unsafe_bypass and (
                state.phase != "stage-install"
                or not state.staged_manifests_match
                or not state.source_fingerprint_current
                or not _authority_install_is_current(state)
                or not state.rollback_verified
            ):
                yield from self._emit("installation_activation_blocked", state)
                return
            router_binding = _router_refresh_binding(
                state,
                surface_fingerprint=CURRENT_SKILLGUARD_SURFACE_FINGERPRINT,
                stale_prompt=self.broken_mode == "router_prompt_matches_old_registry",
                missing_receipt=self.broken_mode == "router_refresh_receipt_missing",
            )
            if self.broken_mode == "router_surface_drift_after_refresh":
                router_binding["skillguard_surface_fingerprint"] = (
                    "skillguard-surface:post-refresh-drift"
                )
                router_binding["skillguard_surface_drift_count"] = (
                    state.skillguard_surface_drift_count + 1
                )
            yield from self._emit(
                "installation_committed",
                state,
                phase="activate-install",
                checkpoint="activate-install",
                install_transaction_committed=True,
                side_effects=_append_unique(
                    _append_unique(state.side_effects, "managed-install"),
                    str(router_binding["router_refresh_receipt"])
                    or "router-refresh-receipt-missing",
                ),
                **router_binding,
            )
            return

        if kind == "observe_skillguard_surface_drift":
            if (
                not state.install_transaction_committed
                or state.phase
                not in {"activate-install", "validate", "committed"}
            ):
                yield from self._emit("router_surface_drift_ignored", state)
                return
            drift_count = state.skillguard_surface_drift_count + 1
            drifted_surface = f"skillguard-surface:post-refresh-drift-{drift_count}"
            if self.broken_mode == "router_surface_drift_after_refresh":
                yield from self._emit(
                    "router_surface_drift_unchecked",
                    state,
                    skillguard_surface_fingerprint=drifted_surface,
                    skillguard_surface_drift_count=drift_count,
                )
                return
            yield from self._emit(
                "router_surface_drift_reopened",
                state,
                phase="activate-install",
                checkpoint="activate-install",
                automations_paused=True,
                validation_passed=False,
                committed_version=0,
                restored_automation_states=(),
                skillguard_surface_fingerprint=drifted_surface,
                router_refresh_receipt_current=False,
                live_registry_current=False,
                live_prompt_current=False,
                router_refresh_required=True,
                skillguard_surface_drift_count=drift_count,
                aggregate_assurance_passed=False,
                aggregate_assurance_current=False,
                aggregate_assurance_receipt="",
                post_assurance_data_current=False,
            )
            return

        if kind == "refresh_router":
            if (
                state.phase != "activate-install"
                or not state.install_transaction_committed
                or not state.automations_paused
            ):
                yield from self._emit("router_refresh_blocked", state)
                return
            if _router_refresh_is_current(state):
                yield from self._emit("router_refresh_reused", state)
                return
            router_binding = _router_refresh_binding(
                state,
                stale_prompt=self.broken_mode == "router_prompt_matches_old_registry",
                missing_receipt=self.broken_mode == "router_refresh_receipt_missing",
            )
            yield from self._emit(
                "router_refresh_committed",
                state,
                side_effects=_append_unique(
                    state.side_effects,
                    str(router_binding["router_refresh_receipt"])
                    or "router-refresh-receipt-missing",
                ),
                **router_binding,
            )
            return

        if kind == "rollback_install":
            if state.phase not in {"stage-install", "activate-install", "paused_failed"}:
                yield from self._emit("installation_rollback_not_needed", state)
                return
            if state.phase == "paused_failed" and state.checkpoint == "committed":
                yield from self._emit("installation_rollback_not_needed", state)
                return
            yield from self._emit(
                "installation_rolled_back",
                state,
                phase="paused_failed",
                checkpoint="stage-install",
                automations_paused=True,
                restored_automation_states=(),
                validation_passed=False,
                committed_version=0,
                install_transaction_committed=False,
                rollback_verified=True,
                skillguard_surface_fingerprint="",
                router_refresh_receipt="",
                router_refresh_receipt_durable=False,
                router_refresh_receipt_current=False,
                router_refresh_surface_fingerprint="",
                live_registry_fingerprint="",
                live_registry_surface_fingerprint="",
                live_registry_current=False,
                live_prompt_registry_fingerprint="",
                live_prompt_current=False,
                router_refresh_required=False,
                aggregate_assurance_passed=False,
                aggregate_assurance_current=False,
                aggregate_assurance_receipt="",
                post_assurance_data_current=False,
                side_effects=_append_unique(state.side_effects, "install-rollback"),
            )
            return

        if kind == "validate":
            if state.phase != "activate-install" or not state.index_ready:
                yield from self._emit("validation_blocked", state)
                return
            if state.managed_surface_residual_count:
                yield from self._emit("validation_blocked_managed_debt", state)
                return
            if (
                not state.runtime_canonicalized
                or state.obsolete_runtime_residual_count
                or state.canonicalization_receipt_count != 1
            ):
                yield from self._emit("validation_blocked_runtime_canonicalization", state)
                return
            if state.architect_present:
                yield from self._emit("validation_blocked_architect", state)
                return
            if not state.install_transaction_committed:
                yield from self._emit("validation_blocked_install", state)
                return
            if not _router_refresh_is_current(state):
                yield from self._emit("validation_blocked_router_freshness", state)
                return
            yield from self._emit(
                "migration_validated",
                state,
                phase="validate",
                checkpoint="validate",
                validation_passed=True,
            )
            return

        if kind == "reintroduce_managed_debt":
            if state.phase not in {"validate", "committed"}:
                yield from self._emit("managed_debt_reintroduction_ignored", state)
                return
            residual = state.managed_surface_residual_count + 1
            reintroduced = state.managed_surface_reintroduced_count + 1
            if self.broken_mode == "late_managed_debt_unchecked":
                yield from self._emit(
                    "managed_debt_reintroduced_unchecked",
                    state,
                    managed_surface_residual_count=residual,
                    managed_surface_reintroduced_count=reintroduced,
                )
                return
            yield from self._emit(
                "managed_debt_reopened",
                state,
                phase="reconcile-managed-surface",
                validation_passed=False,
                committed_version=0,
                automations_paused=True,
                restored_automation_states=(),
                aggregate_assurance_passed=False,
                aggregate_assurance_current=False,
                aggregate_assurance_receipt="",
                post_assurance_data_current=False,
                managed_surface_residual_count=residual,
                managed_surface_reintroduced_count=reintroduced,
            )
            return

        if kind == "reconcile_managed_debt":
            if not state.managed_surface_residual_count:
                yield from self._emit("managed_debt_reconciliation_no_delta", state)
                return
            target_phase = "committed" if state.checkpoint == "committed" else "validate"
            receipt_number = state.reconciliation_receipt_count + 1
            yield from self._emit(
                "managed_debt_reconciled",
                state,
                phase=target_phase,
                validation_passed=True,
                committed_version=1 if target_phase == "committed" else 0,
                managed_surface_residual_count=0,
                reconciliation_receipt_count=receipt_number,
                side_effects=_append_unique(
                    state.side_effects,
                    f"managed-surface-reconciliation-{receipt_number}",
                ),
            )
            return

        if kind == "admit_post_commit_observation":
            if state.phase not in {"validate", "committed"}:
                yield from self._emit("post_commit_observation_ignored", state)
                return
            debt_count = state.post_commit_observation_debt_count + 1
            if self.broken_mode == "post_commit_logical_debt_unchecked":
                yield from self._emit(
                    "post_commit_observation_unchecked",
                    state,
                    post_commit_observation_debt_count=debt_count,
                )
                return
            yield from self._emit(
                "post_commit_observation_reopened",
                state,
                phase="reconcile-logical-debt",
                validation_passed=False,
                committed_version=0,
                automations_paused=True,
                restored_automation_states=(),
                aggregate_assurance_passed=False,
                aggregate_assurance_current=False,
                aggregate_assurance_receipt="",
                post_assurance_data_current=False,
                post_commit_observation_debt_count=debt_count,
            )
            return

        if kind == "reconcile_logical_debt":
            if not state.post_commit_observation_debt_count:
                yield from self._emit("logical_debt_reconciliation_no_delta", state)
                return
            target_phase = "committed" if state.checkpoint == "committed" else "validate"
            receipt_number = state.logical_reconciliation_receipt_count + 1
            yield from self._emit(
                "logical_debt_reconciled",
                state,
                phase=target_phase,
                validation_passed=True,
                committed_version=1 if target_phase == "committed" else 0,
                post_commit_observation_debt_count=0,
                logical_reconciliation_receipt_count=receipt_number,
                side_effects=_append_unique(
                    state.side_effects,
                    f"logical-debt-reconciliation-{receipt_number}",
                ),
            )
            return

        if kind == "commit":
            if self.broken_mode == "stale_committed_failure":
                yield from self._emit(
                    "migration_committed",
                    state,
                    phase="committed",
                    checkpoint="committed",
                    committed_version=1,
                    active_failure=True,
                )
                return
            if self.broken_mode == "residual_architect":
                yield from self._emit(
                    "migration_committed",
                    state,
                    phase="committed",
                    checkpoint="committed",
                    validation_passed=True,
                    committed_version=1,
                )
                return
            if state.phase != "validate" or not state.validation_passed:
                yield from self._emit("commit_blocked", state)
                return
            if state.architect_present:
                yield from self._emit("commit_blocked_architect", state)
                return
            if not _router_refresh_is_current(state):
                yield from self._emit("commit_blocked_router_freshness", state)
                return
            yield from self._emit(
                "migration_committed",
                state,
                phase="committed",
                checkpoint="committed",
                committed_version=1,
                aggregate_assurance_passed=False,
                aggregate_assurance_current=False,
                aggregate_assurance_receipt="",
                post_assurance_data_current=False,
            )
            return

        if kind == "assurance_pass":
            if state.phase != "committed" or state.committed_version != 1:
                yield from self._emit("aggregate_assurance_blocked", state)
                return
            if not _router_refresh_is_current(state):
                yield from self._emit("aggregate_assurance_blocked_router_freshness", state)
                return
            reusable_full_regression = bool(
                state.full_regression_receipt_current
                and input_obj.context not in {"owner-input-drift", "owner-proof-drift"}
            )
            duplicate_current_execution = bool(
                reusable_full_regression
                and self.broken_mode == "duplicate_current_full_regression"
            )
            full_execution_count = state.full_regression_execution_count
            full_reuse_count = state.full_regression_reuse_count
            duplicate_count = state.full_regression_duplicate_current_execution_count
            if reusable_full_regression and not duplicate_current_execution:
                full_reuse_count += 1
            else:
                full_execution_count += 1
                duplicate_count += 1 if duplicate_current_execution else 0
            yield from self._emit(
                "aggregate_assurance_current",
                state,
                aggregate_assurance_passed=True,
                aggregate_assurance_current=True,
                aggregate_assurance_receipt="aggregate-assurance:current",
                full_regression_execution_count=full_execution_count,
                full_regression_reuse_count=full_reuse_count,
                full_regression_duplicate_current_execution_count=duplicate_count,
                full_regression_receipt_current=True,
                aggregate_script_import_current=(
                    self.broken_mode != "aggregate_script_import_ambiguous"
                ),
                performance_validation_lane_exclusive=(
                    self.broken_mode
                    != "performance_validation_resource_competition"
                ),
                scheduled_production_validation_lane_exclusive=(
                    self.broken_mode
                    != "scheduled_production_resource_competition"
                ),
                post_assurance_data_current=True,
                side_effects=_append_unique(
                    state.side_effects, "aggregate-assurance-current"
                ),
            )
            return

        if kind == "restore":
            if self.broken_mode == "early_restore":
                yield from self._emit(
                    "survivors_restored",
                    state,
                    automations_paused=False,
                    restored_automation_states=tuple(
                        f"{item}=ACTIVE" for item in SURVIVING_AUTOMATIONS
                    ),
                )
                return
            if self.broken_mode == "postcommit_preassurance_restore":
                yield from self._emit(
                    "survivors_restored",
                    state,
                    automations_paused=False,
                    restored_automation_states=state.prior_automation_states,
                    side_effects=_append_unique(
                        state.side_effects, "restore-survivors"
                    ),
                )
                return
            if self.broken_mode == "pause_state_lost":
                yield from self._emit(
                    "survivors_restored",
                    state,
                    automations_paused=False,
                    restored_automation_states=tuple(
                        f"{item}=ACTIVE" for item in SURVIVING_AUTOMATIONS
                    ),
                )
                return
            if self.broken_mode == "post_assurance_data_skip":
                yield from self._emit(
                    "survivors_restored",
                    state,
                    automations_paused=False,
                    restored_automation_states=state.prior_automation_states,
                    side_effects=_append_unique(
                        state.side_effects, "restore-survivors"
                    ),
                )
                return
            if (
                state.phase != "committed"
                or state.committed_version != 1
                or not state.aggregate_assurance_passed
                or not state.aggregate_assurance_current
                or not state.aggregate_assurance_receipt
                or not state.post_assurance_data_current
                or not _router_refresh_is_current(state)
            ):
                yield from self._emit("restore_blocked", state)
                return
            yield from self._emit(
                "survivors_restored",
                state,
                automations_paused=False,
                restored_automation_states=state.prior_automation_states,
                side_effects=_append_unique(state.side_effects, "restore-survivors"),
            )
            return

        if kind == "fail":
            if state.phase == "idle":
                yield from self._emit("failure_ignored", state)
                return
            if state.phase == "paused_failed":
                yield from self._emit("failure_reused", state)
                return
            if state.phase == "committed":
                failure_count = state.post_commit_assurance_failure_count + 1
                if self.broken_mode == "post_commit_assurance_failure_ignored":
                    yield from self._emit(
                        "post_commit_assurance_failure_ignored",
                        state,
                        aggregate_assurance_passed=False,
                        aggregate_assurance_current=False,
                        aggregate_assurance_receipt="",
                        post_assurance_data_current=False,
                        post_commit_assurance_failure_count=failure_count,
                        post_commit_assurance_failure_pending=True,
                    )
                    return
                yield from self._emit(
                    "post_commit_assurance_failed_paused",
                    state,
                    checkpoint="committed",
                    phase="paused_failed",
                    automations_paused=True,
                    restored_automation_states=(),
                    active_failure=True,
                    aggregate_assurance_passed=False,
                    aggregate_assurance_current=False,
                    aggregate_assurance_receipt="",
                    post_assurance_data_current=False,
                    post_commit_assurance_failure_count=failure_count,
                    post_commit_assurance_failure_pending=True,
                )
                return
            yield from self._emit(
                "migration_paused_failed",
                state,
                checkpoint=state.phase,
                phase="paused_failed",
                automations_paused=True,
                active_failure=True,
            )
            return

        if kind == "resume":
            if state.phase != "paused_failed":
                yield from self._emit("resume_not_needed", state)
                return
            post_commit_retry = bool(
                state.checkpoint == "committed"
                and state.post_commit_assurance_failure_pending
            )
            yield from self._emit(
                "migration_resumed",
                state,
                phase=state.checkpoint,
                automations_paused=True,
                restored_automation_states=(),
                active_failure=False,
                resolved_failure_count=state.resolved_failure_count + 1,
                post_commit_assurance_retry_count=(
                    state.post_commit_assurance_retry_count
                    + (1 if post_commit_retry else 0)
                ),
                post_commit_assurance_failure_pending=(
                    False
                    if post_commit_retry
                    else state.post_commit_assurance_failure_pending
                ),
            )


def migration_terminal(output: object, state: MigrationState, trace: object) -> bool:
    del state, trace
    return isinstance(output, MigrationOutput) and output.label.endswith("_blocked")


def _authority_install_is_current(state: MigrationState) -> bool:
    active_class_valid = state.active_managed_tree_class in {
        "absent",
        "current",
        "opaque-noncurrent",
    }
    comparison_valid = (
        state.active_semantic_comparison_performed
        and state.anti_downgrade_comparison_basis
        == "obligation-evidence-owner-coverage"
        and state.semantic_hard_authority_preserved
        and state.current_to_current_anti_downgrade_passed
        if state.active_managed_tree_class == "current"
        else not state.active_semantic_comparison_performed
        and not state.anti_downgrade_comparison_basis
        and not state.semantic_hard_authority_preserved
        and not state.current_to_current_anti_downgrade_passed
    )
    return bool(
        state.authority_install_policy_id == AUTHORITY_INSTALL_POLICY_ID
        and state.incoming_current_compiler_validated
        and state.authority_validation_identity_stable
        and state.authority_validation_snapshot_current
        and state.authority_validation_toolchains
        == CURRENT_AUTHORITY_VALIDATION_TOOLCHAINS
        and active_class_valid
        and state.whole_tree_replacement_staged
        and comparison_valid
        and state.authority_install_receipt_replay_current
        and state.authority_install_member_count == AUTHORITY_INSTALL_MEMBER_COUNT
    )


def migration_archive_precedes_prune(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    if state.pruned and not state.archive_ready:
        return InvariantResult.fail("derived data was pruned before cold archive commit")
    return InvariantResult.pass_()


def migration_commit_is_complete(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    if state.committed_version:
        missing = []
        if not state.debt_settled:
            missing.append("debt_settled")
        if not state.runtime_canonicalized:
            missing.append("runtime_canonicalized")
        if state.obsolete_runtime_residual_count:
            missing.append("obsolete_runtime_residual_count")
        if state.canonicalization_receipt_count != 1:
            missing.append("canonicalization_receipt_count")
        if not state.archive_ready:
            missing.append("archive_ready")
        if not state.index_ready:
            missing.append("index_ready")
        if not state.validation_passed:
            missing.append("validation_passed")
        if state.architect_present:
            missing.append("architect_absent")
        if not state.staged_manifests_match:
            missing.append("staged_manifests_match")
        if not state.source_fingerprint_current:
            missing.append("source_fingerprint_current")
        if not _authority_install_is_current(state):
            missing.append("authority_install_current")
        if not state.rollback_verified:
            missing.append("rollback_verified")
        if not state.install_transaction_committed:
            missing.append("install_transaction_committed")
        if not _router_refresh_is_current(state):
            missing.append("router_refresh_current")
        if state.managed_surface_residual_count:
            missing.append("managed_surface_residual_count")
        if state.post_commit_observation_debt_count:
            missing.append("post_commit_observation_debt_count")
        if missing:
            return InvariantResult.fail(
                "migration committed without required gates: " + ",".join(missing)
            )
    return InvariantResult.pass_()


def migration_restore_is_last(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    if (
        not state.automations_paused
        and state.phase not in {"idle", "committed"}
    ):
        return InvariantResult.fail("surviving automations restored before committed migration")
    if state.restored_automation_states and state.phase != "committed":
        return InvariantResult.fail("restored automation state exists outside committed phase")
    if any(value.startswith("kb-architect=") for value in state.restored_automation_states):
        return InvariantResult.fail("retired Architect automation was restored")
    if state.restored_automation_states and set(state.restored_automation_states) != set(
        state.prior_automation_states
    ):
        return InvariantResult.fail("surviving automation pause state was not preserved exactly")
    if state.restored_automation_states and (
        not state.aggregate_assurance_passed
        or not state.aggregate_assurance_current
        or not state.aggregate_assurance_receipt
        or not state.post_assurance_data_current
    ):
        return InvariantResult.fail(
            "surviving automations restored without current aggregate and post-assurance data evidence"
        )
    if state.restored_automation_states and not _router_refresh_is_current(state):
        return InvariantResult.fail(
            "surviving automations restored without current router registry and prompt"
        )
    return InvariantResult.pass_()


def migration_install_is_transactional(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    if state.install_transaction_committed and (
        not state.staged_manifests_match
        or not state.source_fingerprint_current
        or not _authority_install_is_current(state)
        or not state.rollback_verified
    ):
        return InvariantResult.fail(
            "managed installation committed without current incoming authority, whole-tree/current comparison, replay, or rollback proof"
        )
    return InvariantResult.pass_()


def migration_router_refresh_is_durable_and_current(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    if state.router_refresh_required:
        retry_position_valid = bool(
            state.phase == "activate-install"
            or (
                state.phase == "paused_failed"
                and state.checkpoint == "activate-install"
                and state.active_failure
            )
        )
        if (
            not retry_position_valid
            or not state.install_transaction_committed
            or not state.automations_paused
            or state.validation_passed
            or state.committed_version
            or state.restored_automation_states
            or state.aggregate_assurance_passed
            or state.aggregate_assurance_current
        ):
            return InvariantResult.fail(
                "router refresh debt did not reopen the paused installation gate"
            )
        if (
            state.router_refresh_receipt_current
            or state.live_registry_current
            or state.live_prompt_current
        ):
            return InvariantResult.fail(
                "stale router evidence remained marked current after SkillGuard surface drift"
            )
        return InvariantResult.pass_()
    freshness_required = bool(
        state.install_transaction_committed
        or state.validation_passed
        or state.committed_version
        or state.aggregate_assurance_passed
        or state.aggregate_assurance_current
        or state.restored_automation_states
    )
    if freshness_required and not _router_refresh_is_current(state):
        return InvariantResult.fail(
            "managed install lacks a durable current router receipt, live registry, or live prompt"
        )
    return InvariantResult.pass_()


def migration_side_effects_are_at_most_once(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    if len(state.side_effects) != len(set(state.side_effects)):
        return InvariantResult.fail("a migration side effect was applied more than once")
    return InvariantResult.pass_()


def migration_lock_recovery_is_owner_safe(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    if state.live_migration_lock_stolen:
        return InvariantResult.fail("a live migration lock owner was displaced")
    if state.recent_ownerless_lock_stolen:
        return InvariantResult.fail("a recent ownerless migration lock was displaced")
    if state.migration_lock_recovery_receipt_count:
        if state.migration_lock_recovery_reason not in {"dead-owner", "legacy-stale"}:
            return InvariantResult.fail(
                "migration lock recovery lacks an allowed stale-owner reason"
            )
        if "migration-lock-recovery" not in state.side_effects:
            return InvariantResult.fail(
                "stale migration lock disappeared without a recovery receipt"
            )
    return InvariantResult.pass_()


def migration_assurance_is_non_recursive(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    child_contexts = {"aggregate-child", "isolated-fixture"}
    if state.assurance_depth > 1:
        return InvariantResult.fail("aggregate assurance recursively invoked itself")
    if state.assurance_context in child_contexts:
        if not state.fixture_gates_skipped:
            return InvariantResult.fail(
                "an assurance child did not enter isolated fixture mode"
            )
        if not state.fixture_shell_isolated:
            return InvariantResult.fail(
                "an assurance child retained a writable global shell-tools side effect"
            )
        if state.assurance_depth != 0:
            return InvariantResult.fail(
                "an assurance child incremented the real upgrade depth"
            )
        if state.phase != "idle":
            return InvariantResult.fail(
                "an isolated assurance child re-entered the real migration"
            )
    return InvariantResult.pass_()


def migration_settlement_is_scale_bounded(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    if not state.debt_settled:
        return InvariantResult.pass_()
    if state.settlement_mode != "atomic-batch":
        return InvariantResult.fail(
            "historical settlement replayed lifecycle authority per item"
        )
    if state.settlement_event_count < 1 or state.settlement_batch_count < 1:
        return InvariantResult.fail("historical settlement lacks batch progress evidence")
    if state.settlement_replay_passes > state.settlement_batch_count * 2:
        return InvariantResult.fail(
            "historical settlement exceeded one replay before and after each batch"
        )
    if state.settlement_reused_count > state.settlement_event_count:
        return InvariantResult.fail("settlement reused count exceeds requested events")
    if (
        state.settlement_event_count > 1
        and state.settlement_batch_count >= state.settlement_event_count
    ):
        return InvariantResult.fail("historical settlement degenerated to one batch per item")
    return InvariantResult.pass_()


def migration_prune_permissions_are_accounted(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    if state.prune_read_only_cleared_count > state.prune_verified_read_only_count:
        return InvariantResult.fail("a read-only attribute was cleared before file verification")
    if (
        state.pruned
        and state.prune_verified_read_only_count
        > state.prune_read_only_cleared_count
    ):
        return InvariantResult.fail(
            "migration claimed pruning while a verified read-only artifact was not cleared"
        )
    if state.pruned and state.prune_permission_blocker_count:
        return InvariantResult.fail("migration pruned through an unresolved ACL blocker")
    return InvariantResult.pass_()


def migration_committed_failure_is_resolved(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    if state.phase == "committed" and state.committed_version and state.active_failure:
        return InvariantResult.fail(
            "migration committed while the journal still reports an active failure"
        )
    return InvariantResult.pass_()


def migration_post_commit_assurance_failure_is_retryable(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    expected_failures = state.post_commit_assurance_retry_count + (
        1 if state.post_commit_assurance_failure_pending else 0
    )
    if state.post_commit_assurance_failure_count != expected_failures:
        return InvariantResult.fail(
            "post-commit assurance failure journal lost or duplicated a retry"
        )
    if state.post_commit_assurance_failure_pending:
        if (
            state.phase != "paused_failed"
            or state.checkpoint != "committed"
            or not state.active_failure
            or not state.automations_paused
            or state.restored_automation_states
            or state.aggregate_assurance_passed
            or state.aggregate_assurance_current
            or state.aggregate_assurance_receipt
        ):
            return InvariantResult.fail(
                "post-commit assurance failure did not keep all survivors paused and retryable"
            )
    return InvariantResult.pass_()


def migration_full_regression_reuses_current_owner_receipt(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    if state.full_regression_duplicate_current_execution_count:
        return InvariantResult.fail(
            "aggregate relaunched a still-current full-regression owner instead of reusing its immutable receipt"
        )
    if state.full_regression_reuse_count and (
        not state.full_regression_receipt_current
        or state.full_regression_execution_count < 1
    ):
        return InvariantResult.fail(
            "full-regression reuse lacks one prior current owner execution"
        )
    if state.aggregate_assurance_current and (
        not state.full_regression_receipt_current
        or state.full_regression_execution_count < 1
    ):
        return InvariantResult.fail(
            "current aggregate assurance lacks a current full-regression owner receipt"
        )
    if state.aggregate_assurance_current and not state.aggregate_script_import_current:
        return InvariantResult.fail(
            "aggregate direct-script execution resolved its alignment owner through an ambiguous scripts namespace"
        )
    if (
        state.aggregate_assurance_current
        and not state.performance_validation_lane_exclusive
    ):
        return InvariantResult.fail(
            "performance validation competed with sibling aggregate checks for the same runtime budget"
        )
    if (
        state.aggregate_assurance_current
        and not state.scheduled_production_validation_lane_exclusive
    ):
        return InvariantResult.fail(
            "real scheduled production competed with sibling aggregate checks for the same runtime budget"
        )
    return InvariantResult.pass_()


def migration_managed_surface_converges(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    if state.committed_version and state.managed_surface_residual_count:
        return InvariantResult.fail(
            "migration remained committed after managed physical debt was reintroduced"
        )
    if (
        state.managed_surface_reintroduced_count
        and not state.managed_surface_residual_count
        and state.reconciliation_receipt_count < 1
    ):
        return InvariantResult.fail(
            "reintroduced managed debt disappeared without a reconciliation receipt"
        )
    return InvariantResult.pass_()


def migration_long_paths_are_visible(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    if state.managed_enumerated_path_count < state.managed_long_path_count:
        return InvariantResult.fail(
            "one or more Windows extended-length managed paths were invisible to inventory"
        )
    return InvariantResult.pass_()


def migration_post_commit_observations_converge(
    state: MigrationState, trace: object
) -> InvariantResult:
    del trace
    if state.committed_version and state.post_commit_observation_debt_count:
        return InvariantResult.fail(
            "migration remained committed with newly admitted observation debt"
        )
    return InvariantResult.pass_()


MIGRATION_INVARIANTS = (
    Invariant(
        "archive_before_prune",
        "Cold archive and rollback coverage precede physical deletion",
        migration_archive_precedes_prune,
    ),
    Invariant(
        "commit_requires_all_gates",
        "Commit requires settled debt, archive, index, validation, and Architect absence",
        migration_commit_is_complete,
    ),
    Invariant(
        "restore_only_after_commit",
        "Surviving automations remain paused until migration commit and current aggregate assurance",
        migration_restore_is_last,
    ),
    Invariant(
        "migration_side_effect_at_most_once",
        "Archive, pruning, index, retirement, and restore effects are idempotent",
        migration_side_effects_are_at_most_once,
    ),
    Invariant(
        "migration_lock_recovery_owner_safe",
        "Only dead or stale ownerless migration locks may be recovered with a receipt",
        migration_lock_recovery_is_owner_safe,
    ),
    Invariant(
        "transactional_install_before_commit",
        "Managed installation requires parity, current source, anti-downgrade, and rollback evidence",
        migration_install_is_transactional,
    ),
    Invariant(
        "durable_current_router_refresh",
        "The last managed Skill transaction is followed by a durable refresh receipt plus independent live registry and prompt freshness",
        migration_router_refresh_is_durable_and_current,
    ),
    Invariant(
        "aggregate_assurance_non_recursive",
        "Aggregate assurance children remain isolated from real migration gates and global shell tools",
        migration_assurance_is_non_recursive,
    ),
    Invariant(
        "historical_settlement_scale_bounded",
        "Historical lifecycle settlement uses bounded atomic batches and at most two replays per batch",
        migration_settlement_is_scale_bounded,
    ),
    Invariant(
        "prune_permission_boundary_accounted",
        "Only verified read-only attributes are cleared and ACL blockers prevent prune completion",
        migration_prune_permissions_are_accounted,
    ),
    Invariant(
        "committed_failure_is_resolved",
        "Resolved failures move to diagnostic history before the migration can be committed",
        migration_committed_failure_is_resolved,
    ),
    Invariant(
        "post_commit_assurance_failure_is_retryable",
        "A post-commit assurance failure re-pauses all five survivors and preserves one durable retry path",
        migration_post_commit_assurance_failure_is_retryable,
    ),
    Invariant(
        "current_full_regression_receipt_is_reused",
        "A second aggregate reuses the exact current full-regression owner receipt, and real scheduled production owns an exclusive resource lane",
        migration_full_regression_reuses_current_owner_receipt,
    ),
    Invariant(
        "managed_surface_reintroduction_converges",
        "Late or post-commit managed debt reopens the gate and requires a reconciliation receipt",
        migration_managed_surface_converges,
    ),
    Invariant(
        "windows_long_paths_are_visible",
        "Managed paths beyond the legacy Win32 limit remain inventory, hash, archive, and prune visible",
        migration_long_paths_are_visible,
    ),
    Invariant(
        "post_commit_observations_converge",
        "Observations admitted during upgrade reopen the gate and receive a logical reconciliation receipt",
        migration_post_commit_observations_converge,
    ),
)

MIGRATION_INPUTS = (
    MigrationInput("recover_migration_lock", context="dead-owner"),
    MigrationInput("recover_migration_lock", context="legacy-stale"),
    MigrationInput("recover_migration_lock", context="live-owner"),
    MigrationInput("recover_migration_lock", context="legacy-recent"),
    MigrationInput("assurance_invoke", context="outer-upgrade"),
    MigrationInput("assurance_invoke", context="aggregate-child"),
    MigrationInput("assurance_invoke", context="isolated-fixture"),
    MigrationInput("prune", context="read-only-managed"),
    MigrationInput("prune", context="acl-denied"),
    MigrationInput("prune", context="partial-prune-resume"),
    MigrationInput("repair_prune_permission"),
    MigrationInput("reintroduce_managed_debt"),
    MigrationInput("reconcile_managed_debt"),
    MigrationInput("inventory_managed_path", context="normal"),
    MigrationInput("inventory_managed_path", context="windows-long"),
    MigrationInput("admit_post_commit_observation"),
    MigrationInput("reconcile_logical_debt"),
    MigrationInput("observe_skillguard_surface_drift"),
    MigrationInput("refresh_router"),
    MigrationInput("assurance_pass", context="owner-current"),
    MigrationInput("assurance_pass", context="owner-input-drift"),
    MigrationInput("assurance_pass", context="owner-proof-drift"),
) + tuple(
    MigrationInput(kind)
    for kind in (
        "begin",
        "snapshot",
        "classify",
        "canonicalize_runtime",
        "settle",
        "archive",
        "prune",
        "rebuild",
        "remove_architect",
        "stage_install",
        "activate_install",
        "rollback_install",
        "validate",
        "commit",
        "assurance_pass",
        "restore",
        "fail",
        "resume",
    )
)

MIGRATION_INITIAL_STATES = (
    MigrationState(),
    MigrationState(
        phase="preflight", checkpoint="preflight", automations_paused=True,
        rollback_ref="snapshot:pre-upgrade"
    ),
    MigrationState(
        phase="snapshot", checkpoint="snapshot", automations_paused=True,
        rollback_ref="snapshot:pre-upgrade"
    ),
    MigrationState(
        phase="classify", checkpoint="classify", automations_paused=True,
        rollback_ref="snapshot:pre-upgrade", classified=True
    ),
    MigrationState(
        phase="canonicalize-runtime", checkpoint="canonicalize-runtime",
        automations_paused=True, rollback_ref="snapshot:pre-upgrade",
        classified=True, runtime_canonicalized=True,
        canonicalization_receipt_count=1,
        side_effects=("runtime-canonicalization",),
    ),
    MigrationState(
        phase="settle-logical-debt", checkpoint="settle-logical-debt",
        automations_paused=True, rollback_ref="snapshot:pre-upgrade",
        classified=True, runtime_canonicalized=True,
        canonicalization_receipt_count=1, debt_settled=True,
        side_effects=("runtime-canonicalization",),
    ),
    MigrationState(
        phase="archive-cold-evidence", checkpoint="archive-cold-evidence",
        automations_paused=True, rollback_ref="snapshot:pre-upgrade",
        classified=True, runtime_canonicalized=True,
        canonicalization_receipt_count=1, debt_settled=True, archive_ready=True,
        side_effects=("runtime-canonicalization", "cold-archive")
    ),
    MigrationState(
        phase="prune-derived-data", checkpoint="prune-derived-data",
        automations_paused=True, rollback_ref="snapshot:pre-upgrade",
        classified=True, runtime_canonicalized=True,
        canonicalization_receipt_count=1, debt_settled=True, archive_ready=True, pruned=True,
        side_effects=("runtime-canonicalization", "cold-archive", "prune")
    ),
    MigrationState(
        phase="rebuild-index", checkpoint="rebuild-index",
        automations_paused=True, architect_present=False,
        rollback_ref="snapshot:pre-upgrade", classified=True,
        runtime_canonicalized=True, canonicalization_receipt_count=1, debt_settled=True,
        archive_ready=True, pruned=True, index_ready=True,
        side_effects=("runtime-canonicalization", "cold-archive", "prune", "active-index", "architect-tombstone")
    ),
    MigrationState(
        phase="stage-install", checkpoint="stage-install", automations_paused=True,
        architect_present=False, rollback_ref="snapshot:pre-upgrade",
        classified=True, runtime_canonicalized=True,
        canonicalization_receipt_count=1, debt_settled=True, archive_ready=True, pruned=True,
        index_ready=True, staged_manifests_match=True,
        source_fingerprint_current=True, rollback_verified=True,
        side_effects=("runtime-canonicalization", "cold-archive", "prune", "active-index", "architect-tombstone"),
        **CURRENT_AUTHORITY_INSTALL_BINDING,
    ),
    MigrationState(
        phase="activate-install", checkpoint="activate-install", automations_paused=True,
        architect_present=False, rollback_ref="snapshot:pre-upgrade",
        classified=True, runtime_canonicalized=True,
        canonicalization_receipt_count=1, debt_settled=True, archive_ready=True, pruned=True,
        index_ready=True, staged_manifests_match=True,
        source_fingerprint_current=True, rollback_verified=True,
        install_transaction_committed=True,
        side_effects=(
            "runtime-canonicalization", "cold-archive", "prune", "active-index", "architect-tombstone",
            "managed-install", CURRENT_ROUTER_REFRESH_RECEIPT,
        ),
        **CURRENT_AUTHORITY_INSTALL_BINDING,
        **CURRENT_ROUTER_BINDING,
    ),
    MigrationState(
        phase="validate", checkpoint="validate", automations_paused=True,
        architect_present=False, rollback_ref="snapshot:pre-upgrade",
        classified=True, runtime_canonicalized=True,
        canonicalization_receipt_count=1, debt_settled=True, archive_ready=True, pruned=True,
        index_ready=True, validation_passed=True, staged_manifests_match=True,
        source_fingerprint_current=True, rollback_verified=True,
        install_transaction_committed=True,
        side_effects=(
            "runtime-canonicalization", "cold-archive", "prune", "active-index", "architect-tombstone",
            "managed-install", CURRENT_ROUTER_REFRESH_RECEIPT,
        ),
        **CURRENT_AUTHORITY_INSTALL_BINDING,
        **CURRENT_ROUTER_BINDING,
    ),
    MigrationState(
        phase="committed", checkpoint="committed", automations_paused=True,
        architect_present=False, rollback_ref="snapshot:pre-upgrade",
        classified=True, runtime_canonicalized=True,
        canonicalization_receipt_count=1, debt_settled=True, archive_ready=True, pruned=True,
        index_ready=True, validation_passed=True, committed_version=1,
        staged_manifests_match=True, source_fingerprint_current=True,
        rollback_verified=True, install_transaction_committed=True,
        side_effects=(
            "runtime-canonicalization", "cold-archive", "prune", "active-index", "architect-tombstone",
            "managed-install", CURRENT_ROUTER_REFRESH_RECEIPT,
        ),
        **CURRENT_AUTHORITY_INSTALL_BINDING,
        **CURRENT_ROUTER_BINDING,
    ),
    MigrationState(
        phase="paused_failed", checkpoint="committed", automations_paused=True,
        architect_present=False, rollback_ref="snapshot:pre-upgrade",
        classified=True, runtime_canonicalized=True,
        canonicalization_receipt_count=1, debt_settled=True, archive_ready=True, pruned=True,
        index_ready=True, validation_passed=True, committed_version=1,
        staged_manifests_match=True, source_fingerprint_current=True,
        rollback_verified=True, install_transaction_committed=True,
        active_failure=True, post_commit_assurance_failure_count=1,
        post_commit_assurance_failure_pending=True,
        side_effects=(
            "runtime-canonicalization", "cold-archive", "prune", "active-index", "architect-tombstone",
            "managed-install", CURRENT_ROUTER_REFRESH_RECEIPT,
        ),
        **CURRENT_AUTHORITY_INSTALL_BINDING,
        **CURRENT_ROUTER_BINDING,
    ),
    MigrationState(
        phase="paused_failed", checkpoint="archive-cold-evidence",
        automations_paused=True, architect_present=False,
        rollback_ref="snapshot:pre-upgrade", classified=True,
        runtime_canonicalized=True, canonicalization_receipt_count=1, debt_settled=True,
        archive_ready=True, active_failure=True,
        side_effects=("runtime-canonicalization", "cold-archive", "architect-tombstone")
    ),
)


def migration_workflow(*, broken_mode: str = "") -> Workflow:
    return Workflow(
        (UpgradeMigrationBlock(broken_mode=broken_mode),),
        name=f"kb_upgrade_migration{('_' + broken_mode) if broken_mode else ''}",
    )


@dataclass(frozen=True)
class AutomationInput:
    kind: str
    skill_id: str = ""
    receipt_skill_id: str = ""
    obligation_ids: tuple[str, ...] = ()
    contract_digest: str = ""
    supervisor_contract_digest: str = ""
    run_id: str = ""
    expected_run_id: str = ""
    receipt_hash: str = ""
    expected_receipt_hash: str = ""
    executed_check_ids: tuple[str, ...] = ()
    depth_obligation_ids: tuple[str, ...] = ()
    depth_status: str = "EXECUTION_DEPTH_PASS"
    depth_current: bool = True
    depth_receipt_id: str = ""
    depth_receipt_hash: str = ""
    target_check_execution_count: int = 0
    supervision_stage: str = ""
    authorization_receipt_current: bool = True
    closure_profile: str = "enforced"
    closure_current: bool = True
    consumed_depth_receipt_id: str = ""
    consumed_depth_receipt_hash: str = ""
    close_target_check_execution_count: int = 0
    native_status: str = "completed"
    native_receipt_origin: str = "scheduled-real"
    evidence_domain: str = "scheduled_production"
    scheduler_or_trigger_id: str = "repo-managed-automation"
    scheduled_execution_id: str = ""
    installation_receipt_id: str = "skillguard-installation-receipt"
    installation_receipt_hash: str = "skillguard-installation-receipt-hash"
    installation_receipt_root_ref: tuple[str, str] = (
        "active_skill_root",
        ".sg-runtime/installation",
    )
    installed_runtime_fingerprint: str = "skillguard-installed-runtime-fingerprint"
    installation_receipt_current: bool = True
    runtime_projection_exact_inventory: bool = True
    runtime_projection_bytecode_writes_suppressed: bool = True
    scheduled_supervision_snapshot_frozen_before_native: bool = True
    scheduled_supervision_snapshot_reused_after_native: bool = True
    scheduled_supervision_live_reloaded_after_native: bool = False
    scheduled_dynamic_evidence_projected_after_native: bool = True
    scheduled_dynamic_evidence_whitelist_exact: bool = True
    scheduled_inherited_dynamic_evidence_cleared: bool = True
    supervision_target_root_class: str = "exact-installed-root"
    supervision_surface_label: str = "scheduled-guarded"
    native_disposition_proofs_current: bool = True
    target_native_terminal_receipt_owner: str = ""
    target_native_terminal_receipt_id: str = ""
    target_native_terminal_receipt_hash: str = ""
    target_native_terminal_branch_id: str = ""
    target_native_terminal_kind: str = ""
    target_native_terminal_disposition: str = ""
    target_native_terminal_depth_receipt_id: str = ""
    target_native_terminal_depth_receipt_hash: str = ""
    consumed_target_native_terminal_receipt_id: str = ""
    consumed_target_native_terminal_receipt_hash: str = ""
    closure_completion_scope: str = ""
    overall_complete: bool = False
    maintenance_lane_active: bool = False
    maintenance_lane_executed: bool = False
    shared_maintenance_lock_required: bool = False
    shared_maintenance_lock_acquired: bool = False
    shared_maintenance_lock_released: bool = False
    real_lifecycle_review_ok: bool = True
    fixture_lifecycle_review_ok: bool = False
    selected_obligation_ids: tuple[str, ...] = ()
    evaluated_obligation_ids: tuple[str, ...] = ()
    validated_obligation_ids: tuple[str, ...] = ()
    semantic_validation_receipt_ids: tuple[str, ...] = ()
    semantic_range_receipt_ids: tuple[str, ...] = ()
    positive_fixture_target_ids: tuple[str, ...] = ()
    shallow_fixture_target_ids: tuple[str, ...] = ()
    gated_noop: bool = False
    noop_applicable_obligation_ids: tuple[str, ...] = ()
    noop_executed_obligation_ids: tuple[str, ...] = ()
    noop_passed_obligation_ids: tuple[str, ...] = ()
    noop_receipt_hash: str = ""
    noop_consumed_receipt_hash: str = ""
    noop_closure_profile: str = ""
    survivor_snapshot: tuple[str, ...] = ()
    survivor_user_pause_bits: tuple[bool, ...] = ()
    authorization_run_id: str = ""
    authorization_declared_check_receipt_id: str = "authorization-declared-check-receipt"
    authorization_route_ids: tuple[str, ...] = ()
    staged_target_states: tuple[str, ...] = ()
    staged_user_pause_bits: tuple[bool, ...] = ()
    staged_automation_hashes: tuple[str, ...] = ()
    staged_consumed_native_receipt_hash: str = ""
    staged_consumed_authorization_receipt_id: str = ""
    deferred_install_check_id: str = "normal-install-check-after-live-readback"
    restoration_receipt_id: str = "restoration-finalization-receipt"
    restoration_receipt_hash: str = "restoration-finalization-hash"
    finalization_run_id: str = "finalization-supervisor-run"
    finalization_depth_receipt_id: str = "depth:finalization-supervisor-run"
    finalization_depth_receipt_hash: str = "depth-hash:finalization-supervisor-run"
    finalization_depth_status: str = "EXECUTION_DEPTH_PASS"
    finalization_depth_current: bool = True
    finalization_executed_check_ids: tuple[str, ...] = ()
    finalization_route_ids: tuple[str, ...] = ()
    compose: bool = True
    stage_included_authorize_checks: bool = True
    finalization_target_check_execution_count: int = 0
    finalization_close_target_check_execution_count: int = 0
    finalization_native_terminal_receipt_owner: str = ""
    finalization_native_terminal_receipt_id: str = ""
    finalization_native_terminal_receipt_hash: str = ""
    finalization_native_terminal_branch_id: str = "prepared-update"
    finalization_native_terminal_disposition: str = "terminal_completion"
    finalization_native_terminal_depth_receipt_id: str = ""
    finalization_native_terminal_depth_receipt_hash: str = ""
    finalization_consumed_depth_receipt_hash: str = ""
    finalization_consumed_native_terminal_receipt_id: str = ""
    finalization_consumed_native_terminal_receipt_hash: str = ""
    consumed_native_receipt_hash: str = ""
    consumed_restoration_receipt_hash: str = "restoration-finalization-hash"
    applied_states: tuple[str, ...] = ()
    applied_user_pause_bits: tuple[bool, ...] = ()
    applied_automation_hashes: tuple[str, ...] = ()
    readback_states: tuple[str, ...] = ()
    readback_user_pause_bits: tuple[bool, ...] = ()
    readback_automation_hashes: tuple[str, ...] = ()
    readback_ok: bool = True
    normal_install_check_ok: bool = True
    operation_ok: bool = True


@dataclass(frozen=True)
class AutomationOutput:
    label: str


@dataclass(frozen=True)
class AutomationState:
    target_skill_id: str = ""
    receipt_skill_id: str = ""
    run_id: str = ""
    expected_run_id: str = ""
    receipt_hash: str = ""
    expected_receipt_hash: str = ""
    contract_digest: str = ""
    supervisor_contract_digest: str = ""
    native_terminal: bool = False
    native_status: str = ""
    native_receipt_origin: str = ""
    evidence_domain: str = ""
    scheduler_or_trigger_id: str = ""
    scheduled_execution_id: str = ""
    installation_receipt_id: str = ""
    installation_receipt_hash: str = ""
    installation_receipt_root_ref: tuple[str, str] = ()
    installed_runtime_fingerprint: str = ""
    installation_receipt_current: bool = False
    runtime_projection_exact_inventory: bool = False
    runtime_projection_bytecode_writes_suppressed: bool = False
    scheduled_supervision_snapshot_frozen_before_native: bool = False
    scheduled_supervision_snapshot_reused_after_native: bool = False
    scheduled_supervision_live_reloaded_after_native: bool = False
    scheduled_dynamic_evidence_projected_after_native: bool = False
    scheduled_dynamic_evidence_whitelist_exact: bool = False
    scheduled_inherited_dynamic_evidence_cleared: bool = False
    supervision_target_root_class: str = ""
    supervision_surface_label: str = ""
    native_disposition_proofs_current: bool = False
    maintenance_lane_active: bool = False
    maintenance_lane_executed: bool = False
    shared_maintenance_lock_required: bool = False
    shared_maintenance_lock_acquired: bool = False
    shared_maintenance_lock_released: bool = False
    real_lifecycle_review_ok: bool = False
    fixture_lifecycle_review_ok: bool = False
    selected_obligation_ids: tuple[str, ...] = ()
    evaluated_obligation_ids: tuple[str, ...] = ()
    validated_obligation_ids: tuple[str, ...] = ()
    semantic_validation_receipt_ids: tuple[str, ...] = ()
    semantic_range_receipt_ids: tuple[str, ...] = ()
    positive_fixture_target_ids: tuple[str, ...] = ()
    shallow_fixture_target_ids: tuple[str, ...] = ()
    gated_noop: bool = False
    noop_applicable_obligation_ids: tuple[str, ...] = ()
    noop_executed_obligation_ids: tuple[str, ...] = ()
    noop_passed_obligation_ids: tuple[str, ...] = ()
    noop_receipt_hash: str = ""
    noop_consumed_receipt_hash: str = ""
    noop_closure_profile: str = ""
    receipt_current: bool = False
    obligation_ids: tuple[str, ...] = ()
    obligation_evidence_count: int = 0
    required_obligation_ids: tuple[str, ...] = ()
    required_obligation_count: int = 0
    expected_check_ids: tuple[str, ...] = ()
    executed_check_ids: tuple[str, ...] = ()
    depth_obligation_ids: tuple[str, ...] = ()
    depth_status: str = "NOT_RUN"
    depth_current: bool = False
    depth_receipt_id: str = ""
    depth_receipt_hash: str = ""
    target_check_execution_count: int = 0
    closure_profile: str = ""
    closure_current: bool = False
    consumed_depth_receipt_id: str = ""
    consumed_depth_receipt_hash: str = ""
    close_target_check_execution_count: int = 0
    target_native_terminal_receipt_owner: str = ""
    target_native_terminal_receipt_id: str = ""
    target_native_terminal_receipt_hash: str = ""
    target_native_terminal_branch_id: str = ""
    target_native_terminal_kind: str = ""
    target_native_terminal_disposition: str = ""
    target_native_terminal_depth_receipt_id: str = ""
    target_native_terminal_depth_receipt_hash: str = ""
    consumed_target_native_terminal_receipt_id: str = ""
    consumed_target_native_terminal_receipt_hash: str = ""
    closure_completion_scope: str = ""
    overall_complete: bool = False
    enforced_closed: bool = False
    closure_consumed_depth: bool = False
    update_requires_restore: bool = False
    update_phase: str = "not-update"
    update_status: str = "NOT_UPDATE"
    authorization_run_id: str = ""
    authorization_declared_check_receipt_id: str = ""
    authorization_supervision_stage: str = ""
    authorization_route_ids: tuple[str, ...] = ()
    authorization_staged: bool = False
    authorization_consumed_depth_receipt_id: str = ""
    authorization_consumed_depth_receipt_hash: str = ""
    authorization_reconciliation_target_check_execution_count: int = 0
    authorization_consumed_native_terminal_receipt_id: str = ""
    authorization_consumed_native_terminal_receipt_hash: str = ""
    authorization_completion_scope: str = ""
    authorization_overall_complete: bool = False
    authorization_emitted_closure: bool = False
    survivor_states_snapshotted: bool = False
    survivor_snapshot: tuple[str, ...] = ()
    survivor_user_pause_bits: tuple[bool, ...] = ()
    current_survivor_states: tuple[str, ...] = ()
    current_user_pause_bits: tuple[bool, ...] = ()
    survivors_paused: bool = False
    staged_target_states: tuple[str, ...] = ()
    staged_user_pause_bits: tuple[bool, ...] = ()
    staged_automation_hashes: tuple[str, ...] = ()
    staged_consumed_native_receipt_hash: str = ""
    staged_consumed_authorization_receipt_id: str = ""
    deferred_install_check_id: str = ""
    restoration_staged: bool = False
    restored_survivor_states: tuple[str, ...] = ()
    restored_after_closure: bool = False
    restoration_receipt_id: str = ""
    restoration_receipt_hash: str = ""
    finalization_run_id: str = ""
    finalization_depth_receipt_id: str = ""
    finalization_depth_receipt_hash: str = ""
    finalization_depth_status: str = "NOT_RUN"
    finalization_depth_current: bool = False
    finalization_executed_check_ids: tuple[str, ...] = ()
    finalization_route_ids: tuple[str, ...] = ()
    finalization_composed: bool = False
    finalization_stage_included_authorize_checks: bool = False
    finalization_target_check_execution_count: int = 0
    finalization_close_target_check_execution_count: int = 0
    finalization_native_terminal_receipt_owner: str = ""
    finalization_native_terminal_receipt_id: str = ""
    finalization_native_terminal_receipt_hash: str = ""
    finalization_native_terminal_branch_id: str = ""
    finalization_native_terminal_disposition: str = ""
    finalization_native_terminal_depth_receipt_id: str = ""
    finalization_native_terminal_depth_receipt_hash: str = ""
    finalization_consumed_depth_receipt_hash: str = ""
    finalization_consumed_native_terminal_receipt_id: str = ""
    finalization_consumed_native_terminal_receipt_hash: str = ""
    finalization_consumed_native_hash: str = ""
    finalization_consumed_restoration_hash: str = ""
    live_restore_applied: bool = False
    live_restore_readback_ok: bool = False
    normal_install_check_ok: bool = False
    readback_survivor_states: tuple[str, ...] = ()
    readback_user_pause_bits: tuple[bool, ...] = ()
    readback_automation_hashes: tuple[str, ...] = ()
    marked_current_after_closure: bool = False
    failure_repaused: bool = False
    guarded_terminal: bool = False
    side_effects: tuple[str, ...] = ()


AUTOMATION_TARGET_OBLIGATIONS: dict[str, tuple[str, ...]] = {
    skill_id: expected_obligation_ids(skill_id)
    for skill_id in AUTOMATION_COMPLETION_CONTRACTS
}


AUTOMATION_TARGET_IDS = tuple(AUTOMATION_TARGET_OBLIGATIONS)
AUTOMATION_DEPTH_TARGET_OBLIGATIONS: dict[str, tuple[str, ...]] = {
    skill_id: tuple(
        obligation_id
        for obligation_id in obligation_ids
        if obligation_id
        != "obligation:khaos-brain-update:staged-restoration-authorization"
    )
    for skill_id, obligation_ids in AUTOMATION_TARGET_OBLIGATIONS.items()
}
AUTOMATION_GATED_NOOP_ELIGIBLE_OBLIGATIONS: dict[str, frozenset[str]] = {
    "kb-sleep-maintenance": frozenset(),
    "kb-dream-pass": frozenset(
        {
            "obligation:kb-dream-pass:no-delta-closure",
            "obligation:kb-dream-pass:terminal-receipt",
        }
    ),
    "kb-organization-contribute": frozenset(
        {"obligation:kb-organization-contribute:settings-noop-gate"}
    ),
    "kb-organization-maintenance": frozenset(
        {"obligation:kb-organization-maintenance:settings-participation-gate"}
    ),
    "khaos-brain-update": frozenset(
        {"obligation:khaos-brain-update:authorization-system-check"}
    ),
}


def _semantic_receipt_ids(skill_id: str) -> tuple[str, ...]:
    return tuple(
        f"semantic-receipt:{obligation_id}"
        for obligation_id in AUTOMATION_TARGET_OBLIGATIONS[skill_id]
    )

AUTOMATION_CHECK_KINDS = (
    "intake-runtime",
    "native-runtime",
    "terminal-runtime",
    "depth-positive",
    "depth-shallow",
)
UPDATE_SKILL_ID = "khaos-brain-update"
UPDATE_AUTHORIZE_ROUTE_ID = "route:khaos-brain-update:authorize"
UPDATE_FINALIZE_ROUTE_ID = "route:khaos-brain-update:finalize"
UPDATE_COMPOSED_ROUTE_IDS = (
    UPDATE_AUTHORIZE_ROUTE_ID,
    UPDATE_FINALIZE_ROUTE_ID,
)
UPDATE_SURVIVOR_IDS = (
    "kb-sleep",
    "kb-dream",
    "khaos-brain-system-update",
    "kb-org-contribute",
    "kb-org-maintenance",
)
UPDATE_SURVIVOR_SNAPSHOT = (
    "kb-sleep=ACTIVE",
    "kb-dream=PAUSED",
    "khaos-brain-system-update=ACTIVE",
    "kb-org-contribute=ACTIVE",
    "kb-org-maintenance=PAUSED",
)
UPDATE_SURVIVOR_USER_PAUSE_BITS = (False, True, False, False, True)
UPDATE_PLANNED_AUTOMATION_HASHES = tuple(
    f"{automation_id}=sha256-{index + 1:02d}"
    for index, automation_id in enumerate(UPDATE_SURVIVOR_IDS)
)
ALL_UPDATE_SURVIVORS_PAUSED = tuple(
    f"{automation_id}=PAUSED" for automation_id in UPDATE_SURVIVOR_IDS
)
TARGET_SHALLOW_BROKEN_MODES = {
    "kb-sleep-maintenance": "sleep_shallow_wrong_obligation_count",
    "kb-dream-pass": "dream_shallow_wrong_obligation_count",
    "kb-organization-contribute": "organization_contribute_shallow_wrong_obligation_count",
    "kb-organization-maintenance": "organization_maintenance_shallow_wrong_obligation_count",
    "khaos-brain-update": "system_update_shallow_wrong_obligation_count",
}


def automation_expected_check_ids(skill_id: str) -> tuple[str, ...]:
    checks = tuple(f"check:{skill_id}:{kind}" for kind in AUTOMATION_CHECK_KINDS)
    if skill_id == UPDATE_SKILL_ID:
        return checks + ("check:khaos-brain-update:branch-terminal-runtime",)
    return checks


def automation_manifest_check_ids(skill_id: str) -> tuple[str, ...]:
    checks = automation_expected_check_ids(skill_id)
    if skill_id == UPDATE_SKILL_ID:
        return checks + ("check:khaos-brain-update:finalization-runtime",)
    return checks


def _snapshot_has_exact_survivors(snapshot: tuple[str, ...]) -> bool:
    ids = tuple(value.partition("=")[0] for value in snapshot)
    return len(snapshot) == len(UPDATE_SURVIVOR_IDS) and set(ids) == set(
        UPDATE_SURVIVOR_IDS
    )


def _pause_bits_have_exact_survivors(bits: tuple[bool, ...]) -> bool:
    return len(bits) == len(UPDATE_SURVIVOR_IDS)


def _hashes_have_exact_survivors(values: tuple[str, ...]) -> bool:
    ids = tuple(value.partition("=")[0] for value in values)
    hashes = tuple(value.partition("=")[2] for value in values)
    return (
        len(values) == len(UPDATE_SURVIVOR_IDS)
        and set(ids) == set(UPDATE_SURVIVOR_IDS)
        and all(value.startswith("sha256-") for value in hashes)
    )


SCHEDULED_INSTALLATION_RECEIPT_ROOT_REF = (
    "active_skill_root",
    ".sg-runtime/installation",
)


def _depth_receipt_hash(run_id: str) -> str:
    return f"depth-hash:{run_id}"


def _native_terminal_receipt_id(run_id: str, branch_id: str) -> str:
    return f"native-terminal:{run_id}:{branch_id}"


def _native_terminal_receipt_hash(run_id: str, branch_id: str) -> str:
    return f"native-terminal-hash:{run_id}:{branch_id}"


def _scheduled_production_identity_is_current(state: AutomationState) -> bool:
    """Model the official identity and one start-frozen supervision authority."""

    return bool(
        state.evidence_domain == "scheduled_production"
        and state.scheduler_or_trigger_id
        and state.scheduled_execution_id == state.run_id
        and state.installation_receipt_id
        and state.installation_receipt_hash
        and state.installation_receipt_root_ref
        == SCHEDULED_INSTALLATION_RECEIPT_ROOT_REF
        and state.installed_runtime_fingerprint
        and state.installation_receipt_current
        and state.scheduled_supervision_snapshot_frozen_before_native
        and state.scheduled_supervision_snapshot_reused_after_native
        and not state.scheduled_supervision_live_reloaded_after_native
        and state.scheduled_dynamic_evidence_projected_after_native
        and state.scheduled_dynamic_evidence_whitelist_exact
        and state.scheduled_inherited_dynamic_evidence_cleared
        and state.supervision_target_root_class == "exact-installed-root"
    )


def automation_native_input(
    skill_id: str,
    *,
    contract_digest: str = "",
    partial: bool = False,
) -> AutomationInput:
    obligation_ids = AUTOMATION_TARGET_OBLIGATIONS[skill_id]
    semantic_receipts = _semantic_receipt_ids(skill_id)
    run_id = f"scheduled-run:{skill_id}"
    receipt_hash = f"native-receipt-hash:{skill_id}"
    return AutomationInput(
        "partial_native"
        if partial
        else ("native_update_terminal" if skill_id == UPDATE_SKILL_ID else "native_terminal"),
        skill_id=skill_id,
        receipt_skill_id=skill_id,
        obligation_ids=obligation_ids[:1] if partial else obligation_ids,
        contract_digest=contract_digest or f"contract-digest:{skill_id}",
        run_id=run_id,
        receipt_hash=receipt_hash,
        native_status=(
            "partial"
            if partial
            else ("awaiting-skillguard" if skill_id == UPDATE_SKILL_ID else "completed")
        ),
        native_receipt_origin="scheduled-real",
        evidence_domain="scheduled_production",
        scheduler_or_trigger_id=f"automation:{skill_id}",
        scheduled_execution_id=run_id,
        installation_receipt_id="skillguard-installation-receipt",
        installation_receipt_hash="skillguard-installation-receipt-hash",
        installation_receipt_root_ref=SCHEDULED_INSTALLATION_RECEIPT_ROOT_REF,
        installed_runtime_fingerprint="skillguard-installed-runtime-fingerprint",
        installation_receipt_current=True,
        supervision_target_root_class="exact-installed-root",
        supervision_surface_label=f"scheduled-guarded-{run_id}",
        maintenance_lane_active=skill_id == "kb-dream-pass",
        maintenance_lane_executed=skill_id == "kb-dream-pass",
        shared_maintenance_lock_required=skill_id == "kb-sleep-maintenance",
        shared_maintenance_lock_acquired=skill_id == "kb-sleep-maintenance",
        shared_maintenance_lock_released=skill_id == "kb-sleep-maintenance",
        real_lifecycle_review_ok=True,
        selected_obligation_ids=obligation_ids[:1] if partial else obligation_ids,
        evaluated_obligation_ids=obligation_ids[:1] if partial else obligation_ids,
        validated_obligation_ids=obligation_ids[:1] if partial else obligation_ids,
        semantic_validation_receipt_ids=(
            semantic_receipts[:1] if partial else semantic_receipts
        ),
        semantic_range_receipt_ids=(
            semantic_receipts[:1] if partial else semantic_receipts
        ),
        positive_fixture_target_ids=AUTOMATION_TARGET_IDS,
        shallow_fixture_target_ids=AUTOMATION_TARGET_IDS,
        survivor_snapshot=(
            UPDATE_SURVIVOR_SNAPSHOT if skill_id == UPDATE_SKILL_ID else ()
        ),
        survivor_user_pause_bits=(
            UPDATE_SURVIVOR_USER_PAUSE_BITS if skill_id == UPDATE_SKILL_ID else ()
        ),
    )


def _native_state(skill_id: str) -> AutomationState:
    input_obj = automation_native_input(skill_id)
    obligations = AUTOMATION_TARGET_OBLIGATIONS[skill_id]
    is_update = skill_id == UPDATE_SKILL_ID
    return AutomationState(
        target_skill_id=skill_id,
        receipt_skill_id=skill_id,
        run_id=input_obj.run_id,
        receipt_hash=input_obj.receipt_hash,
        contract_digest=input_obj.contract_digest,
        native_terminal=True,
        native_status=input_obj.native_status,
        native_receipt_origin=input_obj.native_receipt_origin,
        evidence_domain=input_obj.evidence_domain,
        scheduler_or_trigger_id=input_obj.scheduler_or_trigger_id,
        scheduled_execution_id=input_obj.scheduled_execution_id,
        installation_receipt_id=input_obj.installation_receipt_id,
        installation_receipt_hash=input_obj.installation_receipt_hash,
        installation_receipt_root_ref=input_obj.installation_receipt_root_ref,
        installed_runtime_fingerprint=input_obj.installed_runtime_fingerprint,
        installation_receipt_current=input_obj.installation_receipt_current,
        runtime_projection_exact_inventory=(
            input_obj.runtime_projection_exact_inventory
        ),
        runtime_projection_bytecode_writes_suppressed=(
            input_obj.runtime_projection_bytecode_writes_suppressed
        ),
        scheduled_supervision_snapshot_frozen_before_native=(
            input_obj.scheduled_supervision_snapshot_frozen_before_native
        ),
        scheduled_supervision_snapshot_reused_after_native=(
            input_obj.scheduled_supervision_snapshot_reused_after_native
        ),
        scheduled_supervision_live_reloaded_after_native=(
            input_obj.scheduled_supervision_live_reloaded_after_native
        ),
        scheduled_dynamic_evidence_projected_after_native=(
            input_obj.scheduled_dynamic_evidence_projected_after_native
        ),
        scheduled_dynamic_evidence_whitelist_exact=(
            input_obj.scheduled_dynamic_evidence_whitelist_exact
        ),
        scheduled_inherited_dynamic_evidence_cleared=(
            input_obj.scheduled_inherited_dynamic_evidence_cleared
        ),
        supervision_target_root_class=input_obj.supervision_target_root_class,
        supervision_surface_label=input_obj.supervision_surface_label,
        native_disposition_proofs_current=(
            input_obj.native_disposition_proofs_current
        ),
        maintenance_lane_active=input_obj.maintenance_lane_active,
        maintenance_lane_executed=input_obj.maintenance_lane_executed,
        shared_maintenance_lock_required=(
            input_obj.shared_maintenance_lock_required
        ),
        shared_maintenance_lock_acquired=(
            input_obj.shared_maintenance_lock_acquired
        ),
        shared_maintenance_lock_released=(
            input_obj.shared_maintenance_lock_released
        ),
        real_lifecycle_review_ok=input_obj.real_lifecycle_review_ok,
        fixture_lifecycle_review_ok=input_obj.fixture_lifecycle_review_ok,
        selected_obligation_ids=input_obj.selected_obligation_ids,
        evaluated_obligation_ids=input_obj.evaluated_obligation_ids,
        validated_obligation_ids=input_obj.validated_obligation_ids,
        semantic_validation_receipt_ids=(
            input_obj.semantic_validation_receipt_ids
        ),
        semantic_range_receipt_ids=input_obj.semantic_range_receipt_ids,
        positive_fixture_target_ids=(
            input_obj.positive_fixture_target_ids
        ),
        shallow_fixture_target_ids=(
            input_obj.shallow_fixture_target_ids
        ),
        gated_noop=input_obj.gated_noop,
        noop_applicable_obligation_ids=(
            input_obj.noop_applicable_obligation_ids
        ),
        noop_executed_obligation_ids=input_obj.noop_executed_obligation_ids,
        noop_passed_obligation_ids=input_obj.noop_passed_obligation_ids,
        noop_receipt_hash=input_obj.noop_receipt_hash,
        noop_consumed_receipt_hash=input_obj.noop_consumed_receipt_hash,
        noop_closure_profile=input_obj.noop_closure_profile,
        receipt_current=True,
        obligation_ids=obligations,
        obligation_evidence_count=len(obligations),
        required_obligation_ids=obligations,
        required_obligation_count=len(obligations),
        expected_check_ids=automation_expected_check_ids(skill_id),
        update_requires_restore=is_update,
        update_phase="awaiting-skillguard" if is_update else "not-update",
        update_status="AWAITING_SKILLGUARD" if is_update else "NOT_UPDATE",
        survivor_states_snapshotted=is_update,
        survivor_snapshot=UPDATE_SURVIVOR_SNAPSHOT if is_update else (),
        survivor_user_pause_bits=(
            UPDATE_SURVIVOR_USER_PAUSE_BITS if is_update else ()
        ),
        current_survivor_states=ALL_UPDATE_SURVIVORS_PAUSED if is_update else (),
        current_user_pause_bits=(
            UPDATE_SURVIVOR_USER_PAUSE_BITS if is_update else ()
        ),
        survivors_paused=is_update,
        side_effects=(
            "scheduled-supervision-start-snapshot",
            "native-receipt",
            "scheduled-dynamic-evidence-projection",
        ),
    )


def _depth_state(skill_id: str) -> AutomationState:
    state = _native_state(skill_id)
    receipt_id = f"depth:{state.run_id}"
    return replace(
        state,
        expected_run_id=state.run_id,
        expected_receipt_hash=state.receipt_hash,
        supervisor_contract_digest=state.contract_digest,
        executed_check_ids=state.expected_check_ids,
        depth_obligation_ids=AUTOMATION_DEPTH_TARGET_OBLIGATIONS[skill_id],
        depth_status="EXECUTION_DEPTH_PASS",
        depth_current=True,
        depth_receipt_id=receipt_id,
        depth_receipt_hash=_depth_receipt_hash(state.run_id),
        target_check_execution_count=len(state.expected_check_ids),
        side_effects=_append_unique(state.side_effects, "depth-receipt"),
    )


def _closed_state(skill_id: str) -> AutomationState:
    if skill_id == UPDATE_SKILL_ID:
        return _authorized_update_state()
    state = _depth_state(skill_id)
    return replace(
        state,
        closure_profile="enforced",
        closure_current=True,
        consumed_depth_receipt_id=state.depth_receipt_id,
        consumed_depth_receipt_hash=state.depth_receipt_hash,
        close_target_check_execution_count=0,
        enforced_closed=True,
        closure_consumed_depth=True,
        closure_completion_scope="overall_complete",
        overall_complete=True,
        update_phase="not-update",
        update_status="NOT_UPDATE",
        side_effects=_append_unique(state.side_effects, "closure-receipt"),
    )


def _terminal_ready_update_state() -> AutomationState:
    state = _depth_state(UPDATE_SKILL_ID)
    branch_id = "prepared-update"
    return replace(
        state,
        target_native_terminal_receipt_owner=UPDATE_SKILL_ID,
        target_native_terminal_receipt_id=_native_terminal_receipt_id(
            state.run_id, branch_id
        ),
        target_native_terminal_receipt_hash=_native_terminal_receipt_hash(
            state.run_id, branch_id
        ),
        target_native_terminal_branch_id=branch_id,
        target_native_terminal_kind="prepared_update",
        target_native_terminal_disposition="non_terminal_authorization",
        target_native_terminal_depth_receipt_id=state.depth_receipt_id,
        target_native_terminal_depth_receipt_hash=state.depth_receipt_hash,
        side_effects=_append_unique(
            state.side_effects, "target-native-terminal-receipt"
        ),
    )


def _authorized_update_state() -> AutomationState:
    state = _terminal_ready_update_state()
    return replace(
        state,
        overall_complete=False,
        authorization_run_id=state.run_id,
        authorization_declared_check_receipt_id="authorization-declared-check-receipt",
        authorization_supervision_stage="declared_check_authorization",
        authorization_route_ids=(UPDATE_AUTHORIZE_ROUTE_ID,),
        authorization_staged=True,
        authorization_consumed_depth_receipt_id=state.depth_receipt_id,
        authorization_consumed_depth_receipt_hash=state.depth_receipt_hash,
        authorization_reconciliation_target_check_execution_count=0,
        authorization_consumed_native_terminal_receipt_id=(
            state.target_native_terminal_receipt_id
        ),
        authorization_consumed_native_terminal_receipt_hash=(
            state.target_native_terminal_receipt_hash
        ),
        authorization_completion_scope="authorization_only",
        authorization_overall_complete=False,
        update_phase="authorized",
        update_status="AUTHORIZED_AWAITING_STAGING",
        current_survivor_states=ALL_UPDATE_SURVIVORS_PAUSED,
        survivors_paused=True,
        side_effects=_append_unique(state.side_effects, "authorization-declared-check-receipt"),
    )


def _staged_update_state() -> AutomationState:
    state = _authorized_update_state()
    return replace(
        state,
        update_phase="restoration-staged",
        update_status="RESTORATION_STAGED_AWAITING_FINALIZATION",
        staged_target_states=state.survivor_snapshot,
        staged_user_pause_bits=state.survivor_user_pause_bits,
        staged_automation_hashes=UPDATE_PLANNED_AUTOMATION_HASHES,
        staged_consumed_native_receipt_hash=state.receipt_hash,
        staged_consumed_authorization_receipt_id=state.authorization_declared_check_receipt_id,
        deferred_install_check_id="normal-install-check-after-live-readback",
        restoration_receipt_id="restoration-finalization-receipt",
        restoration_receipt_hash="restoration-finalization-hash",
        restoration_staged=True,
        current_survivor_states=ALL_UPDATE_SURVIVORS_PAUSED,
        survivors_paused=True,
        side_effects=_append_unique(
            state.side_effects, "stage-restoration-authorization"
        ),
    )


def _finalization_depth_state() -> AutomationState:
    state = _staged_update_state()
    run_id = "finalization-supervisor-run"
    return replace(
        state,
        finalization_run_id=run_id,
        finalization_depth_receipt_id=f"depth:{run_id}",
        finalization_depth_receipt_hash=_depth_receipt_hash(run_id),
        finalization_depth_status="EXECUTION_DEPTH_PASS",
        finalization_depth_current=True,
        finalization_executed_check_ids=automation_manifest_check_ids(
            UPDATE_SKILL_ID
        ),
        finalization_route_ids=UPDATE_COMPOSED_ROUTE_IDS,
        finalization_composed=True,
        finalization_stage_included_authorize_checks=True,
        finalization_target_check_execution_count=len(
            automation_manifest_check_ids(UPDATE_SKILL_ID)
        ),
        side_effects=_append_unique(state.side_effects, "finalization-depth-receipt"),
    )


def _finalization_terminal_ready_state() -> AutomationState:
    state = _finalization_depth_state()
    branch_id = "prepared-update"
    return replace(
        state,
        finalization_native_terminal_receipt_owner=UPDATE_SKILL_ID,
        finalization_native_terminal_receipt_id=_native_terminal_receipt_id(
            state.finalization_run_id, branch_id
        ),
        finalization_native_terminal_receipt_hash=_native_terminal_receipt_hash(
            state.finalization_run_id, branch_id
        ),
        finalization_native_terminal_branch_id=branch_id,
        finalization_native_terminal_disposition="terminal_completion",
        finalization_native_terminal_depth_receipt_id=(
            state.finalization_depth_receipt_id
        ),
        finalization_native_terminal_depth_receipt_hash=(
            state.finalization_depth_receipt_hash
        ),
        side_effects=_append_unique(
            state.side_effects, "finalization-target-native-terminal-receipt"
        ),
    )


def _finalized_update_state() -> AutomationState:
    state = _finalization_terminal_ready_state()
    finalization_run_id = state.finalization_run_id
    finalization_depth_receipt_id = state.finalization_depth_receipt_id
    finalization_depth_receipt_hash = state.finalization_depth_receipt_hash
    branch_id = "prepared-update"
    return replace(
        state,
        closure_profile="enforced",
        closure_current=True,
        consumed_depth_receipt_id=finalization_depth_receipt_id,
        consumed_depth_receipt_hash=finalization_depth_receipt_hash,
        enforced_closed=True,
        closure_consumed_depth=True,
        closure_completion_scope="terminal_completion",
        overall_complete=True,
        update_phase="finalization-closed",
        update_status="FINALIZATION_CLOSED_AWAITING_LIVE_RESTORE",
        finalization_run_id=finalization_run_id,
        finalization_depth_receipt_id=finalization_depth_receipt_id,
        finalization_depth_receipt_hash=finalization_depth_receipt_hash,
        finalization_depth_status="EXECUTION_DEPTH_PASS",
        finalization_depth_current=True,
        finalization_executed_check_ids=automation_manifest_check_ids(
            UPDATE_SKILL_ID
        ),
        finalization_route_ids=UPDATE_COMPOSED_ROUTE_IDS,
        finalization_composed=True,
        finalization_stage_included_authorize_checks=True,
        finalization_target_check_execution_count=len(
            automation_manifest_check_ids(UPDATE_SKILL_ID)
        ),
        finalization_close_target_check_execution_count=0,
        finalization_native_terminal_receipt_owner=UPDATE_SKILL_ID,
        finalization_native_terminal_receipt_id=_native_terminal_receipt_id(
            finalization_run_id, branch_id
        ),
        finalization_native_terminal_receipt_hash=_native_terminal_receipt_hash(
            finalization_run_id, branch_id
        ),
        finalization_native_terminal_branch_id=branch_id,
        finalization_native_terminal_depth_receipt_id=(
            finalization_depth_receipt_id
        ),
        finalization_native_terminal_depth_receipt_hash=(
            finalization_depth_receipt_hash
        ),
        finalization_consumed_depth_receipt_hash=finalization_depth_receipt_hash,
        finalization_consumed_native_terminal_receipt_id=(
            _native_terminal_receipt_id(finalization_run_id, branch_id)
        ),
        finalization_consumed_native_terminal_receipt_hash=(
            _native_terminal_receipt_hash(finalization_run_id, branch_id)
        ),
        finalization_consumed_native_hash=state.receipt_hash,
        finalization_consumed_restoration_hash=state.restoration_receipt_hash,
        current_survivor_states=ALL_UPDATE_SURVIVORS_PAUSED,
        survivors_paused=True,
        side_effects=_append_unique(
            state.side_effects, "finalization-enforced-closure"
        ),
    )


def _restored_update_state() -> AutomationState:
    state = _finalized_update_state()
    return replace(
        state,
        update_phase="restored-verified",
        update_status="RESTORED_VERIFIED",
        current_survivor_states=state.survivor_snapshot,
        current_user_pause_bits=state.survivor_user_pause_bits,
        survivors_paused=False,
        restored_survivor_states=state.survivor_snapshot,
        restored_after_closure=True,
        live_restore_applied=True,
        live_restore_readback_ok=True,
        normal_install_check_ok=True,
        readback_survivor_states=state.survivor_snapshot,
        readback_user_pause_bits=state.survivor_user_pause_bits,
        readback_automation_hashes=state.staged_automation_hashes,
        side_effects=_append_unique(
            _append_unique(
                _append_unique(state.side_effects, "restore-survivors"),
                "readback-survivors",
            ),
            "normal-install-check",
        ),
    )


class AutomationRuntimeAssuranceBlock:
    name = "AutomationRuntimeAssuranceBlock"
    reads = tuple(AutomationState.__dataclass_fields__)
    writes = reads
    accepted_input_type = AutomationInput
    input_description = "one scheduled native-receipt or SkillGuard closure event"
    output_description = "one fail-closed automation completion decision"
    idempotency = (
        "Target Skill ids, contract digests, run ids, immutable receipt hashes, depth "
        "receipt ids, and update phase side effects make replay idempotent."
    )

    def __init__(self, *, broken_mode: str = "") -> None:
        self.broken_mode = broken_mode

    @staticmethod
    def _fail_closed(state: AutomationState) -> AutomationState:
        if not state.update_requires_restore and state.target_skill_id != UPDATE_SKILL_ID:
            return state
        return replace(
            state,
            update_phase="failed",
            update_status="FAILED",
            current_survivor_states=ALL_UPDATE_SURVIVORS_PAUSED,
            survivors_paused=True,
            live_restore_applied=False,
            live_restore_readback_ok=False,
            normal_install_check_ok=False,
            marked_current_after_closure=False,
            guarded_terminal=False,
            failure_repaused=True,
        )

    def apply(
        self, input_obj: AutomationInput, state: AutomationState
    ) -> Iterable[FunctionResult]:
        if input_obj.kind in {"native_terminal", "native_update_terminal"}:
            skill_id = input_obj.skill_id
            expected_obligations = AUTOMATION_TARGET_OBLIGATIONS.get(skill_id, ())
            update_run = skill_id == UPDATE_SKILL_ID
            obligation_ids = input_obj.obligation_ids
            receipt_skill_id = input_obj.receipt_skill_id or skill_id
            maintenance_lane_active = input_obj.maintenance_lane_active
            maintenance_lane_executed = input_obj.maintenance_lane_executed
            shared_lock_acquired = input_obj.shared_maintenance_lock_acquired
            shared_lock_released = input_obj.shared_maintenance_lock_released
            real_lifecycle_review_ok = input_obj.real_lifecycle_review_ok
            fixture_lifecycle_review_ok = input_obj.fixture_lifecycle_review_ok
            selected_obligations = input_obj.selected_obligation_ids
            evaluated_obligations = input_obj.evaluated_obligation_ids
            validated_obligations = input_obj.validated_obligation_ids
            semantic_receipts = input_obj.semantic_validation_receipt_ids
            semantic_range_receipts = input_obj.semantic_range_receipt_ids
            positive_fixture_targets = input_obj.positive_fixture_target_ids
            shallow_fixture_targets = input_obj.shallow_fixture_target_ids
            gated_noop = input_obj.gated_noop
            noop_applicable = input_obj.noop_applicable_obligation_ids
            noop_executed = input_obj.noop_executed_obligation_ids
            noop_passed = input_obj.noop_passed_obligation_ids
            noop_receipt_hash = input_obj.noop_receipt_hash
            noop_consumed_receipt_hash = input_obj.noop_consumed_receipt_hash
            noop_closure_profile = input_obj.noop_closure_profile
            evidence_domain = input_obj.evidence_domain
            native_receipt_origin = input_obj.native_receipt_origin
            installation_receipt_root_ref = input_obj.installation_receipt_root_ref
            installation_receipt_current = input_obj.installation_receipt_current
            runtime_projection_exact_inventory = (
                input_obj.runtime_projection_exact_inventory
            )
            runtime_projection_bytecode_writes_suppressed = (
                input_obj.runtime_projection_bytecode_writes_suppressed
            )
            snapshot_frozen_before_native = (
                input_obj.scheduled_supervision_snapshot_frozen_before_native
            )
            snapshot_reused_after_native = (
                input_obj.scheduled_supervision_snapshot_reused_after_native
            )
            live_reloaded_after_native = (
                input_obj.scheduled_supervision_live_reloaded_after_native
            )
            dynamic_evidence_projected_after_native = (
                input_obj.scheduled_dynamic_evidence_projected_after_native
            )
            dynamic_evidence_whitelist_exact = (
                input_obj.scheduled_dynamic_evidence_whitelist_exact
            )
            inherited_dynamic_evidence_cleared = (
                input_obj.scheduled_inherited_dynamic_evidence_cleared
            )
            supervision_target_root_class = input_obj.supervision_target_root_class
            supervision_surface_label = input_obj.supervision_surface_label
            native_disposition_proofs_current = (
                input_obj.native_disposition_proofs_current
            )
            if self.broken_mode == "wrong_target_obligation_set" and obligation_ids:
                obligation_ids = obligation_ids[:-1]
            if self.broken_mode == "wrong_target_receipt":
                receipt_skill_id = next(
                    item for item in AUTOMATION_TARGET_OBLIGATIONS if item != skill_id
                )
            if self.broken_mode == "dream_active_lane_skipped":
                maintenance_lane_active = True
                maintenance_lane_executed = False
            elif self.broken_mode == "phase_single_source_overclaims_full_semantics":
                one_source = "semantic-receipt:one-passing-source-check"
                selected_obligations = expected_obligations
                evaluated_obligations = expected_obligations
                validated_obligations = expected_obligations
                semantic_receipts = (one_source,) * len(expected_obligations)
                semantic_range_receipts = tuple(
                    f"fabricated-sequence-range:{index}"
                    for index, _ in enumerate(expected_obligations)
                )
            elif self.broken_mode == "update_noop_authorization_only":
                gated_noop = True
                noop_applicable = expected_obligations
                noop_executed = ()
                noop_passed = expected_obligations
                noop_receipt_hash = input_obj.receipt_hash
                noop_consumed_receipt_hash = ""
                noop_closure_profile = "declared_check_authorization"
            elif self.broken_mode == "generic_fixture_targets_substitute_exact_obligations":
                positive_fixture_targets = ("obligation:one", "obligation:two")
                shallow_fixture_targets = ("obligation:one", "obligation:two")
            elif self.broken_mode == "sleep_shared_lock_unheld":
                shared_lock_acquired = False
                shared_lock_released = False
            elif self.broken_mode == "sleep_fixture_masks_real_lifecycle_failure":
                real_lifecycle_review_ok = False
                fixture_lifecycle_review_ok = True
            elif self.broken_mode == "gated_noop_overclaims_obligations":
                gated_noop = True
                noop_applicable = expected_obligations[:1]
                noop_executed = ()
                noop_passed = expected_obligations
            elif self.broken_mode == "source_capability_closes_scheduled_production":
                evidence_domain = "source_capability"
                native_receipt_origin = "source-only-capability"
            elif self.broken_mode == "fixture_closes_scheduled_production":
                evidence_domain = "fixture"
                native_receipt_origin = "fixture"
            elif self.broken_mode == "scheduled_identity_missing_root_ref":
                installation_receipt_root_ref = ()
            elif self.broken_mode == "scheduled_identity_installation_stale":
                installation_receipt_current = False
            elif self.broken_mode == "runtime_projection_bytecode_mutated":
                runtime_projection_exact_inventory = False
                runtime_projection_bytecode_writes_suppressed = False
            elif self.broken_mode == "scheduled_supervision_live_reloaded_after_native":
                snapshot_reused_after_native = False
                live_reloaded_after_native = True
            elif self.broken_mode == "scheduled_dynamic_evidence_not_projected":
                dynamic_evidence_projected_after_native = False
            elif self.broken_mode == "scheduled_dynamic_evidence_not_isolated":
                dynamic_evidence_whitelist_exact = False
                inherited_dynamic_evidence_cleared = False
            elif self.broken_mode == "surface_label_selects_supervision_authority":
                supervision_target_root_class = "label-derived-source"
            elif self.broken_mode in {
                "not_applicable_without_gate_proof",
                "branch_projection_requires_inapplicable_fields",
            }:
                native_disposition_proofs_current = False
            native_status = input_obj.native_status
            marked_current = False
            update_phase = "awaiting-skillguard" if update_run else "not-update"
            if update_run and self.broken_mode == "native_update_prematurely_current":
                marked_current = True
                update_phase = "current"
            valid_native = bool(
                expected_obligations
                and receipt_skill_id == skill_id
                and obligation_ids == expected_obligations
                and input_obj.contract_digest
                and input_obj.run_id
                and input_obj.receipt_hash
                and evidence_domain == "scheduled_production"
                and native_receipt_origin == "scheduled-real"
                and input_obj.scheduler_or_trigger_id
                and input_obj.scheduled_execution_id == input_obj.run_id
                and input_obj.installation_receipt_id
                and input_obj.installation_receipt_hash
                and installation_receipt_root_ref
                == SCHEDULED_INSTALLATION_RECEIPT_ROOT_REF
                and input_obj.installed_runtime_fingerprint
                and installation_receipt_current
                and runtime_projection_exact_inventory
                and runtime_projection_bytecode_writes_suppressed
                and snapshot_frozen_before_native
                and snapshot_reused_after_native
                and not live_reloaded_after_native
                and dynamic_evidence_projected_after_native
                and dynamic_evidence_whitelist_exact
                and inherited_dynamic_evidence_cleared
                and supervision_target_root_class == "exact-installed-root"
                and native_disposition_proofs_current
                and (
                    native_status == "awaiting-skillguard"
                    if update_run
                    else native_status == "completed"
                )
                and (
                    not update_run
                    or (
                        _snapshot_has_exact_survivors(input_obj.survivor_snapshot)
                        and _pause_bits_have_exact_survivors(
                            input_obj.survivor_user_pause_bits
                        )
                        and input_obj.kind == "native_update_terminal"
                    )
                )
            )
            bypass_native = self.broken_mode in {
                "wrong_target_obligation_set",
                "wrong_target_receipt",
                "native_update_prematurely_current",
                "source_capability_closes_scheduled_production",
                "fixture_closes_scheduled_production",
                "scheduled_identity_missing_root_ref",
                "scheduled_identity_installation_stale",
                "runtime_projection_bytecode_mutated",
                "scheduled_supervision_live_reloaded_after_native",
                "scheduled_dynamic_evidence_not_projected",
                "scheduled_dynamic_evidence_not_isolated",
                "surface_label_selects_supervision_authority",
                "not_applicable_without_gate_proof",
                "branch_projection_requires_inapplicable_fields",
            }
            if not valid_native and not bypass_native:
                failed = replace(
                    state,
                    target_skill_id=skill_id,
                    update_requires_restore=update_run,
                )
                yield FunctionResult(
                    AutomationOutput("native_terminal_blocked"),
                    self._fail_closed(failed),
                    "native_terminal_blocked",
                )
                return
            yield FunctionResult(
                AutomationOutput("native_terminal_receipted"),
                AutomationState(
                    target_skill_id=skill_id,
                    receipt_skill_id=receipt_skill_id,
                    run_id=input_obj.run_id,
                    receipt_hash=input_obj.receipt_hash,
                    contract_digest=input_obj.contract_digest,
                    native_terminal=True,
                    native_status=native_status,
                    native_receipt_origin=native_receipt_origin,
                    evidence_domain=evidence_domain,
                    scheduler_or_trigger_id=input_obj.scheduler_or_trigger_id,
                    scheduled_execution_id=input_obj.scheduled_execution_id,
                    installation_receipt_id=input_obj.installation_receipt_id,
                    installation_receipt_hash=input_obj.installation_receipt_hash,
                    installation_receipt_root_ref=installation_receipt_root_ref,
                    installed_runtime_fingerprint=(
                        input_obj.installed_runtime_fingerprint
                    ),
                    installation_receipt_current=installation_receipt_current,
                    runtime_projection_exact_inventory=(
                        runtime_projection_exact_inventory
                    ),
                    runtime_projection_bytecode_writes_suppressed=(
                        runtime_projection_bytecode_writes_suppressed
                    ),
                    scheduled_supervision_snapshot_frozen_before_native=(
                        snapshot_frozen_before_native
                    ),
                    scheduled_supervision_snapshot_reused_after_native=(
                        snapshot_reused_after_native
                    ),
                    scheduled_supervision_live_reloaded_after_native=(
                        live_reloaded_after_native
                    ),
                    scheduled_dynamic_evidence_projected_after_native=(
                        dynamic_evidence_projected_after_native
                    ),
                    scheduled_dynamic_evidence_whitelist_exact=(
                        dynamic_evidence_whitelist_exact
                    ),
                    scheduled_inherited_dynamic_evidence_cleared=(
                        inherited_dynamic_evidence_cleared
                    ),
                    supervision_target_root_class=supervision_target_root_class,
                    supervision_surface_label=supervision_surface_label,
                    native_disposition_proofs_current=(
                        native_disposition_proofs_current
                    ),
                    maintenance_lane_active=maintenance_lane_active,
                    maintenance_lane_executed=maintenance_lane_executed,
                    shared_maintenance_lock_required=(
                        input_obj.shared_maintenance_lock_required
                    ),
                    shared_maintenance_lock_acquired=shared_lock_acquired,
                    shared_maintenance_lock_released=shared_lock_released,
                    real_lifecycle_review_ok=real_lifecycle_review_ok,
                    fixture_lifecycle_review_ok=fixture_lifecycle_review_ok,
                    selected_obligation_ids=selected_obligations,
                    evaluated_obligation_ids=evaluated_obligations,
                    validated_obligation_ids=validated_obligations,
                    semantic_validation_receipt_ids=semantic_receipts,
                    semantic_range_receipt_ids=semantic_range_receipts,
                    positive_fixture_target_ids=positive_fixture_targets,
                    shallow_fixture_target_ids=shallow_fixture_targets,
                    gated_noop=gated_noop,
                    noop_applicable_obligation_ids=noop_applicable,
                    noop_executed_obligation_ids=noop_executed,
                    noop_passed_obligation_ids=noop_passed,
                    noop_receipt_hash=noop_receipt_hash,
                    noop_consumed_receipt_hash=noop_consumed_receipt_hash,
                    noop_closure_profile=noop_closure_profile,
                    receipt_current=True,
                    obligation_ids=obligation_ids,
                    obligation_evidence_count=len(obligation_ids),
                    required_obligation_ids=expected_obligations,
                    required_obligation_count=len(expected_obligations),
                    expected_check_ids=automation_expected_check_ids(skill_id),
                    update_requires_restore=update_run,
                    update_phase=update_phase,
                    update_status=(
                        "CURRENT"
                        if marked_current
                        else ("AWAITING_SKILLGUARD" if update_run else "NOT_UPDATE")
                    ),
                    survivor_states_snapshotted=update_run,
                    survivor_snapshot=(
                        input_obj.survivor_snapshot if update_run else ()
                    ),
                    survivor_user_pause_bits=(
                        input_obj.survivor_user_pause_bits if update_run else ()
                    ),
                    current_survivor_states=(
                        ALL_UPDATE_SURVIVORS_PAUSED if update_run else ()
                    ),
                    current_user_pause_bits=(
                        input_obj.survivor_user_pause_bits if update_run else ()
                    ),
                    survivors_paused=update_run,
                    marked_current_after_closure=marked_current,
                    side_effects=(
                        "scheduled-supervision-start-snapshot",
                        "native-receipt",
                        "scheduled-dynamic-evidence-projection",
                    ),
                ),
                "native_terminal_receipted",
            )
            return
        if input_obj.kind == "partial_native":
            skill_id = input_obj.skill_id
            expected_obligations = AUTOMATION_TARGET_OBLIGATIONS.get(skill_id, ())
            update_run = skill_id == UPDATE_SKILL_ID
            broken_target = TARGET_SHALLOW_BROKEN_MODES.get(skill_id)
            wrongly_terminal = self.broken_mode in {
                "shallow_automation_completion",
                broken_target,
            }
            yield FunctionResult(
                AutomationOutput("partial_native_receipt"),
                AutomationState(
                    target_skill_id=skill_id,
                    receipt_skill_id=input_obj.receipt_skill_id or skill_id,
                    run_id=input_obj.run_id,
                    receipt_hash=input_obj.receipt_hash,
                    contract_digest=input_obj.contract_digest,
                    native_terminal=wrongly_terminal,
                    native_status="partial",
                    native_receipt_origin=input_obj.native_receipt_origin,
                    evidence_domain=input_obj.evidence_domain,
                    scheduler_or_trigger_id=input_obj.scheduler_or_trigger_id,
                    scheduled_execution_id=input_obj.scheduled_execution_id,
                    installation_receipt_id=input_obj.installation_receipt_id,
                    installation_receipt_hash=input_obj.installation_receipt_hash,
                    installation_receipt_root_ref=(
                        input_obj.installation_receipt_root_ref
                    ),
                    installed_runtime_fingerprint=(
                        input_obj.installed_runtime_fingerprint
                    ),
                    installation_receipt_current=(
                        input_obj.installation_receipt_current
                    ),
                    runtime_projection_exact_inventory=(
                        input_obj.runtime_projection_exact_inventory
                    ),
                    runtime_projection_bytecode_writes_suppressed=(
                        input_obj.runtime_projection_bytecode_writes_suppressed
                    ),
                    scheduled_supervision_snapshot_frozen_before_native=(
                        input_obj.scheduled_supervision_snapshot_frozen_before_native
                    ),
                    scheduled_supervision_snapshot_reused_after_native=(
                        input_obj.scheduled_supervision_snapshot_reused_after_native
                    ),
                    scheduled_supervision_live_reloaded_after_native=(
                        input_obj.scheduled_supervision_live_reloaded_after_native
                    ),
                    scheduled_dynamic_evidence_projected_after_native=(
                        input_obj.scheduled_dynamic_evidence_projected_after_native
                    ),
                    scheduled_dynamic_evidence_whitelist_exact=(
                        input_obj.scheduled_dynamic_evidence_whitelist_exact
                    ),
                    scheduled_inherited_dynamic_evidence_cleared=(
                        input_obj.scheduled_inherited_dynamic_evidence_cleared
                    ),
                    supervision_target_root_class=(
                        input_obj.supervision_target_root_class
                    ),
                    supervision_surface_label=input_obj.supervision_surface_label,
                    maintenance_lane_active=input_obj.maintenance_lane_active,
                    maintenance_lane_executed=input_obj.maintenance_lane_executed,
                    shared_maintenance_lock_required=(
                        input_obj.shared_maintenance_lock_required
                    ),
                    shared_maintenance_lock_acquired=(
                        input_obj.shared_maintenance_lock_acquired
                    ),
                    shared_maintenance_lock_released=(
                        input_obj.shared_maintenance_lock_released
                    ),
                    real_lifecycle_review_ok=input_obj.real_lifecycle_review_ok,
                    fixture_lifecycle_review_ok=input_obj.fixture_lifecycle_review_ok,
                    selected_obligation_ids=input_obj.selected_obligation_ids,
                    evaluated_obligation_ids=input_obj.evaluated_obligation_ids,
                    validated_obligation_ids=input_obj.validated_obligation_ids,
                    semantic_validation_receipt_ids=(
                        input_obj.semantic_validation_receipt_ids
                    ),
                    semantic_range_receipt_ids=input_obj.semantic_range_receipt_ids,
                    positive_fixture_target_ids=(
                        input_obj.positive_fixture_target_ids
                    ),
                    shallow_fixture_target_ids=(
                        input_obj.shallow_fixture_target_ids
                    ),
                    receipt_current=True,
                    obligation_ids=input_obj.obligation_ids,
                    obligation_evidence_count=len(input_obj.obligation_ids),
                    required_obligation_ids=expected_obligations,
                    required_obligation_count=len(expected_obligations),
                    expected_check_ids=automation_expected_check_ids(skill_id),
                    update_requires_restore=update_run,
                    update_phase="awaiting-skillguard" if update_run else "not-update",
                    update_status="AWAITING_SKILLGUARD" if update_run else "NOT_UPDATE",
                    survivor_states_snapshotted=update_run,
                    survivor_snapshot=(
                        input_obj.survivor_snapshot if update_run else ()
                    ),
                    survivor_user_pause_bits=(
                        input_obj.survivor_user_pause_bits if update_run else ()
                    ),
                    current_survivor_states=(
                        ALL_UPDATE_SURVIVORS_PAUSED if update_run else ()
                    ),
                    current_user_pause_bits=(
                        input_obj.survivor_user_pause_bits if update_run else ()
                    ),
                    survivors_paused=update_run,
                    side_effects=(
                        "scheduled-supervision-start-snapshot",
                        "native-receipt",
                        "scheduled-dynamic-evidence-projection",
                    ),
                ),
                "partial_native_receipt",
            )
            return
        if input_obj.kind == "depth_evaluate":
            expected_checks = state.expected_check_ids
            executed_checks = input_obj.executed_check_ids or expected_checks
            expected_run_id = input_obj.expected_run_id or state.run_id
            expected_receipt_hash = (
                input_obj.expected_receipt_hash or state.receipt_hash
            )
            supervisor_digest = (
                input_obj.supervisor_contract_digest or state.contract_digest
            )
            expected_depth_obligations = AUTOMATION_DEPTH_TARGET_OBLIGATIONS.get(
                state.target_skill_id, ()
            )
            depth_obligations = (
                input_obj.depth_obligation_ids or expected_depth_obligations
            )
            if (
                self.broken_mode
                == "conditional_finalize_in_generic_depth_denominator"
            ):
                depth_obligations = state.required_obligation_ids
            depth_current = input_obj.depth_current
            if self.broken_mode == "missing_check_id" and executed_checks:
                executed_checks = executed_checks[:-1]
            if self.broken_mode == "duplicate_check_id" and executed_checks:
                executed_checks = executed_checks + (executed_checks[0],)
            if self.broken_mode == "run_id_mismatch":
                expected_run_id = f"{state.run_id}:mismatch"
            if self.broken_mode == "receipt_hash_mismatch":
                expected_receipt_hash = f"{state.receipt_hash}:mismatch"
            if self.broken_mode == "stale_depth_or_closure":
                depth_current = False
            depth_receipt_hash = (
                input_obj.depth_receipt_hash or _depth_receipt_hash(state.run_id)
            )
            if self.broken_mode == "depth_receipt_hash_mismatch":
                depth_receipt_hash = "depth-hash:wrong-run"
            full = (
                state.native_terminal
                and state.receipt_current
                and _scheduled_production_identity_is_current(state)
                and state.target_skill_id in AUTOMATION_TARGET_OBLIGATIONS
                and state.receipt_skill_id == state.target_skill_id
                and state.obligation_ids == state.required_obligation_ids
                and state.obligation_evidence_count == state.required_obligation_count
                and state.contract_digest
                and supervisor_digest == state.contract_digest
                and expected_run_id == state.run_id
                and expected_receipt_hash == state.receipt_hash
                and set(executed_checks) == set(expected_checks)
                and len(executed_checks) == len(expected_checks)
                and len(executed_checks) == len(set(executed_checks))
                and depth_obligations == expected_depth_obligations
                and input_obj.depth_status == "EXECUTION_DEPTH_PASS"
                and depth_current
            )
            depth_bypasses = {
                "shallow_automation_completion",
                "wrong_target_obligation_set",
                "wrong_target_receipt",
                "missing_check_id",
                "duplicate_check_id",
                "run_id_mismatch",
                "receipt_hash_mismatch",
                "stale_depth_or_closure",
                "depth_receipt_hash_mismatch",
                "conditional_finalize_in_generic_depth_denominator",
                *TARGET_SHALLOW_BROKEN_MODES.values(),
            }
            if not full and self.broken_mode not in depth_bypasses:
                yield FunctionResult(
                    AutomationOutput("execution_depth_blocked"),
                    self._fail_closed(
                        replace(state, depth_status="SHALLOW_BLOCKED")
                    ),
                    "execution_depth_blocked",
                )
                return
            depth_receipt_id = input_obj.depth_receipt_id or f"depth:{state.run_id}"
            yield FunctionResult(
                AutomationOutput("execution_depth_passed"),
                replace(
                    state,
                    expected_run_id=expected_run_id,
                    expected_receipt_hash=expected_receipt_hash,
                    supervisor_contract_digest=supervisor_digest,
                    executed_check_ids=executed_checks,
                    depth_obligation_ids=depth_obligations,
                    depth_status="EXECUTION_DEPTH_PASS",
                    depth_current=depth_current,
                    depth_receipt_id=depth_receipt_id,
                    depth_receipt_hash=depth_receipt_hash,
                    target_check_execution_count=len(executed_checks),
                    side_effects=_append_unique(
                        state.side_effects, "depth-receipt"
                    ),
                ),
                "execution_depth_passed",
            )
            return
        if input_obj.kind == "build_native_terminal":
            if not state.update_requires_restore:
                yield FunctionResult(
                    AutomationOutput("target_native_terminal_not_applicable_blocked"),
                    state,
                    "target_native_terminal_not_applicable_blocked",
                )
                return
            branch_id = (
                input_obj.target_native_terminal_branch_id
                or ("no-update" if state.gated_noop else "prepared-update")
            )
            owner = input_obj.target_native_terminal_receipt_owner or state.target_skill_id
            receipt_id = input_obj.target_native_terminal_receipt_id or (
                _native_terminal_receipt_id(state.run_id, branch_id)
            )
            receipt_hash = input_obj.target_native_terminal_receipt_hash or (
                _native_terminal_receipt_hash(state.run_id, branch_id)
            )
            bound_depth_id = (
                input_obj.target_native_terminal_depth_receipt_id
                or state.depth_receipt_id
            )
            bound_depth_hash = (
                input_obj.target_native_terminal_depth_receipt_hash
                or state.depth_receipt_hash
            )
            if self.broken_mode == "update_terminal_receipt_wrong_owner":
                owner = "skillguard-supervisor"
            elif self.broken_mode == "update_terminal_receipt_depth_mismatch":
                bound_depth_hash = "depth-hash:wrong-run"
            valid = bool(
                state.update_phase == "awaiting-skillguard"
                and state.depth_status == "EXECUTION_DEPTH_PASS"
                and state.depth_current
                and state.depth_receipt_id
                and state.depth_receipt_hash == _depth_receipt_hash(state.run_id)
                and _scheduled_production_identity_is_current(state)
                and owner == state.target_skill_id
                and branch_id
                in {"no-update", "waiting-for-user", "ui-running", "prepared-update"}
                and receipt_id
                and receipt_hash
                and bound_depth_id == state.depth_receipt_id
                and bound_depth_hash == state.depth_receipt_hash
            )
            bypass = self.broken_mode in {
                "update_terminal_receipt_wrong_owner",
                "update_terminal_receipt_depth_mismatch",
            }
            if not valid and not bypass:
                yield FunctionResult(
                    AutomationOutput("target_native_terminal_blocked"),
                    self._fail_closed(state),
                    "target_native_terminal_blocked",
                )
                return
            yield FunctionResult(
                AutomationOutput("target_native_terminal_built"),
                replace(
                    state,
                    target_native_terminal_receipt_owner=owner,
                    target_native_terminal_receipt_id=receipt_id,
                    target_native_terminal_receipt_hash=receipt_hash,
                    target_native_terminal_branch_id=branch_id,
                    target_native_terminal_kind=(
                        "prepared_update"
                        if branch_id == "prepared-update"
                        else "legitimate_noop"
                    ),
                    target_native_terminal_disposition=(
                        "non_terminal_authorization"
                        if branch_id == "prepared-update"
                        else "terminal_completion"
                    ),
                    target_native_terminal_depth_receipt_id=bound_depth_id,
                    target_native_terminal_depth_receipt_hash=bound_depth_hash,
                    side_effects=_append_unique(
                        state.side_effects, "target-native-terminal-receipt"
                    ),
                ),
                "target_native_terminal_built",
            )
            return
        if input_obj.kind == "reconcile_update_checks":
            if not state.update_requires_restore:
                yield FunctionResult(
                    AutomationOutput("authorization_not_applicable_blocked"),
                    state,
                    "authorization_not_applicable_blocked",
                )
                return
            consumed_depth_id = (
                input_obj.consumed_depth_receipt_id or state.depth_receipt_id
            )
            consumed_depth_hash = (
                input_obj.consumed_depth_receipt_hash or state.depth_receipt_hash
            )
            close_check_count = input_obj.close_target_check_execution_count
            authorization_routes = (
                input_obj.authorization_route_ids
                or (UPDATE_AUTHORIZE_ROUTE_ID,)
            )
            consumed_native = input_obj.consumed_native_receipt_hash or state.receipt_hash
            authorization_run_id = input_obj.authorization_run_id or state.run_id
            consumed_terminal_id = (
                input_obj.consumed_target_native_terminal_receipt_id
                or state.target_native_terminal_receipt_id
            )
            consumed_terminal_hash = (
                input_obj.consumed_target_native_terminal_receipt_hash
                or state.target_native_terminal_receipt_hash
            )
            prepared_authorization = (
                state.target_native_terminal_branch_id == "prepared-update"
            )
            expected_profile = (
                "declared_check_authorization" if prepared_authorization else "enforced"
            )
            expected_disposition = (
                "non_terminal_authorization"
                if prepared_authorization
                else "terminal_completion"
            )
            profile = (
                input_obj.supervision_stage
                if prepared_authorization
                else input_obj.closure_profile
            )
            if self.broken_mode == "prepared_authorization_not_nonterminal":
                profile = "enforced"
            elif self.broken_mode == "close_reruns_target_checks":
                close_check_count = 1
            elif self.broken_mode == "update_terminal_receipt_not_consumed":
                consumed_terminal_id = ""
                consumed_terminal_hash = ""
            valid = bool(
                state.update_phase == "awaiting-skillguard"
                and state.depth_status == "EXECUTION_DEPTH_PASS"
                and state.depth_current
                and profile == expected_profile
                and (
                    input_obj.authorization_receipt_current
                    if prepared_authorization
                    else input_obj.closure_current
                )
                and state.depth_receipt_id
                and consumed_depth_id == state.depth_receipt_id
                and state.depth_receipt_hash
                and consumed_depth_hash == state.depth_receipt_hash
                and authorization_run_id == state.run_id
                and input_obj.authorization_declared_check_receipt_id
                and authorization_routes == (UPDATE_AUTHORIZE_ROUTE_ID,)
                and consumed_native == state.receipt_hash
                and close_check_count == 0
                and state.target_native_terminal_receipt_owner
                == state.target_skill_id
                and state.target_native_terminal_receipt_id
                and state.target_native_terminal_receipt_hash
                and state.target_native_terminal_disposition
                == expected_disposition
                and state.target_native_terminal_depth_receipt_id
                == state.depth_receipt_id
                and state.target_native_terminal_depth_receipt_hash
                == state.depth_receipt_hash
                and consumed_terminal_id
                == state.target_native_terminal_receipt_id
                and consumed_terminal_hash
                == state.target_native_terminal_receipt_hash
                and state.current_survivor_states == ALL_UPDATE_SURVIVORS_PAUSED
                and input_obj.operation_ok
            )
            bypass = self.broken_mode in {
                "authorization_overclaims_complete",
                "authorization_unpauses",
                "prepared_authorization_not_nonterminal",
                "close_reruns_target_checks",
                "update_terminal_receipt_not_consumed",
            }
            if not valid and not bypass:
                yield FunctionResult(
                    AutomationOutput("authorization_reconciliation_blocked"),
                    self._fail_closed(state),
                    "authorization_reconciliation_blocked",
                )
                return
            next_state = replace(
                state,
                closure_profile=("" if prepared_authorization else profile),
                closure_current=(False if prepared_authorization else input_obj.closure_current),
                consumed_depth_receipt_id=("" if prepared_authorization else consumed_depth_id),
                consumed_depth_receipt_hash=("" if prepared_authorization else consumed_depth_hash),
                close_target_check_execution_count=(0 if prepared_authorization else close_check_count),
                consumed_target_native_terminal_receipt_id=(
                    "" if prepared_authorization else consumed_terminal_id
                ),
                consumed_target_native_terminal_receipt_hash=(
                    "" if prepared_authorization else consumed_terminal_hash
                ),
                closure_consumed_depth=not prepared_authorization,
                closure_completion_scope=("" if prepared_authorization else "terminal_completion"),
                overall_complete=not prepared_authorization,
                enforced_closed=not prepared_authorization,
                update_requires_restore=prepared_authorization,
                authorization_run_id=authorization_run_id,
                authorization_declared_check_receipt_id=input_obj.authorization_declared_check_receipt_id,
                authorization_supervision_stage=profile,
                authorization_route_ids=authorization_routes,
                authorization_staged=prepared_authorization,
                authorization_consumed_depth_receipt_id=consumed_depth_id,
                authorization_consumed_depth_receipt_hash=consumed_depth_hash,
                authorization_reconciliation_target_check_execution_count=(
                    close_check_count
                ),
                authorization_consumed_native_terminal_receipt_id=(
                    consumed_terminal_id
                ),
                authorization_consumed_native_terminal_receipt_hash=(
                    consumed_terminal_hash
                ),
                authorization_completion_scope=(
                    "authorization_only" if prepared_authorization else ""
                ),
                authorization_overall_complete=False,
                authorization_emitted_closure=False,
                update_phase=("authorized" if prepared_authorization else "noop-terminal"),
                update_status=(
                    "AUTHORIZED_AWAITING_STAGING"
                    if prepared_authorization
                    else "NOOP_TERMINAL"
                ),
                current_survivor_states=ALL_UPDATE_SURVIVORS_PAUSED,
                survivors_paused=True,
                side_effects=_append_unique(
                    state.side_effects,
                    (
                        "authorization-declared-check-receipt"
                        if prepared_authorization
                        else "closure-receipt"
                    ),
                ),
            )
            if self.broken_mode == "authorization_overclaims_complete":
                next_state = replace(
                    next_state,
                    update_phase="current",
                    update_status="CURRENT",
                    marked_current_after_closure=True,
                )
            if self.broken_mode == "authorization_unpauses":
                next_state = replace(
                    next_state,
                    current_survivor_states=state.survivor_snapshot,
                    survivors_paused=False,
                )
            label = (
                "authorization_declared_checks_staged"
                if prepared_authorization
                else "enforced_noop_closed"
            )
            yield FunctionResult(AutomationOutput(label), next_state, label)
            return
        if input_obj.kind == "stage_restoration":
            if not state.update_requires_restore:
                yield FunctionResult(
                    AutomationOutput("staging_not_applicable_blocked"),
                    state,
                    "staging_not_applicable_blocked",
                )
                return
            target_states = input_obj.staged_target_states or state.survivor_snapshot
            pause_bits = (
                input_obj.staged_user_pause_bits or state.survivor_user_pause_bits
            )
            automation_hashes = (
                input_obj.staged_automation_hashes
                or UPDATE_PLANNED_AUTOMATION_HASHES
            )
            staged_consumed_native = (
                input_obj.staged_consumed_native_receipt_hash
                or state.receipt_hash
            )
            staged_consumed_authorization = (
                input_obj.staged_consumed_authorization_receipt_id
                or state.authorization_declared_check_receipt_id
            )
            if self.broken_mode == "staging_state_mismatch" and target_states:
                target_states = (
                    f"{UPDATE_SURVIVOR_IDS[0]}=PAUSED",
                ) + target_states[1:]
            elif self.broken_mode == "staging_pause_bits_mismatch" and pause_bits:
                pause_bits = (not pause_bits[0],) + pause_bits[1:]
            elif self.broken_mode == "staging_hash_set_incomplete":
                automation_hashes = automation_hashes[:-1]
            elif self.broken_mode == "staging_not_bound_native":
                staged_consumed_native = "wrong-native-receipt"
            elif self.broken_mode == "staging_not_bound_authorization_receipt":
                staged_consumed_authorization = "wrong-authorization-declared-check-receipt"
            valid = bool(
                state.update_phase == "authorized"
                and state.authorization_staged
                and state.authorization_supervision_stage == "declared_check_authorization"
                and state.authorization_run_id == state.run_id
                and state.authorization_completion_scope == "authorization_only"
                and not state.closure_profile
                and not state.closure_current
                and not state.closure_consumed_depth
                and not state.overall_complete
                and state.authorization_route_ids == (UPDATE_AUTHORIZE_ROUTE_ID,)
                and target_states == state.survivor_snapshot
                and pause_bits == state.survivor_user_pause_bits
                and _snapshot_has_exact_survivors(target_states)
                and _pause_bits_have_exact_survivors(pause_bits)
                and _hashes_have_exact_survivors(automation_hashes)
                and staged_consumed_native == state.receipt_hash
                and staged_consumed_authorization
                == state.authorization_declared_check_receipt_id
                and input_obj.deferred_install_check_id
                and input_obj.restoration_receipt_id
                and input_obj.restoration_receipt_hash
                and state.current_survivor_states == ALL_UPDATE_SURVIVORS_PAUSED
                and input_obj.operation_ok
            )
            bypass = self.broken_mode in {
                "staging_state_mismatch",
                "staging_pause_bits_mismatch",
                "staging_hash_set_incomplete",
                "staging_not_bound_native",
                "staging_not_bound_authorization_receipt",
                "staging_unpauses_live",
            }
            if not valid and not bypass:
                yield FunctionResult(
                    AutomationOutput("staging_blocked_repaused"),
                    self._fail_closed(state),
                    "staging_blocked_repaused",
                )
                return
            next_state = replace(
                state,
                update_phase="restoration-staged",
                update_status="RESTORATION_STAGED_AWAITING_FINALIZATION",
                current_survivor_states=ALL_UPDATE_SURVIVORS_PAUSED,
                survivors_paused=True,
                staged_target_states=target_states,
                staged_user_pause_bits=pause_bits,
                staged_automation_hashes=automation_hashes,
                staged_consumed_native_receipt_hash=staged_consumed_native,
                staged_consumed_authorization_receipt_id=(
                    staged_consumed_authorization
                ),
                deferred_install_check_id=input_obj.deferred_install_check_id,
                restoration_receipt_id=input_obj.restoration_receipt_id,
                restoration_receipt_hash=input_obj.restoration_receipt_hash,
                restoration_staged=True,
                side_effects=_append_unique(
                    state.side_effects, "stage-restoration-authorization"
                ),
            )
            if self.broken_mode == "staging_unpauses_live":
                next_state = replace(
                    next_state,
                    current_survivor_states=target_states,
                    survivors_paused=False,
                )
            yield FunctionResult(
                AutomationOutput("restoration_authorization_staged"),
                next_state,
                "restoration_authorization_staged",
            )
            return
        if input_obj.kind == "finalization_stage_depth":
            if not state.update_requires_restore:
                yield FunctionResult(
                    AutomationOutput("finalization_depth_not_applicable_blocked"),
                    state,
                    "finalization_depth_not_applicable_blocked",
                )
                return
            run_id = input_obj.finalization_run_id
            depth_receipt_id = input_obj.finalization_depth_receipt_id
            depth_receipt_hash = input_obj.finalization_depth_receipt_hash
            executed_checks = (
                input_obj.finalization_executed_check_ids
                or automation_manifest_check_ids(state.target_skill_id)
            )
            finalization_expected_checks = automation_manifest_check_ids(
                state.target_skill_id
            )
            routes = input_obj.finalization_route_ids or UPDATE_COMPOSED_ROUTE_IDS
            composed = input_obj.compose
            included_authorize = input_obj.stage_included_authorize_checks
            bypass = False
            if self.broken_mode == "finalize_without_staged_authorization":
                bypass = True
            elif self.broken_mode == "finalization_reuses_authorization_run":
                run_id = state.authorization_run_id
                depth_receipt_id = f"depth:{run_id}"
                bypass = True
            elif self.broken_mode == "finalization_missing_composition":
                routes = (UPDATE_FINALIZE_ROUTE_ID,)
                composed = False
                bypass = True
            elif self.broken_mode == "finalization_skips_authorize_rerun":
                included_authorize = False
                bypass = True
            elif self.broken_mode == "finalization_missing_check_id":
                executed_checks = executed_checks[:-1]
                bypass = True
            if not depth_receipt_hash:
                depth_receipt_hash = _depth_receipt_hash(run_id)
            valid = bool(
                state.update_phase == "restoration-staged"
                and state.restoration_staged
                and state.current_survivor_states == ALL_UPDATE_SURVIVORS_PAUSED
                and input_obj.operation_ok
                and run_id
                and run_id != state.authorization_run_id
                and depth_receipt_id == f"depth:{run_id}"
                and depth_receipt_hash == _depth_receipt_hash(run_id)
                and input_obj.finalization_depth_status == "EXECUTION_DEPTH_PASS"
                and input_obj.finalization_depth_current
                and set(executed_checks) == set(finalization_expected_checks)
                and len(executed_checks) == len(finalization_expected_checks)
                and len(executed_checks) == len(set(executed_checks))
                and composed
                and routes == UPDATE_COMPOSED_ROUTE_IDS
                and included_authorize
                and _scheduled_production_identity_is_current(state)
            )
            if not valid and not bypass:
                yield FunctionResult(
                    AutomationOutput("finalization_depth_blocked_repaused"),
                    self._fail_closed(state),
                    "finalization_depth_blocked_repaused",
                )
                return
            yield FunctionResult(
                AutomationOutput("finalization_execution_depth_staged"),
                replace(
                    state,
                    finalization_run_id=run_id,
                    finalization_depth_receipt_id=depth_receipt_id,
                    finalization_depth_receipt_hash=depth_receipt_hash,
                    finalization_depth_status=input_obj.finalization_depth_status,
                    finalization_depth_current=input_obj.finalization_depth_current,
                    finalization_executed_check_ids=executed_checks,
                    finalization_route_ids=routes,
                    finalization_composed=composed,
                    finalization_stage_included_authorize_checks=(
                        included_authorize
                    ),
                    finalization_target_check_execution_count=len(executed_checks),
                    side_effects=_append_unique(
                        state.side_effects, "finalization-depth-receipt"
                    ),
                ),
                "finalization_execution_depth_staged",
            )
            return
        if input_obj.kind == "finalization_build_native_terminal":
            branch_id = input_obj.finalization_native_terminal_branch_id
            owner = (
                input_obj.finalization_native_terminal_receipt_owner
                or state.target_skill_id
            )
            receipt_id = input_obj.finalization_native_terminal_receipt_id or (
                _native_terminal_receipt_id(state.finalization_run_id, branch_id)
            )
            receipt_hash = input_obj.finalization_native_terminal_receipt_hash or (
                _native_terminal_receipt_hash(state.finalization_run_id, branch_id)
            )
            bound_depth_id = (
                input_obj.finalization_native_terminal_depth_receipt_id
                or state.finalization_depth_receipt_id
            )
            bound_depth_hash = (
                input_obj.finalization_native_terminal_depth_receipt_hash
                or state.finalization_depth_receipt_hash
            )
            valid = bool(
                state.update_phase == "restoration-staged"
                and state.finalization_depth_status == "EXECUTION_DEPTH_PASS"
                and state.finalization_depth_current
                and state.finalization_run_id
                and branch_id == "prepared-update"
                and owner == state.target_skill_id
                and receipt_id
                and receipt_hash
                and bound_depth_id == state.finalization_depth_receipt_id
                and bound_depth_hash == state.finalization_depth_receipt_hash
            )
            if not valid:
                yield FunctionResult(
                    AutomationOutput("finalization_native_terminal_blocked_repaused"),
                    self._fail_closed(state),
                    "finalization_native_terminal_blocked_repaused",
                )
                return
            yield FunctionResult(
                AutomationOutput("finalization_native_terminal_built"),
                replace(
                    state,
                    finalization_native_terminal_receipt_owner=owner,
                    finalization_native_terminal_receipt_id=receipt_id,
                    finalization_native_terminal_receipt_hash=receipt_hash,
                    finalization_native_terminal_branch_id=branch_id,
                    finalization_native_terminal_disposition=(
                        "terminal_completion"
                    ),
                    finalization_native_terminal_depth_receipt_id=bound_depth_id,
                    finalization_native_terminal_depth_receipt_hash=(
                        bound_depth_hash
                    ),
                    side_effects=_append_unique(
                        state.side_effects,
                        "finalization-target-native-terminal-receipt",
                    ),
                ),
                "finalization_native_terminal_built",
            )
            return
        if input_obj.kind == "finalization_close":
            consumed_native = input_obj.consumed_native_receipt_hash or state.receipt_hash
            consumed_restoration = input_obj.consumed_restoration_receipt_hash
            consumed_depth_hash = (
                input_obj.finalization_consumed_depth_receipt_hash
                or state.finalization_depth_receipt_hash
            )
            consumed_terminal_id = (
                input_obj.finalization_consumed_native_terminal_receipt_id
                or state.finalization_native_terminal_receipt_id
            )
            consumed_terminal_hash = (
                input_obj.finalization_consumed_native_terminal_receipt_hash
                or state.finalization_native_terminal_receipt_hash
            )
            profile = input_obj.closure_profile
            close_check_count = input_obj.finalization_close_target_check_execution_count
            bypass = False
            if self.broken_mode == "finalization_not_enforced":
                profile = "declared_check_authorization"
                bypass = True
            elif self.broken_mode == "finalization_not_bound_native":
                consumed_native = "wrong-native-receipt"
                bypass = True
            elif self.broken_mode == "finalization_not_bound_staging":
                consumed_restoration = "wrong-staging-receipt"
                bypass = True
            elif self.broken_mode == "finalization_close_reruns_target_checks":
                close_check_count = 1
                bypass = True
            valid = bool(
                state.update_phase == "restoration-staged"
                and state.restoration_staged
                and state.finalization_depth_status == "EXECUTION_DEPTH_PASS"
                and state.finalization_depth_current
                and state.finalization_depth_receipt_id
                == f"depth:{state.finalization_run_id}"
                and state.finalization_depth_receipt_hash
                == _depth_receipt_hash(state.finalization_run_id)
                and profile == "enforced"
                and input_obj.closure_current
                and close_check_count == 0
                and consumed_depth_hash == state.finalization_depth_receipt_hash
                and state.finalization_native_terminal_receipt_owner
                == state.target_skill_id
                and state.finalization_native_terminal_receipt_id
                and state.finalization_native_terminal_receipt_hash
                and state.finalization_native_terminal_disposition
                == "terminal_completion"
                and state.finalization_native_terminal_depth_receipt_id
                == state.finalization_depth_receipt_id
                and state.finalization_native_terminal_depth_receipt_hash
                == state.finalization_depth_receipt_hash
                and consumed_terminal_id
                == state.finalization_native_terminal_receipt_id
                and consumed_terminal_hash
                == state.finalization_native_terminal_receipt_hash
                and consumed_native == state.receipt_hash
                and consumed_restoration == state.restoration_receipt_hash
                and state.current_survivor_states == ALL_UPDATE_SURVIVORS_PAUSED
                and input_obj.operation_ok
            )
            if not valid and not bypass:
                yield FunctionResult(
                    AutomationOutput("finalization_closure_blocked_repaused"),
                    self._fail_closed(state),
                    "finalization_closure_blocked_repaused",
                )
                return
            next_state = replace(
                state,
                closure_profile=profile,
                closure_current=input_obj.closure_current,
                consumed_depth_receipt_id=state.finalization_depth_receipt_id,
                consumed_depth_receipt_hash=consumed_depth_hash,
                enforced_closed=True,
                closure_consumed_depth=True,
                closure_completion_scope="terminal_completion",
                overall_complete=True,
                update_phase="finalization-closed",
                update_status="FINALIZATION_CLOSED_AWAITING_LIVE_RESTORE",
                current_survivor_states=ALL_UPDATE_SURVIVORS_PAUSED,
                survivors_paused=True,
                finalization_close_target_check_execution_count=close_check_count,
                finalization_consumed_depth_receipt_hash=consumed_depth_hash,
                finalization_consumed_native_terminal_receipt_id=(
                    consumed_terminal_id
                ),
                finalization_consumed_native_terminal_receipt_hash=(
                    consumed_terminal_hash
                ),
                finalization_consumed_native_hash=consumed_native,
                finalization_consumed_restoration_hash=consumed_restoration,
                side_effects=_append_unique(
                    state.side_effects, "finalization-enforced-closure"
                ),
            )
            if self.broken_mode == "finalization_unpauses_live":
                next_state = replace(
                    next_state,
                    current_survivor_states=state.staged_target_states,
                    survivors_paused=False,
                )
            yield FunctionResult(
                AutomationOutput("enforced_closure_closed_still_paused"),
                next_state,
                "enforced_closure_closed_still_paused",
            )
            return
        if input_obj.kind == "close":
            if state.update_requires_restore:
                if self.broken_mode == "legacy_update_close_bypass":
                    yield FunctionResult(
                        AutomationOutput("legacy_update_enforced_closed"),
                        replace(
                            state,
                            closure_profile="enforced",
                            closure_current=True,
                            consumed_depth_receipt_id=state.depth_receipt_id,
                            enforced_closed=True,
                            closure_consumed_depth=True,
                            update_phase="finalization-closed",
                            update_status="FINALIZATION_CLOSED_AWAITING_LIVE_RESTORE",
                            side_effects=_append_unique(
                                state.side_effects, "closure-receipt"
                            ),
                        ),
                        "legacy_update_enforced_closed",
                    )
                    return
                yield FunctionResult(
                    AutomationOutput("legacy_update_close_blocked"),
                    self._fail_closed(state),
                    "legacy_update_close_blocked",
                )
                return
            closure_current = input_obj.closure_current
            if self.broken_mode == "stale_depth_or_closure":
                closure_current = False
            consumed_depth_id = (
                input_obj.consumed_depth_receipt_id or state.depth_receipt_id
            )
            consumed_depth_hash = (
                input_obj.consumed_depth_receipt_hash or state.depth_receipt_hash
            )
            close_check_count = input_obj.close_target_check_execution_count
            if self.broken_mode == "close_reruns_target_checks":
                close_check_count = 1
            full = bool(
                state.depth_status == "EXECUTION_DEPTH_PASS"
                and state.depth_current
                and input_obj.closure_profile == "enforced"
                and closure_current
                and state.depth_receipt_id
                and consumed_depth_id == state.depth_receipt_id
                and state.depth_receipt_hash == _depth_receipt_hash(state.run_id)
                and consumed_depth_hash == state.depth_receipt_hash
                and close_check_count == 0
            )
            if not full and self.broken_mode not in {
                "static_contract_only_completion",
                "close_reruns_target_checks",
            }:
                yield FunctionResult(
                    AutomationOutput("enforced_closure_blocked"),
                    self._fail_closed(state),
                    "enforced_closure_blocked",
                )
                return
            yield FunctionResult(
                AutomationOutput("enforced_closed"),
                replace(
                    state,
                    closure_profile=input_obj.closure_profile,
                    closure_current=closure_current,
                    consumed_depth_receipt_id=consumed_depth_id,
                    consumed_depth_receipt_hash=consumed_depth_hash,
                    close_target_check_execution_count=close_check_count,
                    enforced_closed=True,
                    closure_consumed_depth=full,
                    closure_completion_scope="overall_complete",
                    overall_complete=True,
                    update_phase=state.update_phase,
                    update_status=state.update_status,
                    side_effects=_append_unique(
                        state.side_effects, "closure-receipt"
                    ),
                ),
                "enforced_closed",
            )
            return
        if input_obj.kind == "restore":
            if not state.update_requires_restore:
                yield FunctionResult(
                    AutomationOutput("update_restore_not_applicable_blocked"),
                    state,
                    "update_restore_not_applicable_blocked",
                )
                return
            if self.broken_mode not in {
                "live_restore_before_final_closure",
                "preclosure_update_restore",
            }:
                yield FunctionResult(
                    AutomationOutput("preclosure_live_restore_blocked_repaused"),
                    self._fail_closed(state),
                    "preclosure_live_restore_blocked_repaused",
                )
                return
            restored = state.staged_target_states or state.survivor_snapshot
            yield FunctionResult(
                AutomationOutput("live_restore_applied_before_final_closure"),
                replace(
                    state,
                    update_phase="restored-verified",
                    update_status="RESTORED_VERIFIED",
                    current_survivor_states=restored,
                    current_user_pause_bits=(
                        state.staged_user_pause_bits
                        or state.survivor_user_pause_bits
                    ),
                    survivors_paused=False,
                    restored_survivor_states=restored,
                    restored_after_closure=True,
                    live_restore_applied=True,
                    live_restore_readback_ok=True,
                    normal_install_check_ok=True,
                    readback_survivor_states=restored,
                    readback_user_pause_bits=(
                        state.staged_user_pause_bits
                        or state.survivor_user_pause_bits
                    ),
                    readback_automation_hashes=state.staged_automation_hashes,
                    side_effects=_append_unique(
                        _append_unique(
                            _append_unique(state.side_effects, "restore-survivors"),
                            "readback-survivors",
                        ),
                        "normal-install-check",
                    ),
                ),
                "live_restore_applied_before_final_closure",
            )
            return
        if input_obj.kind == "apply_restore":
            if not state.update_requires_restore:
                yield FunctionResult(
                    AutomationOutput("update_restore_not_applicable_blocked"),
                    state,
                    "update_restore_not_applicable_blocked",
                )
                return
            operation_ok = input_obj.operation_ok
            if self.broken_mode == "restore_failure_not_repaused":
                operation_ok = False
            applied_states = input_obj.applied_states or state.staged_target_states
            applied_pause_bits = (
                input_obj.applied_user_pause_bits or state.staged_user_pause_bits
            )
            applied_hashes = (
                input_obj.applied_automation_hashes
                or state.staged_automation_hashes
            )
            readback_states = input_obj.readback_states or state.staged_target_states
            readback_pause_bits = (
                input_obj.readback_user_pause_bits or state.staged_user_pause_bits
            )
            readback_hashes = (
                input_obj.readback_automation_hashes
                or state.staged_automation_hashes
            )
            if self.broken_mode == "restore_state_mismatch" and applied_states:
                applied_states = (
                    f"{UPDATE_SURVIVOR_IDS[0]}=PAUSED",
                ) + applied_states[1:]
            elif self.broken_mode == "readback_state_mismatch" and readback_states:
                readback_states = (
                    f"{UPDATE_SURVIVOR_IDS[0]}=PAUSED",
                ) + readback_states[1:]
            elif self.broken_mode == "readback_pause_bits_mismatch" and readback_pause_bits:
                readback_pause_bits = (
                    not readback_pause_bits[0],
                ) + readback_pause_bits[1:]
            elif self.broken_mode == "readback_hash_mismatch":
                readback_hashes = readback_hashes[:-1]
            failed_signal = bool(
                not operation_ok
                or not input_obj.readback_ok
                or not input_obj.normal_install_check_ok
            )
            if failed_signal:
                failed = self._fail_closed(state)
                if self.broken_mode in {
                    "restore_failure_not_repaused",
                    "readback_failure_not_repaused",
                    "install_check_failure_not_repaused",
                }:
                    failed = replace(
                        failed,
                        current_survivor_states=state.staged_target_states,
                        survivors_paused=False,
                        failure_repaused=False,
                    )
                yield FunctionResult(
                    AutomationOutput("update_restore_failed_repaused"),
                    failed,
                    "update_restore_failed_repaused",
                )
                return
            valid = bool(
                state.update_phase == "finalization-closed"
                and state.enforced_closed
                and state.closure_consumed_depth
                and state.finalization_depth_status == "EXECUTION_DEPTH_PASS"
                and state.finalization_depth_current
                and state.restoration_staged
                and applied_states == state.staged_target_states
                and applied_pause_bits == state.staged_user_pause_bits
                and applied_hashes == state.staged_automation_hashes
                and readback_states == state.staged_target_states
                and readback_pause_bits == state.staged_user_pause_bits
                and readback_hashes == state.staged_automation_hashes
                and _snapshot_has_exact_survivors(applied_states)
                and _pause_bits_have_exact_survivors(applied_pause_bits)
                and _hashes_have_exact_survivors(applied_hashes)
            )
            bypass = self.broken_mode in {
                "restore_state_mismatch",
                "readback_state_mismatch",
                "readback_pause_bits_mismatch",
                "readback_hash_mismatch",
            }
            if not valid and not bypass:
                yield FunctionResult(
                    AutomationOutput("update_restore_blocked_repaused"),
                    self._fail_closed(state),
                    "update_restore_blocked_repaused",
                )
                return
            yield FunctionResult(
                AutomationOutput("update_restore_readback_install_verified"),
                replace(
                    state,
                    update_phase="restored-verified",
                    update_status="RESTORED_VERIFIED",
                    current_survivor_states=applied_states,
                    current_user_pause_bits=applied_pause_bits,
                    survivors_paused=False,
                    restored_survivor_states=applied_states,
                    restored_after_closure=True,
                    live_restore_applied=True,
                    live_restore_readback_ok=input_obj.readback_ok,
                    normal_install_check_ok=input_obj.normal_install_check_ok,
                    readback_survivor_states=readback_states,
                    readback_user_pause_bits=readback_pause_bits,
                    readback_automation_hashes=readback_hashes,
                    side_effects=_append_unique(
                        _append_unique(
                            _append_unique(state.side_effects, "restore-survivors"),
                            "readback-survivors",
                        ),
                        "normal-install-check",
                    ),
                ),
                "update_restore_readback_install_verified",
            )
            return
        if input_obj.kind == "mark_current":
            if not state.update_requires_restore:
                yield FunctionResult(
                    AutomationOutput("update_mark_current_not_applicable_blocked"),
                    state,
                    "update_mark_current_not_applicable_blocked",
                )
                return
            operation_ok = input_obj.operation_ok
            if self.broken_mode == "mark_current_failure_not_repaused":
                operation_ok = False
            valid = bool(
                state.update_phase == "restored-verified"
                and state.restored_after_closure
                and state.restored_survivor_states == state.survivor_snapshot
                and state.current_survivor_states == state.survivor_snapshot
                and state.live_restore_applied
                and state.live_restore_readback_ok
                and state.normal_install_check_ok
                and state.readback_survivor_states == state.survivor_snapshot
                and state.readback_user_pause_bits == state.survivor_user_pause_bits
                and state.readback_automation_hashes == state.staged_automation_hashes
            )
            if not operation_ok:
                failed = self._fail_closed(state)
                if self.broken_mode == "mark_current_failure_not_repaused":
                    failed = replace(
                        failed,
                        current_survivor_states=state.survivor_snapshot,
                        survivors_paused=False,
                        failure_repaused=False,
                    )
                yield FunctionResult(
                    AutomationOutput("update_mark_current_failed_repaused"),
                    failed,
                    "update_mark_current_failed_repaused",
                )
                return
            if not valid and self.broken_mode not in {
                "mark_current_before_restore",
                "mark_current_before_postclosure_validation",
            }:
                yield FunctionResult(
                    AutomationOutput("update_mark_current_blocked_repaused"),
                    self._fail_closed(state),
                    "update_mark_current_blocked_repaused",
                )
                return
            yield FunctionResult(
                AutomationOutput("update_marked_current"),
                replace(
                    state,
                    update_phase="current",
                    update_status="CURRENT",
                    marked_current_after_closure=True,
                    side_effects=_append_unique(state.side_effects, "mark-current"),
                ),
                "update_marked_current",
            )
            return
        if input_obj.kind == "finalize":
            if self.broken_mode == "preclosure_update_restore" and state.update_requires_restore:
                yield FunctionResult(
                    AutomationOutput("guarded_terminal_finalized"),
                    replace(
                        state,
                        update_phase="guarded",
                        update_status="GUARDED_TERMINAL",
                        current_survivor_states=state.survivor_snapshot,
                        survivors_paused=False,
                        restored_survivor_states=state.survivor_snapshot,
                        restored_after_closure=True,
                        marked_current_after_closure=True,
                        guarded_terminal=True,
                    ),
                    "guarded_terminal_finalized",
                )
                return
            ready = bool(
                state.enforced_closed
                and state.closure_consumed_depth
                and (
                    not state.update_requires_restore
                    or (
                        state.update_phase == "current"
                        and state.authorization_staged
                        and state.restoration_staged
                        and state.finalization_run_id
                        and state.finalization_run_id != state.authorization_run_id
                        and state.finalization_depth_status
                        == "EXECUTION_DEPTH_PASS"
                        and state.finalization_depth_current
                        and state.finalization_route_ids
                        == UPDATE_COMPOSED_ROUTE_IDS
                        and state.finalization_composed
                        and state.finalization_stage_included_authorize_checks
                        and state.finalization_consumed_native_hash
                        == state.receipt_hash
                        and state.finalization_consumed_restoration_hash
                        == state.restoration_receipt_hash
                        and state.restored_after_closure
                        and state.restored_survivor_states == state.survivor_snapshot
                        and state.live_restore_applied
                        and state.live_restore_readback_ok
                        and state.normal_install_check_ok
                        and state.readback_survivor_states
                        == state.survivor_snapshot
                        and state.marked_current_after_closure
                        and not state.survivors_paused
                    )
                )
            )
            if not ready:
                yield FunctionResult(
                    AutomationOutput("guarded_finalization_blocked"),
                    self._fail_closed(state),
                    "guarded_finalization_blocked",
                )
                return
            yield FunctionResult(
                AutomationOutput("guarded_terminal_finalized"),
                replace(
                    state,
                    guarded_terminal=True,
                    update_phase=(
                        "guarded" if state.update_requires_restore else state.update_phase
                    ),
                    update_status=(
                        "GUARDED_TERMINAL"
                        if state.update_requires_restore
                        else state.update_status
                    ),
                    side_effects=_append_unique(
                        state.side_effects, "guarded-terminal"
                    ),
                ),
                "guarded_terminal_finalized",
            )
            return
        if input_obj.kind == "fail":
            yield FunctionResult(
                AutomationOutput("automation_failed_repaused"),
                self._fail_closed(state),
                "automation_failed_repaused",
            )


def automation_terminal(output: object, state: AutomationState, trace: object) -> bool:
    del state, trace
    return isinstance(output, AutomationOutput) and (
        "blocked" in output.label or output.label.endswith("failed_repaused")
    )


def automation_completion_requires_native_depth(
    state: AutomationState, trace: object
) -> InvariantResult:
    del trace
    expected = AUTOMATION_TARGET_OBLIGATIONS.get(state.target_skill_id, ())
    if state.native_terminal and (
        not state.runtime_projection_exact_inventory
        or not state.runtime_projection_bytecode_writes_suppressed
        or not state.scheduled_supervision_snapshot_frozen_before_native
        or not state.scheduled_supervision_snapshot_reused_after_native
        or state.scheduled_supervision_live_reloaded_after_native
        or not state.scheduled_dynamic_evidence_projected_after_native
        or not state.scheduled_dynamic_evidence_whitelist_exact
        or not state.scheduled_inherited_dynamic_evidence_cleared
    ):
        return InvariantResult.fail(
            "scheduled native receipt did not retain one immutable start-frozen SkillGuard authority plus one isolated post-native evidence channel"
        )
    if state.depth_status == "EXECUTION_DEPTH_PASS" or state.enforced_closed or state.guarded_terminal:
        missing = []
        if not expected:
            missing.append("known_target_skill_id")
        if state.receipt_skill_id != state.target_skill_id:
            missing.append("receipt_target_binding")
        if not state.native_terminal or not state.receipt_current:
            missing.append("current_native_terminal")
        if not _scheduled_production_identity_is_current(state):
            missing.append("current_six_field_scheduled_production_identity")
        if not state.runtime_projection_exact_inventory:
            missing.append("runtime_projection_exact_inventory")
        if not state.runtime_projection_bytecode_writes_suppressed:
            missing.append("runtime_projection_bytecode_writes_suppressed")
        if not state.scheduled_supervision_snapshot_frozen_before_native:
            missing.append("supervision_snapshot_frozen_before_native")
        if not state.scheduled_supervision_snapshot_reused_after_native:
            missing.append("supervision_snapshot_reused_after_native")
        if state.scheduled_supervision_live_reloaded_after_native:
            missing.append("no_live_supervision_reload_after_native")
        if not state.scheduled_dynamic_evidence_projected_after_native:
            missing.append("post_native_dynamic_evidence_projection")
        if not state.scheduled_dynamic_evidence_whitelist_exact:
            missing.append("exact_dynamic_evidence_whitelist")
        if not state.scheduled_inherited_dynamic_evidence_cleared:
            missing.append("inherited_dynamic_evidence_cleared")
        if not state.native_disposition_proofs_current:
            missing.append("current_per_obligation_disposition_proofs")
        if state.obligation_ids != expected:
            missing.append("exact_target_obligation_set")
        if state.required_obligation_ids != expected:
            missing.append("required_target_obligation_set")
        if state.obligation_evidence_count != len(expected):
            missing.append("exact_target_obligation_count")
        if not state.contract_digest or state.supervisor_contract_digest != state.contract_digest:
            missing.append("contract_digest_binding")
        if not state.run_id or state.expected_run_id != state.run_id:
            missing.append("run_id_binding")
        if not state.receipt_hash or state.expected_receipt_hash != state.receipt_hash:
            missing.append("receipt_hash_binding")
        expected_checks = automation_expected_check_ids(state.target_skill_id)
        if set(state.executed_check_ids) != set(expected_checks):
            missing.append("exact_check_id_set")
        if len(state.executed_check_ids) != len(expected_checks) or len(
            state.executed_check_ids
        ) != len(set(state.executed_check_ids)):
            missing.append("each_check_id_exactly_once")
        expected_depth = AUTOMATION_DEPTH_TARGET_OBLIGATIONS.get(
            state.target_skill_id, ()
        )
        if state.depth_obligation_ids != expected_depth:
            missing.append("depth_exact_obligation_set")
        if not state.depth_current:
            missing.append("current_execution_depth")
        if state.depth_receipt_hash != _depth_receipt_hash(state.run_id):
            missing.append("exact_depth_receipt_hash")
        if state.target_check_execution_count != len(expected_checks):
            missing.append("target_checks_execute_once_during_stage_depth")
        if missing:
            return InvariantResult.fail(
                "automation depth passed without exact target evidence: "
                + ",".join(missing)
            )
    if state.enforced_closed or state.guarded_terminal:
        missing = []
        if state.closure_profile != "enforced":
            missing.append("enforced_profile")
        if not state.closure_current:
            missing.append("current_closure")
        if not state.closure_consumed_depth:
            missing.append("closure_consumed_depth")
        expected_completion_scope = (
            "terminal_completion"
            if state.target_skill_id == UPDATE_SKILL_ID
            else "overall_complete"
        )
        if (
            state.closure_completion_scope != expected_completion_scope
            or not state.overall_complete
        ):
            missing.append("overall_completion_scope")
        if state.update_requires_restore:
            if (
                not state.finalization_depth_receipt_id
                or state.consumed_depth_receipt_id
                != state.finalization_depth_receipt_id
            ):
                missing.append("exact_finalization_depth_receipt_consumed")
            if (
                not state.finalization_depth_receipt_hash
                or state.consumed_depth_receipt_hash
                != state.finalization_depth_receipt_hash
            ):
                missing.append("exact_finalization_depth_receipt_hash_consumed")
            if state.finalization_close_target_check_execution_count:
                missing.append("finalization_close_reran_target_checks")
        elif (
            not state.depth_receipt_id
            or state.consumed_depth_receipt_id != state.depth_receipt_id
        ):
            missing.append("exact_depth_receipt_consumed")
        elif state.consumed_depth_receipt_hash != state.depth_receipt_hash:
            missing.append("exact_depth_receipt_hash_consumed")
        if not state.update_requires_restore and state.close_target_check_execution_count:
            missing.append("close_reran_target_checks")
        if state.target_skill_id == UPDATE_SKILL_ID and state.gated_noop and (
            state.target_native_terminal_disposition != "terminal_completion"
            or state.target_native_terminal_branch_id
            not in {"no-update", "waiting-for-user", "ui-running"}
            or state.target_native_terminal_kind != "legitimate_noop"
            or state.target_native_terminal_receipt_owner != state.target_skill_id
            or state.target_native_terminal_depth_receipt_id
            != state.depth_receipt_id
            or state.target_native_terminal_depth_receipt_hash
            != state.depth_receipt_hash
            or state.consumed_target_native_terminal_receipt_id
            != state.target_native_terminal_receipt_id
            or state.consumed_target_native_terminal_receipt_hash
            != state.target_native_terminal_receipt_hash
        ):
            missing.append("noop_terminal_completion_receipt")
        if missing:
            return InvariantResult.fail(
                "enforced closure lacks current depth consumption: "
                + ",".join(missing)
            )
    if state.update_requires_restore:
        if state.target_native_terminal_receipt_id and (
            state.target_native_terminal_receipt_owner != state.target_skill_id
            or not state.target_native_terminal_receipt_hash
            or state.target_native_terminal_branch_id
            not in {"no-update", "waiting-for-user", "ui-running", "prepared-update"}
            or (
                state.target_native_terminal_branch_id == "prepared-update"
                and state.target_native_terminal_kind != "prepared_update"
            )
            or (
                state.target_native_terminal_branch_id == "prepared-update"
                and state.target_native_terminal_disposition
                != "non_terminal_authorization"
            )
            or (
                state.target_native_terminal_branch_id != "prepared-update"
                and state.target_native_terminal_kind != "legitimate_noop"
            )
            or (
                state.target_native_terminal_branch_id != "prepared-update"
                and state.target_native_terminal_disposition
                != "terminal_completion"
            )
            or state.target_native_terminal_depth_receipt_id
            != state.depth_receipt_id
            or state.target_native_terminal_depth_receipt_hash
            != state.depth_receipt_hash
        ):
            return InvariantResult.fail(
                "system update target-owned terminal receipt is not bound to the exact staged depth receipt"
            )
        if state.finalization_native_terminal_receipt_id and (
            state.finalization_native_terminal_receipt_owner
            != state.target_skill_id
            or not state.finalization_native_terminal_receipt_hash
            or state.finalization_native_terminal_disposition
            != "terminal_completion"
            or state.finalization_native_terminal_depth_receipt_id
            != state.finalization_depth_receipt_id
            or state.finalization_native_terminal_depth_receipt_hash
            != state.finalization_depth_receipt_hash
        ):
            return InvariantResult.fail(
                "system update final target-owned terminal receipt is not bound to the exact staged depth receipt"
            )
        if state.native_terminal and (
            state.native_status != "awaiting-skillguard"
            or state.update_status
            not in {
                "AWAITING_SKILLGUARD",
                "AUTHORIZED_AWAITING_STAGING",
                "RESTORATION_STAGED_AWAITING_FINALIZATION",
                "FINALIZATION_CLOSED_AWAITING_LIVE_RESTORE",
                "RESTORED_VERIFIED",
                "CURRENT",
                "GUARDED_TERMINAL",
                "FAILED",
            }
            or not state.survivor_states_snapshotted
            or not _snapshot_has_exact_survivors(state.survivor_snapshot)
            or not _pause_bits_have_exact_survivors(
                state.survivor_user_pause_bits
            )
        ):
            return InvariantResult.fail(
                "system update native terminal was not an exact awaiting-skillguard snapshot"
            )
        if state.authorization_staged:
            authorization_missing = []
            if state.target_native_terminal_branch_id != "prepared-update":
                authorization_missing.append("prepared_update_branch")
            if state.authorization_supervision_stage != "declared_check_authorization":
                authorization_missing.append("branch_profile")
            if state.authorization_route_ids != (UPDATE_AUTHORIZE_ROUTE_ID,):
                authorization_missing.append("authorize_route_only")
            if state.authorization_run_id != state.run_id:
                authorization_missing.append("stage_depth_close_same_run")
            if not state.authorization_declared_check_receipt_id:
                authorization_missing.append("authorization_declared_check_receipt_id")
            if (
                state.authorization_completion_scope != "authorization_only"
                or state.authorization_overall_complete
            ):
                authorization_missing.append("branch_completion_disposition")
            if state.authorization_emitted_closure:
                authorization_missing.append("nonterminal_stage_emitted_closure")
            if state.authorization_consumed_depth_receipt_id != state.depth_receipt_id:
                authorization_missing.append("exact_depth_receipt_id_consumed")
            if state.authorization_consumed_depth_receipt_hash != state.depth_receipt_hash:
                authorization_missing.append("exact_depth_receipt_hash_consumed")
            if state.authorization_reconciliation_target_check_execution_count:
                authorization_missing.append("close_reran_target_checks")
            if state.target_native_terminal_receipt_owner != state.target_skill_id:
                authorization_missing.append("target_owned_native_terminal")
            if (
                not state.target_native_terminal_receipt_id
                or not state.target_native_terminal_receipt_hash
                or state.target_native_terminal_depth_receipt_id
                != state.depth_receipt_id
                or state.target_native_terminal_depth_receipt_hash
                != state.depth_receipt_hash
                or state.authorization_consumed_native_terminal_receipt_id
                != state.target_native_terminal_receipt_id
                or state.authorization_consumed_native_terminal_receipt_hash
                != state.target_native_terminal_receipt_hash
            ):
                authorization_missing.append("exact_target_native_terminal_consumption")
            if authorization_missing:
                return InvariantResult.fail(
                    "system update non-terminal declared-check authorization incomplete: "
                    + ",".join(authorization_missing)
                )
        preapply_phases = {
            "awaiting-skillguard",
            "authorized",
            "restoration-staged",
            "finalization-closed",
        }
        if state.update_phase in preapply_phases and (
            not state.survivors_paused
            or state.current_survivor_states != ALL_UPDATE_SURVIVORS_PAUSED
        ):
            return InvariantResult.fail(
                "system update changed live automations before final closure"
            )
        if state.restoration_staged:
            staging_missing = []
            if not state.authorization_staged:
                staging_missing.append("authorization_receipt")
            if state.staged_target_states != state.survivor_snapshot:
                staging_missing.append("target_states")
            if state.staged_user_pause_bits != state.survivor_user_pause_bits:
                staging_missing.append("user_pause_bits")
            if not _hashes_have_exact_survivors(state.staged_automation_hashes):
                staging_missing.append("automation_hashes")
            if state.staged_consumed_native_receipt_hash != state.receipt_hash:
                staging_missing.append("native_receipt_binding")
            if (
                state.staged_consumed_authorization_receipt_id
                != state.authorization_declared_check_receipt_id
            ):
                staging_missing.append("authorization_receipt_binding")
            if not state.deferred_install_check_id:
                staging_missing.append("deferred_install_check")
            if not state.restoration_receipt_id or not state.restoration_receipt_hash:
                staging_missing.append("staging_receipt")
            if staging_missing:
                return InvariantResult.fail(
                    "system update staging authorization incomplete: "
                    + ",".join(staging_missing)
                )
        if state.finalization_depth_status == "EXECUTION_DEPTH_PASS":
            staged_depth_missing = []
            if not state.restoration_staged:
                staged_depth_missing.append("staged_restoration_authorization")
            if state.finalization_depth_receipt_hash != _depth_receipt_hash(
                state.finalization_run_id
            ):
                staged_depth_missing.append("exact_finalization_depth_hash")
            if state.finalization_target_check_execution_count != len(
                automation_manifest_check_ids(state.target_skill_id)
            ):
                staged_depth_missing.append("target_checks_execute_once_during_stage_depth")
            if (
                not state.finalization_composed
                or state.finalization_route_ids != UPDATE_COMPOSED_ROUTE_IDS
            ):
                staged_depth_missing.append("authorize_finalize_composition")
            if not state.finalization_stage_included_authorize_checks:
                staged_depth_missing.append("stage_depth_includes_authorize_checks")
            if staged_depth_missing:
                return InvariantResult.fail(
                    "system update finalization depth incomplete: "
                    + ",".join(staged_depth_missing)
                )
        if state.enforced_closed:
            finalization_missing = []
            finalization_expected_checks = automation_manifest_check_ids(
                state.target_skill_id
            )
            if not state.restoration_staged:
                finalization_missing.append("staged_restoration_authorization")
            if (
                not state.finalization_run_id
                or state.finalization_run_id == state.authorization_run_id
            ):
                finalization_missing.append("new_finalization_run")
            if (
                state.finalization_depth_receipt_id
                != f"depth:{state.finalization_run_id}"
            ):
                finalization_missing.append("same_run_depth_receipt")
            if state.finalization_depth_status != "EXECUTION_DEPTH_PASS":
                finalization_missing.append("finalization_depth_pass")
            if not state.finalization_depth_current:
                finalization_missing.append("current_finalization_depth")
            if (
                set(state.finalization_executed_check_ids)
                != set(finalization_expected_checks)
                or len(state.finalization_executed_check_ids)
                != len(finalization_expected_checks)
                or len(state.finalization_executed_check_ids)
                != len(set(state.finalization_executed_check_ids))
            ):
                finalization_missing.append("stage_depth_check_set_exactly_once")
            if state.finalization_target_check_execution_count != len(
                finalization_expected_checks
            ):
                finalization_missing.append("stage_depth_target_check_execution_count")
            if state.finalization_close_target_check_execution_count:
                finalization_missing.append("close_reran_target_checks")
            if (
                not state.finalization_composed
                or state.finalization_route_ids != UPDATE_COMPOSED_ROUTE_IDS
            ):
                finalization_missing.append("authorize_finalize_composition")
            if not state.finalization_stage_included_authorize_checks:
                finalization_missing.append("stage_depth_includes_authorize_checks")
            if (
                state.finalization_native_terminal_receipt_owner
                != state.target_skill_id
                or not state.finalization_native_terminal_receipt_id
                or not state.finalization_native_terminal_receipt_hash
                or state.finalization_native_terminal_depth_receipt_id
                != state.finalization_depth_receipt_id
                or state.finalization_native_terminal_depth_receipt_hash
                != state.finalization_depth_receipt_hash
                or state.finalization_consumed_native_terminal_receipt_id
                != state.finalization_native_terminal_receipt_id
                or state.finalization_consumed_native_terminal_receipt_hash
                != state.finalization_native_terminal_receipt_hash
            ):
                finalization_missing.append("target_owned_native_terminal_consumed")
            if state.finalization_consumed_native_hash != state.receipt_hash:
                finalization_missing.append("native_receipt_binding")
            if (
                state.finalization_consumed_restoration_hash
                != state.restoration_receipt_hash
            ):
                finalization_missing.append("staging_receipt_binding")
            if finalization_missing:
                return InvariantResult.fail(
                    "system update final closure incomplete: "
                    + ",".join(finalization_missing)
                )
        if state.live_restore_applied and not state.enforced_closed:
            return InvariantResult.fail(
                "system update restored live automations before final SkillGuard closure"
            )
        if state.live_restore_applied:
            restore_missing = []
            if not state.restored_after_closure:
                restore_missing.append("postclosure_restore")
            if state.restored_survivor_states != state.staged_target_states:
                restore_missing.append("exact_applied_states")
            if not state.live_restore_readback_ok:
                restore_missing.append("readback_status")
            if state.readback_survivor_states != state.staged_target_states:
                restore_missing.append("readback_states")
            if state.readback_user_pause_bits != state.staged_user_pause_bits:
                restore_missing.append("readback_user_pause_bits")
            if state.readback_automation_hashes != state.staged_automation_hashes:
                restore_missing.append("readback_automation_hashes")
            if not state.normal_install_check_ok:
                restore_missing.append("normal_install_check")
            if state.current_survivor_states != state.staged_target_states:
                restore_missing.append("live_states")
            if restore_missing:
                return InvariantResult.fail(
                    "system update post-closure restore incomplete: "
                    + ",".join(restore_missing)
                )
        if (
            state.update_phase == "restored-verified"
            and state.update_status != "RESTORED_VERIFIED"
        ):
            return InvariantResult.fail(
                "system update verified restore lacks RESTORED_VERIFIED status"
            )
        if state.marked_current_after_closure and (
            not state.restored_after_closure
            or not state.enforced_closed
            or not state.live_restore_applied
            or not state.live_restore_readback_ok
            or not state.normal_install_check_ok
            or state.update_phase not in {"current", "guarded"}
            or state.update_status not in {"CURRENT", "GUARDED_TERMINAL"}
        ):
            return InvariantResult.fail(
                "system update marked current before exact post-closure restore"
            )
        if state.update_phase == "failed" and (
            state.update_status != "FAILED"
            or not state.survivors_paused
            or state.current_survivor_states != ALL_UPDATE_SURVIVORS_PAUSED
            or not state.failure_repaused
        ):
            return InvariantResult.fail(
                "system update failure did not re-pause all retained automations"
            )
        if state.guarded_terminal and (
            state.update_phase != "guarded"
            or state.update_status != "GUARDED_TERMINAL"
            or not state.marked_current_after_closure
            or state.survivors_paused
            or state.current_survivor_states != state.survivor_snapshot
            or not state.live_restore_readback_ok
            or not state.normal_install_check_ok
        ):
            return InvariantResult.fail(
                "system update guarded terminal skipped restore or mark-current ordering"
            )
    if state.guarded_terminal and (
        not state.native_terminal
        or state.depth_status != "EXECUTION_DEPTH_PASS"
        or not state.enforced_closed
    ):
        return InvariantResult.fail(
            "automation guarded terminal lacks native, depth, or closure terminal"
        )
    if len(state.side_effects) != len(set(state.side_effects)):
        return InvariantResult.fail("automation assurance side effect was applied twice")
    if state.update_requires_restore:
        effect_order = (
            "scheduled-supervision-start-snapshot",
            "native-receipt",
            "scheduled-dynamic-evidence-projection",
            "depth-receipt",
            "target-native-terminal-receipt",
            "authorization-declared-check-receipt",
            "stage-restoration-authorization",
            "finalization-depth-receipt",
            "finalization-target-native-terminal-receipt",
            "finalization-enforced-closure",
            "restore-survivors",
            "readback-survivors",
            "normal-install-check",
            "mark-current",
            "guarded-terminal",
        )
        positions = [
            state.side_effects.index(effect)
            for effect in effect_order
            if effect in state.side_effects
        ]
        if positions != sorted(positions):
            return InvariantResult.fail(
                "system update side effects violated staged-closure-restore order"
            )
    return InvariantResult.pass_()


def automation_native_semantics_require_target_receipts(
    state: AutomationState, trace: object
) -> InvariantResult:
    """Reject count-shaped receipts that do not prove target-native semantics."""

    del trace
    if not (
        state.native_terminal
        or state.depth_status == "EXECUTION_DEPTH_PASS"
        or state.enforced_closed
        or state.guarded_terminal
    ):
        return InvariantResult.pass_()
    expected = AUTOMATION_TARGET_OBLIGATIONS.get(state.target_skill_id, ())
    missing: list[str] = []
    if not expected:
        return InvariantResult.fail("native semantic receipt has no known target")
    if state.native_receipt_origin != "scheduled-real":
        missing.append("scheduled_real_native_receipt")
    if not _scheduled_production_identity_is_current(state):
        missing.append("current_six_field_scheduled_production_identity")
    for name, values in (
        ("selected", state.selected_obligation_ids),
        ("evaluated", state.evaluated_obligation_ids),
        ("validated", state.validated_obligation_ids),
    ):
        if values != expected:
            missing.append(f"exact_{name}_target_obligations")
    if not state.native_disposition_proofs_current:
        missing.append("performed_or_proven_not_applicable_per_obligation")
    semantic_receipts = _semantic_receipt_ids(state.target_skill_id)
    if (
        state.semantic_validation_receipt_ids != semantic_receipts
        or len(set(state.semantic_validation_receipt_ids)) != len(expected)
    ):
        missing.append("one_unique_semantic_validation_receipt_per_obligation")
    if (
        state.semantic_range_receipt_ids != semantic_receipts
        or len(set(state.semantic_range_receipt_ids)) != len(expected)
    ):
        missing.append("semantic_ranges_bind_exact_validation_receipts")
    for name, target_ids in (
        ("positive", state.positive_fixture_target_ids),
        ("shallow", state.shallow_fixture_target_ids),
    ):
        if (
            set(target_ids) != set(AUTOMATION_TARGET_IDS)
            or len(target_ids) != len(AUTOMATION_TARGET_IDS)
            or len(target_ids) != len(set(target_ids))
        ):
            missing.append(f"five_target_owned_{name}_fixtures")
    if state.target_skill_id == "kb-dream-pass" and (
        state.maintenance_lane_active and not state.maintenance_lane_executed
    ):
        missing.append("active_dream_maintenance_lane_executed")
    if state.target_skill_id == "kb-sleep-maintenance":
        if not state.shared_maintenance_lock_required:
            missing.append("sleep_shared_maintenance_lock_required")
        if not state.shared_maintenance_lock_acquired:
            missing.append("sleep_shared_maintenance_lock_acquired")
        if not state.shared_maintenance_lock_released:
            missing.append("sleep_shared_maintenance_lock_released")
        if not state.real_lifecycle_review_ok:
            missing.append("real_sleep_lifecycle_review_passed")
        if state.fixture_lifecycle_review_ok and not state.real_lifecycle_review_ok:
            missing.append("fixture_cannot_mask_real_lifecycle_failure")
    if state.gated_noop:
        allowed = AUTOMATION_GATED_NOOP_ELIGIBLE_OBLIGATIONS.get(
            state.target_skill_id, frozenset()
        )
        applicable = set(state.noop_applicable_obligation_ids)
        executed = set(state.noop_executed_obligation_ids)
        passed = set(state.noop_passed_obligation_ids)
        if not applicable.issubset(allowed):
            missing.append("noop_only_applies_to_declared_gate_obligations")
        if applicable & executed:
            missing.append("noop_and_executed_obligations_are_disjoint")
        if passed != applicable | executed:
            missing.append("noop_pass_set_matches_gate_plus_executed_evidence")
        if applicable | executed != set(expected):
            missing.append("functional_obligations_execute_even_on_noop")
        if state.target_skill_id == UPDATE_SKILL_ID and (
            state.noop_closure_profile != "enforced"
            or not state.noop_receipt_hash
            or state.noop_receipt_hash != state.receipt_hash
            or state.noop_consumed_receipt_hash != state.noop_receipt_hash
        ):
            missing.append("update_noop_exact_receipt_enforced_closure")
    if missing:
        return InvariantResult.fail(
            "automation native semantic evidence incomplete: " + ",".join(missing)
        )
    return InvariantResult.pass_()


AUTOMATION_INVARIANTS = (
    Invariant(
        "automation_completion_requires_native_depth",
        "Scheduled completion requires a current native terminal, full obligation evidence, EXECUTION_DEPTH_PASS, and closure consumption",
        automation_completion_requires_native_depth,
    ),
    Invariant(
        "automation_native_semantics_require_target_receipts",
        "Each target requires real target-native semantic receipts, target-specific calibration, lane/lock closure, and discriminating no-op evidence",
        automation_native_semantics_require_target_receipts,
    ),
)

AUTOMATION_INPUTS = (
    *(automation_native_input(skill_id) for skill_id in AUTOMATION_TARGET_OBLIGATIONS),
    *(
        automation_native_input(skill_id, partial=True)
        for skill_id in AUTOMATION_TARGET_OBLIGATIONS
    ),
    AutomationInput("depth_evaluate"),
    AutomationInput("close"),
    AutomationInput("build_native_terminal"),
    AutomationInput(
        "reconcile_update_checks",
        supervision_stage="declared_check_authorization",
        authorization_route_ids=(UPDATE_AUTHORIZE_ROUTE_ID,),
    ),
    AutomationInput("stage_restoration"),
    AutomationInput(
        "finalization_stage_depth",
        finalization_route_ids=UPDATE_COMPOSED_ROUTE_IDS,
    ),
    AutomationInput("finalization_build_native_terminal"),
    AutomationInput(
        "finalization_close",
        finalization_route_ids=UPDATE_COMPOSED_ROUTE_IDS,
    ),
    AutomationInput("restore", survivor_snapshot=UPDATE_SURVIVOR_SNAPSHOT),
    AutomationInput(
        "apply_restore", operation_ok=False
    ),
    AutomationInput("apply_restore"),
    AutomationInput("apply_restore", readback_ok=False),
    AutomationInput("apply_restore", normal_install_check_ok=False),
    AutomationInput("mark_current"),
    AutomationInput("mark_current", operation_ok=False),
    AutomationInput("finalize"),
    AutomationInput("fail"),
)

AUTOMATION_INITIAL_STATES = (
    AutomationState(),
    *(_native_state(skill_id) for skill_id in AUTOMATION_TARGET_OBLIGATIONS),
    _terminal_ready_update_state(),
    _authorized_update_state(),
    _staged_update_state(),
    _finalization_depth_state(),
    _finalization_terminal_ready_state(),
    _finalized_update_state(),
    _restored_update_state(),
)


def automation_workflow(*, broken_mode: str = "") -> Workflow:
    return Workflow(
        (AutomationRuntimeAssuranceBlock(broken_mode=broken_mode),),
        name=f"kb_automation_runtime_assurance{('_' + broken_mode) if broken_mode else ''}",
    )


__all__ = [
    "LIFECYCLE_INITIAL_STATES",
    "LIFECYCLE_INPUTS",
    "LIFECYCLE_INVARIANTS",
    "MIGRATION_INITIAL_STATES",
    "MIGRATION_INPUTS",
    "MIGRATION_INVARIANTS",
    "AUTOMATION_INITIAL_STATES",
    "AUTOMATION_INPUTS",
    "AUTOMATION_INVARIANTS",
    "AUTOMATION_TARGET_OBLIGATIONS",
    "AUTOMATION_CHECK_KINDS",
    "TARGET_SHALLOW_BROKEN_MODES",
    "UPDATE_SKILL_ID",
    "UPDATE_SURVIVOR_IDS",
    "UPDATE_SURVIVOR_SNAPSHOT",
    "ALL_UPDATE_SURVIVORS_PAUSED",
    "AutomationInput",
    "AutomationState",
    "LifecycleInput",
    "LifecycleState",
    "MigrationInput",
    "MigrationState",
    "lifecycle_terminal",
    "lifecycle_workflow",
    "migration_terminal",
    "migration_workflow",
    "automation_terminal",
    "automation_expected_check_ids",
    "automation_native_input",
    "automation_workflow",
]
