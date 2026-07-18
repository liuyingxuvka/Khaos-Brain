"""Replay representative model expectations against production code."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.maintenance_lanes import acquire_lane_lock, read_lane_lock, release_lane_lock
from local_kb.software_update import (
    UPDATE_STATUS_AVAILABLE,
    UPDATE_STATUS_CURRENT,
    UPDATE_STATUS_DIVERGED,
    UPDATE_STATUS_FAILED,
    UPDATE_STATUS_LOCAL_AHEAD,
    UPDATE_STATUS_UNAVAILABLE,
    UPDATE_STATUS_UPGRADING,
    load_update_state,
    manual_update_check,
    save_update_state,
)
from local_kb.store import load_organization_entries, write_yaml_file


def _check(condition: bool, name: str, failures: list[str], detail: str = "") -> None:
    if not condition:
        failures.append(f"{name}: {detail}".strip(": "))


def replay_maintenance_locks(failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = acquire_lane_lock(root, "kb-sleep", run_id="sleep-1", poll_seconds=0)
        second = acquire_lane_lock(root, "kb-dream", run_id="dream-1", wait=False, poll_seconds=0)
        _check(bool(first.get("acquired")), "local first lock acquired", failures)
        _check(not bool(second.get("acquired")), "local second lock waits", failures, str(second))
        release_lane_lock(root, "kb-sleep", run_id="sleep-1")
        third = acquire_lane_lock(root, "kb-dream", run_id="dream-1", wait=False, poll_seconds=0)
        _check(bool(third.get("acquired")), "local lock acquired after release", failures)
        release_lane_lock(root, "kb-dream", run_id="dream-1")
        _check(read_lane_lock(root, "local-maintenance") == {}, "local lock released", failures)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        org = acquire_lane_lock(root, "kb-org-contribute", run_id="contrib-1", poll_seconds=0)
        local = acquire_lane_lock(root, "kb-dream", run_id="dream-1", wait=False, poll_seconds=0)
        blocked_org = acquire_lane_lock(root, "kb-org-maintenance", run_id="maint-1", wait=False, poll_seconds=0)
        _check(bool(org.get("acquired")), "org first lock acquired", failures)
        _check(bool(local.get("acquired")), "local and org lock groups are independent", failures)
        _check(not bool(blocked_org.get("acquired")), "org second lock waits", failures, str(blocked_org))


def replay_organization_download_surface(failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        org = Path(tmp)
        write_yaml_file(org / "kb" / "main" / "trusted.yaml", {"id": "trusted", "status": "trusted"})
        write_yaml_file(org / "kb" / "main" / "candidate.yaml", {"id": "candidate", "status": "candidate"})
        write_yaml_file(org / "kb" / "main" / "rejected.yaml", {"id": "rejected", "status": "rejected"})
        write_yaml_file(org / "kb" / "imports" / "alice" / "import.yaml", {"id": "import", "status": "candidate"})
        entries = load_organization_entries(org, "sandbox")
        ids = sorted(str(entry.data.get("id") or "") for entry in entries)
        _check(ids == ["candidate", "trusted"], "organization download reads active main only", failures, repr(ids))


def replay_update_gate(failures: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "VERSION").write_text("0.4.3\n", encoding="utf-8")
        save_update_state(
            root,
            {
                "status": UPDATE_STATUS_AVAILABLE,
                "update_available": True,
                "latest_version": "0.4.4",
                "latest_revision": "remote",
                "upstream_ref": "origin/main",
                "behind_count": 1,
            },
        )
        state_before = (root / ".local" / "khaos_brain_update_state.json").read_bytes()
        missing_authorization = manual_update_check(
            root,
            explicit_user_request=False,
            check_remote=False,
            ui_processes=[],
        )
        _check(
            not bool(missing_authorization.get("apply_ready")),
            "manual update requires current request authorization",
            failures,
            str(missing_authorization),
        )
        _check(
            state_before
            == (root / ".local" / "khaos_brain_update_state.json").read_bytes(),
            "missing authorization does not mutate update state",
            failures,
        )
        blocked = manual_update_check(
            root,
            explicit_user_request=True,
            check_remote=False,
            ui_processes=[{"Name": "KhaosBrain.exe"}],
        )
        _check(not bool(blocked.get("apply_ready")), "update waits while UI is running", failures, str(blocked))
        allowed = manual_update_check(
            root,
            explicit_user_request=True,
            check_remote=False,
            ui_processes=[],
        )
        _check(bool(allowed.get("apply_ready")), "explicit manual update applies when UI is closed", failures, str(allowed))
        _check(allowed.get("state", {}).get("status") == UPDATE_STATUS_UPGRADING, "update marks upgrading", failures)

    for status, expected_reason in (
        (UPDATE_STATUS_CURRENT, "no-update"),
        (UPDATE_STATUS_LOCAL_AHEAD, "non-fast-forward-topology"),
        (UPDATE_STATUS_DIVERGED, "non-fast-forward-topology"),
        (UPDATE_STATUS_UNAVAILABLE, "remote-check-failed"),
        (UPDATE_STATUS_FAILED, "previous-update-failed"),
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("0.4.3\n", encoding="utf-8")
            save_update_state(root, {"status": status})
            observed = manual_update_check(
                root,
                explicit_user_request=True,
                check_remote=False,
                ui_processes=[],
            )
            _check(
                not bool(observed.get("apply_ready")),
                f"manual update blocks topology/status {status}",
                failures,
                str(observed),
            )
            _check(
                observed.get("reason") == expected_reason,
                f"manual update reason for {status}",
                failures,
                str(observed),
            )
            _check(
                load_update_state(root).get("status") == status,
                f"manual status check preserves {status}",
                failures,
            )


def main() -> int:
    failures: list[str] = []
    replay_maintenance_locks(failures)
    replay_organization_download_surface(failures)
    replay_update_gate(failures)
    report = {
        "ok": not failures,
        "failures": failures,
        "replayed_expectations": [
            "local lanes are mutually exclusive",
            "organization lanes are mutually exclusive but independent from local lanes",
            "organization downloads read kb/main trusted/candidate, not kb/imports or rejected",
            "software update requires an explicit current-conversation request and a closed UI",
            "current is the sole no-update terminal; ahead, diverged, unavailable, and failed remain blocked",
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
