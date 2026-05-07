from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_kb.consolidate import consolidate_history
from local_kb.maintenance import build_maintenance_decision, record_maintenance_decision


def append_events(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


class MaintenanceDecisionHistoryTests(unittest.TestCase):
    def test_same_route_repeated_entry_updates_stay_hub_for_now(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            append_events(
                history_path,
                [
                    {
                        "event_id": "hub-1",
                        "event_type": "observation",
                        "created_at": "2026-04-20T07:00:00+00:00",
                        "source": {"kind": "task", "agent": "worker-4"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-004"],
                            "route_hint": ["system", "knowledge-library", "retrieval"],
                            "task_summary": "Retriever card needs tighter wording for postflight",
                        },
                        "rationale": "next=update-card",
                        "context": {
                            "suggested_action": "update-card",
                            "hit_quality": "hit",
                            "predictive_observation": {
                                "scenario": "A retrieval workflow needs clearer postflight wording.",
                                "action_taken": "Update the same retrieval card guidance.",
                                "observed_result": "The card remains the right route entry point.",
                                "operational_use": "Keep the card as the hub and tighten wording only.",
                            },
                        },
                    },
                    {
                        "event_id": "hub-2",
                        "event_type": "observation",
                        "created_at": "2026-04-20T07:05:00+00:00",
                        "source": {"kind": "task", "agent": "worker-5"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-004"],
                            "route_hint": ["system", "knowledge-library", "retrieval"],
                            "task_summary": "Retriever card still needs stronger repository wording",
                        },
                        "rationale": "next=update-card",
                        "context": {
                            "suggested_action": "update-card",
                            "hit_quality": "hit",
                            "predictive_observation": {
                                "scenario": "A repository task still routes through the same retrieval hub card.",
                                "action_taken": "Inspect the hub card wording rather than splitting it.",
                                "observed_result": "The card still looks like one bounded retrieval rule.",
                                "operational_use": "Keep the same hub card and revise wording if needed.",
                            },
                        },
                    },
                ],
            )

            result = consolidate_history(repo_root=repo_root, run_id="hub-run")
            entry_update_action = next(action for action in result["actions"] if action["action_type"] == "review-entry-update")
            self.assertEqual(
                entry_update_action["split_review_suggestion"]["recommendation"],
                "keep-as-hub-for-now",
            )
            self.assertEqual(
                entry_update_action["split_review_suggestion"]["distinct_route_count"],
                1,
            )

    def test_same_route_but_clearly_multi_branch_evidence_triggers_split_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            append_events(
                history_path,
                [
                    {
                        "event_id": "hub-branch-1",
                        "event_type": "observation",
                        "created_at": "2026-04-20T07:00:00+00:00",
                        "source": {"kind": "task", "agent": "worker-4"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-004"],
                            "route_hint": ["system", "knowledge-library", "retrieval"],
                            "task_summary": "Retrieval hub needs stronger wording for repo preflight",
                        },
                        "rationale": "next=update-card",
                        "context": {
                            "suggested_action": "update-card",
                            "hit_quality": "hit",
                            "predictive_observation": {
                                "scenario": "Repository preflight work lands on the retrieval hub card.",
                                "action_taken": "Use the hub card before repository work starts.",
                                "observed_result": "Repository tasks surface prior models earlier.",
                                "operational_use": "Treat the card as the first step for repository preflight.",
                            },
                        },
                    },
                    {
                        "event_id": "hub-branch-2",
                        "event_type": "observation",
                        "created_at": "2026-04-20T07:05:00+00:00",
                        "source": {"kind": "task", "agent": "worker-5"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-004"],
                            "route_hint": ["system", "knowledge-library", "retrieval"],
                            "task_summary": "Retrieval hub now also frames maintenance self-check workflow",
                        },
                        "rationale": "next=update-card",
                        "context": {
                            "suggested_action": "update-card",
                            "hit_quality": "hit",
                            "predictive_observation": {
                                "scenario": "Maintenance work reuses the same card to decide whether KB self-check is required.",
                                "action_taken": "Use the hub card as maintenance preflight guidance.",
                                "observed_result": "Maintenance tasks remember to run KB self-check before editing prompts or cards.",
                                "operational_use": "Review whether maintenance guidance should move into a sibling card.",
                            },
                        },
                    },
                    {
                        "event_id": "hub-branch-3",
                        "event_type": "observation",
                        "created_at": "2026-04-20T07:10:00+00:00",
                        "source": {"kind": "task", "agent": "worker-6"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-004"],
                            "route_hint": ["system", "knowledge-library", "retrieval"],
                            "task_summary": "Retrieval hub is now being used as publish-audit checklist entry",
                        },
                        "rationale": "next=update-card",
                        "context": {
                            "suggested_action": "update-card",
                            "hit_quality": "hit",
                            "predictive_observation": {
                                "scenario": "Publish and release-audit work reaches the same card as a release hygiene checkpoint.",
                                "action_taken": "Apply the same hub card before release-facing repository work.",
                                "observed_result": "Release tasks are less likely to skip KB preflight and privacy review.",
                                "operational_use": "Review whether publish/release hygiene deserves a sibling retrieval card.",
                            },
                        },
                    },
                ],
            )

            result = consolidate_history(repo_root=repo_root, run_id="hub-branch-run")
            entry_update_action = next(action for action in result["actions"] if action["action_type"] == "review-entry-update")
            self.assertEqual(
                entry_update_action["split_review_suggestion"]["recommendation"],
                "consider-split-review",
            )
            self.assertEqual(
                entry_update_action["split_review_suggestion"]["distinct_route_count"],
                1,
            )
            self.assertEqual(
                entry_update_action["split_review_suggestion"]["distinct_observed_result_count"],
                3,
            )

    def test_ignored_observation_suppresses_only_already_resolved_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            append_events(
                history_path,
                [
                    {
                        "event_id": "obs-1",
                        "event_type": "observation",
                        "created_at": "2026-04-20T08:00:00+00:00",
                        "source": {"kind": "task", "agent": "worker-1"},
                        "target": {
                            "kind": "task-observation",
                            "route_hint": ["work", "reporting", "ppt"],
                            "task_summary": "Need a route-specific reporting deck card",
                        },
                        "rationale": "next=new-candidate",
                        "context": {"suggested_action": "new-candidate"},
                    }
                ],
            )

            first = consolidate_history(repo_root=repo_root, run_id="ignore-run-1")
            review_action = next(
                action for action in first["actions"] if action["action_type"] == "review-observation-evidence"
            )
            ignore_event = build_maintenance_decision(
                decision_type="observation-ignored",
                action_key=review_action["action_key"],
                resolved_event_ids=review_action["event_ids"],
                reason="This was a one-off observation and should stay history-only.",
                route_ref="work/reporting/ppt",
                decision_summary="ignore-if-one-off",
            )
            record_maintenance_decision(repo_root, ignore_event)

            second = consolidate_history(repo_root=repo_root, run_id="ignore-run-2")
            self.assertEqual(second["suppressed_action_count"], 1)
            self.assertNotIn(
                "review-observation-evidence",
                [action["action_type"] for action in second["actions"]],
            )
            self.assertEqual(
                second["suppressed_actions"][0]["action_key"],
                review_action["action_key"],
            )

            append_events(
                history_path,
                [
                    {
                        "event_id": "obs-2",
                        "event_type": "observation",
                        "created_at": "2026-04-20T08:10:00+00:00",
                        "source": {"kind": "task", "agent": "worker-1"},
                        "target": {
                            "kind": "task-observation",
                            "route_hint": ["work", "reporting", "ppt"],
                            "task_summary": "Still missing a reusable reporting route card",
                        },
                        "rationale": "next=new-candidate",
                        "context": {"suggested_action": "new-candidate"},
                    }
                ],
            )

            third = consolidate_history(repo_root=repo_root, run_id="ignore-run-3")
            resurfaced = next(
                action for action in third["actions"] if action["action_type"] == "review-observation-evidence"
            )
            self.assertEqual(resurfaced["event_count"], 2)
            self.assertEqual(third["suppressed_action_count"], 0)

    def test_candidate_rejection_suppresses_review_candidate_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            append_events(
                history_path,
                [
                    {
                        "event_id": "candidate-1",
                        "event_type": "candidate-created",
                        "created_at": "2026-04-20T09:00:00+00:00",
                        "source": {"kind": "kb-capture", "agent": "worker-2"},
                        "target": {
                            "kind": "candidate-entry",
                            "entry_id": "cand-email-default",
                            "domain_path": ["work", "communication", "email"],
                        },
                        "rationale": "manual candidate capture",
                        "context": {},
                    }
                ],
            )

            first = consolidate_history(repo_root=repo_root, run_id="reject-run-1")
            review_action = next(action for action in first["actions"] if action["action_type"] == "review-candidate")
            rejection_event = build_maintenance_decision(
                decision_type="candidate-rejected",
                action_key=review_action["action_key"],
                resolved_event_ids=review_action["event_ids"],
                reason="This candidate did not hold up as a reusable predictive card.",
                entry_id="cand-email-default",
                decision_summary="reject-candidate",
            )
            record_maintenance_decision(repo_root, rejection_event)

            second = consolidate_history(repo_root=repo_root, run_id="reject-run-2")
            self.assertEqual(second["suppressed_action_count"], 1)
            self.assertEqual(second["candidate_action_count"], 0)
            self.assertFalse(second["actions"])

    def test_consolidation_reports_bounded_review_batch_for_large_candidate_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            events = []
            for index in range(36):
                events.append(
                    {
                        "event_id": f"candidate-{index}",
                        "event_type": "observation",
                        "created_at": f"2026-04-20T10:{index:02d}:00+00:00",
                        "source": {"kind": "task", "agent": "worker"},
                        "target": {
                            "kind": "task-observation",
                            "route_hint": ["predictive-kb", "maintenance", f"topic-{index}"],
                            "task_summary": f"Maintenance topic {index}",
                        },
                        "rationale": "next=new-candidate",
                        "context": {
                            "suggested_action": "new-candidate",
                            "predictive_observation": {
                                "scenario": f"Scenario {index}",
                                "action_taken": "Use a bounded maintenance review.",
                                "observed_result": "Review stays small.",
                                "operational_use": "Prefer bounded Sleep review batches for maintenance candidate intake.",
                                "reuse_judgment": "Reusable for candidate backlog control.",
                            },
                        },
                    }
                )
            append_events(history_path, events)

            result = consolidate_history(repo_root=repo_root, run_id="bounded-review")
            review_batch = result["review_batch"]

        self.assertEqual(result["candidate_action_count"], 36)
        self.assertEqual(review_batch["status"], "bounded")
        self.assertEqual(review_batch["max_selected_actions"], 30)
        self.assertEqual(review_batch["selected_action_count"], 30)
        self.assertEqual(review_batch["deferred_action_count"], 6)
        self.assertEqual(review_batch["apply_eligible_action_count"], 36)
        self.assertEqual(review_batch["selected_apply_eligible_action_count"], 30)

    def test_confidence_review_suppresses_resolved_signal_but_resurfaces_with_new_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            append_events(
                history_path,
                [
                    {
                        "event_id": "conf-1",
                        "event_type": "observation",
                        "created_at": "2026-04-20T10:00:00+00:00",
                        "source": {"kind": "task", "agent": "worker-3"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-release-notes-first"],
                            "route_hint": ["engineering", "debugging", "version-change"],
                            "task_summary": "Release notes card missed an obvious regression clue",
                        },
                        "rationale": "next=update-card",
                        "context": {"suggested_action": "update-card", "hit_quality": "miss"},
                    }
                ],
            )

            first = consolidate_history(repo_root=repo_root, run_id="confidence-run-1")
            review_action = next(action for action in first["actions"] if action["action_type"] == "review-confidence")
            review_event = build_maintenance_decision(
                decision_type="confidence-reviewed",
                action_key=review_action["action_key"],
                resolved_event_ids=review_action["event_ids"],
                reason="Reviewed weakening evidence and decided to keep watching for now.",
                entry_id="model-release-notes-first",
                decision_summary="watch-and-review",
                review_state="watch-and-review",
                previous_confidence=0.88,
                new_confidence=0.72,
            )
            record_maintenance_decision(repo_root, review_event)

            recorded_events = [
                json.loads(line)
                for line in history_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(recorded_events[-1]["event_type"], "confidence-reviewed")
            self.assertEqual(recorded_events[-1]["context"]["previous_confidence"], 0.88)
            self.assertEqual(recorded_events[-1]["context"]["new_confidence"], 0.72)

            second = consolidate_history(repo_root=repo_root, run_id="confidence-run-2")
            self.assertEqual(second["suppressed_action_count"], 1)
            self.assertNotIn("review-confidence", [action["action_type"] for action in second["actions"]])

            append_events(
                history_path,
                [
                    {
                        "event_id": "conf-2",
                        "event_type": "observation",
                        "created_at": "2026-04-20T10:20:00+00:00",
                        "source": {"kind": "task", "agent": "worker-3"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-release-notes-first"],
                            "route_hint": ["engineering", "debugging", "version-change"],
                            "task_summary": "The same card still missed a later version-change clue",
                        },
                        "rationale": "next=update-card",
                        "context": {"suggested_action": "update-card", "hit_quality": "miss"},
                    }
                ],
            )

            third = consolidate_history(repo_root=repo_root, run_id="confidence-run-3")
            resurfaced = next(action for action in third["actions"] if action["action_type"] == "review-confidence")
            self.assertEqual(resurfaced["event_count"], 2)
            self.assertEqual(third["suppressed_action_count"], 0)

    def test_split_review_decision_suppresses_resolved_entry_update_but_resurfaces_with_new_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            append_events(
                history_path,
                [
                    {
                        "event_id": "split-1",
                        "event_type": "observation",
                        "created_at": "2026-04-20T11:00:00+00:00",
                        "source": {"kind": "task", "agent": "worker-6"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-004"],
                            "route_hint": ["system", "knowledge-library", "retrieval"],
                            "task_summary": "Retriever card is now being reached from a repo workflow",
                        },
                        "rationale": "next=update-card",
                        "context": {
                            "suggested_action": "update-card",
                            "hit_quality": "hit",
                            "predictive_observation": {
                                "scenario": "A repository workflow still lands on the retrieval hub card.",
                                "action_taken": "Reuse the existing card first.",
                                "observed_result": "The card may now carry route-specific subcases.",
                                "operational_use": "Review whether the card should split by route.",
                            },
                        },
                    },
                    {
                        "event_id": "split-2",
                        "event_type": "observation",
                        "created_at": "2026-04-20T11:05:00+00:00",
                        "source": {"kind": "task", "agent": "worker-7"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-004"],
                            "route_hint": ["repository", "usage", "local-kb-retrieve"],
                            "task_summary": "Retriever card now also serves repository preflight work",
                        },
                        "rationale": "next=update-card",
                        "context": {
                            "suggested_action": "update-card",
                            "hit_quality": "hit",
                            "predictive_observation": {
                                "scenario": "Repository workflow reaches the same card from a different route.",
                                "action_taken": "Use the hub card as a first step.",
                                "observed_result": "The card now looks broad enough for split review.",
                                "operational_use": "Review hub-vs-overloaded and split if it now holds multiple relations.",
                            },
                        },
                    },
                ],
            )

            first = consolidate_history(repo_root=repo_root, run_id="split-run-1")
            entry_update_action = next(action for action in first["actions"] if action["action_type"] == "review-entry-update")
            self.assertEqual(
                entry_update_action["split_review_suggestion"]["recommendation"],
                "consider-split-review",
            )
            split_event = build_maintenance_decision(
                decision_type="split-reviewed",
                action_key=entry_update_action["action_key"],
                resolved_event_ids=entry_update_action["event_ids"],
                reason="Reviewed the repeated hit pattern and decided to keep a lighter hub plus future sibling split option.",
                entry_id="model-004",
                decision_summary="split-review-completed",
            )
            record_maintenance_decision(repo_root, split_event)

            second = consolidate_history(repo_root=repo_root, run_id="split-run-2")
            self.assertEqual(second["suppressed_action_count"], 1)
            self.assertNotIn("review-entry-update", [action["action_type"] for action in second["actions"]])

            append_events(
                history_path,
                [
                    {
                        "event_id": "split-3",
                        "event_type": "observation",
                        "created_at": "2026-04-20T11:10:00+00:00",
                        "source": {"kind": "task", "agent": "worker-8"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-004"],
                            "route_hint": ["planning", "prefetch", "prior-lessons"],
                            "task_summary": "Retriever card now also shows up in planning prefetch work",
                        },
                        "rationale": "next=update-card",
                        "context": {
                            "suggested_action": "update-card",
                            "hit_quality": "hit",
                            "predictive_observation": {
                                "scenario": "Planning prefetch work reaches the same card from another route.",
                                "action_taken": "Use the existing hub card before planning work starts.",
                                "observed_result": "The same card now spans another route-specific subcase.",
                                "operational_use": "Re-open split review when a new route starts relying on the same card.",
                            },
                        },
                    }
                ],
            )

            third = consolidate_history(repo_root=repo_root, run_id="split-run-3")
            resurfaced = next(action for action in third["actions"] if action["action_type"] == "review-entry-update")
            self.assertEqual(resurfaced["event_count"], 3)
            self.assertEqual(
                resurfaced["split_review_suggestion"]["recommendation"],
                "consider-split-review",
            )
            self.assertEqual(third["suppressed_action_count"], 0)

    def test_split_review_decision_requires_resolved_event_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "split-reviewed decisions require non-empty resolved_event_ids"):
            build_maintenance_decision(
                decision_type="split-reviewed",
                action_key="review-entry-update::entry::model-004",
                resolved_event_ids=[],
                reason="Attempted to close split review without binding it to supporting evidence.",
                entry_id="model-004",
                decision_summary="keep-as-hub-for-now",
            )


if __name__ == "__main__":
    unittest.main()
