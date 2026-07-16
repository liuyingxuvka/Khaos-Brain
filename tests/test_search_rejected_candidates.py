from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.maintenance import build_maintenance_decision, record_maintenance_decision
from local_kb.search import render_search_payload, search_entries
from local_kb.store import write_yaml_file
from tests.current_runtime_helpers import activate_current_kb_runtime


class RejectedCandidateSearchTests(unittest.TestCase):
    def test_rejected_candidate_is_filtered_out_of_search_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            candidate_path = repo_root / "kb" / "candidates" / "cand-email-default.yaml"
            write_yaml_file(
                candidate_path,
                {
                    "id": "cand-email-default",
                    "title": "English work email default remains useful for recurring drafting",
                    "type": "model",
                    "scope": "private",
                    "domain_path": ["work", "communication", "email"],
                    "cross_index": ["writing/business/email"],
                    "tags": ["email", "work", "language"],
                    "trigger_keywords": ["email", "reply", "draft"],
                    "if": {"notes": "Drafting a work email for the user."},
                    "action": {"description": "Default to English unless the user says otherwise."},
                    "predict": {"expected_result": "The draft matches the user's usual work-email preference."},
                    "use": {"guidance": "Use as a candidate card until validated."},
                    "confidence": 0.55,
                    "status": "candidate",
                    "retrieval_eligible": True,
                },
            )
            activate_current_kb_runtime(repo_root)

            initial_results = render_search_payload(
                search_entries(repo_root, query="default work email drafting"),
                repo_root,
            )
            self.assertEqual([item["id"] for item in initial_results], ["cand-email-default"])

            rejection_event = build_maintenance_decision(
                decision_type="candidate-rejected",
                action_key="review-candidate::entry::cand-email-default",
                resolved_event_ids=["candidate-created-1"],
                reason="Rejected during maintenance because it was too generic.",
                entry_id="cand-email-default",
                decision_summary="reject-candidate",
            )
            record_maintenance_decision(repo_root, rejection_event)
            activate_current_kb_runtime(repo_root)

            final_results = render_search_payload(
                search_entries(repo_root, query="default work email drafting"),
                repo_root,
            )
            self.assertEqual(final_results, [])


if __name__ == "__main__":
    unittest.main()
