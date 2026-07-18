"""Shared FlowGuard export for one independent Khaos Brain maintenance skill."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import flowguard


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.automation_contracts import (  # noqa: E402
    AUTOMATION_COMPLETION_CONTRACTS,
    expected_obligation_ids,
    obligation_id,
    step_id,
)


def build_contract_model(skill_id: str, purpose: str) -> dict[str, Any]:
    """Describe one target-owned route with no author-side runtime stage."""

    spec = AUTOMATION_COMPLETION_CONTRACTS[skill_id]
    route_id = f"route:{skill_id}:run"
    function_id = f"function:{skill_id}:run"
    intake = step_id(skill_id, "intake")
    execute = step_id(skill_id, "execute")
    verify = step_id(skill_id, "verify")
    success = f"step:{skill_id}:success"
    blocked = f"step:{skill_id}:blocked"
    obligations = [
        {
            "obligation_id": obligation_id(skill_id, str(row["suffix"])),
            "invariant_id": f"invariant:{skill_id}:{row['suffix']}",
            "owner_step_ids": [step_id(skill_id, str(row["phase"]))],
            "required": True,
            "description": str(row["summary"]),
        }
        for row in spec["obligations"]
    ]
    return {
        "schema_version": "skillguard.flowguard_model_export.v2",
        "flowguard_schema_version": str(flowguard.SCHEMA_VERSION),
        "model_id": f"khaos-brain.{skill_id}.executable-contract.v2",
        "parent_model_id": "khaos-brain.consumer-independent-maintenance.v3",
        "maintenance_unit_id": f"unit:{skill_id}",
        "member_skill_ids": [skill_id],
        "consumer_projection": {
            "author_control_allowed": False,
            "prohibited_paths": [".skillguard/"],
            "prohibited_tokens": ["SkillGuard", ".skillguard", "skillguard.py"],
        },
        "claim_boundary": (
            f"The {skill_id} consumer route owns intake, execution, verification, "
            "and terminal completion. Author-side certification is not a route, "
            "handoff, dependency, receipt, or installed projection."
        ),
        "functions": [
            {
                "function_id": function_id,
                "business_intent": purpose,
                "owner_id": skill_id,
                "route_ids": [route_id],
                "signature": "Input x State -> Set(Output x State)",
            }
        ],
        "routes": [
            {
                "route_id": route_id,
                "function_id": function_id,
                "owner_id": skill_id,
                "step_ids": [intake, execute, verify, success, blocked],
                "success_terminal_step_id": success,
                "blocked_terminal_step_id": blocked,
                "handoffs": [],
            }
        ],
        "steps": [
            {
                "step_id": intake,
                "route_id": route_id,
                "owner_id": skill_id,
                "action_kind": "inventory",
                "prerequisite_step_ids": [],
                "terminal_kind": "",
            },
            {
                "step_id": execute,
                "route_id": route_id,
                "owner_id": skill_id,
                "action_kind": "native",
                "prerequisite_step_ids": [intake],
                "terminal_kind": "",
            },
            {
                "step_id": verify,
                "route_id": route_id,
                "owner_id": skill_id,
                "action_kind": "validator",
                "prerequisite_step_ids": [execute],
                "terminal_kind": "",
            },
            {
                "step_id": success,
                "route_id": route_id,
                "owner_id": skill_id,
                "action_kind": "terminal",
                "prerequisite_step_ids": [verify],
                "terminal_kind": "success",
            },
            {
                "step_id": blocked,
                "route_id": route_id,
                "owner_id": skill_id,
                "action_kind": "terminal",
                "prerequisite_step_ids": [],
                "terminal_kind": "blocked",
            },
        ],
        "invariant_ids": [row["invariant_id"] for row in obligations],
        "obligations": obligations,
    }


def review_current_model(model: dict[str, Any]) -> dict[str, Any]:
    member_ids = list(model.get("member_skill_ids") or [])
    skill_id = str(member_ids[0]) if len(member_ids) == 1 else ""
    expected = set(expected_obligation_ids(skill_id)) if skill_id else set()
    actual = {
        str(row.get("obligation_id") or "")
        for row in model.get("obligations", [])
        if isinstance(row, dict)
    }
    route_steps = {
        str(item)
        for route in model.get("routes", [])
        if isinstance(route, dict)
        for item in route.get("step_ids", [])
    }
    owner_steps = {
        str(item)
        for row in model.get("obligations", [])
        if isinstance(row, dict)
        for item in row.get("owner_step_ids", [])
    }
    consumer = model.get("consumer_projection")
    issues: list[str] = []
    if not skill_id:
        issues.append("single-member-maintenance-unit-required")
    if actual != expected:
        issues.append(f"obligation-set-mismatch:{sorted(expected ^ actual)}")
    if len(actual) != len(model.get("obligations", [])):
        issues.append("duplicate-or-empty-obligation-id")
    if not owner_steps.issubset(route_steps):
        issues.append(f"orphan-obligation-steps:{sorted(owner_steps - route_steps)}")
    if not isinstance(consumer, dict) or consumer.get("author_control_allowed") is not False:
        issues.append("consumer-independence-not-declared")
    if any(route.get("handoffs") for route in model.get("routes", [])):
        issues.append("cross-control-plane-handoff-present")
    return {
        "ok": not issues,
        "skill_id": skill_id,
        "maintenance_unit_id": str(model.get("maintenance_unit_id") or ""),
        "obligation_count": len(actual),
        "issues": issues,
        "flowguard_schema_version": str(flowguard.SCHEMA_VERSION),
        "claim_boundary": (
            "Single-skill topology and consumer-independence model only; "
            "executed checks remain separate evidence."
        ),
    }


def run_current_model_checks(model: dict[str, Any]) -> int:
    report = review_current_model(model)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ok"] else 1
