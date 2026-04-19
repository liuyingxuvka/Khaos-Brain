from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from local_kb.common import csv_to_list, normalize_string_list, parse_route_segments, slugify
from local_kb.history import build_history_event, record_history_event
from local_kb.store import candidate_dir, history_events_path, write_yaml_file


SCHEMA_VERSION = 1
CONSOLIDATION_NOTES = [
    "This scaffold only groups likely maintenance actions from stored history.",
    "AI consolidation should inspect these grouped actions before changing cards or taxonomy.",
]
APPLY_MODE_NONE = "none"
APPLY_MODE_NEW_CANDIDATES = "new-candidates"
AUTO_CANDIDATE_SCOPE = "private"
ACTION_BASE_SCORES = {
    "review-candidate": 3,
    "review-entry-update": 4,
    "consider-new-candidate": 3,
    "review-taxonomy": 3,
    "investigate-gap": 2,
}
HIT_QUALITY_SCORES = {
    "weak": 1,
    "miss": 2,
    "misleading": 3,
}


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sanitize_run_id(value: str | None) -> str:
    if not value:
        return utc_now_compact()
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "-", value.strip())
    return cleaned.strip("-") or utc_now_compact()


def normalize_apply_mode(value: str | None) -> str:
    mode = str(value or APPLY_MODE_NONE).strip().lower() or APPLY_MODE_NONE
    if mode in {APPLY_MODE_NONE, APPLY_MODE_NEW_CANDIDATES}:
        return mode
    raise ValueError(f"Unsupported consolidation apply mode: {value}")


