from __future__ import annotations

import re
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_kb.install import (
    AUTOMATION_MODEL_ENV_VAR,
    AUTOMATION_REASONING_EFFORT_ENV_VAR,
    MAINTENANCE_SKILL_NAMES,
    REPO_AUTOMATION_SPECS,
    RETIRED_AUTOMATION_IDS,
    RETIRED_MAINTENANCE_SKILL_IDS,
    automation_rrule_for_spec,
    build_installation_check,
    global_agents_path,
    install_codex_integration,
    latest_upgrade_attempt,
    _automation_spec_payload,
    _check_repo_skillguard_current_sources,
    _freeze_flowguard_validation_toolchain,
    _freeze_logicguard_validation_toolchain,
    _freeze_skillguard_validation_toolchain,
    _require_live_flowguard_matches_snapshot,
    _require_live_logicguard_matches_snapshot,
    _require_live_skillguard_matches_snapshot,
    _restore_exact_file_snapshot,
    _run_pre_restore_upgrade_assurance,
    _skillguard_compiler_path,
    _refresh_and_verify_skillguard_global_router,
    _verify_skillguard_global_router,
)
from local_kb.config import install_state_path
from local_kb.transactional_install import tree_manifest
from scripts.check_retired_kb_architect import build_report as build_architect_retirement_report


SURVIVING_SKILLS = {
    "kb-sleep-maintenance",
    "kb-dream-pass",
    "kb-organization-contribute",
    "kb-organization-maintenance",
    "khaos-brain-update",
}
SURVIVING_AUTOMATIONS = {
    "kb-sleep",
    "kb-dream",
    "khaos-brain-system-update",
    "kb-org-contribute",
    "kb-org-maintenance",
}


def _write_fake_tools(root: Path) -> tuple[Path, Path, Path]:
    shell_bin = root / "shell-bin"
    git_real = root / "tools" / "git-real.cmd"
    rg_source = root / "tools" / "rg-source.exe"
    git_real.parent.mkdir(parents=True, exist_ok=True)
    git_real.write_text("@echo off\r\necho git version test\r\n", encoding="utf-8")
    rg_source.write_bytes(b"rg-binary")
    return shell_bin, git_real, rg_source


def _automation_status(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'^status = "([A-Z]+)"$', text, re.MULTILINE)
    return match.group(1) if match else ""


class CodexInstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self._automation_runtime = patch.dict(
            os.environ,
            {
                AUTOMATION_MODEL_ENV_VAR: "test-current-model",
                AUTOMATION_REASONING_EFFORT_ENV_VAR: "high",
            },
        )
        self._automation_runtime.start()
        self.addCleanup(self._automation_runtime.stop)
        self._update_state_migration = patch(
            "local_kb.software_update.canonicalize_obsolete_update_state",
            return_value={
                "ok": True,
                "status": "fixture_skipped",
                "retired_state_found": False,
                "retired_schema_found": False,
                "residual_retired_state_count": 0,
            },
        )
        self._update_state_migration.start()
        self.addCleanup(self._update_state_migration.stop)

    def test_update_state_rollback_restores_exact_bytes_or_prior_absence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".local" / "khaos_brain_update_state.json"
            original = b'{"status":"available","old_shape":true}\r\n'
            path.parent.mkdir(parents=True)
            path.write_bytes(original)

            path.write_bytes(b'{"schema_version":1,"status":"failed"}\n')
            _restore_exact_file_snapshot(path, existed=True, content=original)
            self.assertEqual(path.read_bytes(), original)

            _restore_exact_file_snapshot(path, existed=False, content=b"")
            self.assertFalse(path.exists())

    def test_automation_payload_preserves_status_and_user_pause_independently(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        spec = next(item for item in REPO_AUTOMATION_SPECS if item["id"] == "kb-sleep")

        system_paused = _automation_spec_payload(
            spec,
            repo_root,
            existing={"status": "PAUSED", "user_paused": False},
        )
        self.assertEqual("PAUSED", system_paused["status"])
        self.assertFalse(system_paused["user_paused"])

        independently_marked = _automation_spec_payload(
            spec,
            repo_root,
            existing={"status": "ACTIVE", "user_paused": True},
        )
        self.assertEqual("ACTIVE", independently_marked["status"])
        self.assertTrue(independently_marked["user_paused"])

        legacy_paused = _automation_spec_payload(
            spec,
            repo_root,
            existing={"status": "PAUSED"},
        )
        self.assertEqual("PAUSED", legacy_paused["status"])
        self.assertTrue(legacy_paused["user_paused"])

    def test_architect_retirement_checks_only_the_active_codex_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            registry = root / "active-global-registry.json"
            codex_home.mkdir(parents=True)
            codex_home.joinpath("AGENTS.md").write_text(
                f"- registry_path: {registry.as_posix()}\n",
                encoding="utf-8",
            )
            registry.write_text(json.dumps({"skills": []}), encoding="utf-8")
            unrelated_stale = root / "unrelated-old-registry.json"
            unrelated_stale.write_text(
                json.dumps({"skills": [{"skill_id": "kb-architect-pass"}]}),
                encoding="utf-8",
            )

            clean = build_architect_retirement_report(codex_home)
            registry.write_text(
                json.dumps({"skills": [{"skill_id": "kb-architect-pass"}]}),
                encoding="utf-8",
            )
            active_stale = build_architect_retirement_report(codex_home)

        self.assertTrue(clean["ok"], clean)
        clean_registry_check = {
            item["id"]: item for item in clean["checks"]
        }["global_registry_route_absent"]
        self.assertEqual(clean_registry_check["details"], str(registry))
        self.assertNotEqual(clean_registry_check["details"], str(unrelated_stale))
        self.assertFalse(active_stale["ok"])
        registry_check = {
            item["id"]: item for item in active_stale["checks"]
        }["global_registry_route_absent"]
        self.assertFalse(registry_check["ok"])

    def test_real_upgrade_wrapper_keeps_pause_until_final_restore_transaction(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)
            sleep = codex_home / "automations/kb-sleep/automation.toml"
            dream = codex_home / "automations/kb-dream/automation.toml"
            architect = codex_home / "automations/kb-architect/automation.toml"
            for path, status in ((sleep, "ACTIVE"), (dream, "PAUSED"), (architect, "ACTIVE")):
                path.parent.mkdir(parents=True)
                path.write_text(f'status = "{status}"\n', encoding="utf-8")
            router_result = {
                "ok": True,
                "refresh": {"decision": "pass", "registry_hash": "A" * 64},
                "live_freshness": {"ok": True},
                "surface_after_check": {"surface_hash": "B" * 64},
            }

            with patch(
                "local_kb.maintenance_migration.run_maintenance_migration",
                return_value={"ok": True, "status": "committed", "migration_id": "fixture"},
            ), patch(
                "local_kb.install.build_installation_check",
                return_value={"ok": True, "issues": []},
            ), patch(
                "local_kb.install._refresh_and_verify_skillguard_global_router",
                return_value=router_result,
            ):
                payload = install_codex_integration(
                    repo_root,
                    codex_home,
                    shell_bin_dir=shell_bin,
                    git_executable=git_real,
                    rg_source=rg_source,
                    persist_user_shell_path=False,
                    run_upgrade_assurance=False,
                )

            self.assertTrue(payload["paused_install_transaction"]["ok"])
            self.assertNotEqual(
                payload["paused_install_transaction"]["transaction_id"],
                payload["install_transaction"]["transaction_id"],
            )
            self.assertEqual(_automation_status(sleep), "ACTIVE")
            self.assertEqual(_automation_status(dream), "PAUSED")
            self.assertFalse(architect.parent.exists())
            self.assertEqual(payload["upgrade_attempt"]["status"], "completed")
            phases = [
                row["phase"]
                for row in payload["upgrade_attempt"]["checkpoint_refs"]
            ]
            self.assertLess(
                phases.index("final_install_transaction_committed"),
                phases.index("final_router_current"),
            )
            self.assertTrue(payload["global_router_live_freshness"]["ok"])
            self.assertIn(
                payload["skillguard_validation_toolchain"]["status"],
                {"frozen", "inherited_frozen"},
            )
            self.assertIn(
                payload["flowguard_validation_toolchain"]["status"],
                {"frozen", "inherited_frozen"},
            )
            self.assertIn(
                payload["logicguard_validation_toolchain"]["status"],
                {"frozen", "inherited_frozen"},
            )
            self.assertLess(
                phases.index("validation_toolchain_frozen"),
                phases.index("paused_install_transaction_committed"),
            )

    def test_real_upgrade_drains_observations_admitted_during_assurance(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)
            initial = {
                "ok": True,
                "status": "committed",
                "migration_id": "fixture-initial",
            }
            final = {
                "ok": True,
                "status": "reconciled",
                "migration_id": "fixture-final",
                "logical_debt_reconciliation": {"pass_count": 1},
            }
            router_result = {
                "ok": True,
                "refresh": {
                    "decision": "pass",
                    "registry_path": str(
                        codex_home / ".skillguard/global-router/global_registry.json"
                    ),
                    "registry_hash": "A" * 64,
                },
                "live_freshness": {"ok": True},
                "surface_after_check": {"surface_hash": "B" * 64},
            }

            with patch(
                "local_kb.maintenance_migration.run_maintenance_migration",
                side_effect=[initial, final],
            ) as migration, patch(
                "local_kb.maintenance_migration.check_migration",
                return_value={"ok": True, "issues": []},
            ), patch(
                "scripts.evaluate_kb_retrieval.build_report",
                return_value={
                    "ok": True,
                    "metrics": {"useful_top3_rate": 1.0},
                    "threshold_results": {"active_index_current": True},
                },
            ), patch(
                "local_kb.install._refresh_and_verify_skillguard_global_router",
                return_value=router_result,
            ), patch(
                "local_kb.install._run_pre_restore_upgrade_assurance",
                return_value={"ok": True, "failed_checks": []},
            ), patch(
                "local_kb.install.build_installation_check",
                return_value={"ok": True, "issues": []},
            ):
                payload = install_codex_integration(
                    repo_root,
                    codex_home,
                    shell_bin_dir=shell_bin,
                    git_executable=git_real,
                    rg_source=rg_source,
                    persist_user_shell_path=False,
                )

            self.assertEqual(migration.call_count, 2)
            self.assertEqual(payload["initial_history_migration"], initial)
            self.assertEqual(payload["history_migration"], final)
            self.assertEqual(payload["post_assurance_history_migration"], final)
            self.assertTrue(payload["post_assurance_data_convergence"]["ok"])
            self.assertEqual(
                payload["post_assurance_data_convergence"]["attempt_count"], 1
            )
            phases = [
                row["phase"] for row in payload["upgrade_attempt"]["checkpoint_refs"]
            ]
            self.assertLess(
                phases.index("aggregate_assurance_passed"),
                phases.index("post_assurance_history_current"),
            )
            self.assertLess(
                phases.index("post_assurance_history_current"),
                phases.index("final_install_transaction_committed"),
            )

    def test_post_assurance_data_convergence_failure_keeps_survivors_paused(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)
            initial = {
                "ok": True,
                "status": "committed",
                "migration_id": "fixture-initial",
            }
            failed = {
                "ok": False,
                "status": "paused_failed",
                "issues": ["late observation debt kept changing"],
            }
            router_result = {
                "ok": True,
                "refresh": {
                    "decision": "pass",
                    "registry_path": str(
                        codex_home / ".skillguard/global-router/global_registry.json"
                    ),
                    "registry_hash": "A" * 64,
                },
                "live_freshness": {"ok": True},
                "surface_after_check": {"surface_hash": "B" * 64},
            }

            with patch(
                "local_kb.maintenance_migration.run_maintenance_migration",
                side_effect=[initial, failed, failed, failed, failed],
            ), patch(
                "local_kb.install._refresh_and_verify_skillguard_global_router",
                return_value=router_result,
            ), patch(
                "local_kb.install._run_pre_restore_upgrade_assurance",
                return_value={"ok": True, "failed_checks": []},
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "post-assurance data convergence failed"
                ):
                    install_codex_integration(
                        repo_root,
                        codex_home,
                        shell_bin_dir=shell_bin,
                        git_executable=git_real,
                        rg_source=rg_source,
                        persist_user_shell_path=False,
                    )

            attempt = latest_upgrade_attempt(codex_home)
            self.assertEqual(attempt["status"], "failed")
            phases = [row["phase"] for row in attempt["checkpoint_refs"]]
            self.assertIn("aggregate_assurance_passed", phases)
            self.assertNotIn("final_install_transaction_committed", phases)
            for automation_id in SURVIVING_AUTOMATIONS:
                self.assertEqual(
                    _automation_status(
                        codex_home / "automations" / automation_id / "automation.toml"
                    ),
                    "PAUSED",
                )

    def test_failed_post_commit_assurance_keeps_old_manifest_and_durable_attempt(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)
            old_manifest = {"sentinel": "last-known-good"}
            state_path = install_state_path(codex_home)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(old_manifest), encoding="utf-8")
            update_state = root / "obsolete-update-state.json"
            obsolete_update_bytes = (
                b'{"schema_version":1,"status":"failed",'
                b'"error":"SkillGuard installation identity is not current"}\r\n'
            )
            update_state.write_bytes(obsolete_update_bytes)
            migration_calls: list[dict[str, object]] = []

            def migrate_before_assurance(
                _repo_root: Path, *, install_receipt: dict[str, object]
            ) -> dict[str, object]:
                self.assertEqual(install_receipt.get("status"), "committed")
                migration_calls.append(dict(install_receipt))
                update_state.write_text(
                    '{"schema_version":1,"status":"current","error":""}\n',
                    encoding="utf-8",
                )
                return {
                    "ok": True,
                    "status": "committed",
                    "residual_retired_state_count": 0,
                }

            def fail_after_current_state(*_args: object, **_kwargs: object) -> dict:
                self.assertIn('"status":"current"', update_state.read_text(encoding="utf-8"))
                raise RuntimeError("fixture aggregate failure")
            router_result = {
                "ok": True,
                "refresh": {
                    "decision": "pass",
                    "registry_path": str(
                        codex_home
                        / ".skillguard/global-router/global_registry.json"
                    ),
                    "registry_hash": "A" * 64,
                },
                "live_freshness": {"ok": True},
                "surface_after_check": {"surface_hash": "B" * 64},
            }

            with patch(
                "local_kb.maintenance_migration.run_maintenance_migration",
                return_value={
                    "ok": True,
                    "status": "committed",
                    "migration_id": "fixture",
                },
            ), patch(
                "local_kb.software_update.update_state_path",
                return_value=update_state,
            ), patch(
                "local_kb.software_update.canonicalize_obsolete_update_state",
                side_effect=migrate_before_assurance,
            ), patch(
                "local_kb.install._refresh_and_verify_skillguard_global_router",
                return_value=router_result,
            ), patch(
                "local_kb.install._run_pre_restore_upgrade_assurance",
                side_effect=fail_after_current_state,
            ):
                with self.assertRaisesRegex(RuntimeError, "fixture aggregate failure"):
                    install_codex_integration(
                        repo_root,
                        codex_home,
                        shell_bin_dir=shell_bin,
                        git_executable=git_real,
                        rg_source=rg_source,
                        persist_user_shell_path=False,
                    )

            self.assertEqual(
                json.loads(state_path.read_text(encoding="utf-8")), old_manifest
            )
            self.assertEqual(len(migration_calls), 1)
            self.assertEqual(update_state.read_bytes(), obsolete_update_bytes)
            attempt = latest_upgrade_attempt(codex_home)
            self.assertEqual(attempt["status"], "failed")
            self.assertEqual(attempt["phase"], "failed_paused_recoverable")
            phases = [row["phase"] for row in attempt["checkpoint_refs"]]
            self.assertIn("paused_install_transaction_committed", phases)
            self.assertIn("pre_assurance_router_current", phases)
            for automation_id in SURVIVING_AUTOMATIONS:
                self.assertEqual(
                    _automation_status(
                        codex_home / "automations" / automation_id / "automation.toml"
                    ),
                    "PAUSED",
                )

    def test_router_refresh_retries_when_active_skillguard_surface_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            refresh = {
                "decision": "pass",
                "registry_path": str(
                    codex_home / ".skillguard/global-router/global_registry.json"
                ),
            }
            surfaces = [
                {"surface_hash": "A" * 64},
                {"surface_hash": "B" * 64},
                {"surface_hash": "C" * 64},
                {"surface_hash": "C" * 64},
            ]
            with patch(
                "local_kb.install._refresh_skillguard_global_router",
                return_value=refresh,
            ) as refresh_mock, patch(
                "local_kb.install._verify_skillguard_global_router",
                return_value={"ok": True},
            ), patch(
                "local_kb.install._skillguard_router_surface",
                side_effect=surfaces,
            ):
                result = _refresh_and_verify_skillguard_global_router(codex_home)

            self.assertTrue(result["ok"])
            self.assertEqual(result["attempt_number"], 2)
            self.assertEqual(refresh_mock.call_count, 2)

    def test_router_live_check_uses_canonical_registry_not_display_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            registry = (
                codex_home
                / ".skillguard/global-router/global_registry.json"
            )
            registry.parent.mkdir(parents=True)
            registry.write_text("{}", encoding="utf-8")
            seen: list[Path] = []

            def checked(_home: Path, *, command: str, registry_path: Path) -> dict:
                seen.append(registry_path)
                return {"ok": True, "decision": "pass", "command": command}

            with patch(
                "local_kb.install._run_skillguard_router_check",
                side_effect=checked,
            ):
                result = _verify_skillguard_global_router(
                    codex_home,
                    {
                        "registry_path": "AppData/Local/Temp/redacted/.codex/.skillguard/global-router/global_registry.json",
                        "registry_hash": "A" * 64,
                    },
                )

            self.assertTrue(result["ok"])
            self.assertEqual(seen, [registry.resolve(), registry.resolve()])

    def test_sleep_and_dream_prompts_are_automatic_and_convergent(self) -> None:
        root = Path(__file__).resolve().parents[1]
        sleep = (root / ".agents/skills/local-kb-retrieve/MAINTENANCE_PROMPT.md").read_text(encoding="utf-8")
        dream = (root / ".agents/skills/local-kb-retrieve/DREAM_PROMPT.md").read_text(encoding="utf-8")
        self.assertIn("kb_sleep.py", sleep)
        self.assertIn("exactly one current disposition", sleep)
        self.assertIn("Do not ask a human", sleep)
        self.assertIn("no_delta_closed", dream)
        self.assertIn("typed idempotent Sleep handoff", dream)
        self.assertIn("Never directly modify cards", dream)

    def test_fixture_install_requires_isolated_shell_tools(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            with self.assertRaisesRegex(RuntimeError, "explicit shell_bin_dir"):
                install_codex_integration(
                    repo_root=repo_root,
                    codex_home=codex_home,
                    persist_user_shell_path=False,
                    run_history_migration=False,
                )

    def test_source_validation_rejects_compiler_identity_change(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        configured_validation_root = os.environ.get(
            "KHAOS_BRAIN_SKILLGUARD_VALIDATION_ROOT", ""
        ).strip()
        source_skillguard = (
            Path(configured_validation_root).resolve()
            if configured_validation_root
            else Path.home() / ".codex" / "skills" / "skillguard"
        )
        self.assertTrue(source_skillguard.is_dir())
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            copied_skillguard = codex_home / "skills" / "skillguard"
            shutil.copytree(source_skillguard, copied_skillguard)
            compiler = copied_skillguard / "scripts" / "skillguard_compile.py"
            real_run = subprocess.run
            mutated = False

            def run_and_mutate(*args, **kwargs):  # type: ignore[no-untyped-def]
                nonlocal mutated
                result = real_run(*args, **kwargs)
                command = args[0] if args else kwargs.get("args", ())
                if (
                    not mutated
                    and len(command) > 1
                    and Path(command[1]).resolve() == compiler.resolve()
                ):
                    compiler.write_bytes(compiler.read_bytes() + b"\n")
                    mutated = True
                return result

            manifest_digest = tree_manifest(copied_skillguard)["digest"]
            with patch.dict(
                os.environ,
                {
                    "KHAOS_BRAIN_SKILLGUARD_VALIDATION_ROOT": str(copied_skillguard),
                    "KHAOS_BRAIN_SKILLGUARD_VALIDATION_DIGEST": str(
                        manifest_digest
                    ),
                },
            ), patch(
                "local_kb.install.subprocess.run", side_effect=run_and_mutate
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "Validation identity changed during source validation"
                ):
                    _check_repo_skillguard_current_sources(repo_root, codex_home)
            self.assertTrue(mutated)

    def test_skillguard_validation_toolchain_is_a_stable_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            live = codex_home / "skills" / "skillguard"
            scripts = live / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "skillguard_compile.py").write_text(
                "print('compiler')\n", encoding="utf-8"
            )
            (scripts / "skillguard.py").write_text(
                "print('cli')\n", encoding="utf-8"
            )
            destination = root / "receipts" / "skillguard"
            with patch.dict(
                os.environ,
                {
                    "KHAOS_BRAIN_SKILLGUARD_VALIDATION_ROOT": "",
                    "KHAOS_BRAIN_SKILLGUARD_VALIDATION_DIGEST": "",
                },
            ):
                receipt = _freeze_skillguard_validation_toolchain(
                    codex_home, destination
                )
            self.assertEqual(receipt["status"], "frozen")
            self.assertEqual(
                receipt["manifest"]["digest"], tree_manifest(destination)["digest"]
            )
            shutil.rmtree(live)
            self.assertTrue(
                _skillguard_compiler_path(codex_home, destination).is_file()
            )
            with self.assertRaisesRegex(RuntimeError, "identity changed"):
                _require_live_skillguard_matches_snapshot(receipt)

    def test_flowguard_validation_toolchain_is_a_stable_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live = root / "live" / "flowguard"
            live.mkdir(parents=True)
            (live / "__init__.py").write_text(
                "SCHEMA_VERSION = 'test'\n", encoding="utf-8"
            )
            (live / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
            destination = root / "receipts" / "python" / "flowguard"
            with patch.dict(
                os.environ,
                {
                    "KHAOS_BRAIN_FLOWGUARD_VALIDATION_ROOT": "",
                    "KHAOS_BRAIN_FLOWGUARD_VALIDATION_DIGEST": "",
                },
            ):
                receipt = _freeze_flowguard_validation_toolchain(
                    destination, source_root=live
                )
            self.assertEqual(receipt["status"], "frozen")
            self.assertEqual(
                receipt["manifest"]["digest"], tree_manifest(destination)["digest"]
            )
            shutil.rmtree(live)
            self.assertTrue((destination / "__init__.py").is_file())
            with self.assertRaisesRegex(RuntimeError, "identity changed"):
                _require_live_flowguard_matches_snapshot(receipt)

    def test_logicguard_validation_toolchain_is_a_stable_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live = root / "live" / "logicguard"
            live.mkdir(parents=True)
            (live / "__init__.py").write_text(
                "SCHEMA_VERSION = 'test'\n", encoding="utf-8"
            )
            (live / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
            destination = root / "receipts" / "python" / "logicguard"
            with patch.dict(
                os.environ,
                {
                    "KHAOS_BRAIN_LOGICGUARD_VALIDATION_ROOT": "",
                    "KHAOS_BRAIN_LOGICGUARD_VALIDATION_DIGEST": "",
                },
            ):
                receipt = _freeze_logicguard_validation_toolchain(
                    destination, source_root=live
                )
            self.assertEqual(receipt["status"], "frozen")
            self.assertEqual(
                receipt["manifest"]["digest"], tree_manifest(destination)["digest"]
            )
            shutil.rmtree(live)
            self.assertTrue((destination / "__init__.py").is_file())
            with self.assertRaisesRegex(RuntimeError, "identity changed"):
                _require_live_logicguard_matches_snapshot(receipt)

    def test_pre_restore_assurance_keeps_baseline_install_identity_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flowguard_root = root / "validation" / "python" / "flowguard"
            flowguard_root.mkdir(parents=True)
            logicguard_root = root / "validation" / "python" / "logicguard"
            logicguard_root.mkdir(parents=True)
            baseline_pythonpath = str(root / "baseline-pythonpath")
            injected_pythonpath = os.pathsep.join(
                (str(flowguard_root.parent), baseline_pythonpath)
            )
            captured: dict[str, object] = {}

            def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
                captured["environment"] = dict(kwargs["env"])
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout=json.dumps({"ok": True}),
                    stderr="",
                )

            with patch.dict(
                os.environ,
                {
                    "PYTHONPATH": injected_pythonpath,
                    "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_PRESENT": "1",
                    "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_VALUE": baseline_pythonpath,
                },
            ), patch("local_kb.install.run_with_timeout_cleanup", side_effect=fake_run):
                result = _run_pre_restore_upgrade_assurance(
                    root,
                    root / ".codex",
                    skillguard_validation_toolchain={
                        "snapshot_root": str(root / "validation" / "skillguard"),
                        "manifest": {"digest": "S" * 64},
                    },
                    flowguard_validation_toolchain={
                        "snapshot_root": str(flowguard_root),
                        "manifest": {"digest": "F" * 64},
                    },
                    logicguard_validation_toolchain={
                        "snapshot_root": str(logicguard_root),
                        "manifest": {"digest": "L" * 64},
                    },
                )

            self.assertTrue(result["ok"])
            environment = captured["environment"]
            self.assertEqual(environment["PYTHONPATH"], injected_pythonpath)
            self.assertEqual(
                environment["KHAOS_BRAIN_LOGICGUARD_VALIDATION_ROOT"],
                str(logicguard_root),
            )
            self.assertEqual(
                environment["KHAOS_BRAIN_LOGICGUARD_VALIDATION_DIGEST"],
                "L" * 64,
            )
            self.assertEqual(
                environment[
                    "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_VALUE"
                ],
                baseline_pythonpath,
            )

    def test_pre_restore_assurance_failure_reports_owner_terminal_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flowguard_root = root / "validation" / "python" / "flowguard"
            flowguard_root.mkdir(parents=True)
            logicguard_root = root / "validation" / "python" / "logicguard"
            logicguard_root.mkdir(parents=True)
            payload = {
                "ok": False,
                "failed_checks": ["full_regression"],
                "checks": {
                    "full_regression": {
                        "terminal_status": "failed",
                        "exit_code": 1,
                        "timed_out": False,
                        "cleanup_confirmed": True,
                        "junit": {
                            "testcase_count": 2,
                            "passed_node_ids": ["tests/test_one.py::test_ok"],
                            "failed_node_ids": ["tests/test_two.py::test_failed"],
                            "errored_node_ids": [],
                            "skipped_node_ids": [],
                            "unparsed_cases": [
                                {"classname": "unexpected.module", "name": "test_unknown"}
                            ],
                            "parse_error": "",
                        },
                        "json_payload": {
                            "checks": [
                                {"id": "fixture-static-owner", "ok": False}
                            ],
                            "skills": {
                                "khaos-brain-update": {
                                    "executed_supervision": {
                                        "scheduled_production": {
                                            "ok": False,
                                            "exit_code": 1,
                                            "status": "blocked",
                                            "blockers": ["fixture-production-block"],
                                        }
                                    }
                                }
                            },
                        },
                        "stdout_tail": "one regression failed",
                        "stderr_tail": "assertion detail",
                    }
                },
            }
            completed = subprocess.CompletedProcess(
                args=["python"],
                returncode=1,
                stdout=json.dumps(payload),
                stderr="outer diagnostic",
            )

            with patch(
                "local_kb.install.run_with_timeout_cleanup",
                return_value=completed,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "unexpected.module",
                ) as raised:
                    _run_pre_restore_upgrade_assurance(
                        root,
                        root / ".codex",
                        skillguard_validation_toolchain={
                            "snapshot_root": str(root / "validation" / "skillguard"),
                            "manifest": {"digest": "S" * 64},
                        },
                        flowguard_validation_toolchain={
                            "snapshot_root": str(flowguard_root),
                            "manifest": {"digest": "F" * 64},
                        },
                        logicguard_validation_toolchain={
                            "snapshot_root": str(logicguard_root),
                            "manifest": {"digest": "L" * 64},
                        },
                    )

            message = str(raised.exception)
            self.assertIn('"terminal_status": "failed"', message)
            self.assertIn('"exit_code": 1', message)
            self.assertIn('"passed_count": 1', message)
            self.assertIn("tests/test_two.py::test_failed", message)
            self.assertIn("fixture-static-owner", message)
            self.assertIn("fixture-production-block", message)
            self.assertNotIn("one regression failed", message)

    def test_install_is_transactional_current_and_retires_exact_architect(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)

            # Model a supported old machine, including exact retired ids and a
            # similarly named user surface that must remain untouched.
            (codex_home / "skills/kb-architect-pass").mkdir(parents=True)
            (codex_home / "skills/kb-architect-pass/SKILL.md").write_text("legacy", encoding="utf-8")
            (codex_home / "automations/kb-architect").mkdir(parents=True)
            (codex_home / "automations/kb-architect/automation.toml").write_text("id='legacy'", encoding="utf-8")
            (codex_home / "skills/kb-architect-pass-personal").mkdir(parents=True)
            (codex_home / "skills/kb-architect-pass-personal/keep.txt").write_text("user", encoding="utf-8")

            payload = install_codex_integration(
                repo_root,
                codex_home,
                shell_bin_dir=shell_bin,
                git_executable=git_real,
                rg_source=rg_source,
                persist_user_shell_path=False,
                run_history_migration=False,
            )

            self.assertEqual(set(payload["maintenance_skill_names"]), SURVIVING_SKILLS)
            self.assertEqual(set(payload["automation_ids"]), SURVIVING_AUTOMATIONS)
            self.assertEqual(set(MAINTENANCE_SKILL_NAMES), SURVIVING_SKILLS)
            self.assertEqual({item["id"] for item in REPO_AUTOMATION_SPECS}, SURVIVING_AUTOMATIONS)
            self.assertEqual(tuple(payload["retired_skill_ids"]), RETIRED_MAINTENANCE_SKILL_IDS)
            self.assertEqual(tuple(payload["retired_automation_ids"]), RETIRED_AUTOMATION_IDS)
            self.assertFalse((codex_home / "skills/kb-architect-pass").exists())
            self.assertFalse((codex_home / "automations/kb-architect").exists())
            self.assertTrue((codex_home / "skills/kb-architect-pass-personal/keep.txt").exists())

            transaction = payload["install_transaction"]
            self.assertTrue(transaction["ok"])
            self.assertTrue(transaction["receipt_hash"])
            self.assertTrue(Path(transaction["journal_path"]).exists())
            self.assertTrue(Path(transaction["backup_root"]).exists())
            source_checks = {
                row["skill_id"]: row for row in payload["skillguard_source_checks"]
            }
            self.assertEqual(set(source_checks), SURVIVING_SKILLS)
            authority_receipts = transaction["skillguard_authority_receipts"]
            self.assertEqual(set(authority_receipts), SURVIVING_SKILLS)
            for skill in SURVIVING_SKILLS:
                source_check = source_checks[skill]
                self.assertEqual(source_check["status"], "current")
                self.assertTrue(source_check["ok"])
                self.assertRegex(source_check["compiler_sha256"], r"^[0-9a-f]{64}$")
                self.assertRegex(source_check["generator_sha256"], r"^[0-9a-f]{64}$")
                self.assertRegex(source_check["receipt_hash"], r"^[0-9a-f]{64}$")
                authority = authority_receipts[skill]
                self.assertEqual(
                    authority["decision"], "validated-current-replaces-non-current"
                )
                self.assertFalse(authority["semantic_comparison_performed"])
                self.assertEqual(
                    authority["incoming_validation"]["receipt_hash"],
                    source_check["receipt_hash"],
                )
            for skill in SURVIVING_SKILLS:
                root_path = codex_home / "skills" / skill
                self.assertTrue((root_path / "SKILL.md").exists())
                self.assertTrue((root_path / ".skillguard/contract-source.json").exists())
                self.assertTrue((root_path / ".skillguard/compiled-contract.json").exists())
                self.assertTrue((root_path / ".skillguard/check-manifest.json").exists())
            for automation in SURVIVING_AUTOMATIONS:
                self.assertTrue((codex_home / "automations" / automation / "automation.toml").exists())
            self.assertTrue(global_agents_path(codex_home).exists())

            check = build_installation_check(repo_root, codex_home)
            self.assertTrue(check["ok"], check["issues"])
            checklist = {item["id"]: item for item in check["checklist"]}
            self.assertTrue(checklist["retired_architect_surfaces"]["ok"])
            self.assertTrue(checklist["transactional_install_receipt"]["ok"])
            self.assertTrue(checklist["repo_maintenance_skills"]["ok"])
            self.assertTrue(checklist["khaos_brain_system_update_automation"]["ok"])

    def test_reinstall_preserves_pause_state_for_every_surviving_automation(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)
            kwargs = dict(
                repo_root=repo_root,
                codex_home=codex_home,
                shell_bin_dir=shell_bin,
                git_executable=git_real,
                rg_source=rg_source,
                persist_user_shell_path=False,
                run_history_migration=False,
            )
            install_codex_integration(**kwargs)
            for automation in ("kb-sleep", "kb-dream", "khaos-brain-system-update"):
                path = codex_home / "automations" / automation / "automation.toml"
                text = path.read_text(encoding="utf-8").replace('status = "ACTIVE"', 'status = "PAUSED"')
                text = text.replace("user_paused = false", "user_paused = true")
                path.write_text(text, encoding="utf-8")

            install_codex_integration(**kwargs)
            self.assertEqual(_automation_status(codex_home / "automations/kb-sleep/automation.toml"), "PAUSED")
            self.assertEqual(_automation_status(codex_home / "automations/kb-dream/automation.toml"), "PAUSED")
            self.assertEqual(
                _automation_status(codex_home / "automations/khaos-brain-system-update/automation.toml"),
                "PAUSED",
            )
            self.assertEqual(_automation_status(codex_home / "automations/kb-org-contribute/automation.toml"), "ACTIVE")

    def test_complete_tree_drift_fails_install_check(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)
            install_codex_integration(
                repo_root,
                codex_home,
                shell_bin_dir=shell_bin,
                git_executable=git_real,
                rg_source=rg_source,
                persist_user_shell_path=False,
                run_history_migration=False,
            )
            target = codex_home / "skills/kb-dream-pass/.skillguard/check-manifest.json"
            target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            check = build_installation_check(repo_root, codex_home)
            self.assertFalse(check["ok"])
            self.assertTrue(any("complete tree differs" in item for item in check["issues"]))

    def test_organization_automation_times_are_stable_and_windowed(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        by_id = {item["id"]: item for item in REPO_AUTOMATION_SPECS}
        first = automation_rrule_for_spec(by_id["kb-org-contribute"], repo_root)
        second = automation_rrule_for_spec(by_id["kb-org-contribute"], repo_root)
        self.assertEqual(first, second)
        self.assertRegex(first, r"BYHOUR=\d+;BYMINUTE=\d+")


if __name__ == "__main__":
    unittest.main()
