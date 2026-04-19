#!/usr/bin/env python3
"""Navigate the route structure of the local predictive knowledge base."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.routes import build_route_view, build_selected_views, format_route_view
from local_kb.store import load_entries, resolve_repo_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--route", default="")
    parser.add_argument("--select", default="")
    parser.add_argument("--include-cross-index", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    if args.select.strip():
        payload = build_selected_views(
            repo_root,
            route=args.route,
            selection=args.select,
            include_cross_index=args.include_cross_index,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        print("\n\n".join(format_route_view(view) for view in payload))
        return

    entries = load_entries(repo_root)
    view = build_route_view(entries, repo_root, route=args.route, include_cross_index=args.include_cross_index)
    if args.json:
        print(json.dumps(view, ensure_ascii=False, indent=2))
        return

    print(format_route_view(view))


if __name__ == "__main__":
    main()

