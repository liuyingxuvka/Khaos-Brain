from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.maintenance_lanes import (
    acquire_lane_lock,
    build_lane_guard,
    lane_lock_group,
    read_lane_lock,
    release_lane_lock,
)


class MaintenanceLaneLockTests(unittest.TestCase):
    def test_local_maintenance_lanes_share_one_waiting_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)

            first = acquire_lane_lock(repo_root, "kb-sleep", run_id="sleep-1", poll_seconds=0)
            second = acquire_lane_lock(repo_root, "kb-dream", run_id="dream-1", wait=False, poll_seconds=0)

            self.assertTrue(first["acquired"])
            self.assertFalse(second["acquired"])
            self.assertEqual(second["blocked_by"]["lane"], "kb-sleep")
            self.assertEqual(build_lane_guard(repo_root, "kb-dream")["blocking_lanes"], ["kb-sleep"])

            released = release_lane_lock(repo_root, "kb-sleep", run_id="sleep-1")
            self.assertTrue(released["released"])
            self.assertEqual(read_lane_lock(repo_root, "local-maintenance"), {})

    def test_organization_lanes_share_a_separate_waiting_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)

            org = acquire_lane_lock(repo_root, "kb-org-contribute", run_id="contrib-1", poll_seconds=0)
            local = acquire_lane_lock(repo_root, "kb-dream", run_id="dream-1", wait=False, poll_seconds=0)
            blocked_org = acquire_lane_lock(
                repo_root,
                "kb-org-maintenance",
                run_id="maint-1",
                wait=False,
                poll_seconds=0,
            )

            self.assertEqual(lane_lock_group("kb-org-maintenance"), "organization-maintenance")
            self.assertTrue(org["acquired"])
            self.assertTrue(local["acquired"])
            self.assertFalse(blocked_org["acquired"])
            self.assertEqual(blocked_org["blocked_by"]["lane"], "kb-org-contribute")

    def test_stale_lane_lock_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)

            acquire_lane_lock(repo_root, "kb-sleep", run_id="sleep-1", poll_seconds=0)
            recovered = acquire_lane_lock(
                repo_root,
                "kb-dream",
                run_id="dream-1",
                poll_seconds=0,
                stale_after_seconds=0,
            )

            self.assertTrue(recovered["acquired"])
            self.assertEqual(recovered["lane"], "kb-dream")


if __name__ == "__main__":
    unittest.main()
