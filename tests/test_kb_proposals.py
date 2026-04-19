from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from local_kb.proposals import build_proposal_report, load_proposal_stubs


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "local-kb-retrieve"
    / "scripts"
    / "kb_proposals.py"
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class KbProposalInspectionTests(unittest.TestCase):
    def test_loads_and_summarizes_action_stubs_from_temp_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            run_id = "daily-maintenance"
            actions_dir = repo_root / "kb" / "history" / "consolidation" / run_id / "actions"

            write_json(
                actions_dir / "candidate-1.json",
                {
                    "schema_version": 1,
                    "kind": "local-kb-proposal-stub",
                    "run_id": run_id,
                    "generated_at": "2026-04-19T20:00:00+00:00",
                    "action_key": "candidate-route-work-reporting-ppt",
                    "action_type": "consider-new-candidate",
                    "target": {"kind": "route", "ref": "work/reporting/ppt"},
                    "priority_score": 3.5,
                    "event_count": 2,
                    "event_ids": ["obs-1", "obs-2"],
                    "routes": ["work/reporting/ppt"],
                    "task_summaries": ["Management deck feedback kept missing a route card"],
                    "signals": {"miss_count": 2},
                    "suggested_artifact_kind": "candidate-card",
                    "apply_eligibility": {"eligible": True, "reason": "repeated route group"},
                    "recommended_next_step": "Draft a candidate card for this route.",
                    "ai_decision_required": False,
                },
            )
            write_json(
                actions_dir / "taxonomy-1.json",
                {
                    "schema_version": 1,
                    "kind": "local-kb-proposal-stub",
                    "run_id": run_id,
                    "generated_at": "2026-04-19T20:00:01+00:00",
                    "action_key": "taxonomy-design-presentation",
                    "action_type": "review-taxonomy",
                    "target": {"kind": "route", "ref": "design/presentation"},
                    "priority_score": 4.0,
                    "event_count": 3,
                    "event_ids": ["obs-3", "obs-4", "obs-5"],
                    "routes": ["design/presentation/message-ordering"],
                    "task_summaries": ["Observed undeclared design presentation route"],
                    "signals": {"gap_count": 3},
                    "suggested_artifact_kind": "taxonomy-branch",
                    "apply_eligibility": {"eligible": False, "reason": "proposal only"},
                    "recommended_next_step": "Review whether a new taxonomy branch should be declared.",
                    "ai_decision_required": True,
                },
            )
            write_json(
                actions_dir / "entry-update-1.json",
                {
                    "schema_version": 1,
                    "kind": "local-kb-proposal-stub",
                    "run_id": run_id,
                    "generated_at": "2026-04-19T20:00:02+00:00",
                    "action_key": "update-example-entry-001",
                    "action_type": "review-entry-update",
                    "target": {"kind": "entry", "entry_id": "example-entry-001"},
                    "priority_score": 2.0,
                    "event_count": 1,
                    "event_ids": ["obs-6"],
                    "routes": ["system/knowledge-library/retrieval"],
                    "task_summaries": ["Retriever preflight card needs narrower wording"],
                    "suggested_artifact_kind": "entry-update",
                    "apply_eligibility": {"eligible": False, "reason": "AI should inspect"},
                    "recommended_next_step": "Inspect the current model card and tighten its scope.",
                    "ai_decision_required": True,
                },
            )

            stubs = load_proposal_stubs(repo_root, run_id=run_id)
            report = build_proposal_report(repo_root, run_id=run_id)

            self.assertEqual(len(stubs), 3)
            self.assertEqual(report["stub_count"], 3)
            self.assertEqual(report["valid_stub_count"], 2)
            self.assertEqual(report["invalid_stub_count"], 1)
            self.assertEqual(report["ai_decision_required_count"], 2)
            candidate_action_summary = next(
                item for item in report["action_type_summary"] if item["action_type"] == "consider-new-candidate"
            )
            candidate_artifact_summary = next(
                item
                for item in report["suggested_artifact_kind_summary"]
                if item["suggested_artifact_kind"] == "candidate-card"
            )
            self.assertEqual(candidate_action_summary["stub_count"], 1)
            self.assertEqual(candidate_artifact_summary["stub_count"], 1)

            invalid_stub = next(item for item in stubs if item["action_key"] == "update-example-entry-001")
            self.assertEqual(invalid_stub["missing_fields"], ["signals"])
            self.assertFalse(invalid_stub["valid"])

    def test_cli_json_supports_run_id_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            run_id = "nightly-pass"
            actions_dir = repo_root / "kb" / "history" / "consolidation" / run_id / "actions"
            write_json(
                actions_dir / "candidate.json",
                {
                    "schema_version": 1,
                    "kind": "local-kb-proposal-stub",
                    "run_id": run_id,
                    "generated_at": "2026-04-19T21:00:00+00:00",
                    "action_key": "candidate-work-email",
                    "action_type": "consider-new-candidate",
                    "target": {"kind": "route", "ref": "work/communication/email"},
                    "priority_score": 3,
                    "event_count": 2,
                    "event_ids": ["obs-1", "obs-2"],
                    "routes": ["work/communication/email"],
                    "task_summaries": ["Email card gap"],
                    "signals": {"miss_count": 2},
                    "suggested_artifact_kind": "candidate-card",
                    "apply_eligibility": {"eligible": True, "reason": "repeated"},
                    "recommended_next_step": "Create a candidate card.",
                    "ai_decision_required": False,
                },
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--repo-root",
                    str(repo_root),
                    "--run-id",
                    run_id,
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(result.stdout)

            self.assertEqual(payload["kind"], "local-kb-proposal-inspection")
            self.assertEqual(payload["run_id"], run_id)
            self.assertEqual(payload["stub_count"], 1)
            self.assertEqual(payload["action_type_summary"][0]["action_type"], "consider-new-candidate")

    def test_cli_human_output_supports_run_dir_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            run_dir = repo_root / "kb" / "history" / "consolidation" / "manual-check"
            actions_dir = run_dir / "actions"
            write_json(
                actions_dir / "taxonomy.json",
                {
                    "schema_version": 1,
                    "kind": "local-kb-proposal-stub",
                    "run_id": "manual-check",
                    "generated_at": "2026-04-19T21:30:00+00:00",
                    "action_key": "taxonomy-gap-design",
                    "action_type": "review-taxonomy",
                    "target": {"kind": "route", "ref": "design"},
                    "priority_score": 4.5,
                    "event_count": 4,
                    "event_ids": ["obs-1", "obs-2", "obs-3", "obs-4"],
                    "routes": ["design/presentation/message-ordering"],
                    "task_summaries": ["Design route is still undeclared"],
                    "signals": {"gap_count": 4},
                    "suggested_artifact_kind": "taxonomy-branch",
                    "apply_eligibility": {"eligible": False, "reason": "AI maintenance only"},
                    "recommended_next_step": "Review the taxonomy gap during maintenance.",
                    "ai_decision_required": True,
                },
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--repo-root",
                    str(repo_root),
                    "--run-dir",
                    str(run_dir),
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertIn("Run manual-check has 1 proposal stubs", result.stdout)
            self.assertIn("By action type:", result.stdout)
            self.assertIn("review-taxonomy", result.stdout)
            self.assertIn("taxonomy-gap-design", result.stdout)


if __name__ == "__main__":
    unittest.main()
