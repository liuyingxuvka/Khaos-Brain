#!/usr/bin/env python3
"""Validate one target-owned immutable scheduled-or-manual native receipt."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.automation_contracts import AUTOMATION_COMPLETION_CONTRACTS  # noqa: E402
from local_kb.automation_runtime import (  # noqa: E402
    build_native_receipt,
    build_fixture_payload,
    validate_native_receipt,
)


def _fixture_report(skill_id: str, fixture: str, phase: str) -> dict:
    shallow = fixture == "shallow"
    fixture_run_id = f"fixture-{fixture}-{skill_id}"
    payload = build_fixture_payload(
        skill_id,
        shallow=shallow,
        run_id=fixture_run_id,
    )
    receipt = build_native_receipt(
        skill_id,
        run_id=fixture_run_id,
        command=["fixture", fixture, skill_id],
        native_payload=payload,
        exit_code=0,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        fixture=fixture,
    )
    evidence = receipt.get("obligation_evidence", {})
    phase_ids = {
        f"obligation:{skill_id}:{row['suffix']}"
        for row in AUTOMATION_COMPLETION_CONTRACTS[skill_id]["obligations"]
        if row["suffix"] != "depth-calibration"
        and str(row.get("evidence_source") or "native-receipt") == "native-receipt"
        and (phase == "all" or row["phase"] == phase)
    }
    failed = sorted(
        item for item in phase_ids if evidence.get(item, {}).get("ok") is not True
    )
    positive_ok = receipt.get("terminal_status") in {"completed", "no-op"} and not failed
    ok = (not shallow and positive_ok) or (shallow and not positive_ok)
    return {
        "ok": ok,
        "fixture": fixture,
        "skill_id": skill_id,
        "phase": phase,
        "observed_status": "deep-pass" if positive_ok else "shallow-blocked",
        "failed_obligation_ids": failed,
        "claim_boundary": "Target-owned positive/shallow native receipt calibration fixture only.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill", choices=tuple(AUTOMATION_COMPLETION_CONTRACTS), required=True)
    parser.add_argument("--phase", choices=("intake", "execute", "verify", "all"), default="all")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--fixture", choices=("positive", "shallow"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.fixture:
        report = _fixture_report(args.skill, args.fixture, args.phase)
    else:
        raw_path = str(args.receipt or os.environ.get("KHAOS_BRAIN_AUTOMATION_RECEIPT", ""))
        expected_run_id = os.environ.get("KHAOS_BRAIN_AUTOMATION_RUN_ID", "")
        expected_hash = os.environ.get("KHAOS_BRAIN_AUTOMATION_RECEIPT_HASH", "")
        report = validate_native_receipt(
            Path(raw_path),
            skill_id=args.skill,
            phase=args.phase,
            expected_run_id=expected_run_id,
            expected_receipt_hash=expected_hash,
            allow_fixture=os.environ.get("KHAOS_BRAIN_ALLOW_AUTOMATION_FIXTURE") == "1",
        ) if raw_path else {"ok": False, "issues": ["receipt-path-missing"]}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("PASS" if report.get("ok") else "FAIL", args.skill, args.phase)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
