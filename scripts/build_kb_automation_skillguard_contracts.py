"""Build four automation bindings and one explicit-manual update binding.

The target obligation catalog lives in ``local_kb.automation_contracts`` and
the executable topology lives in the declared FlowGuard child model.  This
builder only emits the deterministic SkillGuard binding layer; the official
SkillGuard compiler still owns compiled-contract and check-manifest output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.automation_contracts import (  # noqa: E402
    AUTOMATION_COMPLETION_CONTRACTS,
    SKILLGUARD_AUTOMATION_PROVIDER_ID,
    SKILLGUARD_AUTOMATION_RUNTIME_CAPABILITY_IDS,
    SKILLGUARD_AUTOMATION_RUNTIME_CONTRACT_ID,
    check_id,
    expected_obligation_ids,
    native_receipt_artifact_id,
    obligation_id,
    obligation_ids_by_phase,
    step_id,
)


MODEL_PATHS = {
    "kb-sleep-maintenance": ".flowguard/kb_sleep_skill_contract_model.py",
    "kb-dream-pass": ".flowguard/kb_dream_skill_contract_model.py",
    "kb-organization-contribute": ".flowguard/kb_org_contribute_skill_contract_model.py",
    "kb-organization-maintenance": ".flowguard/kb_org_maintenance_skill_contract_model.py",
    "khaos-brain-update": ".flowguard/khaos_brain_update_skill_contract_model.py",
}

NATIVE_IMPLEMENTATION_PATHS = {
    "kb-sleep-maintenance": (
        "local_kb/lifecycle.py",
        "local_kb/candidate_lifecycle.py",
        "local_kb/calibration.py",
        "local_kb/logicguard_models.py",
        "local_kb/model_projection.py",
        "local_kb/model_maintenance.py",
        "local_kb/active_index.py",
        "local_kb/maintenance.py",
        "local_kb/maintenance_lanes.py",
    ),
    "kb-dream-pass": (
        "local_kb/dream.py",
        "local_kb/lifecycle.py",
        "local_kb/logicguard_models.py",
        "local_kb/model_projection.py",
        "local_kb/model_maintenance.py",
        "local_kb/maintenance_lanes.py",
    ),
    "kb-organization-contribute": (
        "local_kb/org_automation.py",
        "local_kb/org_outbox.py",
    ),
    "kb-organization-maintenance": (
        "local_kb/org_automation.py",
        "local_kb/org_maintenance.py",
    ),
    "khaos-brain-update": (
        "local_kb/software_update.py",
        "local_kb/install.py",
        "local_kb/transactional_install.py",
        "local_kb/maintenance_migration.py",
        "local_kb/logicguard_models.py",
        "local_kb/model_projection.py",
        "local_kb/model_maintenance.py",
        "local_kb/active_index.py",
        "local_kb/settings_migration.py",
        "local_kb/card_schema_migration.py",
        "local_kb/org_migration.py",
        "scripts/run_khaos_brain_manual_update.py",
    ),
}

SKILLGUARD_RUNTIME_PROVIDER_ID = SKILLGUARD_AUTOMATION_PROVIDER_ID
SKILLGUARD_RUNTIME_CONTRACT_ID = SKILLGUARD_AUTOMATION_RUNTIME_CONTRACT_ID
SKILLGUARD_RUNTIME_CAPABILITY_IDS = SKILLGUARD_AUTOMATION_RUNTIME_CAPABILITY_IDS


def _native_route_id(skill_id: str, *, phase: str = "") -> str:
    del phase
    return f"route:{skill_id}:run"


def _calibration_check(skill_id: str, case_kind: str, covers: list[str]) -> dict[str, Any]:
    kind = "depth-positive" if case_kind == "positive" else "depth-shallow"
    row = _check(
        skill_id,
        kind,
        covers,
        command="python",
        args=[
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
    row.update(
        {
            "native_route_id": _native_route_id(skill_id),
            "evidence_domain_id": f"target:{skill_id}:fixture-calibration",
        }
    )
    return row


def _check(
    skill_id: str,
    kind: str,
    covers: list[str],
    *,
    command: str | None = None,
    args: list[str] | None = None,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "check_id": check_id(skill_id, kind),
        "kind": "model_assertion" if command is None else "command",
        "evidence_class": "hard",
        "covers_obligation_ids": covers,
        "timeout_seconds": timeout_seconds,
        "execution_owner_id": f"owner:{skill_id}:{kind}",
        "semantic_check_id": f"semantic:{skill_id}:{kind}",
        "maintenance_unit_id": f"unit:{skill_id}",
        "member_skill_id": skill_id,
        "evidence_subject_id": f"subject:{check_id(skill_id, kind)}",
    }
    if command is not None:
        row.update(
            {
                "command": command,
                "args": args or [],
                "cwd_token": "repository_root",
                "expected": {"exit_code": 0},
            }
        )
    return row


def build_contract_source(skill_id: str) -> dict[str, Any]:
    spec = AUTOMATION_COMPLETION_CONTRACTS[skill_id]
    phases = obligation_ids_by_phase(skill_id)
    all_ids = list(expected_obligation_ids(skill_id))
    depth_id = obligation_id(skill_id, "depth-calibration")
    verify_ids = [item for item in phases.get("verify", ()) if item != depth_id]
    shared_paths = (
        "local_kb/automation_contracts.py",
        "local_kb/automation_runtime.py",
        "local_kb/process_control.py",
        "local_kb/install.py",
        "scripts/build_kb_automation_skillguard_contracts.py",
        "scripts/check_kb_automation_run_receipt.py",
        "scripts/check_kb_skillguard.py",
        "scripts/run_kb_automation.py",
        "tests/test_kb_automation_skillguard.py",
    )
    implementation_paths = list(
        dict.fromkeys(
            (
                f".agents/skills/{skill_id}",
                MODEL_PATHS[skill_id],
                str(spec["entrypoint_path"]),
                *NATIVE_IMPLEMENTATION_PATHS[skill_id],
                *[str(item) for item in spec["native_test_files"]],
                *shared_paths,
            )
        )
    )
    positive_check = _calibration_check(skill_id, "positive", [depth_id])
    shallow_check = _calibration_check(skill_id, "shallow", [depth_id])
    intake_check = _check(
        skill_id,
        "intake-runtime",
        list(phases.get("intake", ())),
        command="python",
        args=[
            "scripts/check_kb_automation_run_receipt.py",
            "--skill",
            skill_id,
            "--phase",
            "intake",
            "--json",
        ],
        timeout_seconds=120,
    )
    native_check = _check(
        skill_id,
        "native-runtime",
        list(phases.get("execute", ())),
        command="python",
        args=[
            "scripts/check_kb_automation_run_receipt.py",
            "--skill",
            skill_id,
            "--phase",
            "execute",
            "--json",
        ],
        timeout_seconds=120,
    )
    terminal_check = _check(
        skill_id,
        "terminal-runtime",
        verify_ids,
        command="python",
        args=[
            "scripts/check_kb_automation_run_receipt.py",
            "--skill",
            skill_id,
            "--phase",
            "verify",
            "--json",
        ],
        timeout_seconds=120,
    )
    checks = [
        intake_check,
        native_check,
        terminal_check,
        positive_check,
        shallow_check,
    ]
    native_obligation_ids = [
        obligation_id(skill_id, str(row["suffix"]))
        for row in spec["obligations"]
        if str(row.get("evidence_source") or "native-receipt") == "native-receipt"
        and str(row.get("suffix") or "") != "depth-calibration"
    ]
    native_validator_check_ids = [
        check_id(skill_id, kind)
        for phase, kind in (
            ("intake", "intake-runtime"),
            ("execute", "native-runtime"),
            ("verify", "terminal-runtime"),
        )
        if phases.get(phase)
    ]
    native_artifact_id = native_receipt_artifact_id(skill_id)
    artifacts: list[dict[str, Any]] = [
        {
            "artifact_id": native_artifact_id,
            "kind": "native_output",
            "producer_step_id": step_id(skill_id, "execute"),
            "validators": [
                "immutable-receipt",
                "run-id-bound",
                "receipt-hash-bound",
                "target-owned-native-output",
            ],
            "validator_check_ids": native_validator_check_ids,
            "covers_obligation_ids": native_obligation_ids,
            "claim_boundary": (
                "This witness binds the immutable target-owned native receipt to its exact run, "
                "checks, and non-calibration native obligations."
            ),
        }
    ]
    native_route_ids = [
        f"route:{skill_id}:run"
    ]
    claim_boundary = (
        f"SkillGuard supervises the complete native {skill_id} maintenance unit, "
        "its target-specific obligations, and the sole current enforced closure. "
        "It does not ship with or execute on the consumer machine."
    )
    closure_profiles = [
        {"profile_id": "enforced", "required_obligation_ids": all_ids},
    ]
    source = {
        "schema_version": "skillguard.contract_source.v2",
        "skill_id": skill_id,
        "repository_role": "skill_maintainer_source",
        "maintenance_unit_id": f"unit:{skill_id}",
        "member_skill_ids": [skill_id],
        "consumer_projection": {
            "prohibited_path_prefixes": [".skillguard/"],
            "prohibited_prompt_tokens": [
                "SkillGuard",
                ".skillguard",
                "skillguard.py",
            ],
            "projection_id": "projection:consumer-distribution",
            "release_manifest_path": "consumer-release.json",
        },
        "integration_mode": "native-integrated",
        "native_route_owner": skill_id,
        "native_route_bindings": [
            {
                "binding_id": f"native:{skill_id}:run",
                "native_route_id": f"route:{skill_id}:run",
                "required_before_closure": True,
                "source": f".agents/skills/{skill_id}/SKILL.md",
            }
        ],
        "native_check_bindings": [
            {
                "binding_id": f"native-check:{row['check_id'].removeprefix('check:')}",
                "native_check_id": row["check_id"],
                "evidence_source": "scripts/check_kb_automation_run_receipt.py",
                "required": True,
            }
            for row in checks
        ],
        "default_route_id": f"route:{skill_id}:run",
        "may_define_parallel_execution_route": False,
        "may_define_skillguard_runtime_route": False,
        "model_id": f"khaos-brain.{skill_id}.executable-contract.v2",
        "model_path": MODEL_PATHS[skill_id],
        "confirmed": True,
        "release_eligible": False,
        "implementation_paths": implementation_paths,
        "projection_consumers": [
            {
                "consumer_id": f"projection:{skill_id}:target-runtime-sources",
                "kind": "target_runtime_source",
                "input_selectors": [{"kind": "role", "role": "runtime_source"}],
            },
            {
                "consumer_id": f"projection:{skill_id}:target-tests",
                "kind": "target_test_source",
                "input_selectors": [{"kind": "role", "role": "test_dev"}],
            },
        ],
        "step_bindings": [
            {
                "step_id": step_id(skill_id, "intake"),
                "action": {
                    "kind": "inventory",
                    "summary": "Load the target-owned inputs and prove every intake obligation before mutation.",
                },
                "check_ids": [
                    check_id(skill_id, "intake-runtime"),
                ],
                "output_artifact_ids": [],
            },
            {
                "step_id": step_id(skill_id, "execute"),
                "action": {
                    "kind": "native",
                    "summary": "Run the native maintenance owner through every declared execution branch.",
                },
                "check_ids": [
                    check_id(skill_id, "native-runtime"),
                ],
                "output_artifact_ids": [native_artifact_id],
            },
            {
                "step_id": step_id(skill_id, "verify"),
                "action": {
                    "kind": "validator",
                    "summary": "Require the current terminal receipt plus positive and shallow target-owned checks before closure.",
                },
                "check_ids": [
                    check_id(skill_id, "terminal-runtime"),
                    check_id(skill_id, "depth-positive"),
                    check_id(skill_id, "depth-shallow"),
                ],
                "output_artifact_ids": [],
            },
        ],
        "checks": checks,
        "artifacts": artifacts,
        "closure_profiles": closure_profiles,
        "judgment_rubrics": [],
        "depth_profile": {
            "schema_version": "skillguard.depth_profile.v2",
            "profile_id": f"profile:{skill_id}:declared-check-supervision",
            "target_skill_id": skill_id,
            "integration_mode": "native-integrated",
            "native_owner_id": skill_id,
            "native_route_ids": native_route_ids,
            "native_check_ids": [
                check_id(skill_id, "intake-runtime"),
                check_id(skill_id, "native-runtime"),
                check_id(skill_id, "terminal-runtime"),
                check_id(skill_id, "depth-positive"),
                check_id(skill_id, "depth-shallow"),
            ],
            "skillguard_adds_domain_route": False,
            "enforcement_level": "enforced",
            "required_closure_profiles": ["enforced"],
            "provider_runtime": {
                "provider_id": SKILLGUARD_RUNTIME_PROVIDER_ID,
                "required_runtime_contract_id": SKILLGUARD_RUNTIME_CONTRACT_ID,
                "required_capability_ids": list(SKILLGUARD_RUNTIME_CAPABILITY_IDS),
                "required_enrollment_status": "enrolled",
                "readiness_check_ids": [
                    check_id(skill_id, "intake-runtime"),
                    check_id(skill_id, "native-runtime"),
                    check_id(skill_id, "terminal-runtime"),
                    check_id(skill_id, "depth-positive"),
                    check_id(skill_id, "depth-shallow"),
                ],
            },
            "claim_boundary": (
                "Only exact current receipts for the target skill's declared checks are supervised. "
                "The target skill retains all domain judgment, including positive/shallow behavior "
                "and direct native completion."
            ),
        },
        "claim_boundary": claim_boundary,
    }
    return source


def write_contract_source(skill_id: str) -> Path:
    path = REPO_ROOT / ".agents" / "skills" / skill_id / ".skillguard" / "contract-source.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_contract_source(skill_id), ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = []
    for skill_id in AUTOMATION_COMPLETION_CONTRACTS:
        expected = json.dumps(
            build_contract_source(skill_id), ensure_ascii=False, indent=2, sort_keys=False
        ) + "\n"
        path = REPO_ROOT / ".agents" / "skills" / skill_id / ".skillguard" / "contract-source.json"
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        matches = current == expected
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8")
            matches = True
        rows.append({"skill_id": skill_id, "path": str(path), "matches": matches})
    report = {
        "ok": all(row["matches"] for row in rows),
        "mode": "check" if args.check else "write",
        "skills": rows,
        "claim_boundary": "Deterministic current SkillGuard maintenance binding generation only; official compilation and executed supervision remain separate gates.",
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("PASS" if report["ok"] else "FAIL")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
