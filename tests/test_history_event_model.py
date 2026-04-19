from __future__ import annotations

import unittest

from local_kb.feedback import build_observation
from local_kb.history import build_history_event


class HistoryEventModelTests(unittest.TestCase):
    def test_observation_uses_canonical_event_shape(self) -> None:
        event = build_observation(
            task_summary="Summarize weekly status into slides",
            route_hint="work/reporting/ppt",
            entry_ids="example-entry-001",
            hit_quality="hit",
            outcome="Deck draft was accepted",
            suggested_action="update-card",
            exposed_gap=True,
            source_kind="task",
            agent_name="worker-1",
            thread_ref="thread-123",
        )

        self.assertEqual(event["event_type"], "observation")
        self.assertEqual(set(event), {"event_id", "event_type", "created_at", "source", "target", "rationale", "context"})
        self.assertEqual(event["source"]["agent"], "worker-1")
        self.assertEqual(event["target"]["kind"], "task-observation")
        self.assertEqual(event["target"]["entry_ids"], ["example-entry-001"])
        self.assertEqual(event["context"]["hit_quality"], "hit")
        self.assertTrue(event["context"]["exposed_gap"])
        self.assertIn("next=update-card", event["rationale"])

    def test_base_builder_preserves_empty_rationale_and_context_shape(self) -> None:
        event = build_history_event(
            "candidate-created",
            source={"kind": "manual-entry", "agent": "kb-capture"},
            target={"kind": "candidate-entry", "entry_id": "cand-1"},
        )

        self.assertEqual(event["rationale"], "")
        self.assertEqual(event["context"], {})
        self.assertEqual(event["target"]["entry_id"], "cand-1")


if __name__ == "__main__":
    unittest.main()
