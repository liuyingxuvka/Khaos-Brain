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
from local_kb.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, localized_automation_status
from local_kb.lifecycle import run_incremental_sleep
from local_kb.store import resolve_repo_root


DEFAULT_SOFT_DEADLINE_SECONDS = 660


def format_sleep_summary(receipt: dict, *, language: str = DEFAULT_LANGUAGE) -> str:
    state = str(receipt.get("final_run_state") or "failed")
    state_label = localized_automation_status(state, language)
    opening = int(receipt.get("opening_remaining") or 0)
    completed = int(receipt.get("completed_this_attempt") or 0)
    blocked = int(receipt.get("blocked_this_attempt") or 0)
    closing = int(receipt.get("closing_remaining") or 0)
    if language == "zh-CN":
        return (
            f"Sleep {receipt.get('run_id', '')}：{state_label}；"
            f"本轮开始 {opening}，完成 {completed}，阻塞 {blocked}，剩余 {closing}"
        )
    return (
        f"Sleep {receipt.get('run_id', '')}: {state_label}; "
        f"opening {opening}, completed {completed}, blocked {blocked}, remaining {closing}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--max-observations", type=int, default=250)
    parser.add_argument(
        "--soft-deadline-seconds",
        type=int,
        default=DEFAULT_SOFT_DEADLINE_SECONDS,
    )
    parser.add_argument("--language", choices=SUPPORTED_LANGUAGES, default=DEFAULT_LANGUAGE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    repo_root = resolve_repo_root(args.repo_root)
    receipt = run_incremental_sleep(
        repo_root,
        run_id=args.run_id or None,
        max_observations=max(0, int(args.max_observations)),
        soft_deadline_seconds=max(1, int(args.soft_deadline_seconds)),
    )
    if args.json:
        print_json(receipt)
    else:
        print_text(format_sleep_summary(receipt, language=args.language))
    return 0 if receipt.get("final_run_state") in {
        "completed",
        "completed_with_blocks",
        "progress_saved",
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
