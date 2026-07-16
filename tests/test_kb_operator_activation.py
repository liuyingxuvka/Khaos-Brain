from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from local_kb.install import REPO_AUTOMATION_SPECS
from local_kb.operator_activation import (
    REQUIRED_READINESS_CHECKS,
    activate_all_for_current_machine,
    validate_activation_readiness,
    validate_operator_activation_receipt,
)


def _write_paused_automations(codex_home: Path) -> None:
    for spec in REPO_AUTOMATION_SPECS:
        automation_id = str(spec["id"])
        path = codex_home / "automations" / automation_id / "automation.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f'id = "{automation_id}"\nstatus = "PAUSED"\nuser_paused = true\n',
            encoding="utf-8",
        )


def _gate(repo_root: Path) -> dict:
    evidence = repo_root / ".local" / "assurance" / "validation-evidence" / "run" / "manifest.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("{}\n", encoding="utf-8")
    scheduled_refs = {}
    for spec in REPO_AUTOMATION_SPECS:
        skill_id = str(spec["skill_name"])
        proof = (
            repo_root
            / ".local"
            / "automation-runs"
            / skill_id
            / "test"
            / "guarded-result.json"
        )
        proof.parent.mkdir(parents=True, exist_ok=True)
        proof.write_text(
            json.dumps(
                {
                    "ok": True,
                    "skill_id": skill_id,
                    "run_id": str(spec["id"]),
                    "status": "completed",
                }
            ),
            encoding="utf-8",
        )
        scheduled_refs[skill_id] = {
            "path": str(proof),
            "sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
            "run_id": str(spec["id"]),
            "status": "completed",
        }
    return {
        "ok": True,
        "issues": [],
        "binding": {
            "aggregate_receipt_sha256": "A" * 64,
            "evidence_manifest_path": str(evidence),
            "evidence_manifest_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            "source_digest": "source",
            "verifier_digest": "verifier",
            "scheduled_production_refs": scheduled_refs,
        },
    }


