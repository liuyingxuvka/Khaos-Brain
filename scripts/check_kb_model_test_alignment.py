#!/usr/bin/env python3
"""Align each maintained skill with its own model, code, and test evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
FLOWGUARD_ROOT = REPO_ROOT / ".flowguard"
for root in (REPO_ROOT, FLOWGUARD_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from local_kb.automation_contracts import (  # noqa: E402
    AUTOMATION_COMPLETION_CONTRACTS,
    evidence_test_node_ids,
    obligation_id,
)
from scripts.build_kb_automation_skillguard_contracts import (  # noqa: E402
    MODEL_PATHS,
    build_contract_source,
)


RECEIPT_PATH = (
    REPO_ROOT / ".flowguard" / "evidence" / "kb_model_test_alignment.json"
)


def _obligation_rows() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for skill_id, spec in AUTOMATION_COMPLETION_CONTRACTS.items():
        resolved = evidence_test_node_ids(skill_id, repo_root=REPO_ROOT)
        for item in spec["obligations"]:
            rows.append(
                {
                    "id": obligation_id(skill_id, str(item["suffix"])),
                    "maintenance_unit_id": f"unit:{skill_id}",
                    "skill_id": skill_id,
                    "model_path": MODEL_PATHS[skill_id],
                    "code_path": str(spec["entrypoint_path"]),
                    "test_nodes": [
                        resolved[str(marker)]
                        for marker in item["evidence_tests"]
                    ],
                }
            )
    return tuple(rows)


OBLIGATIONS: tuple[dict[str, Any], ...] = _obligation_rows()


def build_report(
    *,
    evidence_manifest: dict[str, Any] | Path | None = None,
    run_missing: bool = False,
) -> dict[str, Any]:
    del evidence_manifest, run_missing
    owner_counts: dict[str, int] = {}
    node_owners: dict[str, str] = {}
    overlaps: list[dict[str, str]] = []
    binding_rows: list[dict[str, Any]] = []
    for row in OBLIGATIONS:
        obligation = str(row["id"])
        owner_counts[obligation] = owner_counts.get(obligation, 0) + 1
        issues: list[str] = []
        model_path = REPO_ROOT / str(row["model_path"])
        code_path = REPO_ROOT / str(row["code_path"])
        if not model_path.is_file():
            issues.append("model_missing")
        if not code_path.is_file():
            issues.append("code_owner_missing")
        for node_id in row["test_nodes"]:
            prior = node_owners.get(node_id)
            current = str(row["maintenance_unit_id"])
            if prior is not None and prior != current:
                overlaps.append(
                    {
                        "node_id": node_id,
                        "first_unit": prior,
                        "second_unit": current,
                    }
                )
                issues.append("cross_unit_test_evidence_reuse")
            node_owners[node_id] = current
        binding_rows.append(
            {
                "model_obligation_id": obligation,
                "maintenance_unit_id": row["maintenance_unit_id"],
                "skill_id": row["skill_id"],
                "model_path": row["model_path"],
                "code_path": row["code_path"],
                "test_nodes": row["test_nodes"],
                "status": "aligned" if not issues else "blocked",
                "open_gap_codes": sorted(set(issues)),
            }
        )
    unit_reports: dict[str, dict[str, Any]] = {}
    for skill_id in AUTOMATION_COMPLETION_CONTRACTS:
        source = build_contract_source(skill_id)
        expected = {
            obligation_id(skill_id, str(item["suffix"]))
            for item in AUTOMATION_COMPLETION_CONTRACTS[skill_id][
                "obligations"
            ]
        }
        closure_profiles = source.get("closure_profiles") or []
        enforced = next(
            (
                item
                for item in closure_profiles
                if item.get("profile_id") == "enforced"
            ),
            {},
        )
        actual = {
            str(item)
            for item in enforced.get("required_obligation_ids", [])
            if str(item)
        }
        unit_reports[skill_id] = {
            "ok": actual == expected,
            "maintenance_unit_id": f"unit:{skill_id}",
            "member_skill_ids": source["member_skill_ids"],
            "obligation_count": len(actual),
            "missing_obligation_ids": sorted(expected - actual),
            "extra_obligation_ids": sorted(actual - expected),
        }
    exactly_one_owner = all(count == 1 for count in owner_counts.values())
    ok = bool(
        exactly_one_owner
        and not overlaps
        and all(row["status"] == "aligned" for row in binding_rows)
        and all(row["ok"] for row in unit_reports.values())
    )
    alignment = {
        "ok": ok,
        "decision": "aligned" if ok else "model_test_alignment_blocked",
        "summary": (
            "Every maintenance unit owns its own model, entrypoint, and test nodes."
            if ok
            else "One or more maintenance units have missing or shared evidence."
        ),
        "binding_rows": binding_rows,
        "findings": overlaps,
    }
    return {
        "schema_version": "khaos-brain.model-code-test-alignment.v2",
        "check": "kb-model-code-test-alignment",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "alignment": alignment,
        "owner_counts": owner_counts,
        "exactly_one_primary_owner": exactly_one_owner,
        "cross_unit_test_evidence_overlaps": overlaps,
        "maintenance_units": unit_reports,
        "obligation_ids": [str(row["id"]) for row in OBLIGATIONS],
        "current_runs": {},
        "receipt_findings": [],
        "claim_boundary": (
            "Static current model/code/test ownership. No test receipt is reused "
            "across maintenance units, and no command is launched by this audit."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write-receipt", action="store_true")
    parser.add_argument("--evidence-manifest", type=Path)
    parser.add_argument("--run-missing", action="store_true")
    args = parser.parse_args()
    report = build_report(
        evidence_manifest=args.evidence_manifest,
        run_missing=args.run_missing,
    )
    if not args.no_write_receipt:
        RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Model-code-test alignment:", "PASS" if report["ok"] else "FAIL")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
