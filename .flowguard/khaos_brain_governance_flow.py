"""FlowGuard model for Khaos Brain governance closure.

This model covers the mature-maintenance problems that are not represented by
the older lane/update/i18n models:

- candidate backlog pressure must reach Sleep review, rejection, watch, or
  promotion decisions instead of only accumulating candidates;
- Dream validation handoffs must be closed by Sleep or explicitly watched;
- Architect ready-for-patch work needs an execution outlet or a concrete
  blocker instead of staying in a permanent patch-plan lane;
- route drift must be reviewed or normalized before card creation;
- health rollups must distinguish user-paused organization automations from
  real install drift and stale lane status.

The abstract scenarios use FlowGuard's Workflow/run_exact_sequence APIs.  The
live projection is read-only and maps current repository reports into the same
governance risk vocabulary.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
import json
import sys
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, ScenarioRun, Workflow, run_exact_sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.common import parse_route_segments
DECLARED_TOP_LEVEL_ROUTES = {
    "codex",
    "communication",
    "engineering",
    "repository",
    "system",
    "troubleshooting",
    "work",
    "writing",
}


@dataclass(frozen=True)
class Event:
    kind: str


@dataclass(frozen=True)
class StepResult:
    event: Event
    action: str


def _event_from_input(input_obj: Event | StepResult) -> Event:
    if isinstance(input_obj, StepResult):
        return input_obj.event
    return input_obj


@dataclass(frozen=True)
class State:
    candidate_backlog: str = "normal"
    candidate_review_debt: bool = False
    trusted_promotion_without_review: bool = False
    dream_handoff_strength: str = "none"
    dream_handoff_status: str = "none"
    architect_patch_debt: bool = False
    architect_outlet_status: str = "none"
    route_status: str = "clean"
    bad_route_card_created: bool = False
    install_policy_drift: bool = False
    org_automation_pause: str = "none"
    stale_running_without_lock: bool = False
    health_rollup_status: str = "unknown"
    release_ready: bool = False
    governance_done: bool = False


class CandidateBacklogBlock:
    """Input x State -> Set(Output x State) for candidate backlog governance."""

    name = "CandidateBacklogBlock"
    reads = ("candidate_backlog", "candidate_review_debt", "trusted_promotion_without_review")
    writes = ("candidate_backlog", "candidate_review_debt", "trusted_promotion_without_review")

    def apply(self, input_obj: Event | StepResult, state: State) -> Iterable[FunctionResult]:
        event = _event_from_input(input_obj)
        if event.kind == "candidate_backlog_high":
            yield FunctionResult(
                output=StepResult(event, "candidate_review_debt_opened"),
                new_state=replace(state, candidate_backlog="high", candidate_review_debt=True),
                label="candidate_review_debt_opened",
                reason="High candidate volume creates explicit Sleep review debt.",
            )
            return
        yield FunctionResult(
            output=StepResult(event, "candidate_noop"),
            new_state=state,
            label="candidate_noop",
            reason="Event has no candidate-backlog effect.",
        )
        if event.kind == "sleep_reviews_candidates":
            yield FunctionResult(
                output=StepResult(event, "candidate_review_debt_closed"),
                new_state=replace(state, candidate_review_debt=False),
                label="candidate_review_debt_closed",
                reason="Sleep reviewed the bounded candidate set and closed the backlog debt.",
            )
            return
        if event.kind == "trusted_promotion_with_review":
            yield FunctionResult(
                output=StepResult(event, "trusted_promotion_reviewed"),
                new_state=state,
                label="trusted_promotion_reviewed",
                reason="Promotion is allowed only after semantic review evidence.",
            )
            return
        if event.kind == "trusted_promotion_without_review":
            yield FunctionResult(
                output=StepResult(event, "trusted_promotion_without_review"),
                new_state=replace(state, trusted_promotion_without_review=True),
                label="trusted_promotion_without_review",
                reason="Broken path: candidate promotion skipped semantic review.",
            )
            return


class DreamSleepHandoffBlock:
    """Input x State -> Set(Output x State) for Dream-to-Sleep handoff closure."""

    name = "DreamSleepHandoffBlock"
    reads = ("dream_handoff_strength", "dream_handoff_status")
    writes = ("dream_handoff_strength", "dream_handoff_status")

    def apply(self, input_obj: Event | StepResult, state: State) -> Iterable[FunctionResult]:
        event = _event_from_input(input_obj)
        if event.kind == "dream_validates_strong":
            yield FunctionResult(
                output=StepResult(event, "dream_handoff_open_strong"),
                new_state=replace(state, dream_handoff_strength="strong", dream_handoff_status="open"),
                label="dream_handoff_open_strong",
                reason="Strong Dream evidence creates a Sleep handoff obligation.",
            )
            return
        yield FunctionResult(
            output=StepResult(event, "dream_sleep_noop"),
            new_state=state,
            label="dream_sleep_noop",
            reason="Event has no Dream/Sleep handoff effect.",
        )
        if event.kind == "dream_validates_moderate":
            yield FunctionResult(
                output=StepResult(event, "dream_handoff_open_moderate"),
                new_state=replace(state, dream_handoff_strength="moderate", dream_handoff_status="open"),
                label="dream_handoff_open_moderate",
                reason="Moderate Dream evidence creates a Sleep handoff obligation.",
            )
            return
        if event.kind == "dream_validates_weak":
            yield FunctionResult(
                output=StepResult(event, "dream_handoff_open_weak"),
                new_state=replace(state, dream_handoff_strength="weak", dream_handoff_status="open"),
                label="dream_handoff_open_weak",
                reason="Weak Dream evidence can be watched but cannot directly promote.",
            )
            return
        if event.kind == "sleep_reviews_handoff":
            yield FunctionResult(
                output=StepResult(event, "dream_handoff_reviewed"),
                new_state=replace(state, dream_handoff_status="reviewed"),
                label="dream_handoff_reviewed",
                reason="Sleep reviewed the handoff and chose a card action or no-op decision.",
            )
            return
        if event.kind == "sleep_watches_handoff":
            yield FunctionResult(
                output=StepResult(event, "dream_handoff_watching"),
                new_state=replace(state, dream_handoff_status="watching"),
                label="dream_handoff_watching",
                reason="Sleep explicitly kept the handoff under watch with a reason.",
            )
            return
        if event.kind == "sleep_drops_handoff":
            yield FunctionResult(
                output=StepResult(event, "dream_handoff_dropped"),
                new_state=replace(state, dream_handoff_status="dropped"),
                label="dream_handoff_dropped",
                reason="Broken path: Dream handoff disappeared without a review or watch decision.",
            )
            return
        if event.kind == "promote_dream_handoff":
            yield FunctionResult(
                output=StepResult(event, "dream_handoff_promoted"),
                new_state=replace(state, dream_handoff_status="promoted"),
                label="dream_handoff_promoted",
                reason="Promotion is safe only for reviewed strong/moderate evidence.",
            )
            return


class ArchitectOutletBlock:
    """Input x State -> Set(Output x State) for ready-for-patch execution outlets."""

    name = "ArchitectOutletBlock"
    reads = ("architect_patch_debt", "architect_outlet_status")
    writes = ("architect_patch_debt", "architect_outlet_status")

    def apply(self, input_obj: Event | StepResult, state: State) -> Iterable[FunctionResult]:
        event = _event_from_input(input_obj)
        if event.kind == "architect_ready_for_patch":
            yield FunctionResult(
                output=StepResult(event, "architect_patch_debt_opened"),
                new_state=replace(state, architect_patch_debt=True, architect_outlet_status="patch-plan"),
                label="architect_patch_debt_opened",
                reason="Ready-for-patch work needs a packet, blocker, or watch decision.",
            )
            return
        yield FunctionResult(
            output=StepResult(event, "architect_noop"),
            new_state=state,
            label="architect_noop",
            reason="Event has no Architect outlet effect.",
        )
        if event.kind == "architect_creates_packet":
            yield FunctionResult(
                output=StepResult(event, "architect_packet_ready"),
                new_state=replace(state, architect_patch_debt=False, architect_outlet_status="packet"),
                label="architect_packet_ready",
                reason="Patch-plan work has a bounded execution packet.",
            )
            return
        if event.kind == "architect_records_blocker":
            yield FunctionResult(
                output=StepResult(event, "architect_blocker_recorded"),
                new_state=replace(state, architect_patch_debt=False, architect_outlet_status="blocked"),
                label="architect_blocker_recorded",
                reason="Patch-plan work cannot proceed and has a concrete blocker.",
            )
            return
        if event.kind == "architect_applies_packet":
            status = "applied" if state.architect_outlet_status == "packet" else "unsafe-applied"
            yield FunctionResult(
                output=StepResult(event, status),
                new_state=replace(state, architect_patch_debt=False, architect_outlet_status=status),
                label=status,
                reason="Packets may be applied only after the execution outlet exists.",
            )
            return
        if event.kind == "architect_stalls":
            yield FunctionResult(
                output=StepResult(event, "architect_patch_stalled"),
                new_state=replace(state, architect_outlet_status="stalled"),
                label="architect_patch_stalled",
                reason="Broken path: ready-for-patch work remained without packet or blocker.",
            )
            return


class RouteGovernanceBlock:
    """Input x State -> Set(Output x State) for route drift and card creation."""

    name = "RouteGovernanceBlock"
    reads = ("route_status", "bad_route_card_created")
    writes = ("route_status", "bad_route_card_created")

    def apply(self, input_obj: Event | StepResult, state: State) -> Iterable[FunctionResult]:
        event = _event_from_input(input_obj)
        if event.kind == "route_drift_observed":
            yield FunctionResult(
                output=StepResult(event, "route_drift_opened"),
                new_state=replace(state, route_status="drift"),
                label="route_drift_opened",
                reason="Blank, project-root, dotted, or undeclared routes need review.",
            )
            return
        yield FunctionResult(
            output=StepResult(event, "route_noop"),
            new_state=state,
            label="route_noop",
            reason="Event has no route-governance effect.",
        )
        if event.kind == "route_reviewed":
            yield FunctionResult(
                output=StepResult(event, "route_reviewed"),
                new_state=replace(state, route_status="reviewed"),
                label="route_reviewed",
                reason="Route drift was reviewed and either accepted, rejected, or mapped.",
            )
            return
        if event.kind == "route_normalized":
            yield FunctionResult(
                output=StepResult(event, "route_normalized"),
                new_state=replace(state, route_status="normalized"),
                label="route_normalized",
                reason="Route drift was normalized before card creation.",
            )
            return
        if event.kind == "create_card_from_route":
            bad = state.route_status == "drift"
            yield FunctionResult(
                output=StepResult(event, "card_created_from_bad_route" if bad else "card_created_from_reviewed_route"),
                new_state=replace(state, bad_route_card_created=bad),
                label="card_created_from_bad_route" if bad else "card_created_from_reviewed_route",
                reason="Broken path when an unreconciled route directly creates a card.",
            )
            return


class HealthRollupBlock:
    """Input x State -> Set(Output x State) for health and manual-pause semantics."""

    name = "HealthRollupBlock"
    reads = (
        "install_policy_drift",
        "org_automation_pause",
        "stale_running_without_lock",
        "health_rollup_status",
        "release_ready",
    )
    writes = (
        "install_policy_drift",
        "org_automation_pause",
        "stale_running_without_lock",
        "health_rollup_status",
        "release_ready",
    )

    def apply(self, input_obj: Event | StepResult, state: State) -> Iterable[FunctionResult]:
        event = _event_from_input(input_obj)
        if event.kind == "install_policy_drift":
            yield FunctionResult(
                output=StepResult(event, "install_policy_drift"),
                new_state=replace(state, install_policy_drift=True, health_rollup_status="attention-needed"),
                label="install_policy_drift",
                reason="Installer/automation policy metadata drift is a real health issue.",
            )
            return
        yield FunctionResult(
            output=StepResult(event, "health_noop"),
            new_state=state,
            label="health_noop",
            reason="Event has no health-rollup effect.",
        )
        if event.kind == "org_automation_user_paused":
            yield FunctionResult(
                output=StepResult(event, "org_automation_user_paused"),
                new_state=replace(state, org_automation_pause="user"),
                label="org_automation_user_paused",
                reason="User-paused organization automation is an allowed local operating mode.",
            )
            return
        if event.kind == "org_automation_unexpected_paused":
            yield FunctionResult(
                output=StepResult(event, "org_automation_unexpected_paused"),
                new_state=replace(state, org_automation_pause="unexpected", health_rollup_status="attention-needed"),
                label="org_automation_unexpected_paused",
                reason="Unexpected paused automation is a health issue.",
            )
            return
        if event.kind == "stale_running_without_lock":
            yield FunctionResult(
                output=StepResult(event, "stale_running_without_lock"),
                new_state=replace(state, stale_running_without_lock=True, health_rollup_status="attention-needed"),
                label="stale_running_without_lock",
                reason="Running lane status without a lock is stale state.",
            )
            return
        if event.kind == "health_rollup":
            status = "attention-needed" if _has_real_health_issue(state) else "green"
            yield FunctionResult(
                output=StepResult(event, f"health_{status}"),
                new_state=replace(state, health_rollup_status=status),
                label=f"health_{status}",
                reason="Health rollup separates user-paused organization cadence from real drift.",
            )
            return
        if event.kind == "mark_release_ready":
            yield FunctionResult(
                output=StepResult(event, "release_ready"),
                new_state=replace(state, release_ready=True),
                label="release_ready",
                reason="Release/update readiness can only be trusted when hard health gates are green.",
            )
            return


def _has_real_health_issue(state: State) -> bool:
    return (
        state.install_policy_drift
        or state.org_automation_pause == "unexpected"
        or state.stale_running_without_lock
    )


def _is_terminal_state(state: State) -> bool:
    return state.governance_done or state.release_ready


def candidate_backlog_must_close(state: State, trace: object) -> InvariantResult:
    if state.trusted_promotion_without_review:
        return InvariantResult.fail("Trusted-card promotion occurred without semantic review evidence.")
    if _is_terminal_state(state) and state.candidate_review_debt:
        return InvariantResult.fail("High candidate backlog ended without a Sleep review, rejection, or watch decision.")
    return InvariantResult.pass_()


def dream_handoff_must_close(state: State, trace: object) -> InvariantResult:
    if state.dream_handoff_strength == "weak" and state.dream_handoff_status == "promoted":
        return InvariantResult.fail("Weak Dream evidence was promoted instead of staying history-only or under watch.")
    if state.dream_handoff_strength in {"strong", "moderate"} and state.dream_handoff_status == "dropped":
        return InvariantResult.fail("Strong or moderate Dream handoff was not reviewed or explicitly watched by Sleep.")
    if (
        _is_terminal_state(state)
        and state.dream_handoff_strength in {"strong", "moderate"}
        and state.dream_handoff_status == "open"
    ):
        return InvariantResult.fail("Strong or moderate Dream handoff was not reviewed or explicitly watched by Sleep.")
    return InvariantResult.pass_()


def architect_patch_work_needs_outlet(state: State, trace: object) -> InvariantResult:
    if state.architect_outlet_status == "unsafe-applied":
        return InvariantResult.fail("Architect applied work before creating a bounded execution packet.")
    if _is_terminal_state(state) and (state.architect_patch_debt or state.architect_outlet_status == "stalled"):
        return InvariantResult.fail("Architect ready-for-patch work ended without a packet, blocker, or closure.")
    return InvariantResult.pass_()


def route_drift_needs_review_before_card(state: State, trace: object) -> InvariantResult:
    if state.bad_route_card_created:
        return InvariantResult.fail("A card was created from an unreconciled route-drift state.")
    if _is_terminal_state(state) and state.route_status == "drift":
        return InvariantResult.fail("Route drift ended without taxonomy review or normalization.")
    return InvariantResult.pass_()


def health_gates_distinguish_manual_pause(state: State, trace: object) -> InvariantResult:
    if state.release_ready and _has_real_health_issue(state):
        return InvariantResult.fail("Release/update readiness was allowed despite real health drift.")
    if (
        _is_terminal_state(state)
        and state.org_automation_pause == "user"
        and not _has_real_health_issue(state)
        and state.health_rollup_status == "attention-needed"
    ):
        return InvariantResult.fail("User-paused organization automation was incorrectly treated as a health failure.")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "candidate_backlog_must_close",
        "High candidate backlog must close through Sleep review, watch, rejection, or promotion decisions.",
        candidate_backlog_must_close,
    ),
    Invariant(
        "dream_handoff_must_close",
        "Strong/moderate Dream handoffs must be reviewed or watched; weak Dream evidence cannot promote.",
        dream_handoff_must_close,
    ),
    Invariant(
        "architect_patch_work_needs_outlet",
        "Architect ready-for-patch work needs packet, blocker, or closure.",
        architect_patch_work_needs_outlet,
    ),
    Invariant(
        "route_drift_needs_review_before_card",
        "Route drift must be reviewed or normalized before card creation.",
        route_drift_needs_review_before_card,
    ),
    Invariant(
        "health_gates_distinguish_manual_pause",
        "Manual org automation pauses are allowed, but real drift blocks readiness.",
        health_gates_distinguish_manual_pause,
    ),
)


class GovernanceBlock:
    """Input x State -> Set(Output x State) for the governance closure model."""

    name = "GovernanceBlock"
    reads = (
        "candidate_backlog",
        "candidate_review_debt",
        "trusted_promotion_without_review",
        "dream_handoff_strength",
        "dream_handoff_status",
        "architect_patch_debt",
        "architect_outlet_status",
        "route_status",
        "bad_route_card_created",
        "install_policy_drift",
        "org_automation_pause",
        "stale_running_without_lock",
        "health_rollup_status",
        "release_ready",
        "governance_done",
    )
    writes = reads

    def apply(self, input_obj: Event | StepResult, state: State) -> Iterable[FunctionResult]:
        event = _event_from_input(input_obj)
        kind = event.kind

        if kind == "candidate_backlog_high":
            yield FunctionResult(
                output=StepResult(event, "candidate_review_debt_opened"),
                new_state=replace(state, candidate_backlog="high", candidate_review_debt=True),
                label="candidate_review_debt_opened",
                reason="High candidate volume creates explicit Sleep review debt.",
            )
            return
        if kind == "sleep_reviews_candidates":
            yield FunctionResult(
                output=StepResult(event, "candidate_review_debt_closed"),
                new_state=replace(state, candidate_review_debt=False),
                label="candidate_review_debt_closed",
                reason="Sleep reviewed the bounded candidate set and closed the backlog debt.",
            )
            return
        if kind == "trusted_promotion_with_review":
            yield FunctionResult(
                output=StepResult(event, "trusted_promotion_reviewed"),
                new_state=state,
                label="trusted_promotion_reviewed",
                reason="Promotion is allowed only after semantic review evidence.",
            )
            return
        if kind == "trusted_promotion_without_review":
            yield FunctionResult(
                output=StepResult(event, "trusted_promotion_without_review"),
                new_state=replace(state, trusted_promotion_without_review=True),
                label="trusted_promotion_without_review",
                reason="Broken path: candidate promotion skipped semantic review.",
            )
            return

        if kind == "dream_validates_strong":
            yield FunctionResult(
                output=StepResult(event, "dream_handoff_open_strong"),
                new_state=replace(state, dream_handoff_strength="strong", dream_handoff_status="open"),
                label="dream_handoff_open_strong",
                reason="Strong Dream evidence creates a Sleep handoff obligation.",
            )
            return
        if kind == "dream_validates_moderate":
            yield FunctionResult(
                output=StepResult(event, "dream_handoff_open_moderate"),
                new_state=replace(state, dream_handoff_strength="moderate", dream_handoff_status="open"),
                label="dream_handoff_open_moderate",
                reason="Moderate Dream evidence creates a Sleep handoff obligation.",
            )
            return
        if kind == "dream_validates_weak":
            yield FunctionResult(
                output=StepResult(event, "dream_handoff_open_weak"),
                new_state=replace(state, dream_handoff_strength="weak", dream_handoff_status="open"),
                label="dream_handoff_open_weak",
                reason="Weak Dream evidence can be watched but cannot directly promote.",
            )
            return
        if kind == "sleep_reviews_handoff":
            yield FunctionResult(
                output=StepResult(event, "dream_handoff_reviewed"),
                new_state=replace(state, dream_handoff_status="reviewed"),
                label="dream_handoff_reviewed",
                reason="Sleep reviewed the handoff and chose a card action or no-op decision.",
            )
            return
        if kind == "sleep_watches_handoff":
            yield FunctionResult(
                output=StepResult(event, "dream_handoff_watching"),
                new_state=replace(state, dream_handoff_status="watching"),
                label="dream_handoff_watching",
                reason="Sleep explicitly kept the handoff under watch with a reason.",
            )
            return
        if kind == "sleep_drops_handoff":
            yield FunctionResult(
                output=StepResult(event, "dream_handoff_dropped"),
                new_state=replace(state, dream_handoff_status="dropped"),
                label="dream_handoff_dropped",
                reason="Broken path: Dream handoff disappeared without a review or watch decision.",
            )
            return
        if kind == "promote_dream_handoff":
            yield FunctionResult(
                output=StepResult(event, "dream_handoff_promoted"),
                new_state=replace(state, dream_handoff_status="promoted"),
                label="dream_handoff_promoted",
                reason="Promotion is safe only for reviewed strong/moderate evidence.",
            )
            return

        if kind == "architect_ready_for_patch":
            yield FunctionResult(
                output=StepResult(event, "architect_patch_debt_opened"),
                new_state=replace(state, architect_patch_debt=True, architect_outlet_status="patch-plan"),
                label="architect_patch_debt_opened",
                reason="Ready-for-patch work needs a packet, blocker, or watch decision.",
            )
            return
        if kind == "architect_creates_packet":
            yield FunctionResult(
                output=StepResult(event, "architect_packet_ready"),
                new_state=replace(state, architect_patch_debt=False, architect_outlet_status="packet"),
                label="architect_packet_ready",
                reason="Patch-plan work has a bounded execution packet.",
            )
            return
        if kind == "architect_records_blocker":
            yield FunctionResult(
                output=StepResult(event, "architect_blocker_recorded"),
                new_state=replace(state, architect_patch_debt=False, architect_outlet_status="blocked"),
                label="architect_blocker_recorded",
                reason="Patch-plan work cannot proceed and has a concrete blocker.",
            )
            return
        if kind == "architect_applies_packet":
            status = "applied" if state.architect_outlet_status == "packet" else "unsafe-applied"
            yield FunctionResult(
                output=StepResult(event, status),
                new_state=replace(state, architect_patch_debt=False, architect_outlet_status=status),
                label=status,
                reason="Packets may be applied only after the execution outlet exists.",
            )
            return
        if kind == "architect_stalls":
            yield FunctionResult(
                output=StepResult(event, "architect_patch_stalled"),
                new_state=replace(state, architect_outlet_status="stalled"),
                label="architect_patch_stalled",
                reason="Broken path: ready-for-patch work remained without packet or blocker.",
            )
            return

        if kind == "route_drift_observed":
            yield FunctionResult(
                output=StepResult(event, "route_drift_opened"),
                new_state=replace(state, route_status="drift"),
                label="route_drift_opened",
                reason="Blank, project-root, dotted, or undeclared routes need review.",
            )
            return
        if kind == "route_reviewed":
            yield FunctionResult(
                output=StepResult(event, "route_reviewed"),
                new_state=replace(state, route_status="reviewed"),
                label="route_reviewed",
                reason="Route drift was reviewed and either accepted, rejected, or mapped.",
            )
            return
        if kind == "route_normalized":
            yield FunctionResult(
                output=StepResult(event, "route_normalized"),
                new_state=replace(state, route_status="normalized"),
                label="route_normalized",
                reason="Route drift was normalized before card creation.",
            )
            return
        if kind == "create_card_from_route":
            bad = state.route_status == "drift"
            yield FunctionResult(
                output=StepResult(event, "card_created_from_bad_route" if bad else "card_created_from_reviewed_route"),
                new_state=replace(state, bad_route_card_created=bad),
                label="card_created_from_bad_route" if bad else "card_created_from_reviewed_route",
                reason="Broken path when an unreconciled route directly creates a card.",
            )
            return

        if kind == "install_policy_drift":
            yield FunctionResult(
                output=StepResult(event, "install_policy_drift"),
                new_state=replace(state, install_policy_drift=True, health_rollup_status="attention-needed"),
                label="install_policy_drift",
                reason="Installer/automation policy metadata drift is a real health issue.",
            )
            return
        if kind == "install_policy_repaired":
            yield FunctionResult(
                output=StepResult(event, "install_policy_repaired"),
                new_state=replace(state, install_policy_drift=False),
                label="install_policy_repaired",
                reason="Installer/automation policy metadata was repaired at the source specification.",
            )
            return
        if kind == "org_automation_user_paused":
            yield FunctionResult(
                output=StepResult(event, "org_automation_user_paused"),
                new_state=replace(state, org_automation_pause="user"),
                label="org_automation_user_paused",
                reason="User-paused organization automation is an allowed local operating mode.",
            )
            return
        if kind == "org_automation_unexpected_paused":
            yield FunctionResult(
                output=StepResult(event, "org_automation_unexpected_paused"),
                new_state=replace(state, org_automation_pause="unexpected", health_rollup_status="attention-needed"),
                label="org_automation_unexpected_paused",
                reason="Unexpected paused automation is a health issue.",
            )
            return
        if kind == "stale_running_without_lock":
            yield FunctionResult(
                output=StepResult(event, "stale_running_without_lock"),
                new_state=replace(state, stale_running_without_lock=True, health_rollup_status="attention-needed"),
                label="stale_running_without_lock",
                reason="Running lane status without a lock is stale state.",
            )
            return
        if kind == "stale_lane_cleared":
            yield FunctionResult(
                output=StepResult(event, "stale_lane_cleared"),
                new_state=replace(state, stale_running_without_lock=False),
                label="stale_lane_cleared",
                reason="Stale lane status was reconciled before health/readiness checks.",
            )
            return
        if kind == "health_rollup":
            status = "attention-needed" if _has_real_health_issue(state) else "green"
            yield FunctionResult(
                output=StepResult(event, f"health_{status}"),
                new_state=replace(state, health_rollup_status=status),
                label=f"health_{status}",
                reason="Health rollup separates user-paused organization cadence from real drift.",
            )
            return
        if kind == "mark_release_ready":
            yield FunctionResult(
                output=StepResult(event, "release_ready"),
                new_state=replace(state, release_ready=True, governance_done=True),
                label="release_ready",
                reason="Release/update readiness can only be trusted when hard health gates are green.",
            )
            return
        if kind == "finalize_governance":
            yield FunctionResult(
                output=StepResult(event, "governance_done"),
                new_state=replace(state, governance_done=True),
                label="governance_done",
                reason="Terminal governance review checks whether all opened obligations were closed.",
            )
            return

        yield FunctionResult(
            output=StepResult(event, "unknown_event"),
            new_state=state,
            label="unknown_event",
            reason="Unknown governance event was ignored.",
        )


def build_workflow() -> Workflow:
    return Workflow(
        (GovernanceBlock(),),
        name="khaos_brain_governance_flow",
    )


ACCEPTED_SEQUENCE = (
    Event("candidate_backlog_high"),
    Event("sleep_reviews_candidates"),
    Event("dream_validates_strong"),
    Event("sleep_reviews_handoff"),
    Event("architect_ready_for_patch"),
    Event("architect_creates_packet"),
    Event("architect_applies_packet"),
    Event("route_drift_observed"),
    Event("route_reviewed"),
    Event("route_normalized"),
    Event("org_automation_user_paused"),
    Event("health_rollup"),
    Event("mark_release_ready"),
)

USER_PAUSED_ORG_SEQUENCE = (
    Event("org_automation_user_paused"),
    Event("health_rollup"),
    Event("mark_release_ready"),
)

MINIMAL_FIX_SEQUENCE = (
    Event("candidate_backlog_high"),
    Event("sleep_reviews_candidates"),
    Event("dream_validates_strong"),
    Event("sleep_reviews_handoff"),
    Event("architect_ready_for_patch"),
    Event("architect_creates_packet"),
    Event("architect_applies_packet"),
    Event("route_drift_observed"),
    Event("route_reviewed"),
    Event("route_normalized"),
    Event("install_policy_drift"),
    Event("install_policy_repaired"),
    Event("stale_running_without_lock"),
    Event("stale_lane_cleared"),
    Event("org_automation_user_paused"),
    Event("health_rollup"),
    Event("mark_release_ready"),
)

BAD_SEQUENCES = {
    "candidate_backlog_unreviewed": (Event("candidate_backlog_high"), Event("finalize_governance")),
    "trusted_promotion_without_review": (Event("trusted_promotion_without_review"),),
    "dream_handoff_unreviewed": (Event("dream_validates_strong"), Event("finalize_governance")),
    "dream_handoff_dropped": (Event("dream_validates_strong"), Event("sleep_drops_handoff")),
    "weak_dream_promoted": (Event("dream_validates_weak"), Event("promote_dream_handoff")),
    "architect_ready_for_patch_no_outlet": (Event("architect_ready_for_patch"), Event("finalize_governance")),
    "architect_ready_for_patch_stalled": (
        Event("architect_ready_for_patch"),
        Event("architect_stalls"),
        Event("finalize_governance"),
    ),
    "route_drift_card_created": (Event("route_drift_observed"), Event("create_card_from_route")),
    "route_drift_unclosed": (Event("route_drift_observed"), Event("finalize_governance")),
    "health_ready_with_install_drift": (
        Event("install_policy_drift"),
        Event("health_rollup"),
        Event("mark_release_ready"),
    ),
    "unexpected_org_pause_blocks_ready": (
        Event("org_automation_unexpected_paused"),
        Event("health_rollup"),
        Event("mark_release_ready"),
    ),
    "stale_lane_blocks_ready": (
        Event("stale_running_without_lock"),
        Event("health_rollup"),
        Event("mark_release_ready"),
    ),
}


def _scenario_summary(run: ScenarioRun) -> dict[str, object]:
    payload = run.to_dict()
    traces = payload.get("traces", []) or []
    labels_seen = sorted({label for trace in traces for label in trace.get("labels", [])})
    return {
        "observed_status": payload.get("observed_status"),
        "model_ok": payload.get("model_report", {}).get("ok"),
        "labels_seen": labels_seen,
        "violation_names": payload.get("observed_violation_names", []),
        "final_states": payload.get("final_states", []),
    }


def run_abstract_scenarios() -> dict[str, object]:
    workflow = build_workflow()
    accepted = run_exact_sequence(workflow, State(), ACCEPTED_SEQUENCE, invariants=INVARIANTS)
    user_paused = run_exact_sequence(workflow, State(), USER_PAUSED_ORG_SEQUENCE, invariants=INVARIANTS)
    minimal_fix = run_exact_sequence(workflow, State(), MINIMAL_FIX_SEQUENCE, invariants=INVARIANTS)
    bad = {
        name: run_exact_sequence(workflow, State(), sequence, invariants=INVARIANTS)
        for name, sequence in BAD_SEQUENCES.items()
    }
    bad_rejected = {name: run.observed_status != "ok" for name, run in bad.items()}
    return {
        "ok": (
            accepted.observed_status == "ok"
            and user_paused.observed_status == "ok"
            and minimal_fix.observed_status == "ok"
            and all(bad_rejected.values())
        ),
        "accepted_sequence": _scenario_summary(accepted),
        "user_paused_org_sequence": _scenario_summary(user_paused),
        "minimal_fix_sequence": _scenario_summary(minimal_fix),
        "bad_sequence_rejections": bad_rejected,
        "bad_sequences": {name: _scenario_summary(run) for name, run in bad.items()},
    }


def _load_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _latest_dir(parent: Path, prefix: str) -> Path | None:
    if not parent.exists():
        return None
    matches = [path for path in parent.iterdir() if path.is_dir() and path.name.startswith(prefix)]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def _proposal_items(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("proposals", "items", "actions"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _event_route_label(event: dict[str, object]) -> str:
    target = event.get("target")
    if not isinstance(target, dict):
        return ""
    route_hint = target.get("route_hint")
    if route_hint is None:
        return ""
    return "/".join(parse_route_segments(route_hint))


def _iter_history_events(root: Path) -> Iterable[dict[str, object]]:
    path = root / "kb" / "history" / "events.jsonl"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            yield payload


def _parse_domain_path(path: Path) -> tuple[str, ...]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "domain_path:":
            continue
        values: list[str] = []
        for item in lines[index + 1 :]:
            stripped = item.strip()
            if not stripped:
                continue
            if not item.startswith(" ") and not item.startswith("-"):
                break
            if stripped.startswith("-"):
                values.append(stripped[1:].strip().strip("\"'"))
                continue
        return tuple(parse_route_segments(values))
    return ()


def _toml_status(path: Path) -> str:
    if not path.exists():
        return "missing"
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped.startswith("status"):
            parts = stripped.split("=", 1)
            if len(parts) == 2:
                return parts[1].strip().strip("\"")
    return "unknown"


def _lock_present(root: Path, group: str) -> bool:
    return (root / "kb" / "history" / "lane-status" / "locks" / f"{group}.lock" / "lock.json").exists()


def project_live_projection(root: Path = REPO_ROOT) -> dict[str, object]:
    candidate_files = list((root / "kb" / "candidates").rglob("*.yaml"))
    public_files = list((root / "kb" / "public").rglob("*.yaml"))
    private_files = list((root / "kb" / "private").rglob("*.yaml"))

    latest_sleep = _latest_dir(root / "kb" / "history" / "consolidation", "kb-sleep-")
    sleep_payload = _load_json(latest_sleep / "proposal.json", {}) if latest_sleep else {}
    sleep_actions = _proposal_items(sleep_payload)
    sleep_apply_eligible = sum(
        1
        for action in sleep_actions
        if isinstance(action.get("apply_eligibility"), dict) and action["apply_eligibility"].get("eligible") is True
    )
    sleep_review_batch = sleep_payload.get("review_batch", {}) if isinstance(sleep_payload, dict) else {}
    sleep_review_batch = sleep_review_batch if isinstance(sleep_review_batch, dict) else {}
    sleep_batch_bounded = (
        sleep_review_batch.get("status") == "bounded"
        and int(sleep_review_batch.get("selected_action_count") or 0)
        <= int(sleep_review_batch.get("max_selected_actions") or 0)
        <= 30
    )
    sleep_dream_review = sleep_payload.get("dream_handoff_review", {}) if isinstance(sleep_payload, dict) else {}
    sleep_dream_review = sleep_dream_review if isinstance(sleep_dream_review, dict) else {}
    sleep_route_governance = sleep_payload.get("route_governance", {}) if isinstance(sleep_payload, dict) else {}
    sleep_route_governance = sleep_route_governance if isinstance(sleep_route_governance, dict) else {}

    latest_dream = _latest_dir(root / "kb" / "history" / "dream", "kb-dream-")
    dream_payload = _load_json(latest_dream / "report.json", {}) if latest_dream else {}
    dream_experiments = dream_payload.get("experiments", []) if isinstance(dream_payload, dict) else []
    if not isinstance(dream_experiments, list):
        dream_experiments = []
    dream_handoffs = [
        experiment
        for experiment in dream_experiments
        if isinstance(experiment, dict) and experiment.get("sleep_handoff")
    ]
    dream_review_ready = [
        experiment
        for experiment in dream_handoffs
        if isinstance(experiment.get("sleep_handoff_detail"), dict)
        and experiment["sleep_handoff_detail"].get("sleep_review_ready") is True
    ]
    dream_strong_or_moderate = [
        experiment
        for experiment in dream_handoffs
        if str(experiment.get("evidence_grade") or "").lower() in {"strong", "moderate"}
    ]

    queue_payload = _load_json(root / "kb" / "history" / "architecture" / "proposal_queue.json", [])
    queue_items = _proposal_items(queue_payload)
    queue_status_counts = Counter(str(item.get("status") or "") for item in queue_items)
    queue_execution_summary = queue_payload.get("execution_summary", {}) if isinstance(queue_payload, dict) else {}
    if not isinstance(queue_execution_summary, dict):
        queue_execution_summary = {}
    patch_plan_count = int(queue_execution_summary.get("patch_plan_count") or 0)
    latest_arch = _latest_dir(root / "kb" / "history" / "architecture" / "runs", "kb-architect-")
    arch_report = _load_json(latest_arch / "report.json", {}) if latest_arch else {}
    sandbox_ready_count = int(arch_report.get("sandbox_ready_count") or 0) if isinstance(arch_report, dict) else 0

    events = list(_iter_history_events(root))
    blank_route_events = sum(1 for event in events if not _event_route_label(event))
    dotted_route_events = sum(1 for event in events if "." in _event_route_label(event).split("/")[0])
    route_counter = Counter(route.split("/")[0] for route in (_event_route_label(event) for event in events) if route)

    undeclared_card_routes: Counter[str] = Counter()
    dotted_card_routes = 0
    root_direct_cards = 0
    for card_path in [*candidate_files, *public_files, *private_files]:
        domain_path = _parse_domain_path(card_path)
        if not domain_path:
            root_direct_cards += 1
            continue
        top = domain_path[0]
        if "." in top:
            dotted_card_routes += 1
        if top not in DECLARED_TOP_LEVEL_ROUTES:
            undeclared_card_routes[top] += 1

    rollup = _load_json(root / "kb" / "history" / "architecture" / "maintenance_rollup.json", {})
    source_reports = rollup.get("source_reports", {}) if isinstance(rollup, dict) else {}
    install_report = source_reports.get("install", {}) if isinstance(source_reports, dict) else {}
    install_ok = install_report.get("ok") is True if isinstance(install_report, dict) else False
    install_issue_count = int(install_report.get("issue_count") or 0) if isinstance(install_report, dict) else 0
    try:
        from local_kb.install import build_installation_check

        current_install_check = build_installation_check(repo_root=root)
    except Exception:
        current_install_check = {}
    if isinstance(current_install_check, dict) and current_install_check:
        install_ok = current_install_check.get("ok") is True
        install_issue_count = len(current_install_check.get("issues", []))

    lane_status_dir = root / "kb" / "history" / "lane-status"
    stale_lanes: list[str] = []
    for lane_name, lock_group in (
        ("kb-sleep", "local-maintenance"),
        ("kb-dream", "local-maintenance"),
        ("kb-architect", "local-maintenance"),
        ("kb-org-contribute", "organization-maintenance"),
        ("kb-org-maintenance", "organization-maintenance"),
    ):
        lane_payload = _load_json(lane_status_dir / f"{lane_name}.json", {})
        if isinstance(lane_payload, dict) and lane_payload.get("status") == "running" and not _lock_present(root, lock_group):
            stale_lanes.append(lane_name)

    codex_home = Path.home() / ".codex"
    org_automation_statuses = {
        "kb-org-contribute": _toml_status(codex_home / "automations" / "kb-org-contribute" / "automation.toml"),
        "kb-org-maintenance": _toml_status(codex_home / "automations" / "kb-org-maintenance" / "automation.toml"),
    }

    findings: list[dict[str, object]] = []
    if (
        len(candidate_files) >= 100
        and len(candidate_files) > 20 * max(len(public_files) + len(private_files), 1)
        and not sleep_batch_bounded
    ):
        findings.append(
            {
                "id": "candidate_backlog_pressure",
                "severity": "attention-needed",
                "message": "Candidate volume is much larger than the formal card surface.",
                "evidence": {
                    "candidate_count": len(candidate_files),
                    "public_count": len(public_files),
                    "private_count": len(private_files),
                },
            }
        )
    if (
        isinstance(sleep_payload, dict)
        and int(sleep_payload.get("candidate_action_count") or 0) >= 500
        and not sleep_batch_bounded
    ):
        findings.append(
            {
                "id": "sleep_review_pressure",
                "severity": "attention-needed",
                "message": "Latest Sleep proposal produced high-volume actions that need bounded editorial selection.",
                "evidence": {
                    "run_id": sleep_payload.get("run_id"),
                    "candidate_action_count": sleep_payload.get("candidate_action_count"),
                    "apply_eligible_count": sleep_apply_eligible,
                },
            }
        )
    sleep_reviewed_latest_dream = (
        sleep_dream_review.get("status") == "reviewed"
        and str(sleep_dream_review.get("latest_dream_run") or "") == str(dream_payload.get("run_id") or "")
        and int(sleep_dream_review.get("review_ready_count") or 0) >= len(dream_review_ready)
    )
    if dream_strong_or_moderate and not sleep_reviewed_latest_dream:
        findings.append(
            {
                "id": "dream_sleep_handoff_open",
                "severity": "attention-needed",
                "message": "Latest Dream produced strong/moderate Sleep handoffs that should be closed by Sleep review or watch decisions.",
                "evidence": {
                    "run_id": dream_payload.get("run_id") if isinstance(dream_payload, dict) else "",
                    "handoff_count": len(dream_handoffs),
                    "review_ready_count": len(dream_review_ready),
                    "strong_or_moderate_count": len(dream_strong_or_moderate),
                },
            }
        )
    if queue_status_counts.get("ready-for-patch", 0) > 0 and sandbox_ready_count == 0 and patch_plan_count == 0:
        findings.append(
            {
                "id": "architect_execution_outlet_gap",
                "severity": "attention-needed",
                "message": "Architect has ready-for-patch proposals but no sandbox-ready execution outlet.",
                "evidence": {
                    "ready_for_patch_count": queue_status_counts.get("ready-for-patch", 0),
                    "ready_for_apply_count": queue_status_counts.get("ready-for-apply", 0),
                    "sandbox_ready_count": sandbox_ready_count,
                },
            }
        )
    route_reviewed = sleep_route_governance.get("status") == "reviewed"
    if (blank_route_events > 0 or undeclared_card_routes) and not route_reviewed:
        findings.append(
            {
                "id": "route_drift_pressure",
                "severity": "attention-needed",
                "message": "Route evidence includes blank, undeclared, project-root, or dotted route families.",
                "evidence": {
                    "blank_route_event_count": blank_route_events,
                    "dotted_route_event_count": dotted_route_events,
                    "dotted_card_route_count": dotted_card_routes,
                    "root_direct_card_count": root_direct_cards,
                    "top_undeclared_card_routes": undeclared_card_routes.most_common(12),
                    "top_observed_event_routes": route_counter.most_common(12),
                },
            }
        )
    if not install_ok and install_issue_count:
        findings.append(
            {
                "id": "install_policy_metadata_drift",
                "severity": "attention-needed",
                "message": "Installer health check reports automation policy metadata drift.",
                "evidence": {"issue_count": install_issue_count},
            }
        )
    if stale_lanes:
        findings.append(
            {
                "id": "stale_running_lane_without_lock",
                "severity": "attention-needed",
                "message": "A lane-status file still says running even though the corresponding lock is absent.",
                "evidence": {"lanes": stale_lanes},
            }
        )

    allowed_notes: list[dict[str, object]] = []
    paused_org = [name for name, status in org_automation_statuses.items() if status.upper() == "PAUSED"]
    if paused_org:
        allowed_notes.append(
            {
                "id": "org_automation_manual_pause_allowed",
                "message": "Organization automations are paused locally; this model treats user-paused org cadence as allowed, not as a failure by itself.",
                "evidence": {"paused_automations": paused_org},
            }
        )

    return {
        "ok": not findings,
        "finding_count": len(findings),
        "findings": findings,
        "allowed_notes": allowed_notes,
        "source_artifacts": {
            "latest_sleep_run": str(latest_sleep.relative_to(root)) if latest_sleep else "",
            "latest_dream_run": str(latest_dream.relative_to(root)) if latest_dream else "",
            "latest_architect_run": str(latest_arch.relative_to(root)) if latest_arch else "",
            "maintenance_rollup": "kb/history/architecture/maintenance_rollup.json",
        },
        "summary_counts": {
            "candidate_count": len(candidate_files),
            "public_count": len(public_files),
            "private_count": len(private_files),
            "history_event_count": len(events),
            "blank_route_event_count": blank_route_events,
            "ready_for_patch_count": queue_status_counts.get("ready-for-patch", 0),
            "sandbox_ready_count": sandbox_ready_count,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Khaos Brain governance FlowGuard model.")
    parser.add_argument("--abstract-only", action="store_true", help="Run only abstract FlowGuard scenarios.")
    parser.add_argument("--live", action="store_true", help="Include read-only live repository projection.")
    args = parser.parse_args()

    abstract = run_abstract_scenarios()
    include_live = args.live or not args.abstract_only
    live = project_live_projection() if include_live else None
    report = {
        "kind": "khaos-brain-governance-flowguard-report",
        "abstract": abstract,
        "live_projection": live,
        "ok": bool(abstract.get("ok")) and (live is None or bool(live.get("ok"))),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
