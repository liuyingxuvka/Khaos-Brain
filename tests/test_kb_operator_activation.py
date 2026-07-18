from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from local_kb.automation_runtime import content_hash
from local_kb.install import MAINTENANCE_SKILL_NAMES, REPO_AUTOMATION_SPECS
from local_kb.operator_activation import (
    MANUAL_ONLY_SKILL_IDS,
    REQUIRED_READINESS_CHECKS,
    SCHEDULED_SKILL_IDS,
    SKILL_INVENTORY_SCHEMA_VERSION,
    activate_all_for_current_machine,
    installation_currentness_projection,
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
    aggregate = repo_root / ".local" / "assurance" / "readiness.json"
    aggregate.write_text("{}\n", encoding="utf-8")
    return {
        "ok": True,
        "issues": [],
        "binding": {
            "aggregate_receipt_path": str(aggregate),
            "aggregate_receipt_sha256": hashlib.sha256(
                aggregate.read_bytes()
            ).hexdigest(),
            "evidence_manifest_path": str(evidence),
            "evidence_manifest_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            "source_digest": "source",
            "verifier_digest": "verifier",
            "skill_inventory": {
                "schema_version": SKILL_INVENTORY_SCHEMA_VERSION,
                "maintained_skill_ids": sorted(MAINTENANCE_SKILL_NAMES),
                "scheduled_skill_ids": sorted(SCHEDULED_SKILL_IDS),
                "manual_only_skill_ids": sorted(MANUAL_ONLY_SKILL_IDS),
            },
            "maintained_skill_refs": {
                skill_id: {
                    "maintenance_unit_id": f"unit:{skill_id}",
                    "consumer_projection_digest": f"digest:{skill_id}",
                    "consumer_file_count": 1,
                }
                for skill_id in MAINTENANCE_SKILL_NAMES
            },
        },
    }


def test_activation_gate_requires_exact_current_aggregate_and_four_scheduled_terminals() -> None:
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
        for skill_id in MAINTENANCE_SKILL_NAMES:
            skills[skill_id] = {
                "ok": True,
                "skill_id": skill_id,
                "maintenance_unit_id": f"unit:{skill_id}",
                "consumer_projection": {
                    "ok": True,
                    "manifest_digest": f"digest:{skill_id}",
                    "file_count": 1,
                },
            }
        checks = {check_id: {"ok": True} for check_id in REQUIRED_READINESS_CHECKS}
        checks["author_contract_assurance"] = {
            "ok": True,
            "json_payload": {
                "schema_version": "khaos-brain.skill-author-maintenance.v1",
                "ok": True,
                "source_only": True,
                "skills": skills,
            },
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
        assert set(
            result["binding"]["skill_inventory"]["maintained_skill_ids"]
        ) == set(MAINTENANCE_SKILL_NAMES)
        assert set(
            result["binding"]["skill_inventory"]["scheduled_skill_ids"]
        ) == {str(spec["skill_name"]) for spec in REPO_AUTOMATION_SPECS}
        assert result["binding"]["skill_inventory"]["manual_only_skill_ids"] == [
            "khaos-brain-update"
        ]


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


def test_installation_identity_ignores_runtime_migration_diagnostics_only() -> None:
    first = {
        "ok": True,
        "repo_root": "repo",
        "manifest_repo_root": "repo",
        "maintenance_skill_checks": [{"name": "kb-sleep-maintenance"}],
        "automation_checks": [{"id": "kb-sleep", "issues": []}],
        "issues": [],
        "warnings": [],
        "history_migration_required": True,
        "history_migration_check": {
            "ok": True,
            "migration_id": "migration-current",
            "maintenance_state": {"committed": True, "phase": "committed"},
            "journal": {"status": "committed"},
            "receipt": {
                "status": "committed",
                "receipt_hash": "migration-receipt",
            },
            "validation": {
                "ok": True,
                "runtime_diagnostic": "first-pass",
            },
        },
        "upgrade_assurance_required": True,
        "upgrade_assurance": {
            "ok": True,
            "evidence_run_id": "run-current",
            "failed_checks": [],
            "source_snapshot_after": {"digest": "source"},
            "verifier_fingerprint": {"digest": "verifier"},
        },
    }
    second = json.loads(json.dumps(first))
    second["history_migration_check"]["validation"]["runtime_diagnostic"] = (
        "second-pass"
    )

    first_projection = installation_currentness_projection(first)
    second_projection = installation_currentness_projection(second)
    assert first_projection == second_projection
    assert content_hash(first_projection) == content_hash(second_projection)

    second["history_migration_check"]["receipt"]["receipt_hash"] = "changed"
    assert installation_currentness_projection(first) != (
        installation_currentness_projection(second)
    )


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


def test_current_machine_override_repauses_group_when_final_check_exhausts_memory() -> None:
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
            side_effect=MemoryError("injected"),
        ):
            result = activate_all_for_current_machine(
                repo_root,
                codex_home,
                repo_root / "readiness.json",
            )

        assert not result["ok"]
        assert result["status"] == "install-check-exception-repaused"
        assert result["error"] == "MemoryError:injected"
        assert result["pause"]["ok"]
        for spec in REPO_AUTOMATION_SPECS:
            text = (
                codex_home
                / "automations"
                / str(spec["id"])
                / "automation.toml"
            ).read_text(encoding="utf-8")
            assert 'status = "PAUSED"' in text


def test_current_activation_receipt_rejects_ambiguous_skill_inventory() -> None:
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
        receipt["readiness"]["skill_inventory"]["scheduled_skill_ids"] = sorted(
            MAINTENANCE_SKILL_NAMES
        )
        receipt["readiness"]["skill_inventory"]["manual_only_skill_ids"] = []
        unsigned = dict(receipt)
        unsigned.pop("receipt_hash")
        receipt["receipt_hash"] = content_hash(unsigned)
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with patch(
            "local_kb.operator_activation.build_installation_check",
            return_value=final_check,
        ), patch(
            "local_kb.operator_activation.validate_activation_readiness",
            return_value=_gate(repo_root),
        ):
            validation = validate_operator_activation_receipt(
                repo_root,
                codex_home,
                receipt_path,
            )
        assert not validation["ok"]
        assert any(
            "activation-skill-inventory" in issue
            for issue in validation["issues"]
        )
