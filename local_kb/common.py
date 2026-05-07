from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "to",
    "in",
    "for",
    "on",
    "with",
    "by",
    "from",
    "at",
    "as",
    "is",
    "are",
    "be",
    "this",
    "that",
    "it",
    "use",
    "when",
}

ROUTE_ALIASES: dict[str, tuple[str, ...]] = {
    "automation": ("system", "automation"),
    "career": ("work", "career"),
    "desktop_app": ("engineering", "desktop-app"),
    "desktop-app": ("engineering", "desktop-app"),
    "flowguard": ("engineering", "architecture", "flowguard"),
    "flowpilot": ("codex", "workflow", "flowpilot"),
    "job-hunter": ("work", "career", "job-hunter"),
    "personal": ("work", "personal"),
    "predictive-kb": ("system", "knowledge-library"),
    "predictive-kb-preflight": ("system", "knowledge-library", "preflight"),
    "product": ("work", "product"),
    "project": ("repository", "project"),
    "repo": ("repository",),
    "search": ("system", "search"),
    "software": ("engineering", "software"),
}


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    tokens = re.findall(r"[a-zA-Z0-9_+-]+|[\u4e00-\u9fff]{1,4}", text.lower())
    cleaned: list[str] = []
    for token in tokens:
        token = token.strip()
        if not token or token in STOP_WORDS:
            continue
        if len(token) == 1 and re.fullmatch(r"[a-z]", token):
            continue
        cleaned.append(token)
    return cleaned


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(normalize_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(f"{key} {normalize_text(item)}" for key, item in value.items())
    return str(value)


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def csv_to_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_route_segments(value: Any) -> list[str]:
    raw_items = normalize_string_list(value)
    segments: list[str] = []
    for item in raw_items:
        parts = re.split(r"[\\/>|:,;]+", item)
        for part in parts:
            segment = part.strip().lower()
            if segment:
                segments.append(segment)
    return canonicalize_route_segments(segments)


def canonicalize_route_segments(value: Any) -> list[str]:
    segments = [str(item).strip().lower() for item in normalize_string_list(value) if str(item).strip()]
    if not segments:
        return []
    first, rest = segments[0], segments[1:]
    if "." in first:
        dotted = [part for part in first.split(".") if part]
        if dotted:
            first, rest = dotted[0], dotted[1:] + rest
    alias = ROUTE_ALIASES.get(first)
    if not alias:
        return segments
    alias_segments = list(alias)
    if rest and rest[: len(alias_segments) - 1] == alias_segments[1:]:
        return alias_segments + rest[len(alias_segments) - 1 :]
    return alias_segments + rest


def safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    return text.strip("-") or "entry"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
