from __future__ import annotations

import tempfile
from pathlib import Path

from local_kb.automation_contracts import AUTOMATION_COMPLETION_CONTRACTS, obligation_id
from local_kb.automation_runtime import build_fixture_payload, evaluate_native_payload
from local_kb.lifecycle import run_incremental_sleep


def _assert_only_gate_performed(
    skill_id: str,
    evidence: dict[str, dict[str, object]],
    gate_suffix: str,
) -> None:
    gate_id = obligation_id(skill_id, gate_suffix)
    performed = {
        item_id
        for item_id, row in evidence.items()
        if row.get("outcome") == "performed"
    }
    assert performed == {gate_id}
    for item_id, row in evidence.items():
        if item_id == gate_id:
            continue
        assert row["outcome"] == "not_applicable"
        assert row["applicability"]["evaluated"] is True
        assert row["applicability"]["applicable"] is False
        assert row["non_mutation"]["proven"] is True
        assert row["non_mutation"]["mutation_performed"] is False
        assert row["non_mutation"]["gate_facts_hash"]
        assert row["terminal_gate"]["evaluated"] is True
        assert row["terminal_gate"]["applicable"] is False
        assert row["terminal_gate"]["mutation_performed"] is False


def test_real_sleep_receipt_requires_exact_lock_owner_and_release() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = run_incremental_sleep(Path(tmp), run_id="sleep-native-lock")
        payload["lifecycle_review"].pop("ok", None)

        current = evaluate_native_payload(
            "kb-sleep-maintenance",
            payload,
            exit_code=0,
            expected_run_id="sleep-native-lock",
        )
        assert current["ok"], current

        wrong_owner = {
            **payload,
            "lane_lock": {**payload["lane_lock"], "run_id": "another-run"},
        }
        wrong_owner_result = evaluate_native_payload(
            "kb-sleep-maintenance",
            wrong_owner,
            exit_code=0,
            expected_run_id="sleep-native-lock",
        )
        assert not wrong_owner_result["ok"]
        assert not wrong_owner_result["evidence"][
            obligation_id("kb-sleep-maintenance", "lane-delta-intake")
        ]["ok"]

        unreleased = {
            **payload,
            "lock_release": {**payload["lock_release"], "released": False},
        }
        unreleased_result = evaluate_native_payload(
            "kb-sleep-maintenance",
            unreleased,
            exit_code=0,
            expected_run_id="sleep-native-lock",
        )
        assert not unreleased_result["ok"]
        assert not unreleased_result["evidence"][
            obligation_id("kb-sleep-maintenance", "index-watermark-commit")
        ]["ok"]
        assert not unreleased_result["evidence"][
            obligation_id("kb-sleep-maintenance", "failure-fail-closed")
        ]["ok"]


def test_organization_contribution_noop_performs_only_settings_gate() -> None:
    skill_id = "kb-organization-contribute"
    reason = "organization mode is not connected to a validated repository"
    payload = {
        "ok": True,
        "skipped": True,
        "run_id": "org-contribute-noop",
        "reason": reason,
        "settings_gate": {"available": False, "organization_validated": False},
        "terminal_gate": {
            "gate_id": "organization-settings",
            "evaluated": True,
            "applicable": False,
            "reason": reason,
        },
    }

    result = evaluate_native_payload(skill_id, payload, exit_code=0)

    assert result["ok"], result
    assert result["terminal_status"] == "no-op"
    _assert_only_gate_performed(
        skill_id,
        result["evidence"],
        "settings-noop-gate",
    )
    assert result["evidence"][obligation_id(skill_id, "lane-failure-recovery")][
        "outcome"
    ] == "not_applicable"


def test_organization_maintenance_noop_performs_only_participation_gate() -> None:
    skill_id = "kb-organization-maintenance"
    reason = "organization maintenance participation is not requested"
    payload = {
        "ok": True,
        "skipped": True,
        "run_id": "org-maintenance-noop",
        "reason": reason,
        "settings_gate": {"available": False, "organization_validated": True},
        "participation": {"available": False, "reason": reason},
        "terminal_gate": {
            "gate_id": "organization-maintenance-participation",
            "evaluated": True,
            "applicable": False,
            "reason": reason,
        },
    }

    result = evaluate_native_payload(skill_id, payload, exit_code=0)

    assert result["ok"], result
    _assert_only_gate_performed(
        skill_id,
        result["evidence"],
        "settings-participation-gate",
    )


