"""Validate and benchmark the current LogicGuard-native Khaos Brain authority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
import time
import tracemalloc
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.logicguard_models import (  # noqa: E402
    researchguard_logic_dependency_preflight,
    read_bound_argument_context,
)
from local_kb.maintenance_migration import validate_logicguard_native_authority  # noqa: E402
from local_kb.model_maintenance import load_current_model_entries  # noqa: E402
from local_kb.model_projection import binding_from_projection  # noqa: E402
from local_kb.search import search_model_bound_entries  # noqa: E402


CATALOG_MAX_SECONDS = 30.0
EXACT_CONTEXT_P95_MAX_SECONDS = 2.0
SEARCH_P95_MAX_SECONDS = 8.0
PEAK_MEMORY_MAX_MIB = 768.0
SAMPLE_LIMIT = 25


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile))))
    return ordered[rank]


def _timed(call: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    value = call()
    return value, time.perf_counter() - started


def build_report(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    issues: list[str] = []
    dependency = researchguard_logic_dependency_preflight(
        strict=False,
        require_no_retired_standalone=True,
    )
    if not dependency.get("ok"):
        issues.extend(f"dependency:{item}" for item in dependency.get("issues", []))

    authority_started = time.perf_counter()
    try:
        authority = validate_logicguard_native_authority(root)
    except Exception as exc:  # visible terminal evidence is more useful than a traceback here
        authority = {"ok": False, "issues": [f"{type(exc).__name__}: {exc}"]}
    authority_seconds = time.perf_counter() - authority_started
    if not authority.get("ok"):
        issues.extend(f"authority:{item}" for item in authority.get("issues", []))

    entries: list[Any] = []
    generation: dict[str, Any] = {}
    catalog_seconds = 0.0
    peak_mib = 0.0
    if authority.get("ok"):
        try:
            (entries, generation), catalog_seconds = _timed(
                lambda: load_current_model_entries(root)
            )
            # Memory instrumentation makes large PyYAML catalogs several
            # times slower. Measure user-facing latency without instrumentation,
            # then run a separate exact-authority load for the memory ceiling.
            # Neither gate is removed or relaxed.
            tracemalloc.start()
            memory_entries, memory_generation = load_current_model_entries(root)
            _current, peak = tracemalloc.get_traced_memory()
            peak_mib = peak / (1024 * 1024)
            if len(memory_entries) != len(entries) or str(
                memory_generation.get("pointer_digest") or ""
            ) != str(generation.get("pointer_digest") or ""):
                issues.append("catalog-memory-probe-authority-mismatch")
            del memory_entries, memory_generation
        except Exception as exc:
            issues.append(f"catalog:{type(exc).__name__}: {exc}")
        finally:
            if tracemalloc.is_tracing():
                tracemalloc.stop()

    if catalog_seconds > CATALOG_MAX_SECONDS:
        issues.append(
            f"catalog-performance:{catalog_seconds:.6f}>{CATALOG_MAX_SECONDS:.6f}"
        )
    if peak_mib > PEAK_MEMORY_MAX_MIB:
        issues.append(f"peak-memory:{peak_mib:.3f}>{PEAK_MEMORY_MAX_MIB:.3f}")

    samples = sorted(
        entries,
        key=lambda item: str(item.data.get("id") or ""),
    )[:SAMPLE_LIMIT]
    exact_context_seconds: list[float] = []
    search_seconds: list[float] = []
    sample_bindings: list[dict[str, str]] = []
    for entry in samples:
        try:
            binding = binding_from_projection(entry.data)
            _context, elapsed = _timed(
                lambda current=binding: read_bound_argument_context(root, current)
            )
            exact_context_seconds.append(elapsed)
            sample_bindings.append(binding.to_dict())
            query = str(entry.data.get("title") or entry.data.get("id") or "")
            _results, elapsed = _timed(
                lambda current_query=query: search_model_bound_entries(
                    root,
                    entries,
                    query=current_query,
                    path_hint="/".join(entry.data.get("domain_path") or []),
                    top_k=5,
                )
            )
            search_seconds.append(elapsed)
        except Exception as exc:
            issues.append(
                f"sample:{entry.data.get('id') or '<unknown>'}:{type(exc).__name__}: {exc}"
            )

    exact_p95 = _percentile(exact_context_seconds, 0.95)
    search_p95 = _percentile(search_seconds, 0.95)
    if exact_p95 > EXACT_CONTEXT_P95_MAX_SECONDS:
        issues.append(
            f"exact-context-p95:{exact_p95:.6f}>{EXACT_CONTEXT_P95_MAX_SECONDS:.6f}"
        )
    if search_p95 > SEARCH_P95_MAX_SECONDS:
        issues.append(f"search-p95:{search_p95:.6f}>{SEARCH_P95_MAX_SECONDS:.6f}")

    expected_count = int(authority.get("card_count") or 0)
    if authority.get("ok") and len(entries) != expected_count:
        issues.append(f"catalog-count:{len(entries)}!={expected_count}")
    if authority.get("ok") and str(generation.get("generation_id") or "") != str(
        authority.get("generation_id") or ""
    ):
        issues.append("catalog-generation-does-not-match-validated-authority")

    return {
        "schema_version": "khaos-brain.logicguard-runtime-readiness.v1",
        "ok": not issues,
        "repo_root": str(root),
        "dependency": dependency,
        "authority": authority,
        "generation_id": str(generation.get("generation_id") or ""),
        "entry_count": len(entries),
        "sample_count": len(samples),
        "sample_bindings": sample_bindings,
        "performance": {
            "authority_validation_seconds": round(authority_seconds, 6),
            "catalog_load_seconds": round(catalog_seconds, 6),
            "exact_context_p50_seconds": round(
                statistics.median(exact_context_seconds) if exact_context_seconds else 0.0,
                6,
            ),
            "exact_context_p95_seconds": round(exact_p95, 6),
            "search_p50_seconds": round(
                statistics.median(search_seconds) if search_seconds else 0.0,
                6,
            ),
            "search_p95_seconds": round(search_p95, 6),
            "catalog_peak_memory_mib": round(peak_mib, 3),
            "budgets": {
                "catalog_max_seconds": CATALOG_MAX_SECONDS,
                "exact_context_p95_max_seconds": EXACT_CONTEXT_P95_MAX_SECONDS,
                "search_p95_max_seconds": SEARCH_P95_MAX_SECONDS,
                "peak_memory_max_mib": PEAK_MEMORY_MAX_MIB,
            },
        },
        "issues": issues,
        "claim_boundary": (
            "This receipt proves exact current local model/mesh/projection authority and "
            "bounded runtime performance for the sampled immutable generation. It does "
            "not prove factual truth or future AI judgment."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(args.repo_root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Khaos Brain LogicGuard runtime:", "PASS" if report["ok"] else "FAIL")
        for issue in report["issues"]:
            print(f"- {issue}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
