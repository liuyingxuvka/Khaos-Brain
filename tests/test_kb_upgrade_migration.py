from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from local_kb.transactional_install import (
    CONTROL_ROOT_NAME,
    install_managed_runtime,
    latest_install_receipt,
    tree_manifest,
)


def _canonical_hash(payload: object) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _write_skill(root: Path, *, checks: int = 2, v2: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text("# fixture\n", encoding="utf-8")
    control = root / ".skillguard"
    control.mkdir()
    if v2:
        skill_id = "kb-sleep-maintenance"
        obligation_id = f"obligation:{skill_id}:run"
        check_ids = [f"check:{skill_id}:{index}" for index in range(checks)]
        contract_hash = hashlib.sha256(
            f"{skill_id}:{checks}".encode("utf-8")
        ).hexdigest().upper()
        depth_profile = {
            "schema_version": "skillguard.depth_profile.v2",
            "profile_id": "profile:fixture-declared-check-supervision",
            "target_skill_id": skill_id,
            "integration_mode": "native-integrated",
            "native_owner_id": skill_id,
            "native_route_ids": [f"route:{skill_id}:run"],
            "native_check_ids": check_ids,
            "skillguard_adds_domain_route": False,
            "enforcement_level": "enforced",
            "required_closure_profiles": ["enforced"],
            "provider_runtime": {
                "provider_id": "skillguard-local-provider",
                "required_runtime_contract_id": (
                    "skillguard-declared-check-supervision-current"
                ),
                "required_capability_ids": [
                    "declared-check-inventory.v1",
                    "declared-check-receipt-reconciliation.v1",
                    "installation-receipt-binding.v1",
                    "installation-currentness-replay.v1",
                    "provider-runtime-enrollment.v1",
                    "single-flight-check-execution.v1",
                ],
                "required_enrollment_status": "enrolled",
                "readiness_check_ids": check_ids,
            },
            "claim_boundary": (
                "Exact current receipts for fixture-declared checks only."
            ),
        }
        source = {
            "schema_version": "skillguard.contract_source.v2",
            "skill_id": skill_id,
            "depth_profile": depth_profile,
        }
        manifest = {
            "schema_version": "skillguard.check_manifest.v2",
            "skill_id": skill_id,
            "contract_hash": contract_hash,
            "checks": [
                {
                    "check_id": check_id,
                    "kind": "command",
                    "evidence_class": "hard",
                    "covers_obligation_ids": [obligation_id],
                    "command": "python",
                    "args": ["scripts/check.py", str(index)],
                    "cwd_token": "repository_root",
                    "expected": {"exit_code": 0},
                    "timeout_seconds": 120,
                }
                for index, check_id in enumerate(check_ids)
            ],
        }
        compiled_checks = [dict(row) for row in manifest["checks"]]
        compiled = {
            "schema_version": "skillguard.compiled_contract.v2",
            "skill_id": skill_id,
            "contract_hash": contract_hash,
            "obligations": [
                {
                    "obligation_id": obligation_id,
                    "invariant_id": f"invariant:{skill_id}:run",
                    "required": True,
                    "owner_step_ids": [f"step:{skill_id}:run"],
                    "required_check_ids": check_ids,
                    "evidence_classes": ["hard"],
                }
            ],
            "closure_profiles": [
                {
                    "profile_id": "enforced",
                    "required_obligation_ids": [obligation_id],
                }
            ],
            "checks": compiled_checks,
            "depth_profile": depth_profile,
        }
        for filename, payload in (
            ("contract-source.json", source),
            ("check-manifest.json", manifest),
            ("compiled-contract.json", compiled),
        ):
            (control / filename).write_text(
                json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
            )
    return root


def _validation_receipt(skill_root: Path) -> dict[str, object]:
    control = skill_root / ".skillguard"
    compiled = json.loads((control / "compiled-contract.json").read_text(encoding="utf-8"))
    receipt: dict[str, object] = {
        "schema_version": "chaos_brain.skillguard_source_validation.v1",
        "skill_id": "kb-sleep-maintenance",
        "status": "current",
        "ok": True,
        "source_tree_digest": tree_manifest(skill_root)["digest"],
        "contract_hash": compiled["contract_hash"],
        "manifest_hash": hashlib.sha256(
            (control / "check-manifest.json").read_bytes()
        ).hexdigest(),
        "contract_source_sha256": hashlib.sha256(
            (control / "contract-source.json").read_bytes()
        ).hexdigest(),
        "compiled_contract_sha256": hashlib.sha256(
            (control / "compiled-contract.json").read_bytes()
        ).hexdigest(),
        "check_manifest_sha256": hashlib.sha256(
            (control / "check-manifest.json").read_bytes()
        ).hexdigest(),
        "compiler_sha256": "1" * 64,
        "generator_sha256": "2" * 64,
        "generator_check_hash": "3" * 64,
    }
    receipt["validation_input_hash"] = _canonical_hash(receipt)
    receipt["receipt_hash"] = _canonical_hash(receipt)
    return receipt


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
    validation_receipt: dict[str, object] | None = None,
):
    return install_managed_runtime(
        repo_root=repo_root,
        codex_home=codex_home,
        global_skill_name="predictive-kb-preflight",
        global_skill_files={"SKILL.md": "# global\n"},
        skill_sources={"kb-sleep-maintenance": skill_source},
        skillguard_validation_receipts={
            "kb-sleep-maintenance": (
                validation_receipt
                if validation_receipt is not None
                else _validation_receipt(skill_source)
            )
        },
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
                    f'id = "kb-architect"\nstatus = "{status}"\n', encoding="utf-8"
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

            # Three replacement activations plus the first retirement have
            # occurred when the injected failure fires.
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

    def test_incomplete_current_authority_is_rejected_before_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            source = _write_skill(root / "source-sleep", v2=False)
            with self.assertRaisesRegex(RuntimeError, "lacks current validated SkillGuard"):
                _install(
                    repo_root=repo_root,
                    codex_home=codex_home,
                    skill_source=source,
                    validation_receipt={},
                )
            self.assertFalse((codex_home / "skills/kb-sleep-maintenance").exists())
            self.assertFalse(latest_install_receipt(codex_home))

    def test_skillguard_check_count_downgrade_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            baseline = _write_skill(root / "baseline-sleep", checks=3)
            _install(
                repo_root=repo_root,
                codex_home=codex_home,
                skill_source=baseline,
            )
            source = _write_skill(root / "source-sleep", checks=1)
            with self.assertRaisesRegex(RuntimeError, "SkillGuard downgrade blocked"):
                _install(
                    repo_root=repo_root,
                    codex_home=codex_home,
                    skill_source=source,
                )
            self.assertEqual(
                3,
                len(
                    json.loads(
                        (
                            codex_home
                            / "skills/kb-sleep-maintenance/.skillguard/check-manifest.json"
                        ).read_text(encoding="utf-8")
                    )["checks"]
                ),
            )

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

            self.assertEqual("old-good", (active / "value.txt").read_text(encoding="utf-8"))
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
            first_manifest = tree_manifest(codex_home / "skills/kb-sleep-maintenance")
            second = _install(
                repo_root=repo_root,
                codex_home=codex_home,
                skill_source=source,
            )

            self.assertNotEqual(first["transaction_id"], second["transaction_id"])
            self.assertEqual(
                first_manifest["digest"],
                tree_manifest(codex_home / "skills/kb-sleep-maintenance")["digest"],
            )
            self.assertFalse(retired_skill.exists())
            self.assertFalse(retired_automation.exists())
            self.assertTrue((user_skill / "keep.txt").exists())
            self.assertEqual(second["transaction_id"], latest_install_receipt(codex_home)["transaction_id"])


if __name__ == "__main__":
    unittest.main()
