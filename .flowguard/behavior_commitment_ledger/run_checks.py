"""Write and review the canonical Chaos Brain behavior commitment ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from flowguard import (  # noqa: E402
    behavior_commitment_ledger_fingerprint,
    review_behavior_commitment_ledger,
    write_behavior_commitment_ledger,
)

from model import build_ledger  # noqa: E402


LEDGER_PATH = Path(__file__).with_name("ledger.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    ledger = build_ledger()
    if args.write:
        write_behavior_commitment_ledger(LEDGER_PATH, ledger)
    report = review_behavior_commitment_ledger(ledger)
    payload = {
        "ok": report.ok,
        "ledger_path": str(LEDGER_PATH),
        "ledger_fingerprint": behavior_commitment_ledger_fingerprint(ledger),
        "report": report.to_dict(),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
