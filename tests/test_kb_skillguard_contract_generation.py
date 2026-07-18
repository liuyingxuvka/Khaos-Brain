from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from local_kb.automation_contracts import (
    AUTOMATION_COMPLETION_CONTRACTS,
    SKILLGUARD_AUTOMATION_PROVIDER_ID,
    SKILLGUARD_AUTOMATION_RUNTIME_CAPABILITY_IDS,
    SKILLGUARD_AUTOMATION_RUNTIME_CONTRACT_ID,
    check_id,
    discover_pytest_nodes,
    evidence_test_node_ids,
    expected_obligation_ids,
    native_receipt_artifact_id,
    obligation_id,
    validate_completion_surface,
)
from local_kb.install import REPO_AUTOMATION_SPECS
from scripts.build_kb_automation_skillguard_contracts import build_contract_source
from scripts.check_kb_automation_skillguard_depth import build_report


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _control(skill_id: str, name: str) -> dict:
    return _load_json(
        REPO_ROOT / ".agents" / "skills" / skill_id / ".skillguard" / name
    )


def _automation_prompt(skill_id: str) -> str:
    return next(
        (
            str(row["prompt"])
            for row in REPO_AUTOMATION_SPECS
            if row["skill_name"] == skill_id
        ),
        "",
    )


