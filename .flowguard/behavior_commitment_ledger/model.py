"""Thin loader for the canonical Chaos Brain behavior commitment ledger."""

from __future__ import annotations

from pathlib import Path

from flowguard import BehaviorCommitmentLedger, load_behavior_commitment_ledger


LEDGER_PATH = Path(__file__).with_name("ledger.json")


def build_ledger() -> BehaviorCommitmentLedger:
    """Load the sole current JSON authority without executing a duplicate inventory."""

    return load_behavior_commitment_ledger(LEDGER_PATH)
