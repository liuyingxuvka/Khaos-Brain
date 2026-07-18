from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_kb.transactional_install import (
    CONTROL_ROOT_NAME,
    install_managed_runtime,
    latest_install_receipt,
    tree_manifest,
)


def _write_skill(
    root: Path,
    *,
    author_checks: int = 2,
    contaminated_consumer: bool = False,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    text = (
        "# fixture\n\nInvoke SkillGuard before ordinary work.\n"
        if contaminated_consumer
        else "# fixture\n\nOrdinary use is self-contained.\n"
    )
    (root / "SKILL.md").write_text(text, encoding="utf-8")
    control = root / ".skillguard"
    control.mkdir()
    (control / "check-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "fixture.author-contract.v1",
                "checks": [
                    {"check_id": f"author-check-{index}"}
                    for index in range(author_checks)
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return root


def _automation_renderer(payload) -> str:
    return (
        f'id = "{payload["id"]}"\n'
        f'status = "{payload.get("status", "ACTIVE")}"\n'
        "user_paused = false\n"
    )


def _install(
    *,
    repo_root: Path,
    codex_home: Path,
    skill_source: Path,
    fail_after_activation: int | None = None,
):
    return install_managed_runtime(
        repo_root=repo_root,
        codex_home=codex_home,
        global_skill_name="predictive-kb-preflight",
        global_skill_files={"SKILL.md": "# global\n"},
        skill_sources={"kb-sleep-maintenance": skill_source},
        automation_payloads={"kb-sleep": {"id": "kb-sleep", "status": "ACTIVE"}},
        automation_renderer=_automation_renderer,
        retired_skill_ids=("kb-architect-pass",),
        retired_automation_ids=("kb-architect",),
        fail_after_activation=fail_after_activation,
    )


class TransactionalUpgradeMigrationTests(unittest.TestCase):
    def test_active_and_paused_legacy_architect_states_are_both_retired(self) -> None:
        for status in ("ACTIVE", "PAUSED"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo_root = root / "repo"
                codex_home = root / ".codex"
                skill_source = _write_skill(repo_root / "skill-source")
                architect_skill = codex_home / "skills" / "kb-architect-pass"
                architect_skill.mkdir(parents=True)
                (architect_skill / "SKILL.md").write_text(
                    "# former managed Architect\n", encoding="utf-8"
                )
                architect_automation = (
                    codex_home / "automations" / "kb-architect" / "automation.toml"
                )
                architect_automation.parent.mkdir(parents=True)
                architect_automation.write_text(
                    f'id = "kb-architect"\nstatus = "{status}"\n',
                    encoding="utf-8",
                )

                result = _install(
                    repo_root=repo_root,
                    codex_home=codex_home,
                    skill_source=skill_source,
                )

                self.assertTrue(result["ok"])
                self.assertFalse(architect_skill.exists())
                self.assertFalse(architect_automation.parent.exists())

    def test_injected_failure_rolls_back_replacements_and_retirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            source = _write_skill(root / "source-sleep")

            active_global = codex_home / "skills/predictive-kb-preflight"
            active_sleep = codex_home / "skills/kb-sleep-maintenance"
            active_automation = codex_home / "automations/kb-sleep"
            retired_skill = codex_home / "skills/kb-architect-pass"
            retired_automation = codex_home / "automations/kb-architect"
            for path, filename, body in (
                (active_global, "old.txt", "old-global"),
                (active_sleep, "old.txt", "old-sleep"),
                (active_automation, "old.txt", "old-automation"),
                (retired_skill, "old.txt", "old-architect-skill"),
                (retired_automation, "old.txt", "old-architect-automation"),
            ):
                path.mkdir(parents=True)
                (path / filename).write_text(body, encoding="utf-8")
            before = {
                str(path): tree_manifest(path)["digest"]
                for path in (
                    active_global,
                    active_sleep,
                    active_automation,
                    retired_skill,
                    retired_automation,
                )
            }

            with self.assertRaisesRegex(RuntimeError, "Injected installation failure"):
                _install(
                    repo_root=repo_root,
                    codex_home=codex_home,
                    skill_source=source,
                    fail_after_activation=4,
                )

            for path_text, digest in before.items():
                self.assertEqual(tree_manifest(Path(path_text))["digest"], digest)
            journals = list(
                (codex_home / CONTROL_ROOT_NAME / "transactions").glob("*.json")
            )
            self.assertEqual(1, len(journals))
            journal = json.loads(journals[0].read_text(encoding="utf-8"))
            self.assertEqual("rolled_back", journal["status"])
            self.assertEqual({}, latest_install_receipt(codex_home))

    def test_consumer_runtime_contamination_is_rejected_before_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            source = _write_skill(
                root / "source-sleep",
                contaminated_consumer=True,
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "Consumer skill projection leaked author-control tokens",
            ):
                _install(
                    repo_root=repo_root,
                    codex_home=codex_home,
                    skill_source=source,
                )
            self.assertFalse((codex_home / "skills/kb-sleep-maintenance").exists())
            self.assertFalse(latest_install_receipt(codex_home))

    def test_author_contract_changes_do_not_enter_or_stale_consumer_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            baseline = _write_skill(root / "baseline-sleep", author_checks=3)
            _install(
                repo_root=repo_root,
                codex_home=codex_home,
                skill_source=baseline,
            )
            installed = codex_home / "skills/kb-sleep-maintenance"
            first_digest = tree_manifest(installed)["digest"]

            source = _write_skill(root / "source-sleep", author_checks=1)
            result = _install(
                repo_root=repo_root,
                codex_home=codex_home,
                skill_source=source,
            )

            self.assertTrue(result["ok"])
            self.assertEqual(first_digest, tree_manifest(installed)["digest"])
            self.assertFalse((installed / ".skillguard").exists())

    def test_interrupted_journal_is_recovered_before_next_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            source = _write_skill(root / "source-sleep")
            control = codex_home / CONTROL_ROOT_NAME
            active = codex_home / "skills/recover-me"
            backup = control / "backups/interrupted/skill/recover-me"
            active.mkdir(parents=True)
            backup.mkdir(parents=True)
            (active / "value.txt").write_text("partial-new", encoding="utf-8")
            (backup / "value.txt").write_text("old-good", encoding="utf-8")
            journal_path = control / "transactions/interrupted.json"
            journal_path.parent.mkdir(parents=True)
            journal_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "transaction_id": "interrupted",
                        "status": "activating",
                        "operations": [
                            {
                                "active_path": str(active),
                                "backup_path": str(backup),
                                "had_active": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = _install(
                repo_root=repo_root,
                codex_home=codex_home,
                skill_source=source,
            )

            self.assertEqual(
                "old-good",
                (active / "value.txt").read_text(encoding="utf-8"),
            )
            recovered = json.loads(journal_path.read_text(encoding="utf-8"))
            self.assertEqual("recovered", recovered["status"])
            self.assertEqual(["interrupted"], result["recovered_transactions"])

    def test_repeat_upgrade_converges_and_keeps_similarly_named_user_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            source = _write_skill(root / "source-sleep")
            retired_skill = codex_home / "skills/kb-architect-pass"
            retired_automation = codex_home / "automations/kb-architect"
            user_skill = codex_home / "skills/kb-architect-pass-personal"
            for path in (retired_skill, retired_automation, user_skill):
                path.mkdir(parents=True)
                (path / "keep.txt").write_text("fixture", encoding="utf-8")

            first = _install(
                repo_root=repo_root,
                codex_home=codex_home,
                skill_source=source,
            )
            first_manifest = tree_manifest(
                codex_home / "skills/kb-sleep-maintenance"
            )
            second = _install(
                repo_root=repo_root,
                codex_home=codex_home,
                skill_source=source,
            )

            self.assertNotEqual(first["transaction_id"], second["transaction_id"])
            self.assertEqual(
                first_manifest["digest"],
                tree_manifest(
                    codex_home / "skills/kb-sleep-maintenance"
                )["digest"],
            )
            self.assertFalse(retired_skill.exists())
            self.assertFalse(retired_automation.exists())
            self.assertTrue((user_skill / "keep.txt").exists())
            self.assertEqual(
                second["transaction_id"],
                latest_install_receipt(codex_home)["transaction_id"],
            )


if __name__ == "__main__":
    unittest.main()