class AutomationSkillGuardContractGenerationTests(unittest.TestCase):
    def test_generated_sources_are_exact_current_declared_check_contracts(self) -> None:
        legacy_depth_fields = {
            "coverage_universes",
            "dimensions",
            "calibration",
            "branch_calibration_requirements",
        }
        for skill_id in AUTOMATION_COMPLETION_CONTRACTS:
            with self.subTest(skill_id=skill_id):
                source = build_contract_source(skill_id)
                self.assertEqual(
                    source,
                    _control(skill_id, "contract-source.json"),
                )
                self.assertEqual(
                    source["closure_profiles"],
                    [
                        {
                            "profile_id": "enforced",
                            "required_obligation_ids": list(
                                expected_obligation_ids(skill_id)
                            ),
                        }
                    ],
                )
                depth = source["depth_profile"]
                self.assertEqual(depth["required_closure_profiles"], ["enforced"])
                self.assertEqual(depth["enforcement_level"], "enforced")
                self.assertFalse(depth["skillguard_adds_domain_route"])
                self.assertFalse(legacy_depth_fields & set(depth))
                self.assertEqual(
                    depth["profile_id"],
                    f"profile:{skill_id}:declared-check-supervision",
                )

    def test_provider_runtime_matches_current_skillguard_runtime(self) -> None:
        for skill_id in AUTOMATION_COMPLETION_CONTRACTS:
            with self.subTest(skill_id=skill_id):
                profile = build_contract_source(skill_id)["depth_profile"]
                provider = profile["provider_runtime"]
                self.assertEqual(
                    provider["provider_id"], SKILLGUARD_AUTOMATION_PROVIDER_ID
                )
                self.assertEqual(
                    provider["required_runtime_contract_id"],
                    SKILLGUARD_AUTOMATION_RUNTIME_CONTRACT_ID,
                )
                self.assertEqual(
                    tuple(provider["required_capability_ids"]),
                    SKILLGUARD_AUTOMATION_RUNTIME_CAPABILITY_IDS,
                )
                self.assertEqual(provider["required_enrollment_status"], "enrolled")
                self.assertTrue(provider["readiness_check_ids"])
                self.assertTrue(
                    set(provider["readiness_check_ids"]).issubset(
                        set(profile["native_check_ids"])
                    )
                )

    def test_target_owned_positive_and_shallow_checks_remain_executable(self) -> None:
        for skill_id in AUTOMATION_COMPLETION_CONTRACTS:
            with self.subTest(skill_id=skill_id, fixture="positive"):
                positive = build_report(skill_id, "positive")
                self.assertTrue(positive["ok"], positive)
                self.assertEqual(positive["observed_status"], "deep-pass")
                self.assertEqual(positive["failed_obligation_ids"], [])
            with self.subTest(skill_id=skill_id, fixture="shallow"):
                shallow = build_report(skill_id, "shallow")
                self.assertTrue(shallow["ok"], shallow)
                self.assertEqual(shallow["observed_status"], "shallow-blocked")
                self.assertTrue(shallow["failed_obligation_ids"])

    def test_fixture_checks_are_target_owned_and_not_skillguard_protocols(self) -> None:
        for skill_id in AUTOMATION_COMPLETION_CONTRACTS:
            source = build_contract_source(skill_id)
            checks = {row["check_id"]: row for row in source["checks"]}
            expected_route = f"route:{skill_id}:run"
            for case_kind in ("positive", "shallow"):
                with self.subTest(skill_id=skill_id, case_kind=case_kind):
                    row = checks[check_id(skill_id, f"depth-{case_kind}")]
                    self.assertEqual(row["native_route_id"], expected_route)
                    self.assertEqual(
                        row["evidence_domain_id"],
                        f"target:{skill_id}:fixture-calibration",
                    )
                    self.assertEqual(
                        row["args"],
                        [
                            "scripts/check_kb_automation_run_receipt.py",
                            "--skill",
                            skill_id,
                            "--phase",
                            "all",
                            "--fixture",
                            case_kind,
                            "--json",
                        ],
                    )
                    self.assertNotIn("behavior", row)
                    self.assertFalse(
                        {
                            "depth_evidence_protocol",
                            "calibration_evidence_protocol",
                        }
                        & set(row)
                    )

    def test_each_native_receipt_artifact_has_exact_target_validators(self) -> None:
        for skill_id, spec in AUTOMATION_COMPLETION_CONTRACTS.items():
            with self.subTest(skill_id=skill_id):
                source = build_contract_source(skill_id)
                artifacts = {
                    row["artifact_id"]: row for row in source["artifacts"]
                }
                native = artifacts[native_receipt_artifact_id(skill_id)]
                expected_validators = {
                    check_id(skill_id, "intake-runtime"),
                    check_id(skill_id, "native-runtime"),
                    check_id(skill_id, "terminal-runtime"),
                }
                self.assertEqual(
                    set(native["validator_check_ids"]), expected_validators
                )
                self.assertEqual(
                    set(native["covers_obligation_ids"]),
                    {
                        obligation_id(skill_id, str(row["suffix"]))
                        for row in spec["obligations"]
                        if str(row.get("evidence_source") or "native-receipt")
                        == "native-receipt"
                        and row["suffix"] != "depth-calibration"
                    },
                )

    def test_update_uses_one_enforced_profile_and_direct_native_closure(self) -> None:
        skill_id = "khaos-brain-update"
        source = build_contract_source(skill_id)
        profile = source["closure_profiles"][0]
        self.assertEqual(profile["profile_id"], "enforced")
        self.assertNotIn("route_branch_requirements", profile)
        self.assertEqual(
            source["depth_profile"]["native_route_ids"],
            ["route:khaos-brain-update:run"],
        )
        self.assertNotIn(
            check_id(skill_id, "finalization-runtime"),
            source["depth_profile"]["native_check_ids"],
        )
        self.assertNotIn(
            check_id(skill_id, "branch-terminal-runtime"),
            source["depth_profile"]["native_check_ids"],
        )
        self.assertNotIn(
            "artifact:khaos-brain-update:restoration-authorization",
            {row["artifact_id"] for row in source["artifacts"]},
        )

    def test_current_completion_validator_accepts_all_generated_surfaces(self) -> None:
        for skill_id in AUTOMATION_COMPLETION_CONTRACTS:
            with self.subTest(skill_id=skill_id):
                skill_root = REPO_ROOT / ".agents" / "skills" / skill_id
                findings = validate_completion_surface(
                    skill_id,
                    repo_root=REPO_ROOT,
                    automation_prompt=_automation_prompt(skill_id),
                    skill_text=(skill_root / "SKILL.md").read_text(encoding="utf-8"),
                    compiled_contract=_control(skill_id, "compiled-contract.json"),
                    check_manifest=_control(skill_id, "check-manifest.json"),
                )
                self.assertEqual(findings, [])

    def test_update_evidence_nodes_cover_authorization_restore_repause_and_current(self) -> None:
        resolved = evidence_test_node_ids(
            "khaos-brain-update", repo_root=REPO_ROOT
        )
        required = {
            "test_manual_check_marks_upgrading_only_with_explicit_request_and_closed_ui",
            "test_manual_update_uses_ff_only_and_closes_natively",
            "test_manual_update_restores_status_and_user_pause_independently",
            "test_consumer_assurance_failure_keeps_survivors_paused_and_marks_failed",
            "test_native_update_runner_keeps_operational_blockers_unfinished",
        }
        self.assertTrue(required.issubset(resolved), sorted(required - set(resolved)))

    def test_ast_discovery_ignores_comments_strings_nested_helpers_and_dead_branches(self) -> None:
        source = '''
# def test_comment_only(): pass
TEXT = "def test_string_only(): pass"
if False:
    def test_dead_branch():
        pass

def helper():
    def test_nested_helper():
        pass

async def test_async_top_level():
    pass

class TestSurface:
    async def test_async_method(self):
        pass
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_surface.py"
            path.write_text(source, encoding="utf-8")
            discovered = discover_pytest_nodes(
                path, relative_path="tests/test_surface.py"
            )
        self.assertEqual(
            discovered,
            {
                "test_async_top_level": (
                    "tests/test_surface.py::test_async_top_level",
                ),
                "test_async_method": (
                    "tests/test_surface.py::TestSurface::test_async_method",
                ),
            },
        )

    def test_every_declared_test_marker_resolves_to_one_exact_pytest_node(self) -> None:
        for skill_id in AUTOMATION_COMPLETION_CONTRACTS:
            with self.subTest(skill_id=skill_id):
                resolved = evidence_test_node_ids(skill_id, repo_root=REPO_ROOT)
                declared = {
                    str(marker)
                    for row in AUTOMATION_COMPLETION_CONTRACTS[skill_id][
                        "obligations"
                    ]
                    for marker in row["evidence_tests"]
                }
                self.assertEqual(set(resolved), declared)
                self.assertEqual(len(set(resolved.values())), len(resolved.values()))


if __name__ == "__main__":
    unittest.main()
