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
    scenario: str = "",
    action_taken: str = "",
    observed_result: str = "",
    previous_action: str = "",
    previous_result: str = "",
    revised_action: str = "",
    revised_result: str = "",
    operational_use: str = "",
    reuse_judgment: str = "",
    source_kind: str = "task",
    agent_name: str = "kb-recorder",
    thread_ref: str = "",
    project_ref: str = "",
    workspace_root: str = "",
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
            "project_ref": project_ref,
            "workspace_root": workspace_root,
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
            "predictive_observation": {
                "scenario": scenario,
                "action_taken": action_taken,
                "observed_result": observed_result,
                "contrastive_evidence": {
                    "previous_action": previous_action,
                    "previous_result": previous_result,
                    "revised_action": revised_action,
                    "revised_result": revised_result,
                },
                "operational_use": operational_use,
                "reuse_judgment": reuse_judgment,
            },
        },
    )


def record_observation(repo_root, observation: dict[str, Any]):
    history_path = record_history_event(repo_root, observation)
    # The append-only history remains the intake authority.  Lifecycle
    # admission is idempotent, and Sleep can recover it from history after an
    # interruption, so an observation can never disappear behind a watermark.
    from local_kb.lifecycle import admit_observation
    from local_kb.maintenance_standard import maintenance_standard_is_active

    if maintenance_standard_is_active(repo_root):
        admit_observation(repo_root, observation)
    return history_path
