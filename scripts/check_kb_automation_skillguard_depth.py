#!/usr/bin/env python3
"""Validate current Khaos Brain declared-check supervision contracts.

Positive and shallow behavior remains owned by each Khaos Brain automation.
SkillGuard is treated only as the current target-neutral declared-check and
receipt supervisor; this module does not import or recreate retired SkillGuard
depth, universe, dimension, or calibration protocols.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.automation_contracts import (  # noqa: E402
    AUTOMATION_COMPLETION_CONTRACTS,
    check_id,
    expected_obligation_ids,
    validate_completion_surface,
)
from local_kb.automation_runtime import (  # noqa: E402
    build_fixture_payload,
    build_native_receipt,
)
from local_kb.install import REPO_AUTOMATION_SPECS  # noqa: E402


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _automation_prompt(skill_id: str) -> str:
    return next(
        str(row.get("prompt") or "")
        for row in REPO_AUTOMATION_SPECS
        if str(row.get("skill_name") or "") == skill_id
    )


def _source_surface(skill_id: str) -> dict[str, Any]:
    skill_root = REPO_ROOT / ".agents" / "skills" / skill_id
    control = skill_root / ".skillguard"
    return {
        "skill_text": (skill_root / "SKILL.md").read_text(
            encoding="utf-8", errors="replace"
        ),
        "automation_prompt": _automation_prompt(skill_id),
        "contract_source": _load_json(control / "contract-source.json"),
        "compiled_contract": _load_json(control / "compiled-contract.json"),
        "check_manifest": _load_json(control / "check-manifest.json"),
    }


def _closure_findings(
    skill_id: str, surface: Mapping[str, Any]
) -> list[dict[str, str]]:
    """Return current contract-shape findings for source or installed bytes."""

    compiled = surface.get("compiled_contract", {})
    manifest = surface.get("check_manifest", {})
    return validate_completion_surface(
        skill_id,
        repo_root=REPO_ROOT,
        automation_prompt=str(surface.get("automation_prompt") or ""),
        skill_text=str(surface.get("skill_text") or ""),
        compiled_contract=(compiled if isinstance(compiled, Mapping) else {}),
        check_manifest=(manifest if isinstance(manifest, Mapping) else {}),
    )


def _fixture_report(skill_id: str, case_kind: str) -> dict[str, Any]:
    shallow = case_kind == "shallow"
    run_id = f"fixture-{case_kind}-{skill_id}"
    payload = build_fixture_payload(skill_id, shallow=shallow, run_id=run_id)
    receipt = build_native_receipt(
        skill_id,
        run_id=run_id,
        command=["fixture", case_kind, skill_id],
        native_payload=payload,
        exit_code=0,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        fixture=case_kind,
    )
    evidence = receipt.get("obligation_evidence", {})
    expected_ids = {
        f"obligation:{skill_id}:{row['suffix']}"
        for row in AUTOMATION_COMPLETION_CONTRACTS[skill_id]["obligations"]
        if str(row.get("evidence_source") or "native-receipt")
        == "native-receipt"
        and str(row.get("suffix") or "") != "depth-calibration"
    }
    failed = sorted(
        obligation_id
        for obligation_id in expected_ids
        if not isinstance(evidence.get(obligation_id), Mapping)
        or evidence[obligation_id].get("ok") is not True
    )
    native_passed = (
        receipt.get("terminal_status") in {"completed", "no-op"} and not failed
    )
    expected_behavior_observed = (
        native_passed if case_kind == "positive" else bool(failed) and not native_passed
    )
    return {
        "ok": expected_behavior_observed,
        "case_kind": case_kind,
        "observed_status": "deep-pass" if native_passed else "shallow-blocked",
        "failed_obligation_ids": failed,
        "receipt_hash": str(receipt.get("receipt_hash") or ""),
        "claim_boundary": (
            "Target-owned positive/shallow native receipt behavior only; "
            "this is not a SkillGuard domain judgment."
        ),
    }


def build_report(skill_id: str, fixture: str) -> dict[str, Any]:
    surface = _source_surface(skill_id)
    source = surface["contract_source"]
    baseline_findings = _closure_findings(skill_id, surface)
    positive = _fixture_report(skill_id, "positive")
    shallow = _fixture_report(skill_id, "shallow")
    checks = {
        str(row.get("check_id") or "")
        for row in source.get("checks", [])
        if isinstance(row, Mapping)
    }
    required_fixture_checks = {
        check_id(skill_id, "depth-positive"),
        check_id(skill_id, "depth-shallow"),
    }
    selected = positive if fixture == "positive" else shallow
    findings = list(baseline_findings)
    if not required_fixture_checks.issubset(checks):
        findings.append(
            {
                "code": "target_fixture_checks_missing",
                "detail": str(sorted(required_fixture_checks - checks)),
            }
        )
    if selected.get("ok") is not True:
        findings.append(
            {
                "code": "target_fixture_behavior_invalid",
                "detail": fixture,
            }
        )
    return {
        "ok": not findings,
        "check": "kb-automation-declared-check-supervision",
        "skill_id": skill_id,
        "fixture": fixture,
        "observed_status": selected["observed_status"],
        "failed_obligation_ids": list(selected["failed_obligation_ids"]),
        "positive_fixture": positive,
        "shallow_fixture": shallow,
        "findings": findings,
        "claim_boundary": (
            "Current contract shape plus target-owned positive/shallow behavior; "
            "executed scheduled supervision remains separate evidence."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skill", choices=tuple(AUTOMATION_COMPLETION_CONTRACTS), required=True
    )
    parser.add_argument("--fixture", choices=("positive", "shallow"), default="positive")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(args.skill, args.fixture)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("PASS" if report["ok"] else "FAIL", args.skill, args.fixture)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
