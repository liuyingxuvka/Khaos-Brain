from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
FLOWGUARD_ROOT = REPO_ROOT / ".flowguard"
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

import kb_convergence_upgrade_model as model  # noqa: E402
import run_kb_convergence_checks as checks  # noqa: E402
from flowguard import run_model_first_checks  # noqa: E402
from scripts import check_kb_model_test_alignment as alignment  # noqa: E402


def _advance(state: model.AutomationState, event: model.AutomationInput):
    run = model.automation_workflow().execute(state, event)
    assert run.completed_paths, event.kind
    next_state = run.completed_paths[0].state
    for invariant in model.AUTOMATION_INVARIANTS:
        result = invariant.check(next_state, None)
        assert result.ok, (event.kind, invariant.name, result.message)
    return next_state


def test_update_authorization_stages_same_run_without_emitting_a_closure() -> None:
    state = model.AutomationState()
    for event in (
        model.automation_native_input(model.UPDATE_SKILL_ID),
        model.AutomationInput("depth_evaluate"),
        model.AutomationInput("build_native_terminal"),
        model.AutomationInput(
            "reconcile_update_checks",
            supervision_stage="declared_check_authorization",
            authorization_route_ids=(model.UPDATE_AUTHORIZE_ROUTE_ID,),
        ),
    ):
        state = _advance(state, event)

    assert state.evidence_domain == "scheduled_production"
    assert state.installation_receipt_root_ref == (
        "active_skill_root",
        ".sg-runtime/installation",
    )
    assert state.installation_receipt_current
    assert state.scheduled_supervision_snapshot_frozen_before_native
    assert state.scheduled_supervision_snapshot_reused_after_native
    assert not state.scheduled_supervision_live_reloaded_after_native
    assert state.scheduled_dynamic_evidence_projected_after_native
    assert state.scheduled_dynamic_evidence_whitelist_exact
    assert state.scheduled_inherited_dynamic_evidence_cleared
    assert state.authorization_run_id == state.run_id
    assert state.authorization_consumed_depth_receipt_id == state.depth_receipt_id
    assert (
        state.authorization_consumed_depth_receipt_hash
        == state.depth_receipt_hash
    )
    assert state.authorization_reconciliation_target_check_execution_count == 0
    assert state.target_check_execution_count == len(state.expected_check_ids)
    assert state.target_native_terminal_receipt_owner == model.UPDATE_SKILL_ID
    assert (
        state.authorization_consumed_native_terminal_receipt_id
        == state.target_native_terminal_receipt_id
    )
    assert state.authorization_supervision_stage == "declared_check_authorization"
    assert (
        state.target_native_terminal_disposition
        == "non_terminal_authorization"
    )
    assert state.authorization_completion_scope == "authorization_only"
    assert not state.authorization_overall_complete
    assert not state.closure_profile
    assert not state.closure_current
    assert not state.closure_consumed_depth
    assert not state.enforced_closed


@pytest.mark.parametrize("branch_id", ("no-update", "waiting-for-user", "ui-running"))
def test_legal_update_noop_is_enforced_terminal_completion(
    branch_id: str,
) -> None:
    native = model.automation_native_input(model.UPDATE_SKILL_ID)
    applicable = tuple(
        sorted(
            model.AUTOMATION_GATED_NOOP_ELIGIBLE_OBLIGATIONS[
                model.UPDATE_SKILL_ID
            ]
        )
    )
    executed = tuple(
        item
        for item in model.AUTOMATION_TARGET_OBLIGATIONS[model.UPDATE_SKILL_ID]
        if item not in set(applicable)
    )
    native = replace(
        native,
        gated_noop=True,
        noop_applicable_obligation_ids=applicable,
        noop_executed_obligation_ids=executed,
        noop_passed_obligation_ids=(
            model.AUTOMATION_TARGET_OBLIGATIONS[model.UPDATE_SKILL_ID]
        ),
        noop_receipt_hash=native.receipt_hash,
        noop_consumed_receipt_hash=native.receipt_hash,
        noop_closure_profile="enforced",
    )
    state = model.AutomationState()
    for event in (
        native,
        model.AutomationInput("depth_evaluate"),
        model.AutomationInput(
            "build_native_terminal",
            target_native_terminal_branch_id=branch_id,
        ),
        model.AutomationInput(
            "reconcile_update_checks",
            closure_profile="enforced",
            authorization_route_ids=(model.UPDATE_AUTHORIZE_ROUTE_ID,),
        ),
    ):
        state = _advance(state, event)

    assert state.target_native_terminal_disposition == "terminal_completion"
    assert not state.authorization_staged
    assert state.closure_completion_scope == "terminal_completion"
    assert state.overall_complete
    assert state.enforced_closed
    assert state.close_target_check_execution_count == 0


def test_composed_finalization_is_enforced_terminal_completion() -> None:
    state = model._staged_update_state()
    for event in (
        model.AutomationInput(
            "finalization_stage_depth",
            finalization_route_ids=model.UPDATE_COMPOSED_ROUTE_IDS,
        ),
        model.AutomationInput("finalization_build_native_terminal"),
        model.AutomationInput("finalization_close"),
    ):
        state = _advance(state, event)

    assert state.closure_profile == "enforced"
    assert state.closure_completion_scope == "terminal_completion"
    assert state.finalization_native_terminal_disposition == "terminal_completion"
    assert state.finalization_close_target_check_execution_count == 0


@pytest.mark.parametrize(
    "case_id",
    (
        "source_capability_closes_scheduled_production",
        "fixture_closes_scheduled_production",
        "scheduled_identity_missing_root_ref",
        "scheduled_identity_installation_stale",
        "runtime_projection_bytecode_mutated",
        "scheduled_supervision_live_reloaded_after_native",
        "scheduled_dynamic_evidence_not_projected",
        "scheduled_dynamic_evidence_not_isolated",
        "depth_receipt_hash_mismatch",
        "close_reruns_target_checks",
        "prepared_authorization_not_nonterminal",
        "update_terminal_receipt_wrong_owner",
        "update_terminal_receipt_depth_mismatch",
        "update_terminal_receipt_not_consumed",
        "finalization_close_reruns_target_checks",
    ),
)
def test_scheduled_production_known_bad_is_executable(case_id: str) -> None:
    summary = run_model_first_checks(
        checks._automation_known_bad_plan(
            case_id,
            model.automation_workflow(broken_mode=case_id),
        )
    )
    assert summary.overall_status == "failed"


def test_alignment_registers_scheduled_production_owner_rows() -> None:
    rows = {row["id"]: row for row in alignment.OBLIGATIONS}
    ids = set(rows)
    assert {
        "req.assurance.scheduled-production-domain",
        "req.assurance.scheduled-six-field-identity",
        "req.assurance.scheduled-installation-currentness",
        "req.assurance.scheduled-start-frozen-supervision",
        "req.assurance.scheduled-dynamic-evidence-channel",
        "req.assurance.declared-check-reconciliation",
        "req.assurance.update-target-owned-terminal",
    }.issubset(ids)
    terminal_description = str(
        rows["req.assurance.update-target-owned-terminal"].get("description")
        or ""
    )
    assert "without emitting a closure" in terminal_description
    assert "non_terminal_authorization" in terminal_description
    assert "enforced" in terminal_description
    assert "terminal_completion" in terminal_description
