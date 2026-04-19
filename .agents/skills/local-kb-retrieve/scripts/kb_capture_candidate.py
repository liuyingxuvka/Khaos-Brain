#!/usr/bin/env python3
"""Append a new predictive candidate entry as a YAML file.

This keeps write-back explicit and reviewable.
"""

from __future__ import annotations

import argparse
from datetime import date
import sys
from pathlib import Path
from typing import Any


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.common import csv_to_list, parse_route_segments, slugify
from local_kb.history import build_history_event, record_history_event
from local_kb.store import candidate_dir, resolve_repo_root, write_yaml_file


def build_entry(args: argparse.Namespace) -> dict[str, Any]:
    today = date.today().isoformat()
    return {
        "id": f"cand-{today}-{slugify(args.title)[:24]}",
        "title": args.title,
        "type": args.entry_type,
        "scope": args.scope,
        "domain_path": parse_route_segments(args.domain_path),
        "cross_index": csv_to_list(args.cross_index),
        "tags": csv_to_list(args.tags),
        "trigger_keywords": csv_to_list(args.trigger_keywords),
        "if": {"notes": args.conditions or ""},
        "action": {"description": args.action},
        "predict": {
            "expected_result": args.expected_result,
            "alternatives": [],
        },
        "use": {"guidance": args.guidance},
        "confidence": float(args.confidence),
        "source": [{"origin": args.source, "date": today}],
        "status": "candidate",
        "updated_at": today,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--entry-type", required=True, choices=["fact", "preference", "heuristic", "model"])
    parser.add_argument("--scope", required=True, choices=["public", "private"])
    parser.add_argument("--domain-path", default="")
    parser.add_argument("--cross-index", default="")
    parser.add_argument("--tags", default="")
    parser.add_argument("--trigger-keywords", default="")
    parser.add_argument("--conditions", default="")
    parser.add_argument("--action", required=True)
    parser.add_argument("--expected-result", required=True)
    parser.add_argument("--guidance", required=True)
    parser.add_argument("--confidence", type=float, default=0.6)
    parser.add_argument("--source", default="manual entry")
    parser.add_argument("--source-kind", default="manual-entry")
    parser.add_argument("--agent-name", default="kb-capture")
    parser.add_argument("--thread-ref", default="")
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    target_dir = candidate_dir(repo_root)

    entry = build_entry(args)
    filename = f"{entry['id']}.yaml"
    path = target_dir / filename

    write_yaml_file(path, entry)
    event = build_history_event(
        "candidate-created",
        source={
            "kind": args.source_kind,
            "agent": args.agent_name,
            "thread_ref": args.thread_ref,
        },
        target={
            "kind": "candidate-entry",
            "entry_id": entry["id"],
            "entry_path": path.relative_to(repo_root).as_posix(),
            "scope": entry["scope"],
            "domain_path": entry["domain_path"],
        },
        rationale=args.source,
        context={
            "title": entry["title"],
            "entry_type": entry["type"],
        },
    )
    record_history_event(repo_root, event)

    print(f"Created predictive candidate entry: {path}")


if __name__ == "__main__":
    main()
