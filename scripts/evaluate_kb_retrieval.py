"""Evaluate real-corpus retrieval safety, Top-3 utility, and P95 latency."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.active_index import load_active_index, validate_active_index  # noqa: E402
from local_kb.maintenance_standard import maintenance_standard_is_active  # noqa: E402
from local_kb.search import (  # noqa: E402
    CANDIDATE_MIN_CONFIDENCE,
    CANDIDATE_MIN_RELEVANCE_SCORE,
    RETRIEVAL_POLICY_VERSION,
    TRUSTED_MIN_CONFIDENCE,
    TRUSTED_MIN_RELEVANCE_SCORE,
    render_search_payload,
    search_with_receipt,
)


DEFAULT_CASES = REPO_ROOT / "tests" / "fixtures" / "kb_retrieval_eval_cases.json"
DEFAULT_RECEIPT = REPO_ROOT / ".local" / "assurance" / "kb_retrieval_evaluation.json"
REQUIRED_KINDS = {"lexical", "direct_id", "route_expansion", "related_traversal", "no_card"}
TERMINAL_STATUSES = {"merged", "rejected", "superseded", "parked", "retired", "deprecated", "history_only"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _percentile_95(values: list[float]) -> float:
    if not values:
        return math.inf
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _load_cases(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or int(payload.get("schema_version") or 0) != 1:
        raise ValueError("retrieval evaluation cases require schema_version 1")
    return payload


def _run_case(repo_root: Path, case: dict[str, Any]) -> dict[str, Any]:
    started = perf_counter()
    entries, _receipt = search_with_receipt(
        repo_root,
        query=str(case.get("query") or ""),
        path_hint=str(case.get("path_hint") or ""),
        top_k=3,
        record_receipt=False,
    )
    duration_ms = (perf_counter() - started) * 1000
    payload = render_search_payload(entries, repo_root)
    returned = [str(item.get("id") or "") for item in payload]
    expected = [str(item) for item in case.get("expected_entry_ids", []) if str(item)]
    kind = str(case.get("kind") or "")
    if kind == "no_card":
        passed = not returned
    else:
        passed = bool(set(expected) & set(returned[:3]))
    terminal = [
        str(item.get("id") or "")
        for item in payload
        if str(item.get("status") or "").lower() in TERMINAL_STATUSES
    ]
    candidate_violations = [
        str(item.get("id") or "")
        for item in payload
        if str(item.get("status") or "").lower() == "candidate"
        and str(item.get("trust_label") or "") != "untrusted-candidate"
    ]
    return {
        "id": str(case.get("id") or ""),
        "kind": kind,
        "query": str(case.get("query") or ""),
        "path_hint": str(case.get("path_hint") or ""),
        "expected_entry_ids": expected,
        "returned_entry_ids": returned,
        "duration_ms": round(duration_ms, 3),
        "passed": passed and not terminal and not candidate_violations,
        "terminal_entry_ids": terminal,
        "candidate_label_violations": candidate_violations,
    }


def build_report(repo_root: Path, cases_path: Path, *, benchmark_queries: int = 40) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    cases_path = Path(cases_path).resolve()
    cases = _load_cases(cases_path)
    useful = [item for item in cases.get("useful_cases", []) if isinstance(item, dict)]
    no_card = [item for item in cases.get("no_card_cases", []) if isinstance(item, dict)]
    all_cases = useful + no_card
    skipped = [
        str(item.get("id") or "")
        for item in all_cases
        if not str(item.get("id") or "") or not str(item.get("query") or "")
    ]
    runnable = [item for item in all_cases if str(item.get("id") or "") and str(item.get("query") or "")]
    active_standard = maintenance_standard_is_active(repo_root)
    index_validation = validate_active_index(repo_root) if active_standard else {
        "ok": False,
        "issues": ["Chaos Brain maintenance standard is not committed"],
    }
    index = load_active_index(repo_root) if active_standard else {}

    cold_start_ms = None
    results: list[dict[str, Any]] = []
    for case in runnable:
        result = _run_case(repo_root, case)
        if cold_start_ms is None:
            cold_start_ms = result["duration_ms"]
        results.append(result)

    useful_results = [item for item in results if item["kind"] != "no_card"]
    no_card_results = [item for item in results if item["kind"] == "no_card"]
    useful_hits = sum(1 for item in useful_results if item["passed"])
    no_card_false = sum(1 for item in no_card_results if item["returned_entry_ids"])
    terminal_returns = sorted(
        {
            entry_id
            for item in results
            for entry_id in item["terminal_entry_ids"]
        }
    )
    candidate_label_violations = sorted(
        {
            entry_id
            for item in results
            for entry_id in item["candidate_label_violations"]
        }
    )

    benchmark_timings: list[float] = []
    if runnable:
        for index_number in range(max(benchmark_queries, len(runnable))):
            case = runnable[index_number % len(runnable)]
            started = perf_counter()
            search_with_receipt(
                repo_root,
                query=str(case.get("query") or ""),
                path_hint=str(case.get("path_hint") or ""),
                top_k=3,
                record_receipt=False,
            )
            benchmark_timings.append((perf_counter() - started) * 1000)
    p95_ms = _percentile_95(benchmark_timings)
    useful_rate = useful_hits / len(useful_results) if useful_results else 0.0
    false_card_rate = no_card_false / len(no_card_results) if no_card_results else 1.0
    observed_kinds = {item["kind"] for item in results}
    missing_kinds = sorted(REQUIRED_KINDS - observed_kinds)
    threshold_results = {
        "useful_top3_at_least_90_percent": useful_rate >= 0.90,
        "no_card_false_returns_below_5_percent": false_card_rate < 0.05,
        "terminal_returns_exactly_zero": not terminal_returns,
        "candidate_labels_exact": not candidate_label_violations,
        "p95_below_1000_ms": p95_ms < 1000.0,
        "active_index_current": bool(index_validation.get("ok")) and not bool(index.get("stale")),
        "all_required_case_kinds_present": not missing_kinds,
        "no_skipped_cases": not skipped,
    }
    return {
        "schema_version": 1,
        "suite_id": str(cases.get("suite_id") or ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": all(threshold_results.values()),
        "repo_root": str(repo_root),
        "case_file": str(cases_path),
        "case_file_sha256": _sha256(cases_path),
        "policy_version": RETRIEVAL_POLICY_VERSION,
        "thresholds": {
            "trusted_minimum_score": TRUSTED_MIN_RELEVANCE_SCORE,
            "candidate_minimum_score": CANDIDATE_MIN_RELEVANCE_SCORE,
            "trusted_minimum_confidence": TRUSTED_MIN_CONFIDENCE,
            "candidate_minimum_confidence": CANDIDATE_MIN_CONFIDENCE,
            "useful_top3_minimum_rate": 0.90,
            "no_card_false_return_maximum_rate": 0.05,
            "p95_maximum_ms": 1000.0,
        },
        "threshold_results": threshold_results,
        "active_standard": active_standard,
        "index": {
            "validation": index_validation,
            "generation": int(index.get("generation") or 0),
            "content_digest": str(index.get("content_digest") or ""),
            "built_at": str(index.get("built_at") or ""),
            "stale": bool(index.get("stale", True)),
            "indexed_record_count": int(index.get("indexed_record_count") or 0),
        },
        "metrics": {
            "useful_case_count": len(useful_results),
            "useful_top3_hits": useful_hits,
            "useful_top3_rate": round(useful_rate, 4),
            "no_card_case_count": len(no_card_results),
            "no_card_false_returns": no_card_false,
            "no_card_false_return_rate": round(false_card_rate, 4),
            "terminal_return_count": len(terminal_returns),
            "candidate_label_violation_count": len(candidate_label_violations),
            "cold_start_ms": cold_start_ms,
            "warm_query_count": len(benchmark_timings),
            "warm_p95_ms": round(p95_ms, 3) if math.isfinite(p95_ms) else None,
        },
        "terminal_entry_ids": terminal_returns,
        "candidate_label_violation_ids": candidate_label_violations,
        "missing_case_kinds": missing_kinds,
        "skipped_case_ids": skipped,
        "cases": results,
        "raw_warm_timings_ms": [round(item, 3) for item in benchmark_timings],
        "claim_boundary": (
            "Current declared real corpus, active index, Top-3/no-card safety, and "
            "single-machine P95 timing. Index construction is reported separately and "
            "is excluded from query latency."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-thresholds", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--benchmark-queries", type=int, default=40)
    parser.add_argument("--no-write-receipt", action="store_true")
    args = parser.parse_args()
    report = build_report(
        args.repo_root,
        args.cases,
        benchmark_queries=max(1, args.benchmark_queries),
    )
    if not args.no_write_receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Retrieval evaluation:", "PASS" if report["ok"] else "FAIL")
        print("Top-3 useful rate:", report["metrics"]["useful_top3_rate"])
        print("No-card false rate:", report["metrics"]["no_card_false_return_rate"])
        print("Warm P95 ms:", report["metrics"]["warm_p95_ms"])
    if args.require_thresholds and not report["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
