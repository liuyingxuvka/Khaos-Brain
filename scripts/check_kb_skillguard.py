#!/usr/bin/env python3
"""Author-side maintenance audit for the five Khaos Brain skills.

This command is intentionally not part of any installed consumer route.  It
checks source contracts, compiler parity, clean consumer projections, unique
maintenance-unit ownership, and optionally executes each target skill's own
declared regression nodes.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.automation_contracts import (  # noqa: E402
    AUTOMATION_COMPLETION_CONTRACTS,
    evidence_test_node_ids,
)
from local_kb.install import maintenance_skill_source_dir  # noqa: E402
from local_kb.transactional_install import consumer_skill_manifest  # noqa: E402
from scripts.build_kb_automation_skillguard_contracts import (  # noqa: E402
    build_contract_source,
)
from scripts.check_kb_automation_skillguard_depth import (  # noqa: E402
    build_report as build_depth_report,
)


AUTHOR_TOKENS = ("skillguard", ".skillguard", "skillguard.py")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _compiler_path() -> Path | None:
    configured = os.environ.get("SKILLGUARD_AUTHOR_COMPILER", "").strip()
    candidates = (
        Path(configured) if configured else None,
        Path.home()
        / ".codex"
        / "skills"
        / "skillguard"
        / "scripts"
        / "skillguard_compile.py",
        REPO_ROOT.parent
        / "SkillGuard_20260614"
        / ".agents"
        / "skills"
        / "skillguard"
        / "scripts"
        / "skillguard_compile.py",
    )
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate.resolve()
    return None


def _run(command: list[str], *, timeout: int = 1800) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
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
        "ok": process.returncode == 0,
        "exit_code": process.returncode,
        "command": command,
        "payload": payload,
        "stdout_tail": process.stdout[-2000:],
        "stderr_tail": process.stderr[-2000:],
    }


def _consumer_projection(skill_id: str) -> dict[str, Any]:
    source_root = maintenance_skill_source_dir(REPO_ROOT, skill_id)
    try:
        manifest = consumer_skill_manifest(source_root)
    except (OSError, RuntimeError) as exc:
        return {
            "ok": False,
            "issues": [f"{type(exc).__name__}:{exc}"],
        }
    issues: list[str] = []
    for row in manifest.get("files", []):
        relative = str(row.get("path") or "")
        if relative.startswith(".skillguard/"):
            issues.append(f"author-path-leak:{relative}")
            continue
        text = (source_root / relative).read_text(
            encoding="utf-8", errors="replace"
        ).lower()
        for token in AUTHOR_TOKENS:
            if token in text:
                issues.append(f"author-token-leak:{relative}:{token}")
    return {
        "ok": not issues,
        "manifest_digest": str(manifest.get("digest") or ""),
        "file_count": int(manifest.get("file_count") or 0),
        "issues": issues,
    }


def _skill_report(
    skill_id: str,
    *,
    compiler: Path | None,
    execute_checks: bool,
) -> dict[str, Any]:
    skill_root = REPO_ROOT / ".agents" / "skills" / skill_id
    control_root = skill_root / ".skillguard"
    expected_source = build_contract_source(skill_id)
    current_source = _load_json(control_root / "contract-source.json")
    compiled = _load_json(control_root / "compiled-contract.json")
    manifest = _load_json(control_root / "check-manifest.json")
    source_current = current_source == expected_source
    unit_id = f"unit:{skill_id}"
    unit_current = bool(
        source_current
        and compiled.get("maintenance_unit_id") == unit_id
        and compiled.get("member_skill_ids") == [skill_id]
        and manifest.get("maintenance_unit_id") == unit_id
        and manifest.get("member_skill_ids") == [skill_id]
    )
    compiler_check = (
        _run(
            [
                sys.executable,
                str(compiler),
                str(skill_root),
                "--repository-root",
                str(REPO_ROOT),
                "--check",
            ],
            timeout=300,
        )
        if compiler is not None
        else {
            "ok": False,
            "exit_code": 1,
            "issues": ["author-compiler-unavailable"],
        }
    )
    positive = build_depth_report(skill_id, "positive")
    shallow = build_depth_report(skill_id, "shallow")
    projection = _consumer_projection(skill_id)
    nodes = evidence_test_node_ids(skill_id, repo_root=REPO_ROOT)
    exact_nodes = sorted(nodes.values())
    regression = {
        "ok": True,
        "status": "not-requested",
        "node_count": len(exact_nodes),
    }
    if execute_checks:
        regression = _run(
            [sys.executable, "-m", "pytest", "-q", *exact_nodes],
            timeout=3600,
        )
        regression["node_count"] = len(exact_nodes)
    checks = {
        "contract_source_current": source_current,
        "single_skill_unit_current": unit_current,
        "compiler_parity": compiler_check.get("ok") is True,
        "positive_depth": positive.get("ok") is True
        and positive.get("observed_status") == "deep-pass",
        "shallow_depth_blocked": shallow.get("ok") is True
        and shallow.get("observed_status") == "shallow-blocked",
        "consumer_projection_clean": projection.get("ok") is True,
        "target_regression": regression.get("ok") is True,
    }
    return {
        "ok": all(checks.values()),
        "skill_id": skill_id,
        "maintenance_unit_id": unit_id,
        "checks": checks,
        "compiler": compiler_check,
        "positive_depth": positive,
        "shallow_depth": shallow,
        "consumer_projection": projection,
        "evidence_nodes": exact_nodes,
        "regression": regression,
    }


def build_report(
    *,
    execute_checks: bool = False,
    **_ignored: object,
) -> dict[str, Any]:
    compiler = _compiler_path()
    skills = {
        skill_id: _skill_report(
            skill_id,
            compiler=compiler,
            execute_checks=execute_checks,
        )
        for skill_id in AUTOMATION_COMPLETION_CONTRACTS
    }
    evidence_owners: dict[str, str] = {}
    overlaps: list[dict[str, str]] = []
    for skill_id, row in skills.items():
        for node_id in row["evidence_nodes"]:
            prior = evidence_owners.get(node_id)
            if prior is not None:
                overlaps.append(
                    {
                        "node_id": node_id,
                        "first_unit": prior,
                        "second_unit": skill_id,
                    }
                )
            evidence_owners[node_id] = skill_id
    checks = [
        {
            "id": f"maintenance_unit:{skill_id}",
            "ok": row["ok"],
            "detail": row,
        }
        for skill_id, row in skills.items()
    ]
    checks.append(
        {
            "id": "cross_unit_test_ownership",
            "ok": not overlaps,
            "detail": {"overlaps": overlaps},
        }
    )
    return {
        "schema_version": "khaos-brain.skill-author-maintenance.v1",
        "ok": all(row["ok"] for row in checks),
        "status": "passed" if all(row["ok"] for row in checks) else "blocked",
        "source_only": True,
        "execute_checks": execute_checks,
        "author_compiler": str(compiler or ""),
        "skills": skills,
        "checks": checks,
        "claim_boundary": (
            "Author-side source maintenance only. This report neither installs nor "
            "invokes an author control plane on a consumer machine, and it never "
            "shares test evidence across maintenance units."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--execute-checks", action="store_true")
    args = parser.parse_args()
    report = build_report(execute_checks=args.execute_checks)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for item in report["checks"]:
            print(("PASS" if item["ok"] else "FAIL"), item["id"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
