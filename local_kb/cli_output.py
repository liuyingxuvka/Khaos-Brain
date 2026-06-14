from __future__ import annotations

import json
import sys
from typing import Any, TextIO


def machine_json_text(payload: Any, *, indent: int | None = 2, sort_keys: bool = False) -> str:
    """Serialize CLI machine JSON so console output is safe on non-UTF-8 Windows shells."""
    return json.dumps(payload, ensure_ascii=True, indent=indent, sort_keys=sort_keys)


def print_json(payload: Any, *, indent: int | None = 2, sort_keys: bool = False) -> None:
    print(machine_json_text(payload, indent=indent, sort_keys=sort_keys))


def console_safe_text(value: Any) -> str:
    text = str(value)
    return text.encode("ascii", errors="backslashreplace").decode("ascii")


def print_text(value: Any = "", *, file: TextIO | None = None) -> None:
    print(console_safe_text(value), file=file or sys.stdout)
