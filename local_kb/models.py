from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Entry:
    path: Path
    data: dict[str, Any]
    score: float = 0.0


@dataclass
class RouteBranch:
    segment: str
    route: list[str]
    entry_ids: set[str] = field(default_factory=set)
    direct_entry_ids: set[str] = field(default_factory=set)

