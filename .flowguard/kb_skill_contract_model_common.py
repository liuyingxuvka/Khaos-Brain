"""Shared FlowGuard export builder for the surviving Chaos Brain Skills."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import flowguard

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.automation_contracts import (
    AUTOMATION_COMPLETION_CONTRACTS,
    expected_obligation_ids,
    obligation_id,
    step_id,
)


UPDATE_SKILL_ID = "khaos-brain-update"
UPDATE_AUTHORIZE_ROUTE_ID = "route:khaos-brain-update:authorize"
UPDATE_FINALIZE_ROUTE_ID = "route:khaos-brain-update:finalize"
UPDATE_FINALIZATION_OBLIGATION_ID = (
    "obligation:khaos-brain-update:staged-restoration-authorization"
)
UPDATE_FINALIZE_STEP_ID = "step:khaos-brain-update:finalize"


def _build_update_contract_model(purpose: str) -> dict[str, Any]:
    """Export two honest update routes with no pre-restoration completion path."""

    skill_id = UPDATE_SKILL_ID
    spec = AUTOMATION_COMPLETION_CONTRACTS[skill_id]
    authorize_function_id = "function:khaos-brain-update:authorize"
    finalize_function_id = "function:khaos-brain-update:finalize"
    intake = step_id(skill_id, "intake")
    execute = step_id(skill_id, "execute")
    verify = step_id(skill_id, "verify")
    auth_success = "step:khaos-brain-update:auth-success"
    auth_blocked = "step:khaos-brain-update:auth-blocked"
    final_success = "step:khaos-brain-update:final-success"
    final_blocked = "step:khaos-brain-update:final-blocked"
    obligation_rows: list[dict[str, Any]] = []
    for row in spec["obligations"]:
        suffix = str(row["suffix"])
        if suffix in {
            "post-restoration-finalization",
            "staged-restoration-authorization",
        }:
            obligation_rows.append(
                {
                    "obligation_id": UPDATE_FINALIZATION_OBLIGATION_ID,
                    "invariant_id": "invariant:khaos-brain-update:staged-restoration-authorization",
                    "owner_step_ids": [UPDATE_FINALIZE_STEP_ID],
                    "required": True,
                    "conditional": True,
                    "description": (
                        "Bind the original native receipt and non-terminal declared-check authorization receipt to an "
                        "immutable staged-restoration authorization containing exact target states, "
                        "user-pause bits, planned automation.toml hashes, and the deferred install "
                        "check. Reconcile the composed authorize+finalize checks in the sole enforced "
                        "closure while all five live automations remain PAUSED."
                    ),
                }
            )
            continue
        obligation_rows.append(
            {
                "obligation_id": obligation_id(skill_id, suffix),
                "invariant_id": f"invariant:{skill_id}:{suffix}",
                "owner_step_ids": [step_id(skill_id, str(row["phase"]))],
                "required": True,
                "description": str(row["summary"]),
            }
        )
    return {
        "schema_version": "skillguard.flowguard_model_export.v2",
        "flowguard_schema_version": str(flowguard.SCHEMA_VERSION),
        "model_id": "khaos-brain.khaos-brain-update.executable-contract.v2",
        "parent_model_id": "khaos-brain.maintenance-runtime.v2",
        "claim_boundary": (
            "The authorize route proves only that the native update reached awaiting-skillguard "
            "with all five retained automations PAUSED. It is not overall completion. The finalize "
            "route consumes an immutable staged-restoration authorization in the sole composed "
            "enforced closure, still with all live automations PAUSED. Only after that "
            "closure may the native updater apply the exact target states, read them back, run the "
            "normal install check, and mark CURRENT. SkillGuard supervises these native stages and "
            "does not create a parallel updater."
        ),
        "functions": [
            {
                "function_id": authorize_function_id,
                "business_intent": purpose,
                "owner_id": skill_id,
                "route_ids": [UPDATE_AUTHORIZE_ROUTE_ID],
                "composable_with": [finalize_function_id],
            },
            {
                "function_id": finalize_function_id,
                "business_intent": (
                    "Authorize the staged restoration through the sole composed enforced "
                    "SkillGuard closure, then require exact native live apply, readback, normal "
                    "install check, and CURRENT in that order."
                ),
                "owner_id": skill_id,
                "route_ids": [UPDATE_FINALIZE_ROUTE_ID],
                "composable_with": [authorize_function_id],
            },
        ],
        "routes": [
            {
                "route_id": UPDATE_AUTHORIZE_ROUTE_ID,
                "function_id": authorize_function_id,
                "owner_id": skill_id,
                "step_ids": [intake, execute, verify, auth_success, auth_blocked],
                "success_terminal_step_id": auth_success,
                "blocked_terminal_step_id": auth_blocked,
                "completion_scope": "authorization_only",
                "overall_complete": False,
                "required_supervision_stage": "declared_check_authorization",
                "emits_closure": False,
                "handoffs": [
                    {
                        "target_kind": "internal_route",
                        "target_id": UPDATE_FINALIZE_ROUTE_ID,
                        "condition": "immutable staged-restoration authorization is available",
                        "claim_scope": "authorization_only_not_overall_complete",
                    }
                ],
            },
            {
                "route_id": UPDATE_FINALIZE_ROUTE_ID,
                "function_id": finalize_function_id,
                "owner_id": skill_id,
                "step_ids": [UPDATE_FINALIZE_STEP_ID, final_success, final_blocked],
                "success_terminal_step_id": final_success,
                "blocked_terminal_step_id": final_blocked,
                "completion_scope": "staged_authorization_then_verified_native_completion",
                "required_profile": "enforced",
                "requires_composed_route_ids": [
                    UPDATE_AUTHORIZE_ROUTE_ID,
                    UPDATE_FINALIZE_ROUTE_ID,
                ],
                "handoffs": [],
            },
        ],
        "steps": [
            {
                "step_id": intake,
                "route_id": UPDATE_AUTHORIZE_ROUTE_ID,
                "owner_id": skill_id,
                "action_kind": "inventory",
                "prerequisite_step_ids": [],
                "terminal_kind": "",
            },
            {
                "step_id": execute,
                "route_id": UPDATE_AUTHORIZE_ROUTE_ID,
                "owner_id": skill_id,
                "action_kind": "native",
                "prerequisite_step_ids": [intake],
                "terminal_kind": "",
            },
            {
                "step_id": verify,
                "route_id": UPDATE_AUTHORIZE_ROUTE_ID,
                "owner_id": skill_id,
                "action_kind": "validator",
                "prerequisite_step_ids": [execute],
                "terminal_kind": "",
            },
            {
                "step_id": auth_success,
                "route_id": UPDATE_AUTHORIZE_ROUTE_ID,
                "owner_id": skill_id,
                "action_kind": "terminal",
                "prerequisite_step_ids": [verify],
                "terminal_kind": "success",
                "completion_scope": "authorization_only",
                "overall_complete": False,
            },
            {
                "step_id": auth_blocked,
                "route_id": UPDATE_AUTHORIZE_ROUTE_ID,
                "owner_id": skill_id,
                "action_kind": "terminal",
                "prerequisite_step_ids": [],
                "terminal_kind": "blocked",
            },
            {
                "step_id": UPDATE_FINALIZE_STEP_ID,
                "route_id": UPDATE_FINALIZE_ROUTE_ID,
                "owner_id": skill_id,
                "action_kind": "finalize",
                "prerequisite_step_ids": [verify],
                "terminal_kind": "",
            },
            {
                "step_id": final_success,
                "route_id": UPDATE_FINALIZE_ROUTE_ID,
                "owner_id": skill_id,
                "action_kind": "terminal",
                "prerequisite_step_ids": [UPDATE_FINALIZE_STEP_ID],
                "terminal_kind": "success",
            },
            {
                "step_id": final_blocked,
                "route_id": UPDATE_FINALIZE_ROUTE_ID,
                "owner_id": skill_id,
                "action_kind": "terminal",
                "prerequisite_step_ids": [],
                "terminal_kind": "blocked",
            },
        ],
        "invariant_ids": [str(row["invariant_id"]) for row in obligation_rows],
        "obligations": obligation_rows,
    }


def build_contract_model(skill_id: str, purpose: str) -> dict[str, Any]:
    if skill_id == UPDATE_SKILL_ID:
        return _build_update_contract_model(purpose)
    slug = skill_id.replace("_", "-")
    model_id = f"khaos-brain.{slug}.executable-contract.v2"
    function_id = f"function:{slug}:run"
    route_id = f"route:{slug}:run"
    intake = step_id(skill_id, "intake")
    execute = step_id(skill_id, "execute")
    verify = step_id(skill_id, "verify")
    success = f"step:{slug}:success"
    blocked = f"step:{slug}:blocked"
    spec = AUTOMATION_COMPLETION_CONTRACTS[skill_id]
    obligations = tuple(
        (
            obligation_id(skill_id, str(row["suffix"])),
            f"invariant:{skill_id}:{row['suffix']}",
            step_id(skill_id, str(row["phase"])),
            str(row["summary"]),
        )
        for row in spec["obligations"]
    )
    return {
        "schema_version": "skillguard.flowguard_model_export.v2",
        "flowguard_schema_version": str(flowguard.SCHEMA_VERSION),
        "model_id": model_id,
        "parent_model_id": "khaos-brain.maintenance-runtime.v2",
        "claim_boundary": (
            f"This model binds every declared {skill_id} completion obligation to its native owner and checks. "
            "It does not create a parallel maintenance implementation, treat proposal-only progress as completion, "
            "or certify future AI behavior."
        ),
        "functions": [
            {
                "function_id": function_id,
                "business_intent": purpose,
                "owner_id": skill_id,
                "route_ids": [route_id],
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
        "invariant_ids": [item[1] for item in obligations],
        "obligations": [
            {
                "obligation_id": obligation_id,
                "invariant_id": invariant_id,
                "owner_step_ids": [owner_step],
                "required": True,
                "description": description,
            }
            for obligation_id, invariant_id, owner_step, description in obligations
        ],
    }


def review_current_model(model: dict[str, Any]) -> dict[str, Any]:
    """Return target-specific topology findings without printing or exiting."""

    skill_id = str(model.get("model_id", "")).split(".")[1]
    expected = set(expected_obligation_ids(skill_id))
    if skill_id == UPDATE_SKILL_ID:
        expected.add(UPDATE_FINALIZATION_OBLIGATION_ID)
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
        for obligation in model.get("obligations", [])
        if isinstance(obligation, dict)
        for item in obligation.get("owner_step_ids", [])
    }
    issues: list[str] = []
    if actual != expected:
        issues.append(f"obligation-set-mismatch:{sorted(expected ^ actual)}")
    if len(model.get("obligations", [])) != len(actual):
        issues.append("duplicate-or-empty-obligation-id")
    if not owner_steps.issubset(route_steps):
        issues.append(f"orphan-obligation-steps:{sorted(owner_steps - route_steps)}")
    if len(actual) < 8:
        issues.append("shallow-target-contract:fewer-than-eight-target-obligations")
    if skill_id == UPDATE_SKILL_ID:
        routes = {
            str(row.get("route_id") or ""): row
            for row in model.get("routes", [])
            if isinstance(row, dict)
        }
        if set(routes) != {UPDATE_AUTHORIZE_ROUTE_ID, UPDATE_FINALIZE_ROUTE_ID}:
            issues.append(f"update-route-set-mismatch:{sorted(routes)}")
        authorize = routes.get(UPDATE_AUTHORIZE_ROUTE_ID, {})
        finalize = routes.get(UPDATE_FINALIZE_ROUTE_ID, {})
        expected_authorize_steps = {
            step_id(UPDATE_SKILL_ID, "intake"),
            step_id(UPDATE_SKILL_ID, "execute"),
            step_id(UPDATE_SKILL_ID, "verify"),
            "step:khaos-brain-update:auth-success",
            "step:khaos-brain-update:auth-blocked",
        }
        expected_finalize_steps = {
            UPDATE_FINALIZE_STEP_ID,
            "step:khaos-brain-update:final-success",
            "step:khaos-brain-update:final-blocked",
        }
        if set(authorize.get("step_ids", [])) != expected_authorize_steps:
            issues.append("authorization-route-topology-mismatch")
        if set(finalize.get("step_ids", [])) != expected_finalize_steps:
            issues.append("finalization-route-topology-mismatch")
        if authorize.get("overall_complete") is not False:
            issues.append("authorization-route-overclaims-overall-completion")
        if (
            str(authorize.get("required_supervision_stage") or "")
            != "declared_check_authorization"
            or authorize.get("emits_closure") is not False
            or "required_profile" in authorize
        ):
            issues.append("authorization-route-must-be-nonterminal-declared-check-stage")
        if str(finalize.get("required_profile") or "") != "enforced":
            issues.append("finalization-route-profile-is-not-enforced")
        if set(finalize.get("requires_composed_route_ids", [])) != {
            UPDATE_AUTHORIZE_ROUTE_ID,
            UPDATE_FINALIZE_ROUTE_ID,
        }:
            issues.append("finalization-route-missing-compose-contract")
        finalization = next(
            (
                row
                for row in model.get("obligations", [])
                if isinstance(row, dict)
                and row.get("obligation_id") == UPDATE_FINALIZATION_OBLIGATION_ID
            ),
            {},
        )
        if finalization.get("owner_step_ids") != [UPDATE_FINALIZE_STEP_ID]:
            issues.append("finalization-obligation-owner-mismatch")
        if finalization.get("conditional") is not True:
            issues.append("finalization-obligation-must-be-route-conditional")
        description = str(finalization.get("description") or "").lower()
        if "staged-restoration" not in description or "paused" not in description:
            issues.append("staged-authorization-obligation-claim-is-ambiguous")
        if "route:khaos-brain-update:run" in routes:
            issues.append("legacy-run-route-can-bypass-two-stage-supervision")
    return {
        "ok": not issues,
        "skill_id": skill_id,
        "obligation_count": len(actual),
        "issues": issues,
        "flowguard_schema_version": str(flowguard.SCHEMA_VERSION),
        "claim_boundary": (
            "Target-specific route topology and obligation ownership only; native "
            "checks and execution depth remain separate."
        ),
    }


def run_current_model_checks(model: dict[str, Any]) -> int:
    """Executable target-specific model assertion used by current SkillGuard."""

    report = review_current_model(model)
    print(
        json.dumps(report, sort_keys=True)
    )
    return 0 if report["ok"] else 1