def normalize_entry_ids(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = csv_to_list(value)
    else:
        raw_items = normalize_string_list(value)
    return sorted({str(item).strip() for item in raw_items if str(item).strip()})


def normalize_event(raw: dict[str, Any], source_line: int) -> dict[str, Any]:
    event = dict(raw)
    source = event.get("source", {}) if isinstance(event.get("source"), dict) else {}
    target = event.get("target", {}) if isinstance(event.get("target"), dict) else {}
    context = event.get("context", {}) if isinstance(event.get("context"), dict) else {}

    route_hint = parse_route_segments(
        target.get("route_hint")
        or target.get("domain_path")
        or event.get("route_hint")
        or event.get("domain_path")
        or []
    )
    entry_ids = normalize_entry_ids(target.get("entry_ids") or event.get("entry_ids"))
    entry_id = str(target.get("entry_id") or event.get("entry_id", "") or "").strip()
    if entry_id:
        entry_ids = sorted(set(entry_ids + [entry_id]))
    event_id = str(event.get("event_id", "") or f"history-line-{source_line:06d}")

    event["event_id"] = event_id
    event["event_type"] = str(event.get("event_type", "") or "").strip().lower()
    event["created_at"] = str(event.get("created_at", "") or "").strip()
    event["source"] = source
    event["target"] = target
    event["context"] = context
    event["entry_id"] = entry_id
    event["entry_ids"] = entry_ids
    event["route_hint"] = route_hint
    event["task_summary"] = str(target.get("task_summary") or event.get("task_summary", "") or "").strip()
    event["suggested_action"] = str(
        context.get("suggested_action") or event.get("suggested_action", "none") or "none"
    ).strip().lower()
    event["hit_quality"] = str(
        context.get("hit_quality") or event.get("hit_quality", "none") or "none"
    ).strip().lower()
    event["exposed_gap"] = bool(context.get("exposed_gap", event.get("exposed_gap", False)))
    event["source_line"] = source_line
    return event


def load_history_events(repo_root: Path, max_events: int | None = None) -> list[dict[str, Any]]:
    path = history_events_path(repo_root)
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for source_line, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:  # pragma: no cover - malformed user data
                raise ValueError(f"Invalid JSON in {path} at line {source_line}") from exc
            if not isinstance(payload, dict):  # pragma: no cover - malformed user data
                raise ValueError(f"History event at line {source_line} is not an object")
            events.append(normalize_event(payload, source_line))

    if max_events is not None and max_events > 0:
        events = events[-max_events:]

    return sorted(
        events,
        key=lambda item: (
            item.get("created_at") or "",
            item.get("source_line") or 0,
            item.get("event_id") or "",
        ),
    )


def route_label(route_hint: list[str]) -> str:
    return "/".join(route_hint)


def relative_repo_path(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def route_or_task_target(event: dict[str, Any]) -> tuple[str, str]:
    route_hint = event.get("route_hint", [])
    if route_hint:
        return "route", route_label(route_hint)
    task_summary = str(event.get("task_summary", "") or "").strip()
    if task_summary:
        return "task", slugify(task_summary)[:48]
    return "event", str(event["event_id"])


def build_action_seeds(event: dict[str, Any]) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    event_type = event.get("event_type", "")
    route_hint = event.get("route_hint", [])
    route_ref = route_label(route_hint)

    if event_type == "candidate-created":
        entry_id = event.get("entry_id") or event["event_id"]
        seeds.append(
            {
                "action_type": "review-candidate",
                "target_kind": "entry",
                "target_ref": str(entry_id),
                "route_ref": route_ref,
                "reason": "candidate-created",
            }
        )
        return seeds

    suggested_action = event.get("suggested_action", "none")
    if suggested_action == "update-card":
        entry_ids = event.get("entry_ids", [])
        if entry_ids:
            for entry_id in entry_ids:
                seeds.append(
                    {
                        "action_type": "review-entry-update",
                        "target_kind": "entry",
                        "target_ref": str(entry_id),
                        "route_ref": route_ref,
                        "reason": "suggested-action:update-card",
                    }
                )
        else:
            target_kind, target_ref = route_or_task_target(event)
            seeds.append(
                {
                    "action_type": "review-entry-update",
                    "target_kind": target_kind,
                    "target_ref": target_ref,
                    "route_ref": route_ref,
                    "reason": "suggested-action:update-card",
                }
            )
        return seeds

    if suggested_action == "new-candidate":
        target_kind, target_ref = route_or_task_target(event)
        seeds.append(
            {
                "action_type": "consider-new-candidate",
                "target_kind": target_kind,
                "target_ref": target_ref,
                "route_ref": route_ref,
                "reason": "suggested-action:new-candidate",
            }
        )
        return seeds

    if suggested_action == "taxonomy-change":
        target_kind, target_ref = route_or_task_target(event)
        seeds.append(
            {
                "action_type": "review-taxonomy",
                "target_kind": target_kind,
                "target_ref": target_ref,
                "route_ref": route_ref,
                "reason": "suggested-action:taxonomy-change",
            }
        )
        return seeds

    if event.get("exposed_gap") or event.get("hit_quality") in HIT_QUALITY_SCORES:
        target_kind, target_ref = route_or_task_target(event)
        seeds.append(
            {
                "action_type": "investigate-gap",
                "target_kind": target_kind,
                "target_ref": target_ref,
                "route_ref": route_ref,
                "reason": f"hit-quality:{event.get('hit_quality', 'none')}",
            }
        )
    return seeds


def sort_counter(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def build_next_step(action_type: str, target_kind: str, target_ref: str, routes: list[str]) -> str:
    if target_kind == "entry":
        if action_type == "review-candidate":
            return f"Inspect candidate entry {target_ref} during AI consolidation and decide whether it should stay a candidate or be promoted."
        if action_type == "review-entry-update":
            return f"Inspect timeline evidence for entry {target_ref} and decide whether the current card needs an AI-authored update."
    if target_kind == "route" and target_ref:
        if action_type == "consider-new-candidate":
            return f"Inspect route {target_ref} and decide whether a new candidate card should be captured."
        if action_type == "review-taxonomy":
            return f"Inspect route {target_ref} for a possible taxonomy adjustment."
        return f"Inspect route {target_ref} for repeated misses or weak hits before changing any cards."
    if routes:
        return f"Inspect supporting history for route {routes[0]} before deciding on any KB edits."
    return "Inspect the grouped history events and choose the next AI consolidation action."


def suggested_artifact_kind(action_type: str, target_kind: str) -> str:
    if action_type == "review-entry-update":
        return "entry-update-proposal"
    if action_type == "review-taxonomy":
        return "taxonomy-change-proposal"
    if action_type == "consider-new-candidate":
        return "candidate-entry-proposal"
    if action_type == "review-candidate":
        return "candidate-review-summary"
    if action_type == "investigate-gap":
        if target_kind == "route":
            return "route-gap-summary"
        return "gap-investigation-summary"
    return "maintenance-note"


def score_action(action_type: str, event_count: int, hit_quality: Counter[str], exposed_gap_count: int) -> int:
    score = ACTION_BASE_SCORES.get(action_type, 1)
    score += event_count
    score += sum(HIT_QUALITY_SCORES.get(key, 0) * count for key, count in hit_quality.items())
    if exposed_gap_count:
        score += 2
    return score


def group_candidate_actions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for event in events:
        for seed in build_action_seeds(event):
            action_key = f"{seed['action_type']}::{seed['target_kind']}::{seed['target_ref']}"
            group = grouped.setdefault(
                action_key,
                {
                    "action_key": action_key,
                    "action_type": seed["action_type"],
                    "target": {
                        "kind": seed["target_kind"],
                        "ref": seed["target_ref"],
                    },
                    "_event_ids": set(),
                    "_entry_ids": set(),
                    "_routes": set(),
                    "_reasons": set(),
                    "_event_types": Counter(),
                    "_suggested_actions": Counter(),
                    "_hit_quality": Counter(),
                    "_exposed_gap_count": 0,
                    "_first_event_at": "",
                    "_latest_event_at": "",
                },
            )

            event_id = str(event["event_id"])
            group["_event_ids"].add(event_id)
            group["_entry_ids"].update(event.get("entry_ids", []))
            if seed.get("route_ref"):
                group["_routes"].add(seed["route_ref"])
            elif event.get("route_hint"):
                group["_routes"].add(route_label(event["route_hint"]))
            group["_reasons"].add(seed["reason"])

            event_type = str(event.get("event_type", "") or "")
            if event_type:
                group["_event_types"][event_type] += 1
            suggested_action = str(event.get("suggested_action", "none") or "none")
            if suggested_action != "none":
                group["_suggested_actions"][suggested_action] += 1
            hit_quality = str(event.get("hit_quality", "none") or "none")
            if hit_quality != "none":
                group["_hit_quality"][hit_quality] += 1
            if event.get("exposed_gap"):
                group["_exposed_gap_count"] += 1

            created_at = str(event.get("created_at", "") or "")
            if created_at and (not group["_first_event_at"] or created_at < group["_first_event_at"]):
                group["_first_event_at"] = created_at
            if created_at and (not group["_latest_event_at"] or created_at > group["_latest_event_at"]):
                group["_latest_event_at"] = created_at

    actions: list[dict[str, Any]] = []
    for action_key, group in grouped.items():
        event_ids = sorted(group["_event_ids"])
        entry_ids = sorted(group["_entry_ids"])
        routes = sorted(route for route in group["_routes"] if route)
        hit_quality = group["_hit_quality"]
        action = {
            "action_key": action_key,
            "action_type": group["action_type"],
            "target": group["target"],
            "priority_score": score_action(
                action_type=group["action_type"],
                event_count=len(event_ids),
                hit_quality=hit_quality,
                exposed_gap_count=group["_exposed_gap_count"],
            ),
            "event_count": len(event_ids),
            "event_ids": event_ids,
            "entry_ids": entry_ids,
            "routes": routes,
            "signals": {
                "event_types": sort_counter(group["_event_types"]),
                "suggested_actions": sort_counter(group["_suggested_actions"]),
                "hit_quality": sort_counter(hit_quality),
                "exposed_gap_count": group["_exposed_gap_count"],
            },
            "reasons": sorted(group["_reasons"]),
            "first_event_at": group["_first_event_at"],
            "latest_event_at": group["_latest_event_at"],
            "ai_decision_required": True,
            "recommended_next_step": build_next_step(
                action_type=group["action_type"],
                target_kind=group["target"]["kind"],
                target_ref=group["target"]["ref"],
                routes=routes,
            ),
        }
        actions.append(action)

    return sorted(
        actions,
        key=lambda item: (
            -int(item["priority_score"]),
            item["action_type"],
            str(item["target"]["kind"]),
            str(item["target"]["ref"]),
        ),
    )


def events_by_id(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(event["event_id"]): event for event in events}


def supporting_events_for_action(
    action: dict[str, Any],
    indexed_events: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    supporting: list[dict[str, Any]] = []
    for event_id in action.get("event_ids", []):
        event = indexed_events.get(str(event_id))
        if event is not None:
            supporting.append(event)
    return supporting


def collect_task_summaries(events: list[dict[str, Any]]) -> list[str]:
    summaries: list[str] = []
    seen: set[str] = set()
    for event in events:
        summary = str(event.get("task_summary", "") or "").strip()
        if not summary or summary in seen:
            continue
        seen.add(summary)
        summaries.append(summary)
    return summaries


def describe_apply_eligibility(
    action: dict[str, Any],
    supporting_events: list[dict[str, Any]],
) -> dict[str, Any]:
    if action["action_type"] != "consider-new-candidate":
        return {
            "supported_mode": APPLY_MODE_NEW_CANDIDATES,
            "eligible": False,
            "reason": "Automatic apply is limited to new candidate creation; this action stays proposal-only.",
        }
    if action["target"]["kind"] != "route":
        return {
            "supported_mode": APPLY_MODE_NEW_CANDIDATES,
            "eligible": False,
            "reason": "Automatic apply only supports route-grouped candidate creation.",
        }
    if int(action.get("event_count", 0)) < 2:
        return {
            "supported_mode": APPLY_MODE_NEW_CANDIDATES,
            "eligible": False,
            "reason": "Automatic apply requires at least 2 grouped new-candidate observations for the same route.",
        }
    if not collect_task_summaries(supporting_events):
        return {
            "supported_mode": APPLY_MODE_NEW_CANDIDATES,
            "eligible": False,
            "reason": "Automatic apply requires supporting observations with task summaries.",
        }
    return {
        "supported_mode": APPLY_MODE_NEW_CANDIDATES,
        "eligible": True,
        "reason": "Eligible for conservative candidate scaffold creation.",
    }


def annotate_actions_with_apply_eligibility(
    actions: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    indexed_events = events_by_id(events)
    annotated: list[dict[str, Any]] = []
    for action in actions:
        annotated_action = dict(action)
        supporting_events = supporting_events_for_action(action, indexed_events)
        task_summaries = collect_task_summaries(supporting_events)
        annotated_action["task_summaries"] = task_summaries
        annotated_action["suggested_artifact_kind"] = suggested_artifact_kind(
            action_type=action["action_type"],
            target_kind=str(action["target"]["kind"]),
        )
        annotated_action["apply_eligibility"] = describe_apply_eligibility(
            action=action,
            supporting_events=supporting_events,
        )
        annotated.append(annotated_action)
    return annotated


def consolidation_run_dir(repo_root: Path, run_id: str) -> Path:
    return repo_root / "kb" / "history" / "consolidation" / run_id


def action_stub_dir(repo_root: Path, run_id: str) -> Path:
    return consolidation_run_dir(repo_root, run_id) / "actions"


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def build_snapshot_payload(
    repo_root: Path,
    run_id: str,
    generated_at: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "local-kb-consolidation-snapshot",
        "run_id": run_id,
        "generated_at": generated_at,
        "history_path": relative_repo_path(repo_root, history_events_path(repo_root)),
        "event_count": len(events),
        "events": events,
    }


def build_proposal_payload(
    repo_root: Path,
    run_id: str,
    generated_at: str,
    actions: list[dict[str, Any]],
    event_count: int,
    max_events: int | None,
) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": "local-kb-consolidation-proposal",
        "run_id": run_id,
        "generated_at": generated_at,
        "history_path": relative_repo_path(repo_root, history_events_path(repo_root)),
        "event_count": event_count,
        "candidate_action_count": len(actions),
        "actions": actions,
        "notes": CONSOLIDATION_NOTES,
    }
    if max_events is not None:
        payload["max_events"] = max_events
    return payload


def action_stub_filename(action_key: str, index: int) -> str:
    base_name = slugify(action_key.replace("::", "-"))[:72] or f"action-{index + 1}"
    action_hash = hashlib.sha1(action_key.encode("utf-8")).hexdigest()[:8]
    return f"{index + 1:03d}-{base_name}-{action_hash}.json"


def build_action_stub_payload(
    action: dict[str, Any],
    run_id: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "local-kb-consolidation-action-stub",
        "run_id": run_id,
        "generated_at": generated_at,
        "action_key": action["action_key"],
        "action_type": action["action_type"],
        "target": dict(action["target"]),
        "priority_score": int(action["priority_score"]),
        "event_count": int(action["event_count"]),
        "event_ids": list(action.get("event_ids", [])),
        "routes": list(action.get("routes", [])),
        "task_summaries": list(action.get("task_summaries", [])),
        "signals": dict(action.get("signals", {})),
        "suggested_artifact_kind": str(action.get("suggested_artifact_kind", "")),
        "apply_eligibility": dict(action.get("apply_eligibility", {})),
        "recommended_next_step": str(action.get("recommended_next_step", "")),
        "ai_decision_required": bool(action.get("ai_decision_required", True)),
    }


def emit_action_stubs(
    repo_root: Path,
    run_id: str,
    generated_at: str,
    actions: list[dict[str, Any]],
) -> dict[str, Any]:
    target_dir = action_stub_dir(repo_root, run_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    stub_paths: list[str] = []
    for index, action in enumerate(actions):
        stub_path = target_dir / action_stub_filename(str(action["action_key"]), index)
        stub_payload = build_action_stub_payload(
            action=action,
            run_id=run_id,
            generated_at=generated_at,
        )
        write_json_file(stub_path, stub_payload)
        stub_paths.append(relative_repo_path(repo_root, stub_path))

    return {
        "action_stub_dir": relative_repo_path(repo_root, target_dir),
        "action_stub_count": len(stub_paths),
        "action_stub_paths": stub_paths,
    }


def emit_artifacts(
    repo_root: Path,
    run_id: str,
    generated_at: str,
    snapshot_payload: dict[str, Any],
    proposal_payload: dict[str, Any],
) -> dict[str, Any]:
    run_dir = consolidation_run_dir(repo_root, run_id)
    snapshot_path = run_dir / "snapshot.json"
    proposal_path = run_dir / "proposal.json"
    write_json_file(snapshot_path, snapshot_payload)
    write_json_file(proposal_path, proposal_payload)
    action_stub_artifacts = emit_action_stubs(
        repo_root=repo_root,
        run_id=run_id,
        generated_at=generated_at,
        actions=list(proposal_payload.get("actions", [])),
    )
    artifact_paths: dict[str, Any] = {
        "run_dir": relative_repo_path(repo_root, run_dir),
        "snapshot_path": relative_repo_path(repo_root, snapshot_path),
        "proposal_path": relative_repo_path(repo_root, proposal_path),
    }
    artifact_paths.update(action_stub_artifacts)
    return artifact_paths


def route_candidate_id(route_ref: str) -> str:
    route_slug = slugify(route_ref.replace("/", "-"))[:32] or "route"
    route_hash = hashlib.sha1(route_ref.encode("utf-8")).hexdigest()[:8]
    return f"cand-auto-{route_slug}-{route_hash}"


def summarize_examples(values: list[str], limit: int = 3) -> str:
    if not values:
        return ""
    clipped = values[:limit]
    suffix = " ..." if len(values) > limit else ""
    return "; ".join(clipped) + suffix


def build_auto_candidate_entry(
    action: dict[str, Any],
    supporting_events: list[dict[str, Any]],
    run_id: str,
    generated_at: str,
) -> dict[str, Any]:
    route_ref = str(action["target"]["ref"])
    route_segments = parse_route_segments(route_ref)
    route_title = " / ".join(route_segments) if route_segments else route_ref
    task_summaries = collect_task_summaries(supporting_events)
    updated_at = generated_at[:10]
    return {
        "id": route_candidate_id(route_ref),
        "title": f"Repeated route gap in {route_title}",
        "type": "model",
        "scope": AUTO_CANDIDATE_SCOPE,
        "domain_path": route_segments,
        "cross_index": [],
        "tags": sorted(set(route_segments + ["auto-generated", "consolidation"])),
        "trigger_keywords": sorted(set(route_segments)),
        "if": {
            "notes": (
                f"Auto-created from {action['event_count']} grouped new-candidate observations. "
                f"Example task summaries: {summarize_examples(task_summaries)}"
            ).strip()
        },
        "action": {
            "description": f"Handle tasks routed through {route_title} without a consolidated KB card."
        },
        "predict": {
            "expected_result": (
                f"Grouped observations suggest Codex will keep missing reusable guidance for {route_title} "
                "until a route-specific card is authored."
            ),
            "alternatives": [],
        },
        "use": {
            "guidance": (
                "Review the cited observations and replace this auto-created scaffold with a specific "
                "predictive card before any promotion."
            )
        },
        "confidence": round(min(0.75, 0.45 + (0.05 * int(action["event_count"]))), 2),
        "source": [
            {
                "origin": "auto consolidation apply",
                "date": updated_at,
                "run_id": run_id,
                "route": route_ref,
                "event_ids": list(action["event_ids"]),
            }
        ],
        "status": "candidate",
        "updated_at": updated_at,
    }


def build_empty_apply_summary(apply_mode: str) -> dict[str, Any]:
    return {
        "apply_mode": apply_mode,
        "created_candidate_count": 0,
        "skipped_action_count": 0,
        "created_candidates": [],
        "skipped_actions": [],
    }


def apply_new_candidate_actions(
    repo_root: Path,
    actions: list[dict[str, Any]],
    events: list[dict[str, Any]],
    run_id: str,
    generated_at: str,
) -> dict[str, Any]:
    indexed_events = events_by_id(events)
    created_candidates: list[dict[str, Any]] = []
    skipped_actions: list[dict[str, Any]] = []

    for action in actions:
        supporting_events = supporting_events_for_action(action, indexed_events)
        eligibility = action.get("apply_eligibility") or describe_apply_eligibility(action, supporting_events)
        if not eligibility.get("eligible", False):
            skipped_actions.append(
                {
                    "action_key": action["action_key"],
                    "action_type": action["action_type"],
                    "target": dict(action["target"]),
                    "reason": eligibility["reason"],
                    "event_ids": list(action["event_ids"]),
                }
            )
            continue

        entry = build_auto_candidate_entry(
            action=action,
            supporting_events=supporting_events,
            run_id=run_id,
            generated_at=generated_at,
        )
        target_path = candidate_dir(repo_root) / f"{entry['id']}.yaml"
        relative_target_path = relative_repo_path(repo_root, target_path)
        if target_path.exists():
            skipped_actions.append(
                {
                    "action_key": action["action_key"],
                    "action_type": action["action_type"],
                    "target": dict(action["target"]),
                    "reason": f"Candidate file already exists: {relative_target_path}",
                    "event_ids": list(action["event_ids"]),
                }
            )
            continue

        write_yaml_file(target_path, entry)
        history_event = build_history_event(
            "candidate-created",
            source={
                "kind": "consolidation-apply",
                "agent": "kb-consolidate",
                "run_id": run_id,
            },
            target={
                "kind": "candidate-entry",
                "entry_id": entry["id"],
                "entry_path": relative_target_path,
                "scope": entry["scope"],
                "domain_path": entry["domain_path"],
            },
            rationale=f"Applied grouped consider-new-candidate action {action['action_key']}",
            context={
                "action_key": action["action_key"],
                "event_count": action["event_count"],
                "event_ids": list(action["event_ids"]),
                "auto_apply_mode": APPLY_MODE_NEW_CANDIDATES,
                "title": entry["title"],
                "entry_type": entry["type"],
            },
        )
        record_history_event(repo_root, history_event)
        created_candidates.append(
            {
                "action_key": action["action_key"],
                "entry_id": entry["id"],
                "entry_path": relative_target_path,
                "event_ids": list(action["event_ids"]),
            }
        )

    return {
        "apply_mode": APPLY_MODE_NEW_CANDIDATES,
        "created_candidate_count": len(created_candidates),
        "skipped_action_count": len(skipped_actions),
        "created_candidates": created_candidates,
        "skipped_actions": skipped_actions,
    }


def build_apply_payload(
    repo_root: Path,
    run_id: str,
    generated_at: str,
    apply_summary: dict[str, Any],
    event_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "local-kb-consolidation-apply-report",
        "run_id": run_id,
        "generated_at": generated_at,
        "history_path": relative_repo_path(repo_root, history_events_path(repo_root)),
        "history_event_count_before_apply": event_count,
        **apply_summary,
    }


def emit_apply_artifact(
    repo_root: Path,
    run_id: str,
    apply_payload: dict[str, Any],
) -> str:
    run_dir = consolidation_run_dir(repo_root, run_id)
    apply_path = run_dir / "apply.json"
    write_json_file(apply_path, apply_payload)
    return relative_repo_path(repo_root, apply_path)


def consolidate_history(
    repo_root: Path,
    run_id: str | None = None,
    emit_files: bool = False,
    max_events: int | None = None,
    apply_mode: str = APPLY_MODE_NONE,
) -> dict[str, Any]:
    clean_run_id = sanitize_run_id(run_id)
    normalized_apply_mode = normalize_apply_mode(apply_mode)
    generated_at = utc_now_iso()
    events = load_history_events(repo_root, max_events=max_events)
    actions = annotate_actions_with_apply_eligibility(group_candidate_actions(events), events)
    proposal_payload = build_proposal_payload(
        repo_root=repo_root,
        run_id=clean_run_id,
        generated_at=generated_at,
        actions=actions,
        event_count=len(events),
        max_events=max_events,
    )
    artifact_paths: dict[str, Any] = {}
    should_emit_artifacts = emit_files or normalized_apply_mode != APPLY_MODE_NONE
    if should_emit_artifacts:
        snapshot_payload = build_snapshot_payload(
            repo_root=repo_root,
            run_id=clean_run_id,
            generated_at=generated_at,
            events=events,
        )
        artifact_paths = emit_artifacts(
            repo_root=repo_root,
            run_id=clean_run_id,
            generated_at=generated_at,
            snapshot_payload=snapshot_payload,
            proposal_payload=proposal_payload,
        )
    apply_summary = build_empty_apply_summary(normalized_apply_mode)
    if normalized_apply_mode == APPLY_MODE_NEW_CANDIDATES:
        apply_summary = apply_new_candidate_actions(
            repo_root=repo_root,
            actions=actions,
            events=events,
            run_id=clean_run_id,
            generated_at=generated_at,
        )
        apply_payload = build_apply_payload(
            repo_root=repo_root,
            run_id=clean_run_id,
            generated_at=generated_at,
            apply_summary=apply_summary,
            event_count=len(events),
        )
        artifact_paths["apply_path"] = emit_apply_artifact(
            repo_root=repo_root,
            run_id=clean_run_id,
            apply_payload=apply_payload,
        )

    return {
        **proposal_payload,
        "apply_mode": normalized_apply_mode,
        "apply_summary": apply_summary,
        "action_stub_dir": artifact_paths.get("action_stub_dir", ""),
        "action_stub_count": int(artifact_paths.get("action_stub_count", 0) or 0),
        "artifact_paths": artifact_paths,
    }
