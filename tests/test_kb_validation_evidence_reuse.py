from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile

from scripts import check_kb_model_test_alignment as alignment


def _manifest(proof: Path) -> dict:
    proof_hash = hashlib.sha256(proof.read_bytes()).hexdigest()

    def receipt(name: str, *, junit: dict | None = None) -> dict:
        return {
            "receipt_id": f"validation:{name}:identity",
            "name": name,
            "terminal_status": "passed",
            "ok": True,
            "timed_out": False,
            "command": ["python", name],
            "input_fingerprints": {"source": "source", "verifier": "verifier"},
            "inventory_revision": "inventory",
            "proof_artifact_ref": {"path": str(proof), "sha256": proof_hash},
            "junit": junit or {},
        }

    full_junit = {
        "passed_node_ids": [
            "tests/test_kb_skillguard_contract_generation.py::AutomationSkillGuardContractGenerationTests::test_target_native_calibration_uses_real_obligation_ids_and_gap"
        ]
    }
    return {
        "schema_version": "khaos-brain.validation-evidence.v1",
        "run_id": "run-1",
        "inventory_revision": "inventory",
        "source_snapshot_before": {"digest": "source"},
        "source_stable_during_leaf_execution": True,
        "verifier_fingerprint": {"digest": "verifier"},
        "duplicate_exact_executions": [],
        "entries": {
            "full_regression": receipt("full_regression", junit=full_junit),
            "flowguard_models": receipt("flowguard_models"),
            "flowguard_meshes": receipt("flowguard_meshes"),
            "skillguard_source_install_parity": receipt(
                "skillguard_source_install_parity"
            ),
            "skillguard_source_assurance": receipt("skillguard_source_assurance"),
        },
    }


def test_alignment_consumes_four_leaf_receipts_without_running_commands() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        proof = Path(temp_dir) / "proof.json"
        proof.write_text("{}", encoding="utf-8")
        runs, findings = alignment._manifest_runs(_manifest(proof))

    assert not findings
    assert set(runs) == set(alignment._RUN_ALIASES)
    assert {
        row["producer_name"] for row in runs.values()
    } == {
        "full_regression",
        "flowguard_models",
        "flowguard_meshes",
        "skillguard_source_assurance",
    }


def test_alignment_rejects_a_changed_proof_artifact() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        proof = Path(temp_dir) / "proof.json"
        proof.write_text("{}", encoding="utf-8")
        manifest = _manifest(proof)
        proof.write_text('{"changed": true}', encoding="utf-8")
        runs, findings = alignment._manifest_runs(manifest)

    assert findings
    assert all(not row["ok"] for row in runs.values())
    assert any("proof_artifact_missing_or_changed" in item for item in findings)


def test_target_parameter_must_match_the_exact_junit_case() -> None:
    run = {
        "junit": {
            "passed_node_ids": [
                "tests/test_kb_automation_skillguard.py::test_target_native_calibration_uses_real_obligation_ids_and_gap[kb-sleep-maintenance]",
                "tests/test_kb_automation_skillguard.py::test_target_native_calibration_uses_real_obligation_ids_and_gap[kb-dream-pass]",
            ]
        }
    }
    target = (
        "tests/test_kb_automation_skillguard.py::"
        "test_target_native_calibration_uses_real_obligation_ids_and_gap"
    )

    assert alignment._matching_passed_nodes(
        run, target, parameter="kb-dream-pass"
    ) == (target + "[kb-dream-pass]",)
    assert not alignment._matching_passed_nodes(
        run, target, parameter="khaos-brain-update"
    )


def test_unknown_alignment_run_is_a_failed_gate_not_an_exception(monkeypatch) -> None:
    monkeypatch.setattr(
        alignment,
        "OBLIGATIONS",
        (
            {
                "id": "req.test.unknown-run",
                "path": "local_kb/search.py",
                "symbol": "search_multi_source_entries",
                "test": "tests/test_multi_source_search.py::missing",
                "run_name": "not-a-declared-logical-owner",
            },
        ),
    )

    report = alignment._alignment_report({})

    assert report.ok is False


def test_archive_prune_same_class_evidence_is_cross_platform() -> None:
    obligation = next(
        item
        for item in alignment.OBLIGATIONS
        if item["id"] == "req.history.archive-prune-index"
    )

    assert obligation["same_class_test"] == (
        "tests/test_kb_history_migration.py::KbHistoryMigrationTests::"
        "test_migration_resumes_cold_archives_prunes_and_is_idempotent"
    )
    assert "windows_long_managed_paths" not in obligation["same_class_test"]
