from __future__ import annotations

import json
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from local_kb.candidate_lifecycle import create_or_reuse_candidate
from local_kb.feedback import build_observation
from local_kb.lifecycle import admit_observation, classify_observation, dispose_observation, load_lifecycle_state
from local_kb.logicguard_models import (
    build_authority_generation_payload,
    load_authority_generation,
    publish_authority_generation,
)
from local_kb.maintenance_migration import (
    MIGRATION_LOCK_LEGACY_STALE_SECONDS,
    MIGRATION_LOCK_SCHEMA_VERSION,
    _fs_exists,
    _fs_path,
    _unlink_verified_managed_file,
    check_migration,
    cold_manifest_path,
    journal_path,
    migrate_legacy_card_generation,
    migration_lock,
    migration_root,
    reconciliation_state_path,
    retired_architect_settlement_path,
    run_maintenance_migration,
    settle_retired_architect_queue,
    settle_knowledge_debt,
    validate_migration,
)
from local_kb.store import write_yaml_file


class KbHistoryMigrationTests(unittest.TestCase):
    def test_migration_lock_publishes_owner_and_cleans_only_its_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with migration_lock(root, timeout_seconds=0.2):
                owner_path = migration_root(root) / ".migration.lock" / "owner.json"
                owner = json.loads(owner_path.read_text(encoding="utf-8"))
                self.assertEqual(MIGRATION_LOCK_SCHEMA_VERSION, owner["schema_version"])
                self.assertEqual(os.getpid(), owner["pid"])
                self.assertTrue(owner["owner_token"])
            self.assertFalse((migration_root(root) / ".migration.lock").exists())

    def test_dead_owned_migration_lock_is_recovered_with_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_dir = migration_root(root) / ".migration.lock"
            lock_dir.mkdir(parents=True)
            (lock_dir / "owner.json").write_text(
                json.dumps(
                    {
                        "schema_version": MIGRATION_LOCK_SCHEMA_VERSION,
                        "owner_token": "dead-owner",
                        "pid": 99999999,
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "local_kb.maintenance_migration._migration_lock_owner_is_alive",
                return_value=False,
            ):
                with migration_lock(root, timeout_seconds=0.2):
                    owner = json.loads(
                        (lock_dir / "owner.json").read_text(encoding="utf-8")
                    )
                    self.assertNotEqual("dead-owner", owner["owner_token"])
            recovery = migration_root(root) / "lock-recovery.jsonl"
            self.assertIn(
                "recorded-owner-not-running", recovery.read_text(encoding="utf-8")
            )

    def test_live_owned_migration_lock_is_never_stolen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_dir = migration_root(root) / ".migration.lock"
            lock_dir.mkdir(parents=True)
            owner_path = lock_dir / "owner.json"
            owner_path.write_text(
                json.dumps(
                    {
                        "schema_version": MIGRATION_LOCK_SCHEMA_VERSION,
                        "owner_token": "live-owner",
                        "pid": 42,
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "local_kb.maintenance_migration._migration_lock_owner_is_alive",
                return_value=True,
            ):
                with self.assertRaises(TimeoutError):
                    with migration_lock(root, timeout_seconds=0.1):
                        self.fail("a live migration lock was stolen")
            self.assertEqual(
                "live-owner",
                json.loads(owner_path.read_text(encoding="utf-8"))["owner_token"],
            )

    def test_old_ownerless_migration_lock_recovers_only_without_old_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_dir = migration_root(root) / ".migration.lock"
            lock_dir.mkdir(parents=True)
            old = time.time() - MIGRATION_LOCK_LEGACY_STALE_SECONDS - 5
            os.utime(lock_dir, (old, old))
            with patch(
                "local_kb.maintenance_migration._legacy_migration_process_is_running",
                return_value=False,
            ):
                with migration_lock(root, timeout_seconds=0.2):
                    owner = json.loads(
                        (lock_dir / "owner.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual(MIGRATION_LOCK_SCHEMA_VERSION, owner["schema_version"])
            self.assertIn(
                "legacy-ownerless-lock-without-running-migration",
                (migration_root(root) / "lock-recovery.jsonl").read_text(
                    encoding="utf-8"
                ),
            )

    def test_recent_ownerless_migration_lock_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_dir = migration_root(root) / ".migration.lock"
            lock_dir.mkdir(parents=True)
            with patch(
                "local_kb.maintenance_migration._legacy_migration_process_is_running",
                return_value=False,
            ):
                with self.assertRaises(TimeoutError):
                    with migration_lock(root, timeout_seconds=0.1):
                        self.fail("a recent ownerless lock was stolen")
            self.assertTrue(lock_dir.exists())

    def build_legacy_repo(self, repo_root: Path) -> None:
        (repo_root / "VERSION").write_text("0.5.2\n", encoding="utf-8")
        write_yaml_file(
            repo_root / "kb" / "public" / "trusted.yaml",
            {
                "id": "trusted",
                "title": "Trusted migration rule",
                "status": "trusted",
                "domain_path": ["engineering", "migration"],
                "if": {"notes": "A migration resumes."},
                "action": {"description": "Verify the checkpoint."},
                "predict": {"expected_result": "The resume is idempotent."},
                "use": {"guidance": "Use current receipts."},
            },
        )
        write_yaml_file(
            repo_root / "kb" / "candidates" / "legacy.yaml",
            {
                "id": "legacy-candidate",
                "title": "Legacy scaffold",
                "status": "candidate",
                "domain_path": ["engineering", "migration"],
                "if": {"notes": "A migration resumes."},
                "action": {"description": "Guess from an old report."},
                "predict": {"expected_result": "It may work."},
                "use": {"guidance": "Needs independent evidence."},
            },
        )
        history = repo_root / "kb" / "history" / "events.jsonl"
        history.parent.mkdir(parents=True, exist_ok=True)
        history.write_text(
            json.dumps(
                {
                    "event_id": "obs-legacy",
                    "event_type": "observation",
                    "created_at": "2026-01-01T00:00:00Z",
                    "source": {"kind": "task"},
                    "target": {"kind": "task-observation", "task_summary": "One-off legacy note"},
                    "rationale": "legacy",
                    "context": {"suggested_action": "none"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        report = repo_root / "kb" / "history" / "architecture" / "run-1" / "report.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text('{"status":"completed"}\n', encoding="utf-8")
        (report.parents[1] / "proposal_queue.json").write_text(
            json.dumps(
                {
                    "proposals": [
                        {"id": "already-applied", "status": "applied", "summary": "old fix"},
                        {"id": "install-follow-up", "status": "ready-for-patch", "summary": "installer rollback"},
                        {"id": "card-follow-up", "status": "watching", "summary": "candidate card retrieval"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        proposal = repo_root / "kb" / "history" / "consolidation" / "run-1" / "proposal.json"
        proposal.parent.mkdir(parents=True, exist_ok=True)
        proposal.write_text('{"derived":true}\n', encoding="utf-8")
        unique = repo_root / ".local" / "maintenance-lab" / "workspaces" / "old" / "unique.txt"
        unique.parent.mkdir(parents=True, exist_ok=True)
        unique.write_text("unique old workspace evidence\n", encoding="utf-8")

    def test_migration_resumes_cold_archives_prunes_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            self.build_legacy_repo(repo_root)

            interrupted = run_maintenance_migration(repo_root, fail_after_phase="classify")
            self.assertFalse(interrupted["ok"])
            self.assertEqual(interrupted["status"], "paused_failed")

            completed = run_maintenance_migration(repo_root)
            self.assertTrue(completed["ok"], completed)
            self.assertEqual(completed["status"], "committed")
            self.assertNotIn("failure", completed["journal"])
            self.assertEqual(len(completed["journal"]["failure_history"]), 1)
            self.assertFalse((repo_root / "kb" / "history" / "architecture").exists())
            self.assertFalse((repo_root / "kb" / "history" / "consolidation").exists())
            self.assertFalse((repo_root / ".local" / "maintenance-lab").exists())
            self.assertTrue(cold_manifest_path(repo_root).exists())
            self.assertTrue(check_migration(repo_root)["ok"])
            settlements = [
                json.loads(line)
                for line in retired_architect_settlement_path(repo_root).read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            self.assertEqual(len(settlements), 3)
            self.assertEqual(settlements[0]["disposition"], "history_only")
            parked = [item for item in settlements if item["disposition"] == "parked"]
            self.assertEqual(len(parked), 2)
            self.assertTrue(all(item["reopen_condition"]["requires_new_fingerprint"] for item in parked))
            self.assertEqual(
                {item["owner"] for item in parked},
                {"khaos-brain-system-update", "kb-sleep"},
            )
            retired_queue = completed["receipt"]["checkpoints"]["settle-logical-debt"]["details"][
                "retired_architect_queue"
            ]
            self.assertEqual(retired_queue["active_debt_count"], 0)
            self.assertEqual(retired_queue["hard_debt_count"], 0)
            self.assertEqual(retired_queue["parked_follow_up_count"], 2)

            committed_journal = json.loads(journal_path(repo_root).read_text(encoding="utf-8"))
            committed_journal["failure"] = {
                "type": "PermissionError",
                "message": "stale resolved failure",
                "resume_from": "prune-derived-data",
                "failed_at": "2026-07-12T00:00:00+00:00",
            }
            journal_path(repo_root).write_text(
                json.dumps(committed_journal, indent=2) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(check_migration(repo_root)["ok"])

            repeated = run_maintenance_migration(repo_root)
            self.assertTrue(repeated["ok"])
            self.assertEqual(repeated["status"], "no_delta")
            self.assertTrue(repeated["idempotent_no_delta"])
            self.assertNotIn("failure", repeated["journal"])
            self.assertEqual(len(repeated["journal"]["failure_history"]), 2)

    def test_post_commit_reintroduced_managed_debt_is_reconciled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            self.build_legacy_repo(repo_root)
            completed = run_maintenance_migration(repo_root)
            self.assertTrue(completed["ok"], completed)

            reintroduced = (
                repo_root
                / ".local"
                / "maintenance-lab"
                / "reintroduced-after-validation"
                / "result.json"
            )
            reintroduced.parent.mkdir(parents=True, exist_ok=True)
            reintroduced.write_text('{"old":"derived"}\n', encoding="utf-8")

            stale_check = check_migration(repo_root)
            self.assertFalse(stale_check["ok"])
            self.assertEqual(
                stale_check["validation"]["residual_managed_file_count"],
                1,
            )

            repaired = run_maintenance_migration(repo_root)

            self.assertTrue(repaired["ok"], repaired)
            self.assertEqual(repaired["status"], "reconciled")
            self.assertFalse(repaired["idempotent_no_delta"])
            self.assertFalse(reintroduced.exists())
            self.assertTrue(check_migration(repo_root)["ok"])
            state = json.loads(
                reconciliation_state_path(repo_root).read_text(encoding="utf-8")
            )
            self.assertEqual(state["status"], "committed")
            self.assertEqual(len(state["receipt_history"]), 1)

    def test_post_commit_authority_only_drift_is_reconciled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            self.build_legacy_repo(repo_root)
            completed = run_maintenance_migration(repo_root)
            self.assertTrue(completed["ok"], completed)

            current = load_authority_generation(repo_root)
            interrupted_generation = build_authority_generation_payload(
                generation_id="generation-interrupted-after-pointer-publication",
                scope_meshes=current["scope_meshes"],
                projection_manifest_digest=current["projection_manifest_digest"],
                projection_count=current["projection_count"],
                actor="test-interrupted-upgrade",
            )
            publish_authority_generation(
                repo_root,
                interrupted_generation,
                writer="local_kb.maintenance_migration",
            )

            stale_check = check_migration(repo_root)
            self.assertFalse(stale_check["ok"])
            self.assertEqual(stale_check["validation"]["residual_managed_file_count"], 0)
            self.assertEqual(stale_check["validation"]["hard_debt_count"], 0)
            self.assertFalse(stale_check["validation"]["logicguard_authority"]["ok"])

            repaired = run_maintenance_migration(repo_root)

            self.assertTrue(repaired["ok"], repaired)
            self.assertEqual(repaired["status"], "reconciled")
            self.assertFalse(repaired["idempotent_no_delta"])
            self.assertTrue(
                repaired["post_commit_convergence_runs"][0][
                    "authority_repair_required"
                ]
            )
            self.assertTrue(check_migration(repo_root)["ok"])

    def test_post_commit_observation_debt_is_settled_with_its_own_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            self.build_legacy_repo(repo_root)
            completed = run_maintenance_migration(repo_root)
            self.assertTrue(completed["ok"], completed)

            observation = build_observation(
                task_summary="Observation arrived while the upgrade was validating",
                route_hint="system/knowledge-library/installation/assurance",
                scenario="Another AI searches the KB during a long upgrade.",
                action_taken="Preserve and settle the new observation after commit.",
                observed_result="The observation remains visible until disposition.",
                suggested_action="new-candidate",
                outcome="success",
            )
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            with history_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(observation, ensure_ascii=False) + "\n")
            admit_observation(repo_root, observation)
            stale_check = check_migration(repo_root)
            self.assertEqual(stale_check["validation"]["hard_debt_count"], 1)

            repaired = run_maintenance_migration(repo_root)

            self.assertTrue(repaired["ok"], repaired)
            self.assertEqual(repaired["status"], "reconciled")
            self.assertEqual(repaired["validation"]["hard_debt_count"], 0)
            logical = repaired["logical_debt_reconciliation"]
            self.assertEqual(logical["status"], "reconciled")
            self.assertEqual(logical["pass_count"], 1)
            receipt_path = repo_root / logical["receipts"][0]["receipt"]
            self.assertTrue(receipt_path.is_file())

    def test_retired_architect_settlement_carries_forward_across_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            prior = (
                repo_root
                / "kb"
                / "history"
                / "migrations"
                / "kb-maintenance-standard-v1"
                / "retired-architect-proposal-settlement.jsonl"
            )
            prior.parent.mkdir(parents=True, exist_ok=True)
            row = {
                "schema_version": 1,
                "proposal_id": "legacy-proposal",
                "prior_status": "watching",
                "disposition": "parked",
                "owner": "kb-sleep",
                "reason": "retired lane",
                "reopen_condition": {"requires_new_fingerprint": True},
                "evidence_fingerprint": "abc",
                "source_queue": "kb/history/architecture/proposal_queue.json",
            }
            prior.write_text(json.dumps(row) + "\n", encoding="utf-8")

            carried = settle_retired_architect_queue(repo_root)

            self.assertTrue(carried["settlement_reused"])
            self.assertEqual(carried["proposal_count"], 1)
            self.assertIn("kb-maintenance-standard-v1", carried["source_settlement"])
            rows = [
                json.loads(line)
                for line in retired_architect_settlement_path(repo_root)
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            self.assertEqual(rows, [row])

    @unittest.skipUnless(os.name == "nt", "Windows extended-length path behavior")
    def test_windows_long_managed_paths_are_inventoried_and_pruned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            self.build_legacy_repo(repo_root)
            long_path = (
                repo_root
                / ".local"
                / "maintenance-lab"
                / ("deep-a-" + "a" * 70)
                / ("deep-b-" + "b" * 70)
                / ("deep-c-" + "c" * 70)
                / "derived-result.json"
            )
            self.assertGreater(len(str(long_path)), 260)
            _fs_path(long_path).parent.mkdir(parents=True, exist_ok=True)
            _fs_path(long_path).write_text('{"derived":true}\n', encoding="utf-8")
            _fs_path(long_path).chmod(stat.S_IREAD)
            self.assertTrue(_fs_exists(long_path))

            completed = run_maintenance_migration(repo_root)

            self.assertTrue(completed["ok"], completed)
            self.assertFalse(_fs_exists(long_path))
            prune = completed["receipt"]["checkpoints"]["prune-derived-data"]["details"]
            self.assertGreaterEqual(prune["read_only_cleared_file_count"], 1)
            self.assertTrue(check_migration(repo_root)["ok"])

    def test_large_settlement_batches_replay_and_closes_every_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / "VERSION").write_text("0.5.2\n", encoding="utf-8")
            history = repo_root / "kb" / "history" / "events.jsonl"
            history.parent.mkdir(parents=True, exist_ok=True)
            observations = [
                build_observation(
                    task_summary=f"Scale migration episode {index}",
                    route_hint=f"system/scale/{index}",
                    scenario=f"Historical scenario {index}",
                    action_taken="Apply the bounded batch action.",
                    observed_result=f"Historical result {index}",
                    suggested_action="new-candidate",
                    outcome="success",
                )
                for index in range(200)
            ]
            history.write_text(
                "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in observations),
                encoding="utf-8",
            )

            result = settle_knowledge_debt(repo_root, run_id="scale-migration")

            self.assertEqual(result["observation_count"], 200)
            self.assertEqual(result["disposition_count"], 200)
            self.assertEqual(result["hard_observation_debt_count"], 0)
            self.assertEqual(result["candidate_created_count"], 200)
            self.assertEqual(result["lifecycle_batch"]["settlement_mode"], "atomic-batch")
            self.assertEqual(result["lifecycle_batch"]["replay_pass_count"], 2)
            self.assertEqual(result["lifecycle_batch"]["atomic_batch_count"], 1)
            self.assertTrue(result["lifecycle_validation"]["ok"])

    def test_batch_settlement_resumes_partial_per_item_attempt_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / "VERSION").write_text("0.5.2\n", encoding="utf-8")
            write_yaml_file(
                repo_root / "kb" / "public" / "seed.yaml",
                {
                    "id": "seed",
                    "title": "Current model authority seed",
                    "status": "trusted",
                    "if": {"notes": "A partial settlement is rehearsed."},
                    "action": {"description": "Use exact lifecycle identities."},
                    "predict": {"expected_result": "The settlement resumes idempotently."},
                    "use": {"guidance": "Keep the current model generation explicit."},
                },
            )
            authority = migrate_legacy_card_generation(repo_root)
            self.assertTrue(authority["ok"], authority)
            history = repo_root / "kb" / "history" / "events.jsonl"
            history.parent.mkdir(parents=True, exist_ok=True)
            observations = [
                build_observation(
                    task_summary=f"Partial settlement episode {index}",
                    route_hint=f"system/partial/{index}",
                    scenario=f"Partial scenario {index}",
                    action_taken="Resume from stable lifecycle identities.",
                    observed_result=f"Partial result {index}",
                    suggested_action="new-candidate",
                    outcome="success",
                )
                for index in range(60)
            ]
            history.write_text(
                "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in observations),
                encoding="utf-8",
            )
            for observation in observations[:10]:
                admit_observation(repo_root, observation)
                decision = classify_observation(observation)
                candidate = create_or_reuse_candidate(
                    repo_root,
                    observation,
                    run_id="legacy-per-item",
                    evidence_grade=str(decision.get("evidence_grade") or "weak"),
                )
                decision.update(
                    {
                        "target_id": candidate["entry_id"],
                        "follow_up_id": candidate["entry_id"],
                        "follow_up_deadline": candidate["decision_deadline"],
                    }
                )
                dispose_observation(
                    repo_root,
                    observation,
                    run_id="legacy-per-item",
                    decision=decision,
                )

            result = settle_knowledge_debt(repo_root, run_id="batch-resume")
            lifecycle = load_lifecycle_state(repo_root)
            idempotency_keys = list(lifecycle["idempotency_keys"])

            self.assertEqual(result["reused_observation_count"], 10)
            self.assertEqual(result["hard_observation_debt_count"], 0)
            self.assertEqual(result["lifecycle_batch"]["replay_pass_count"], 2)
            self.assertEqual(len(lifecycle["observations"]), 60)
            self.assertEqual(len(idempotency_keys), len(set(idempotency_keys)))
            self.assertEqual(
                len(list((repo_root / "kb" / "candidates").glob("cand-auto-*.yaml"))),
                60,
            )

    @unittest.skipUnless(os.name == "nt", "Windows read-only attribute behavior")
    def test_verified_read_only_managed_file_is_cleared_and_receipted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            self.build_legacy_repo(repo_root)
            read_only = (
                repo_root
                / "kb"
                / "history"
                / "consolidation"
                / "run-1"
                / "read-only.bin"
            )
            read_only.write_bytes(b"verified managed read-only artifact")
            read_only.chmod(stat.S_IREAD)

            completed = run_maintenance_migration(repo_root)

            self.assertTrue(completed["ok"], completed)
            self.assertFalse(read_only.exists())
            prune = completed["receipt"]["checkpoints"]["prune-derived-data"]["details"]
            self.assertGreaterEqual(prune["read_only_cleared_file_count"], 1)

    def test_prune_resume_merges_partial_manifest_and_preserves_accounting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            self.build_legacy_repo(repo_root)
            workspace = repo_root / ".local" / "maintenance-lab" / "workspaces" / "old"
            first_path = workspace / "a-first.txt"
            blocked_path = workspace / "b-blocked.txt"
            first_path.write_text("first deleted payload\n", encoding="utf-8")
            blocked_path.write_text("blocked payload\n", encoding="utf-8")
            if os.name == "nt":
                first_path.chmod(stat.S_IREAD)

            def fail_one_verified_delete(target: Path, *, original_mode: int) -> bool:
                if target.resolve() == blocked_path.resolve():
                    raise PermissionError("injected ACL denial")
                return _unlink_verified_managed_file(target, original_mode=original_mode)

            with patch(
                "local_kb.maintenance_migration._unlink_verified_managed_file",
                side_effect=fail_one_verified_delete,
            ):
                interrupted = run_maintenance_migration(repo_root)

            self.assertFalse(interrupted["ok"])
            self.assertEqual(interrupted["journal"]["failure"]["resume_from"], "prune-derived-data")
            self.assertFalse(first_path.exists())
            self.assertTrue(blocked_path.exists())

            completed = run_maintenance_migration(repo_root)

            self.assertTrue(completed["ok"], completed)
            prune = completed["receipt"]["checkpoints"]["prune-derived-data"]["details"]
            self.assertGreaterEqual(prune["resumed_deleted_file_count"], 1)
            self.assertGreaterEqual(prune["resumed_deleted_byte_count"], len("first deleted payload\n"))
            if os.name == "nt":
                self.assertGreaterEqual(prune["read_only_cleared_file_count"], 1)
            self.assertEqual(
                prune["deleted_file_count"],
                completed["receipt"]["before_file_count"],
            )

    def test_precommit_convergence_settles_observation_arriving_during_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            self.build_legacy_repo(repo_root)
            late = build_observation(
                task_summary="Observation arriving during migration validation",
                route_hint="system/migration/concurrent-observation",
                scenario="A shared writer admits feedback while migration validates.",
                action_taken="Run the bounded precommit settlement owner.",
                observed_result="The new observation receives a model-native disposition.",
                suggested_action="new-candidate",
                outcome="success",
            )
            injected = False

            def validate_with_late_observation(root: Path) -> dict[str, object]:
                nonlocal injected
                if not injected:
                    injected = True
                    history = root / "kb" / "history" / "events.jsonl"
                    with history.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(late, ensure_ascii=False) + "\n")
                    admit_observation(root, late)
                return validate_migration(root)

            with patch(
                "local_kb.maintenance_migration.validate_migration",
                side_effect=validate_with_late_observation,
            ):
                completed = run_maintenance_migration(repo_root)

            self.assertTrue(completed["ok"], completed)
            convergence = completed["receipt"]["checkpoints"]["validate"]["details"][
                "precommit_convergence"
            ]
            self.assertGreaterEqual(convergence["pass_count"], 2)
            self.assertTrue(any(item["hard_observation_debt_before"] for item in convergence["passes"]))
            lifecycle = load_lifecycle_state(repo_root)
            self.assertNotIn(
                lifecycle["observations"][late["event_id"]]["state"],
                {"new", "missing-admission"},
            )


if __name__ == "__main__":
    unittest.main()
