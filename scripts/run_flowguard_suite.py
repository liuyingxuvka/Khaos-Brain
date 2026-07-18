#!/usr/bin/env python3
"""Run the release-facing FlowGuard checks for Khaos Brain."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
FLOWGUARD_ROOT = REPO_ROOT / ".flowguard"
for root in (REPO_ROOT, FLOWGUARD_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

import flowguard  # noqa: E402
import khaos_brain_update_field_lifecycle as update_fields  # noqa: E402
import run_kb_convergence_checks as convergence  # noqa: E402
from scripts.check_current_runtime_only import (  # noqa: E402
    check_current_runtime_only,
)


RECEIPT_PATH = (
    REPO_ROOT / ".flowguard" / "evidence" / "kb_convergence_suite.json"
)
MANUAL_UPDATE_ENTRYPOINT = (
    REPO_ROOT / "scripts" / "run_khaos_brain_manual_update.py"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_json(command: list[str]) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        check=False,
    )
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError:
        payload = {}
    return {
        "ok": process.returncode == 0 and payload.get("ok") is True,
        "exit_code": process.returncode,
        "payload": payload,
        "stdout_tail": process.stdout[-2000:],
        "stderr_tail": process.stderr[-2000:],
    }


def _watched_fingerprints() -> dict[str, str]:
    paths = (
        REPO_ROOT / ".flowguard" / "kb_convergence_upgrade_model.py",
        REPO_ROOT / ".flowguard" / "run_kb_convergence_checks.py",
        REPO_ROOT / ".flowguard" / "kb_skill_contract_model_common.py",
        REPO_ROOT / ".flowguard" / "khaos_brain_update_field_lifecycle.py",
        REPO_ROOT / "local_kb" / "automation_contracts.py",
        REPO_ROOT / "local_kb" / "automation_runtime.py",
        REPO_ROOT / "local_kb" / "install.py",
        REPO_ROOT / "local_kb" / "transactional_install.py",
        REPO_ROOT / "scripts" / "run_kb_automation.py",
        MANUAL_UPDATE_ENTRYPOINT,
        REPO_ROOT / "scripts" / "check_consumer_install_assurance.py",
        REPO_ROOT / "tests" / "test_kb_automation_skillguard.py",
        REPO_ROOT / "tests" / "test_kb_flowguard_execution_identity.py",
    )
    return {
        path.relative_to(REPO_ROOT).as_posix(): _sha256(path)
        for path in paths
    }


def build_report() -> dict[str, Any]:
    convergence_report = convergence.build_report()
    field_report = flowguard.review_field_lifecycle(update_fields.build_plan())
    conformance_report = _run_json(
        [
            sys.executable,
            str(REPO_ROOT / ".flowguard" / "run_khaos_brain_conformance.py"),
        ]
    )
    current_runtime = check_current_runtime_only(REPO_ROOT)
    watched = _watched_fingerprints()
    input_fingerprint = hashlib.sha256(
        json.dumps(watched, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    ok = bool(
        convergence_report.get("ok")
        and field_report.ok
        and conformance_report.get("ok")
        and current_runtime.get("ok")
    )
    return {
        "schema_version": "khaos-brain.flowguard-suite.v2",
        "suite": "khaos-brain-consumer-independence",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "flowguard_schema_version": str(flowguard.SCHEMA_VERSION),
        "input_fingerprint": input_fingerprint,
        "receipt_id": f"flowguard-suite:{input_fingerprint}",
        "ok": ok,
        "consumer_independence": convergence_report,
        "field_lifecycle": field_report.to_dict(),
        "production_conformance": conformance_report,
        "current_runtime": current_runtime,
        "watched_fingerprints": watched,
        "claim_boundary": (
            "Current FlowGuard model, scenarios, progress, field lifecycle, "
            "production conformance, and clean consumer runtime evidence. "
            "Author-side SkillGuard certification and publication remain separate."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write-receipt", action="store_true")
    args = parser.parse_args()
    report = build_report()
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
        print("FlowGuard suite:", "PASS" if report["ok"] else "FAIL")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
