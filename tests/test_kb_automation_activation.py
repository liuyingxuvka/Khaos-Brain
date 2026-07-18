from __future__ import annotations

import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from local_kb.install import (
    REPO_AUTOMATION_SPECS,
    apply_repo_automation_restoration_plan,
    capture_repo_automation_state_snapshot,
    plan_repo_automation_restoration,
)
import local_kb.install as install_module


def _write_automations(codex_home: Path, *, active_id: str = "") -> None:
    for spec in REPO_AUTOMATION_SPECS:
        automation_id = str(spec["id"])
        path = codex_home / "automations" / automation_id / "automation.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        status = "ACTIVE" if automation_id == active_id else "PAUSED"
        path.write_text(
            f'id = "{automation_id}"\nstatus = "{status}"\nuser_paused = false\n',
            encoding="utf-8",
        )


def _desired_states() -> tuple[dict[str, str], dict[str, bool]]:
    states = {
        str(spec["id"]): ("PAUSED" if index % 2 else "ACTIVE")
        for index, spec in enumerate(REPO_AUTOMATION_SPECS)
    }
    user_paused = {automation_id: status == "PAUSED" for automation_id, status in states.items()}
    return states, user_paused


def test_restoration_plan_does_not_activate_live_automations() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        codex_home = Path(tmp) / ".codex"
        _write_automations(codex_home)
        states, user_paused = _desired_states()

        plan = plan_repo_automation_restoration(
            codex_home,
            states,
            user_paused_states=user_paused,
        )

        assert plan["ok"], plan
        assert set(plan["source_states"].values()) == {"PAUSED"}
        for spec in REPO_AUTOMATION_SPECS:
            text = (
                codex_home
                / "automations"
                / str(spec["id"])
                / "automation.toml"
            ).read_text(encoding="utf-8")
            assert 'status = "PAUSED"' in text


def test_legacy_snapshot_treats_later_managed_jobs_as_new_not_ambiguous() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        codex_home = Path(tmp) / ".codex"
        for automation_id in ("kb-sleep", "kb-dream"):
            path = codex_home / "automations" / automation_id / "automation.toml"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f'id = "{automation_id}"\nstatus = "ACTIVE"\nuser_paused = false\n',
                encoding="utf-8",
            )

        snapshot = capture_repo_automation_state_snapshot(codex_home)

        assert snapshot["ok"], snapshot
        for automation_id in ("kb-org-contribute", "kb-org-maintenance"):
            assert snapshot["states"][automation_id] == "ACTIVE"
            assert snapshot["user_paused"][automation_id] is False
            assert snapshot["sources"][automation_id] == "new-automation-policy"
        assert "khaos-brain-system-update" not in snapshot["states"]


def test_legacy_snapshot_still_blocks_when_an_owned_sleep_state_is_missing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        codex_home = Path(tmp) / ".codex"
        dream = codex_home / "automations" / "kb-dream" / "automation.toml"
        dream.parent.mkdir(parents=True, exist_ok=True)
        dream.write_text(
            'id = "kb-dream"\nstatus = "ACTIVE"\nuser_paused = false\n',
            encoding="utf-8",
        )

        snapshot = capture_repo_automation_state_snapshot(codex_home)

        assert not snapshot["ok"]
        assert snapshot["states"]["kb-sleep"] == "PAUSED"
        assert snapshot["user_paused"]["kb-sleep"] is True
        assert snapshot["sources"]["kb-sleep"] == "unknown-fail-closed"


def test_restoration_apply_rejects_any_post_authorization_source_change() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        codex_home = Path(tmp) / ".codex"
        _write_automations(codex_home)
        states, user_paused = _desired_states()
        plan = plan_repo_automation_restoration(
            codex_home,
            states,
            user_paused_states=user_paused,
        )
        changed = (
            codex_home
            / "automations"
            / str(REPO_AUTOMATION_SPECS[0]["id"])
            / "automation.toml"
        )
        changed.write_text(changed.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")

        result = apply_repo_automation_restoration_plan(codex_home, plan)

        assert not result["ok"]
        assert any("restoration-source-changed" in item for item in result["issues"])
        assert all(
            'status = "PAUSED"'
            in (
                codex_home
                / "automations"
                / str(spec["id"])
                / "automation.toml"
            ).read_text(encoding="utf-8")
            for spec in REPO_AUTOMATION_SPECS
        )


def test_restoration_apply_rolls_back_a_partial_group_write() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        codex_home = Path(tmp) / ".codex"
        _write_automations(codex_home)
        states = {str(spec["id"]): "ACTIVE" for spec in REPO_AUTOMATION_SPECS}
        user_paused = {automation_id: False for automation_id in states}
        plan = plan_repo_automation_restoration(
            codex_home,
            states,
            user_paused_states=user_paused,
        )
        before = {
            automation_id: (
                codex_home / "automations" / automation_id / "automation.toml"
            ).read_text(encoding="utf-8")
            for automation_id in states
        }
        real_write = install_module._write_text_atomic
        failed_once = False

        def fail_second_target_once(path: Path, text: str) -> None:
            nonlocal failed_once
            if not failed_once and path.parent.name == sorted(states)[1]:
                failed_once = True
                raise OSError("injected group write failure")
            real_write(path, text)

        with patch(
            "local_kb.install._write_text_atomic",
            side_effect=fail_second_target_once,
        ):
            result = apply_repo_automation_restoration_plan(codex_home, plan)

        assert not result["ok"]
        assert result["rollback"]["attempted"]
        assert result["rollback"]["ok"], result
        for automation_id, original in before.items():
            path = codex_home / "automations" / automation_id / "automation.toml"
            assert path.read_text(encoding="utf-8") == original
            assert 'status = "PAUSED"' in original
