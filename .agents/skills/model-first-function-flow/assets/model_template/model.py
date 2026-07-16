"""Minimal flowguard model template.

Copy this directory before production edits and replace the sample domain with
the behavior under review.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Sequence

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class Input:
    item_id: str
    valid: bool


@dataclass(frozen=True)
class Accepted:
    item_id: str


@dataclass(frozen=True)
class Rejected:
    item_id: str
    reason: str


@dataclass(frozen=True)
class Stored:
    item_id: str


@dataclass(frozen=True)
class State:
    seen_ids: tuple[str, ...] = ()
    stored_ids: tuple[str, ...] = ()


class ValidateInput:
    name = "ValidateInput"
    reads = ("seen_ids",)
    writes = ("seen_ids",)
    accepted_input_type = Input
    input_description = "external abstract input"
    output_description = "Accepted or Rejected"
    idempotency = "Repeated item_id returns Rejected('duplicate') without changing state."

    def apply(self, input_obj: Input, state: State) -> Iterable[FunctionResult]:
        if not input_obj.valid:
            yield FunctionResult(
                output=Rejected(input_obj.item_id, "invalid"),
                new_state=state,
                label="rejected_invalid",
            )
            return
        if input_obj.item_id in state.seen_ids:
            yield FunctionResult(
                output=Rejected(input_obj.item_id, "duplicate"),
                new_state=state,
                label="rejected_duplicate",
            )
            return
        yield FunctionResult(
            output=Accepted(input_obj.item_id),
            new_state=replace(state, seen_ids=state.seen_ids + (input_obj.item_id,)),
            label="accepted",
        )


class StoreAccepted:
    name = "StoreAccepted"
    reads = ("stored_ids",)
    writes = ("stored_ids",)
    accepted_input_type = Accepted
    input_description = "Accepted"
    output_description = "Stored"
    idempotency = "Stores each accepted item once."

    def apply(self, input_obj: Accepted, state: State) -> Iterable[FunctionResult]:
        if input_obj.item_id in state.stored_ids:
            yield FunctionResult(
                output=Stored(input_obj.item_id),
                new_state=state,
                label="already_stored",
            )
            return
        yield FunctionResult(
            output=Stored(input_obj.item_id),
            new_state=replace(state, stored_ids=state.stored_ids + (input_obj.item_id,)),
            label="stored",
        )


class BrokenValidateInput:
    name = "BrokenValidateInput"
    reads = ("seen_ids",)
    writes = ("seen_ids",)
    accepted_input_type = Input

    def apply(self, input_obj: Input, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            output=Accepted(input_obj.item_id),
            new_state=replace(state, seen_ids=state.seen_ids + (input_obj.item_id,)),
            label="broken_accepted_duplicate",
        )


class BrokenStoreAccepted:
    name = "BrokenStoreAccepted"
    reads = ("stored_ids",)
    writes = ("stored_ids",)
    accepted_input_type = Accepted

    def apply(self, input_obj: Accepted, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            output=Stored(input_obj.item_id),
            new_state=replace(state, stored_ids=state.stored_ids + (input_obj.item_id,)),
            label="broken_duplicate_store",
        )


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, Rejected)


def no_duplicate_stores(state: State, trace) -> InvariantResult:
    del trace
    if len(state.stored_ids) != len(set(state.stored_ids)):
        return InvariantResult.fail("stored_ids contains duplicates")
    return InvariantResult.pass_()


def every_store_was_accepted(state: State, trace) -> InvariantResult:
    del state
    accepted = {
        step.function_output.item_id
        for step in trace.steps
        if step.label == "accepted" and isinstance(step.function_output, Accepted)
    }
    stored = {
        step.function_output.item_id
        for step in trace.steps
        if step.label == "stored" and isinstance(step.function_output, Stored)
    }
    missing = tuple(sorted(stored - accepted))
    if missing:
        return InvariantResult.fail(f"stored without accepted source: {missing!r}")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        name="no_duplicate_stores",
        description="stored_ids contains each item at most once",
        predicate=no_duplicate_stores,
    ),
    Invariant(
        name="every_store_was_accepted",
        description="Stored outputs must be traceable to Accepted outputs",
        predicate=every_store_was_accepted,
    ),
)


EXTERNAL_INPUTS = (
    Input("item_a", True),
    Input("item_bad", False),
)

MAX_SEQUENCE_LENGTH = 2


def initial_state() -> State:
    return State()


def build_workflow() -> Workflow:
    return Workflow((ValidateInput(), StoreAccepted()), name="model_template")


def broken_workflow() -> Workflow:
    return Workflow((BrokenValidateInput(), BrokenStoreAccepted()), name="model_template_broken")


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "Accepted",
    "BrokenStoreAccepted",
    "BrokenValidateInput",
    "Input",
    "Rejected",
    "State",
    "Stored",
    "broken_workflow",
    "build_workflow",
    "initial_state",
    "terminal_predicate",
]
