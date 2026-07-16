from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import check_khaos_logicguard_native_readiness as readiness
from local_kb.transactional_install import tree_manifest


def base_report(*, fail: str = "", omit: str = "") -> dict:
    checks = {
        name: {
            "ok": name != fail,
            "json_payload": (
                {
                    "generation_id": "generation-test",
                    "authority": {"zero_legacy_projection_residuals": True},
                }
                if name == "logicguard_runtime"
                else {}
            ),
        }
        for name in readiness.REQUIRED_CHECKS
        if name != omit
    }
    return {
        "schema_version": 2,
        "check": "base",
        "ok": not fail and not omit,
        "checks": checks,
        "evidence_manifest": {"path": "manifest.json", "sha256": "abc"},
    }


class KhaosLogicGuardReadinessTests(unittest.TestCase):
    def test_standalone_owner_binds_completed_install_toolchains(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skillguard = root / "skillguard"
            flowguard = root / "python" / "flowguard"
            logicguard = root / "python" / "logicguard"
            (skillguard / "scripts").mkdir(parents=True)
            (skillguard / "scripts" / "skillguard.py").write_text(
                "# current\n", encoding="utf-8"
            )
            (skillguard / "scripts" / "skillguard_compile.py").write_text(
                "# current\n", encoding="utf-8"
            )
            flowguard.mkdir(parents=True)
            (flowguard / "__init__.py").write_text("SCHEMA_VERSION='1.0'\n", encoding="utf-8")
            logicguard.mkdir(parents=True)
            (logicguard / "__init__.py").write_text(
                "SCHEMA_VERSION='logicguard.model-store.v1'\n",
                encoding="utf-8",
            )
            attempt = {
                "attempt_id": "upgrade-current",
                "status": "completed",
                "phase": "post_install_check_passed",
                "updated_at": "2026-07-15T00:00:00Z",
                "skillguard_validation_toolchain": {
                    "snapshot_root": str(skillguard),
                    "manifest": tree_manifest(skillguard),
                },
                "flowguard_validation_toolchain": {
                    "snapshot_root": str(flowguard),
                    "manifest": tree_manifest(flowguard),
                },
                "logicguard_validation_toolchain": {
                    "snapshot_root": str(logicguard),
                    "manifest": tree_manifest(logicguard),
                },
            }
            env_keys = [
                item
                for row in readiness._VALIDATION_TOOLCHAINS
                for item in row[1:3]
            ]
            env_keys.extend(
                [
                    readiness._INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV,
                    readiness._INSTALLATION_IDENTITY_PYTHONPATH_VALUE_ENV,
                ]
            )
            prior_sys_path = list(readiness.sys.path)
            try:
                with patch.object(
                    readiness, "latest_upgrade_attempt", return_value=attempt
                ), patch.dict(
                    os.environ,
                    {key: "" for key in [*env_keys, "PYTHONPATH"]},
                    clear=False,
                ):
                    binding = readiness._configure_completed_install_toolchains(
                        root / ".codex"
                    )
                    self.assertEqual(binding["attempt_id"], "upgrade-current")
                    self.assertEqual(
                        os.environ["KHAOS_BRAIN_LOGICGUARD_VALIDATION_ROOT"],
                        str(logicguard.resolve()),
                    )
                    self.assertIn(str(flowguard.parent.resolve()), os.environ["PYTHONPATH"])
                    self.assertIn(str(logicguard.parent.resolve()), readiness.sys.path)
                    self.assertEqual(
                        os.environ[
                            readiness._INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV
                        ],
                        "1",
                    )
                    self.assertEqual(
                        os.environ[
                            readiness._INSTALLATION_IDENTITY_PYTHONPATH_VALUE_ENV
                        ],
                        "",
                    )
            finally:
                readiness.sys.path[:] = prior_sys_path

    def test_standalone_owner_rejects_nonterminal_install_attempt(self) -> None:
        with patch.object(
            readiness,
            "latest_upgrade_attempt",
            return_value={"status": "failed", "phase": "failed_paused_recoverable"},
        ):
            with self.assertRaisesRegex(RuntimeError, "completed current"):
                readiness._configure_completed_install_toolchains(Path(".codex"))

    def test_final_owner_requires_every_declared_check_and_exact_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            readiness,
            "build_base_report",
            return_value=base_report(),
        ):
            report = readiness.build_report(
                Path(directory),
                Path(directory) / ".codex",
                evidence_root=Path(directory) / "evidence",
            )
        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(report["logicguard_generation_id"], "generation-test")
        self.assertTrue(report["zero_legacy_projection_residuals"])
        self.assertTrue(report["receipt_id"].startswith("khaos-logicguard-native-readiness:"))

    def test_missing_or_failed_child_cannot_close_final_owner(self) -> None:
        for kwargs, expected in (
            ({"omit": "logicguard_model_mesh"}, "missing-check:logicguard_model_mesh"),
            ({"fail": "logicguard_runtime"}, "failed-check:logicguard_runtime"),
        ):
            with self.subTest(**kwargs), tempfile.TemporaryDirectory() as directory, patch.object(
                readiness,
                "build_base_report",
                return_value=base_report(**kwargs),
            ):
                report = readiness.build_report(
                    Path(directory),
                    Path(directory) / ".codex",
                    evidence_root=Path(directory) / "evidence",
                )
            self.assertFalse(report["ok"])
            self.assertIn(expected, report["issues"])


if __name__ == "__main__":
    unittest.main()
