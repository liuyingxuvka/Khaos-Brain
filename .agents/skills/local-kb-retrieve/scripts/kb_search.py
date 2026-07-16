#!/usr/bin/env python3
"""Search the local predictive knowledge base."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.cli_output import print_json, print_text
from local_kb.search import format_search_output, render_search_payload, search_with_receipt
from local_kb.store import resolve_repo_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--query", required=True)
    parser.add_argument("--route-hint", dest="route_hint", default="")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--with-receipt",
        action="store_true",
        help="Return a JSON envelope with the retrieval/no-card receipt.",
    )
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    entries, receipt = search_with_receipt(
        repo_root,
        query=args.query,
        path_hint=args.route_hint,
        top_k=args.top_k,
        record_receipt=True,
    )
    payload = render_search_payload(entries, repo_root)

    if args.json:
        if args.with_receipt:
            print_json(
                {
                    "results": payload,
                    "retrieval_receipt": receipt,
                    "no_card": not bool(payload),
                }
            )
        else:
            print_json(payload)
        return

    print_text(format_search_output(payload, path_hint=args.route_hint))


if __name__ == "__main__":
    main()
