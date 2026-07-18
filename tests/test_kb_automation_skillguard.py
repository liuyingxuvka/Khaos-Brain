from __future__ import annotations

import json
from pathlib import Path

from local_kb.automation_contracts import (
    AUTOMATION_COMPLETION_CONTRACTS,
    evidence_test_node_ids,
)
from local_kb.install import (
    REPO_AUTOMATION_SPECS,
    maintenance_skill_source_dir,
)
from local_kb.transactional_install import consumer_skill_manifest
from scripts.build_kb_automation_skillguard_contracts import build_contract_source
from scripts.check_kb_automation_skillguard_depth import build_report


REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHOR_TOKENS = ("skillguard", ".skillguard", "skillguard.py")


def _control(skill_id: str, name: str) -> dict:
    path = (
        REPO_ROOT
        / ".agents"
        / "skills"
        / skill_id
        / ".skillguard"
        / name
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_deep(skill_id: str) -> None:
    report = build_report(skill_id, "positive")
    assert report["ok"], report
    assert report["observed_status"] == "deep-pass"
    assert report["failed_obligation_ids"] == []


def _assert_shallow_blocked(skill_id: str) -> None:
    report = build_report(skill_id, "shallow")
    assert report["ok"], report
    assert report["observed_status"] == "shallow-blocked"
    assert report["failed_obligation_ids"]


def test_sleep_contract_is_deep_and_current() -> None:
    _assert_deep("kb-sleep-maintenance")


def test_sleep_shallow_contract_is_rejected() -> None:
    _assert_shallow_blocked("kb-sleep-maintenance")


def test_dream_contract_is_deep_and_current() -> None:
    _assert_deep("kb-dream-pass")


def test_dream_shallow_contract_is_rejected() -> None:
    _assert_shallow_blocked("kb-dream-pass")


def test_org_contribute_contract_is_deep_and_current() -> None:
    _assert_deep("kb-organization-contribute")


def test_org_contribute_shallow_contract_is_rejected() -> None:
    _assert_shallow_blocked("kb-organization-contribute")


def test_org_maintenance_contract_is_deep_and_current() -> None:
    _assert_deep("kb-organization-maintenance")


def test_org_maintenance_shallow_contract_is_rejected() -> None:
    _assert_shallow_blocked("kb-organization-maintenance")


def test_update_contract_is_deep_and_current() -> None:
    _assert_deep("khaos-brain-update")


def test_update_shallow_contract_is_rejected() -> None:
    _assert_shallow_blocked("khaos-brain-update")


def test_each_skill_is_one_independent_maintenance_unit() -> None:
    observed_units: set[str] = set()
    observed_owners: set[str] = set()
    observed_subjects: set[str] = set()
    observed_semantics: set[str] = set()
    for skill_id in AUTOMATION_COMPLETION_CONTRACTS:
        source = build_contract_source(skill_id)
        expected_unit = f"unit:{skill_id}"
        assert source["repository_role"] == "skill_maintainer_source"
        assert source["maintenance_unit_id"] == expected_unit
        assert source["member_skill_ids"] == [skill_id]
        assert expected_unit not in observed_units
        observed_units.add(expected_unit)
        for row in source["checks"]:
            assert row["maintenance_unit_id"] == expected_unit
            assert row["member_skill_id"] == skill_id
            assert row["execution_owner_id"] not in observed_owners
            assert row["evidence_subject_id"] not in observed_subjects
            assert row["semantic_check_id"] not in observed_semantics
            observed_owners.add(row["execution_owner_id"])
            observed_subjects.add(row["evidence_subject_id"])
            observed_semantics.add(row["semantic_check_id"])


def test_no_two_maintenance_units_claim_the_same_test_evidence() -> None:
    owners: dict[str, str] = {}
    for skill_id in AUTOMATION_COMPLETION_CONTRACTS:
        resolved = evidence_test_node_ids(skill_id, repo_root=REPO_ROOT)
        for test_name, node_id in resolved.items():
            assert node_id not in owners, (
                f"{node_id} is claimed by both {owners[node_id]} and {skill_id}"
            )
            owners[node_id] = skill_id


def test_generated_author_contracts_are_current_and_single_skill() -> None:
    for skill_id in AUTOMATION_COMPLETION_CONTRACTS:
        source = build_contract_source(skill_id)
        assert source == _control(skill_id, "contract-source.json")
        compiled = _control(skill_id, "compiled-contract.json")
        manifest = _control(skill_id, "check-manifest.json")
        assert compiled["skill_id"] == skill_id
        assert manifest["skill_id"] == skill_id
        assert compiled["maintenance_unit_id"] == f"unit:{skill_id}"
        assert manifest["maintenance_unit_id"] == f"unit:{skill_id}"
        assert compiled["member_skill_ids"] == [skill_id]
        assert manifest["member_skill_ids"] == [skill_id]


def test_consumer_skill_projections_contain_no_author_control_plane() -> None:
    for skill_id in AUTOMATION_COMPLETION_CONTRACTS:
        source_root = maintenance_skill_source_dir(REPO_ROOT, skill_id)
        manifest = consumer_skill_manifest(source_root)
        assert manifest["file_count"] > 0
        for row in manifest["files"]:
            relative = str(row["path"])
            assert not relative.startswith(".skillguard/")
            text = (source_root / relative).read_text(
                encoding="utf-8", errors="replace"
            )
            lowered = text.lower()
            for token in AUTHOR_TOKENS:
                assert token not in lowered, f"{skill_id}:{relative}:{token}"


def test_scheduled_prompts_use_only_target_owned_entrypoints() -> None:
    for row in REPO_AUTOMATION_SPECS:
        prompt = str(row["prompt"])
        lowered = prompt.lower()
        assert "scripts/run_kb_automation.py" in prompt
        assert "target-owned" in lowered
        assert "native terminal receipt" in lowered
        for token in AUTHOR_TOKENS:
            assert token not in lowered


def test_consumer_entrypoints_do_not_import_or_invoke_author_tools() -> None:
    for relative in (
        "scripts/run_kb_automation.py",
        "scripts/run_khaos_brain_manual_update.py",
        "scripts/check_consumer_install_assurance.py",
    ):
        lowered = (REPO_ROOT / relative).read_text(
            encoding="utf-8", errors="replace"
        ).lower()
        for token in AUTHOR_TOKENS:
            assert token not in lowered, f"{relative}:{token}"