def test_all_legal_update_noops_perform_only_system_gate() -> None:
    skill_id = "khaos-brain-update"
    for reason in ("no-update", "waiting-for-user", "ui-running"):
        payload = {
            "ok": True,
            "status": "no-op",
            "run_id": f"update-{reason}",
            "reason": reason,
            "system_check": {"ok": True, "apply_ready": False, "reason": reason},
            "terminal_gate": {
                "gate_id": "system-update-check",
                "evaluated": True,
                "applicable": False,
                "reason": reason,
            },
        }

        result = evaluate_native_payload(skill_id, payload, exit_code=0)

        assert result["ok"], (reason, result)
        assert set(result["evidence"]) == {
            obligation_id(skill_id, str(row["suffix"]))
            for row in AUTOMATION_COMPLETION_CONTRACTS[skill_id]["obligations"]
            if str(row["suffix"]) != "depth-calibration"
            and str(row.get("evidence_source") or "native-receipt")
            == "native-receipt"
        }
        _assert_only_gate_performed(
            skill_id,
            result["evidence"],
            "authorization-system-check",
        )


def test_update_operational_blockers_cannot_close_as_successful_noops() -> None:
    skill_id = "khaos-brain-update"
    for reason in (
        "already-upgrading",
        "failed-awaiting-user",
        "concurrent-update",
    ):
        payload = {
            "ok": True,
            "status": "no-op",
            "run_id": f"update-{reason}",
            "reason": reason,
            "system_check": {"ok": True, "apply_ready": False, "reason": reason},
            "terminal_gate": {
                "gate_id": "system-update-check",
                "evaluated": True,
                "applicable": False,
                "reason": reason,
            },
        }

        result = evaluate_native_payload(skill_id, payload, exit_code=0)

        assert not result["ok"], (reason, result)
        assert result["terminal_status"] == "failed"


def test_contribution_receipt_rejects_materialization_or_privacy_drift() -> None:
    skill_id = "kb-organization-contribute"
    payload = build_fixture_payload(skill_id, run_id="contribution-materialization")
    current = evaluate_native_payload(skill_id, payload, exit_code=0)
    assert current["ok"], current

    payload["branch"]["pre_push_readback"]["manifest_hash"] = "drifted"
    payload["branch"]["organization_check"]["checks"]["privacy_scan"]["ok"] = False
    drifted = evaluate_native_payload(skill_id, payload, exit_code=0)

    assert not drifted["ok"]
    assert not drifted["evidence"][
        obligation_id(skill_id, "branch-pr-auto-merge")
    ]["ok"]


def test_contribution_without_pending_proposals_proves_branch_not_applicable() -> None:
    skill_id = "kb-organization-contribute"
    payload = build_fixture_payload(skill_id, run_id="contribution-no-pending")
    payload["outbox"]["pending_count"] = 0
    payload["branch"] = {"attempted": False}

    result = evaluate_native_payload(skill_id, payload, exit_code=0)

    assert result["ok"], result
    evidence = result["evidence"][
        obligation_id(skill_id, "branch-pr-auto-merge")
    ]
    assert evidence["outcome"] == "not_applicable"
    assert evidence["source_fields"] == [
        "outbox.pending_count",
        "branch.attempted",
    ]
    assert evidence["applicability"]["gate_id"] == (
        "organization-pending-proposals"
    )
    assert evidence["non_mutation"]["proven"] is True
    assert evidence["terminal_gate"]["run_id"] == "contribution-no-pending"


def test_maintenance_receipt_rejects_materialization_readback_drift() -> None:
    skill_id = "kb-organization-maintenance"
    payload = build_fixture_payload(skill_id, run_id="maintenance-materialization")
    current = evaluate_native_payload(skill_id, payload, exit_code=0)
    assert current["ok"], current

    payload["maintenance_branch"]["pre_push_readback"]["file_sha256"] = {
        "kb/imports/fixture/card.yaml": "changed-after-check"
    }
    drifted = evaluate_native_payload(skill_id, payload, exit_code=0)

    assert not drifted["ok"]
    assert not drifted["evidence"][
        obligation_id(skill_id, "postapply-merge-readiness")
    ]["ok"]


def test_maintenance_without_selected_actions_uses_only_applicable_readiness_sources() -> None:
    skill_id = "kb-organization-maintenance"
    payload = build_fixture_payload(skill_id, run_id="maintenance-no-selection")
    cleanup = payload["report"]["cleanup"]
    cleanup["review"]["selected_action_ids"] = []
    cleanup["apply"] = {
        "attempted": False,
        "ok": True,
        "applied_action_ids": [],
    }
    cleanup["exact_selected_apply"] = {
        "complete": True,
        "exact": True,
        "selected_action_ids": [],
        "applied_action_ids": [],
    }
    cleanup["github_merge_readiness"] = {
        "complete": True,
        "eligible": False,
        "label": "org-kb:auto-merge",
        "blockers": ["no-selected-actions"],
    }
    payload["maintenance_branch"] = {"attempted": False}

    result = evaluate_native_payload(skill_id, payload, exit_code=0)

    assert result["ok"], result
    evidence = result["evidence"][
        obligation_id(skill_id, "postapply-merge-readiness")
    ]
    assert evidence["outcome"] == "performed"
    assert evidence["source_fields"] == [
        "report.cleanup.post_apply_check",
        "report.cleanup.github_merge_readiness",
        "maintenance_branch",
    ]
