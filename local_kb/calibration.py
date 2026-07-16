from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from local_kb.lifecycle import content_fingerprint, load_lifecycle_state, outcome_receipts_path


CALIBRATION_POLICY_VERSION = 1
GRADE_WEIGHTS = {"strong": 1.0, "medium": 0.5, "weak": 0.0}
POSITIVE_OUTCOMES = {"success", "no-card-success"}
NEGATIVE_OUTCOMES = {"failure", "misleading", "rework"}


def _outcomes(repo_root: Path) -> list[dict[str, Any]]:
    import json

    path = outcome_receipts_path(repo_root)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            text = raw_line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def build_calibration_evidence_index(
    repo_root: Path,
    *,
    lifecycle_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load shared outcome and lifecycle evidence once for a review cycle."""

    outcomes = _outcomes(repo_root)
    lifecycle = (
        dict(lifecycle_state)
        if lifecycle_state is not None
        else load_lifecycle_state(repo_root, repair_projection=False)
    )
    outcomes_by_entry: dict[str, list[dict[str, Any]]] = {}
    for item in outcomes:
        for value in item.get("used_entry_ids", []):
            entry_id = str(value).strip()
            if entry_id:
                outcomes_by_entry.setdefault(entry_id, []).append(item)
    observations_by_entry: dict[str, list[dict[str, Any]]] = {}
    for observation in lifecycle.get("observations", {}).values():
        if not isinstance(observation, Mapping):
            continue
        entry_id = str(observation.get("target_id") or "").strip()
        if entry_id:
            observations_by_entry.setdefault(entry_id, []).append(
                dict(observation)
            )
    return {
        "outcomes_by_entry": outcomes_by_entry,
        "observations_by_entry": observations_by_entry,
        "outcome_count": len(outcomes),
        "observation_count": sum(
            len(items) for items in observations_by_entry.values()
        ),
        "lifecycle_event_digest": str(lifecycle.get("event_digest") or ""),
    }


def calibrate_entry(
    repo_root: Path,
    entry_id: str,
    *,
    prior_confidence: float = 0.5,
    evidence_index: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    shared = dict(
        build_calibration_evidence_index(repo_root)
        if evidence_index is None
        else evidence_index
    )
    outcomes_by_entry = shared.get("outcomes_by_entry", {})
    observations_by_entry = shared.get("observations_by_entry", {})
    relevant = list(
        outcomes_by_entry.get(entry_id, [])
        if isinstance(outcomes_by_entry, Mapping)
        else []
    )
    support_by_grade = {"strong": 0, "medium": 0, "weak": 0}
    contradiction_by_grade = {"strong": 0, "medium": 0, "weak": 0}
    weighted_support = 0.0
    weighted_contradiction = 0.0
    independent_refs: set[str] = set()
    support_refs_by_grade: dict[str, set[str]] = {"strong": set(), "medium": set(), "weak": set()}
    validation_refs: set[str] = set()
    qualifying_evidence_ids: set[str] = set()
    contradicting_evidence_ids: set[str] = set()
    for item in relevant:
        grade = str(item.get("evidence_grade") or "weak")
        if grade not in GRADE_WEIGHTS:
            grade = "weak"
        outcome = str(item.get("outcome") or "unknown")
        weight = GRADE_WEIGHTS[grade]
        evidence_ref = str(item.get("evidence_ref") or "")
        evidence_key = content_fingerprint([item.get("evidence_kind"), evidence_ref]) if evidence_ref else ""
        if evidence_key:
            independent_refs.add(evidence_key)
        if str(item.get("evidence_kind") or "") == "validation" and bool(item.get("verified")) and evidence_key:
            validation_refs.add(evidence_key)
        if outcome in POSITIVE_OUTCOMES:
            support_by_grade[grade] += 1
            weighted_support += weight
            if evidence_key and str(item.get("evidence_kind") or "") != "validation":
                support_refs_by_grade[grade].add(evidence_key)
                qualifying_evidence_ids.add(str(item.get("outcome_id") or ""))
        elif outcome in NEGATIVE_OUTCOMES:
            contradiction_by_grade[grade] += 1
            weighted_contradiction += weight
            contradicting_evidence_ids.add(str(item.get("outcome_id") or ""))
    relevant_observations = (
        observations_by_entry.get(entry_id, [])
        if isinstance(observations_by_entry, Mapping)
        else []
    )
    for observation in relevant_observations:
        if not isinstance(observation, Mapping):
            continue
        grade = str(observation.get("evidence_grade") or "weak")
        if grade not in GRADE_WEIGHTS:
            grade = "weak"
        source_event = observation.get("source_event", {}) if isinstance(observation.get("source_event"), Mapping) else {}
        context = source_event.get("context", {}) if isinstance(source_event.get("context"), Mapping) else {}
        outcome = str(context.get("outcome") or "success").lower()
        fingerprint = str(observation.get("source_fingerprint") or "")
        evidence_id = str(observation.get("latest_event_id") or observation.get("observation_id") or "")
        if outcome in NEGATIVE_OUTCOMES:
            contradiction_by_grade[grade] += 1
            weighted_contradiction += GRADE_WEIGHTS[grade]
            contradicting_evidence_ids.add(evidence_id)
        else:
            support_by_grade[grade] += 1
            weighted_support += GRADE_WEIGHTS[grade]
            if fingerprint:
                support_refs_by_grade[grade].add(fingerprint)
                independent_refs.add(fingerprint)
            qualifying_evidence_ids.add(evidence_id)
    alpha = 1.0 + weighted_support
    beta = 1.0 + weighted_contradiction
    confidence = alpha / (alpha + beta)
    variance = (alpha * beta) / (((alpha + beta) ** 2) * (alpha + beta + 1.0))
    margin = 1.96 * math.sqrt(variance)
    lower = max(0.0, confidence - margin)
    upper = min(1.0, confidence + margin)
    strong_contradiction = contradiction_by_grade["strong"] > 0
    promotion_ready = bool(
        not strong_contradiction
        and bool(validation_refs)
        and (
            len(support_refs_by_grade["strong"]) >= 1
            or len(support_refs_by_grade["medium"]) >= 2
        )
    )
    return {
        "policy_version": CALIBRATION_POLICY_VERSION,
        "entry_id": entry_id,
        "support_by_grade": support_by_grade,
        "contradiction_by_grade": contradiction_by_grade,
        "effective_sample_size": round(weighted_support + weighted_contradiction, 3),
        "independent_evidence_count": len(independent_refs),
        "independent_validation_count": len(validation_refs),
        "prior_confidence": round(float(prior_confidence), 4),
        "new_confidence": round(confidence, 4),
        "confidence_interval": [round(lower, 4), round(upper, 4)],
        "promotion_ready": promotion_ready,
        "downgrade_required": strong_contradiction,
        "outcome_receipt_count": len(relevant),
        "shared_evidence_index": True,
        "shared_lifecycle_event_digest": str(
            shared.get("lifecycle_event_digest") or ""
        ),
        "qualifying_evidence_ids": sorted(item for item in qualifying_evidence_ids if item),
        "contradicting_evidence_ids": sorted(item for item in contradicting_evidence_ids if item),
        "evidence_references": sorted(independent_refs),
        "evidence_digest": content_fingerprint(
            {
                "support": {key: sorted(value) for key, value in support_refs_by_grade.items()},
                "validation": sorted(validation_refs),
                "contradictions": sorted(contradicting_evidence_ids),
            }
        ),
    }
