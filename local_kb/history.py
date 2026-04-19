from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from local_kb.common import utc_now_iso
from local_kb.store import append_timeline_event


def _clean_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}

    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if item is None:
            continue
        if isinstance(item, str):
            text = item.strip()
            if not text:
                continue
            cleaned[key] = text
            continue
        if isinstance(item, Mapping):
            nested = _clean_mapping(item)
            if nested:
                cleaned[key] = nested
            continue
        if isinstance(item, list):
            if not item:
                continue
            cleaned[key] = item
            continue
        cleaned[key] = item
    return cleaned


def build_history_event(
    event_type: str,
    *,
    source: Mapping[str, Any] | None = None,
    target: Mapping[str, Any] | None = None,
    rationale: str = "",
    context: Mapping[str, Any] | None = None,
    event_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "event_id": event_id or str(uuid4()),
        "event_type": event_type,
        "created_at": created_at or utc_now_iso(),
        "source": _clean_mapping(source),
        "target": _clean_mapping(target),
        "rationale": rationale.strip(),
        "context": _clean_mapping(context),
    }


def record_history_event(repo_root: Path, event: dict[str, Any]) -> Path:
    return append_timeline_event(repo_root, event)
