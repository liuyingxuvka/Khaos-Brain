"""Apply the user's explicit current-machine all-active Chaos Brain rollout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.operator_activation import activate_all_for_current_machine  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument(
        "--readiness-receipt",
        type=Path,
        default=REPO_ROOT / ".local" / "assurance" / "chaos_brain_readiness.json",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = activate_all_for_current_machine(
        args.repo_root,
        args.codex_home,
        args.readiness_receipt,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("PASS" if result.get("ok") else "FAIL", result.get("status", ""))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
