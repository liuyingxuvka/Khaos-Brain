#!/usr/bin/env python3
"""Run the canonical incremental Sleep lifecycle pass."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.cli_output import print_json, print_text
from local_kb.lifecycle import run_incremental_sleep
from local_kb.store import resolve_repo_root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--max-observations", type=int, default=250)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    repo_root = resolve_repo_root(args.repo_root)
    receipt = run_incremental_sleep(
        repo_root,
        run_id=args.run_id or None,
        max_observations=max(0, int(args.max_observations)),
    )
    if args.json:
        print_json(receipt)
    else:
        print_text(
            f"Sleep {receipt['run_id']} {receipt['final_run_state']}: "
            f"watermark {receipt['input_watermark']} -> {receipt['output_watermark']}"
        )
    return 0 if receipt.get("final_run_state") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
