#!/usr/bin/env python3
"""Record one evidence-bound direct-to-current Khaos upgrade AI decision."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.cli_output import print_json
from local_kb.maintenance_migration import record_upgrade_ai_disposition


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        receipt = record_upgrade_ai_disposition(
            Path(args.repo_root),
            work_item_id=args.work_item_id,
            actor=args.actor,
            rationale=args.rationale,
        )
    except Exception as exc:
        receipt = {
            "ok": False,
            "status": "blocked",
            "work_item_id": args.work_item_id,
            "blockers": [f"{type(exc).__name__}: {exc}"],
            "claim_boundary": (
                "No upgrade AI disposition was recorded and no card, model, mesh, "
                "projection, index, or authority pointer was changed."
            ),
        }
        print_json(receipt)
        return 1
    print_json(receipt)
    return 0 if receipt.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
