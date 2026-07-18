#!/usr/bin/env python3
"""Run the target-owned checks required before a consumer installation is restored."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.install import MAINTENANCE_SKILL_SPECS, maintenance_skill_source_dir
from local_kb.transactional_install import consumer_skill_manifest


def _run(command: list[str], repo_root: Path) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=str(repo_root),
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
        check=False,
    )
    payload: dict[str, Any] = {}
    try:
        decoded = json.loads(process.stdout)
        if isinstance(decoded, dict):
            payload = decoded
    except json.JSONDecodeError:
        pass
    return {
        "ok": process.returncode == 0
        and (payload.get("ok") is not False if payload else True),
        "exit_code": process.returncode,
        "command": command,
        "payload": payload,
        "stdout_tail": process.stdout[-1000:],
        "stderr_tail": process.stderr[-1000:],
    }


def build_report(repo_root: Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    checks: dict[str, dict[str, Any]] = {}

    projection_rows: dict[str, dict[str, Any]] = {}
    projection_issues: list[str] = []
    for spec in MAINTENANCE_SKILL_SPECS:
        skill_id = str(spec["name"])
        source = maintenance_skill_source_dir(root, skill_id)
        try:
            manifest = consumer_skill_manifest(source)
        except (OSError, RuntimeError) as exc:
            projection_issues.append(f"{skill_id}:{exc}")
            continue
        projection_rows[skill_id] = {
            "manifest_digest": str(manifest.get("digest") or ""),
            "file_count": int(manifest.get("file_count") or 0),
        }
    checks["consumer_projections"] = {
        "ok": not projection_issues
        and len(projection_rows) == len(MAINTENANCE_SKILL_SPECS),
        "rows": projection_rows,
        "issues": projection_issues,
    }

    commands = {
        "flow_model": [
            sys.executable,
            ".flowguard/run_kb_convergence_checks.py",
        ],
        "reasoning_runtime": [
            sys.executable,
            "scripts/check_khaos_logicguard_runtime.py",
            "--json",
            "--repo-root",
            str(root),
        ],
        "retrieval_quality": [
            sys.executable,
            "scripts/evaluate_kb_retrieval.py",
            "--json",
            "--require-thresholds",
            "--repo-root",
            str(root),
        ],
        "current_runtime": [
            sys.executable,
            "scripts/check_current_runtime_only.py",
            "--json",
            "--repo-root",
            str(root),
            "--consumer-install",
        ],
    }
    for name, command in commands.items():
        checks[name] = _run(command, root)

    failed = [name for name, row in checks.items() if row.get("ok") is not True]
    return {
        "schema_version": "khaos-brain.consumer-install-assurance.v1",
        "ok": not failed,
        "status": "passed" if not failed else "failed",
        "repo_root": str(root),
        "checks": checks,
        "failed_checks": failed,
        "claim_boundary": (
            "Target-owned consumer projection, flow, reasoning-runtime, retrieval, "
            "and current-runtime checks only. Author-side maintenance certification "
            "and release publication are separate."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=SCRIPT_REPO_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(args.repo_root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Consumer install assurance:", "PASS" if report["ok"] else "FAIL")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
