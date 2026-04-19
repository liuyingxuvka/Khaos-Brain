from __future__ import annotations

from typing import Any

from local_kb.common import csv_to_list, parse_route_segments
from local_kb.history import build_history_event, record_history_event


def _default_observation_rationale(
    hit_quality: str,
    suggested_action: str,
    exposed_gap: bool,
) -> str:
    parts: list[str] = []
    if hit_quality and hit_quality != "none":
        parts.append(f"retrieval={hit_quality}")
    if suggested_action and suggested_action != "none":
        parts.append(f"next={suggested_action}")
    if exposed_gap:
        parts.append("gap-exposed")
    return ", ".join(parts)


def build_observation(
    task_summary: str,
    route_hint: str = "",
    entry_ids: str = "",
    hit_quality: str = "none",
    outcome: str = "",
    comment: str = "",
    suggested_action: str = "none",
    exposed_gap: bool = False,
    source_kind: str = "task",
    agent_name: str = "kb-recorder",
    thread_ref: str = "",
) -> dict[str, Any]:
    rationale = comment.strip() or _default_observation_rationale(
        hit_quality=hit_quality,
        suggested_action=suggested_action,
        exposed_gap=exposed_gap,
    )
    return build_history_event(
        "observation",
        source={
            "kind": source_kind,
            "agent": agent_name,
            "thread_ref": thread_ref,
        },
        target={
            "kind": "task-observation",
            "task_summary": task_summary,
            "route_hint": parse_route_segments(route_hint),
            "entry_ids": csv_to_list(entry_ids),
        },
        rationale=rationale,
        context={
            "hit_quality": hit_quality,
            "outcome": outcome,
            "suggested_action": suggested_action,
            "exposed_gap": exposed_gap,
        },
    )


def record_observation(repo_root, observation: dict[str, Any]):
    return record_history_event(repo_root, observation)
