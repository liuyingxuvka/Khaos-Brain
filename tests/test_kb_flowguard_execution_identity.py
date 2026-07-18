from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
FLOWGUARD_ROOT = REPO_ROOT / ".flowguard"
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

import kb_convergence_upgrade_model as model  # noqa: E402
import run_kb_convergence_checks as checks  # noqa: E402


def _advance(state: model.ConsumerState, event: model.ConsumerInput):
    run = model.consumer_independence_workflow().execute(state, event)
    assert run.completed_paths, event.kind
    next_state = run.completed_paths[0].state
    for invariant in model.CONSUMER_INVARIANTS:
        result = invariant.check(next_state, None)
        assert result.ok, (event.kind, invariant.name, result.message)
    return run.completed_paths[0].trace.steps[-1].label, next_state


def test_clean_projection_can_close_through_its_own_native_receipt() -> None:
    skill_id = "kb-sleep-maintenance"
    state = model.ConsumerState()
    label, state = _advance(
        state,
        model.ConsumerInput("install_projection", skill_id=skill_id),
    )
    assert label == "clean_consumer_projection_installed"
    label, state = _advance(
        state,
        model.ConsumerInput(
            "native_complete",
            skill_id=skill_id,
            obligation_ids=model.AUTOMATION_TARGET_OBLIGATIONS[skill_id],
        ),
    )
    assert label == "target_native_terminal_completed"
    assert state.completed_skills == (skill_id,)
    assert state.project_author_control_write_count == 0


def test_author_control_projection_is_rejected() -> None:
    label, state = _advance(
        model.ConsumerState(),
        model.ConsumerInput(
            "install_projection",
            skill_id="kb-dream-pass",
            contains_author_control=True,
        ),
    )
    assert label == "author_control_rejected"
    assert state.clean_installed_skills == ()
    assert state.blocked_skills == ("kb-dream-pass",)


def test_partial_native_receipt_cannot_complete() -> None:
    skill_id = "kb-organization-contribute"
    state = model.ConsumerState(clean_installed_skills=(skill_id,))
    label, state = _advance(
        state,
        model.ConsumerInput(
            "native_complete",
            skill_id=skill_id,
            obligation_ids=(),
        ),
    )
    assert label == "native_completion_blocked"
    assert state.completed_skills == ()


def test_manual_update_closes_directly_without_author_handoff() -> None:
    label, state = _advance(
        model.ConsumerState(),
        model.ConsumerInput(
            "manual_update",
            explicit_user_request=True,
        ),
    )
    assert label == "manual_update_current_and_restored"
    assert state.update_status == "current"
    assert state.update_restoration_ok
    assert state.update_final_health_ok
    assert state.update_mark_current_ok
    assert not state.update_survivors_paused


def test_manual_update_failure_keeps_survivors_paused() -> None:
    label, state = _advance(
        model.ConsumerState(),
        model.ConsumerInput(
            "manual_update",
            explicit_user_request=True,
            restoration_ok=False,
        ),
    )
    assert label == "manual_update_failed_survivors_paused"
    assert state.update_status == "failed"
    assert state.update_survivors_paused


def test_flowguard_consumer_independence_report_passes() -> None:
    report = checks.build_report()
    assert report["ok"], report
    assert report["contracts"]["cross_unit_test_evidence_overlaps"] == []
    assert report["scenarios"]["ok"] is True