def test_activation_gate_requires_exact_current_aggregate_and_five_terminals() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo_root = root / "repo"
        codex_home = root / ".codex"
        repo_root.mkdir()
        evidence = (
            repo_root
            / ".local"
            / "assurance"
            / "validation-evidence"
            / "run"
            / "manifest.json"
        )
        evidence.parent.mkdir(parents=True)
        evidence.write_text("{}\n", encoding="utf-8")
        skills = {}
        for spec in REPO_AUTOMATION_SPECS:
            skill_id = str(spec["skill_name"])
            result_path = (
                repo_root
                / ".local"
                / "automation-runs"
                / skill_id
                / "run"
                / "guarded-result.json"
            )
            result_path.parent.mkdir(parents=True)
            result_path.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "skill_id": skill_id,
                        "run_id": str(spec["id"]),
                        "status": "completed",
                    }
                ),
                encoding="utf-8",
            )
            skills[skill_id] = {
                "executed_supervision": {
                    "ok": True,
                    "scheduled_production": {
                        "ok": True,
                        "guarded_result_path": str(result_path),
                    },
                }
            }
        checks = {check_id: {"ok": True} for check_id in REQUIRED_READINESS_CHECKS}
        checks["skillguard_source_install_parity"] = {
            "ok": True,
            "json_payload": {"ok": True, "skills": skills},
        }
        receipt = {
            "ok": True,
            "pre_restore": True,
            "repo_root": str(repo_root),
            "codex_home": str(codex_home),
            "source_stable_during_checks": True,
            "source_snapshot_after": {"digest": "source"},
            "verifier_fingerprint": {"digest": "verifier"},
            "checks": checks,
            "evidence_manifest": {
                "path": str(evidence),
                "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            },
        }
        receipt_path = repo_root / "readiness.json"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        with patch(
            "local_kb.operator_activation.readiness._source_snapshot",
            return_value={"digest": "source"},
        ), patch(
            "local_kb.operator_activation.readiness._verifier_fingerprint",
            return_value={"digest": "verifier"},
        ):
            result = validate_activation_readiness(
                repo_root,
                codex_home,
                receipt_path,
            )
        assert result["ok"], result
        assert set(result["binding"]["scheduled_production_refs"]) == {
            str(spec["skill_name"]) for spec in REPO_AUTOMATION_SPECS
        }


def test_current_machine_override_activates_all_and_writes_current_receipt() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo_root = root / "repo"
        codex_home = root / ".codex"
        repo_root.mkdir()
        _write_paused_automations(codex_home)
        final_check = {"ok": True, "issues": [], "strong_session_defaults": True}
        with patch(
            "local_kb.operator_activation.validate_activation_readiness",
            return_value=_gate(repo_root),
        ), patch(
            "local_kb.operator_activation.build_installation_check",
            return_value=final_check,
        ):
            result = activate_all_for_current_machine(
                repo_root,
                codex_home,
                repo_root / "readiness.json",
            )

        assert result["ok"], result
        assert result["validation"]["ok"], result
        assert Path(result["receipt_path"]).is_file()
        assert Path(result["head_path"]).is_file()
        for spec in REPO_AUTOMATION_SPECS:
            text = (
                codex_home
                / "automations"
                / str(spec["id"])
                / "automation.toml"
            ).read_text(encoding="utf-8")
            assert 'status = "ACTIVE"' in text
            assert "user_paused = false" in text
        with patch(
            "local_kb.operator_activation.validate_activation_readiness",
            return_value=_gate(repo_root),
        ), patch(
            "local_kb.operator_activation.build_installation_check",
            return_value=final_check,
        ):
            repeated = activate_all_for_current_machine(
                repo_root,
                codex_home,
                repo_root / "readiness.json",
            )
        assert repeated["ok"], repeated
        assert repeated["status"] == "current-machine-all-active-reused"


def test_current_machine_override_blocks_without_current_readiness() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo_root = root / "repo"
        codex_home = root / ".codex"
        repo_root.mkdir()
        _write_paused_automations(codex_home)
        with patch(
            "local_kb.operator_activation.validate_activation_readiness",
            return_value={"ok": False, "issues": ["stale"]},
        ):
            result = activate_all_for_current_machine(
                repo_root,
                codex_home,
                repo_root / "readiness.json",
            )
        assert not result["ok"]
        assert result["status"] == "readiness-blocked"
        for spec in REPO_AUTOMATION_SPECS:
            text = (
                codex_home
                / "automations"
                / str(spec["id"])
                / "automation.toml"
            ).read_text(encoding="utf-8")
            assert 'status = "PAUSED"' in text


def test_current_machine_override_repauses_group_when_final_check_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo_root = root / "repo"
        codex_home = root / ".codex"
        repo_root.mkdir()
        _write_paused_automations(codex_home)
        with patch(
            "local_kb.operator_activation.validate_activation_readiness",
            return_value=_gate(repo_root),
        ), patch(
            "local_kb.operator_activation.build_installation_check",
            return_value={"ok": False, "issues": ["injected"]},
        ):
            result = activate_all_for_current_machine(
                repo_root,
                codex_home,
                repo_root / "readiness.json",
            )
        assert not result["ok"]
        assert result["status"] == "install-check-blocked-repaused"
        for spec in REPO_AUTOMATION_SPECS:
            text = (
                codex_home
                / "automations"
                / str(spec["id"])
                / "automation.toml"
            ).read_text(encoding="utf-8")
            assert 'status = "PAUSED"' in text


def test_current_activation_receipt_rejects_changed_scheduled_proof() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo_root = root / "repo"
        codex_home = root / ".codex"
        repo_root.mkdir()
        _write_paused_automations(codex_home)
        final_check = {"ok": True, "issues": [], "strong_session_defaults": True}
        with patch(
            "local_kb.operator_activation.validate_activation_readiness",
            return_value=_gate(repo_root),
        ), patch(
            "local_kb.operator_activation.build_installation_check",
            return_value=final_check,
        ):
            result = activate_all_for_current_machine(
                repo_root,
                codex_home,
                repo_root / "readiness.json",
            )
        assert result["ok"], result
        receipt_path = Path(result["receipt_path"])
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        proof_path = Path(
            next(iter(receipt["readiness"]["scheduled_production_refs"].values()))[
                "path"
            ]
        )
        proof_path.write_text("{}\n", encoding="utf-8")
        with patch(
            "local_kb.operator_activation.build_installation_check",
            return_value=final_check,
        ):
            validation = validate_operator_activation_receipt(
                repo_root,
                codex_home,
                receipt_path,
            )
        assert not validation["ok"]
        assert any(
            issue.startswith("operator-activation-scheduled-proof-stale:")
            for issue in validation["issues"]
        )
