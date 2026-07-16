"""Validate Guard-family closure report JSON.

This helper is intentionally small and dependency-free. It checks whether a
Guard skill returned the machine-readable fields that FlowGuard needs before a
done, release, or broad confidence claim can be trusted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VALID_STATUSES = {"passed", "partial", "blocked", "downgraded"}
REQUIRED_FIELDS = (
    "owner_guard",
    "artifact_kind",
    "closure_status",
    "findings",
    "missing_inputs",
    "stale_evidence",
    "skipped_checks",
    "next_actions",
    "safe_claim",
    "unsafe_claim_boundary",
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return value


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def review_report(path: Path) -> dict[str, Any]:
    report = _load(path)
    findings: list[dict[str, str]] = []

    for field in REQUIRED_FIELDS:
        if field not in report:
            findings.append({"severity": "error", "type": "missing_required_field", "field": field})

    status = str(report.get("closure_status", "")).strip().lower()
    if status not in VALID_STATUSES:
        findings.append({"severity": "error", "type": "invalid_closure_status", "field": "closure_status"})

    if status == "passed":
        for field, finding_type in (
            ("missing_inputs", "passed_with_missing_inputs"),
            ("stale_evidence", "passed_with_stale_evidence"),
            ("skipped_checks", "passed_with_skipped_checks"),
        ):
            if _as_list(report.get(field)):
                findings.append({"severity": "error", "type": finding_type, "field": field})
        hard_findings = [
            item for item in _as_list(report.get("findings"))
            if str(item.get("severity", "")).lower() in {"error", "blocker"}
        ]
        if hard_findings:
            findings.append({"severity": "error", "type": "passed_with_hard_findings", "field": "findings"})

    next_actions = _as_list(report.get("next_actions"))
    if status in {"partial", "blocked", "downgraded"} and not next_actions:
        findings.append({"severity": "warning", "type": "non_pass_without_next_actions", "field": "next_actions"})

    return {
        "ok": not any(item["severity"] == "error" for item in findings),
        "path": str(path),
        "owner_guard": report.get("owner_guard", ""),
        "closure_status": status,
        "findings": findings,
    }


def review_many(paths: list[Path]) -> dict[str, Any]:
    reports = [review_report(path) for path in paths]
    return {
        "ok": all(report["ok"] for report in reports),
        "reports": reports,
        "blocked_reports": [report for report in reports if not report["ok"]],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Guard-family closure report JSON.")
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = review_many(args.reports)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(("PASS" if result["ok"] else "FAIL") + f": {len(args.reports)} closure report(s)")
        for report in result["reports"]:
            print(f"- {report['owner_guard'] or report['path']}: {report['closure_status']}")
            for finding in report["findings"]:
                print(f"  - {finding['severity']}: {finding['type']} {finding.get('field', '')}".rstrip())
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
