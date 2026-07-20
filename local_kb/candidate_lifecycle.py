from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from local_kb.common import parse_route_segments, utc_now_iso
from local_kb.history import build_history_event, record_history_event
from local_kb.lifecycle import (
    build_entry_transition_event,
    commit_lifecycle_events,
    content_fingerprint,
    evidence_items_for_observation,
    load_lifecycle_state,
)
from local_kb.store import (
    candidate_dir,
    load_yaml_file,
)


CANDIDATE_DECISION_DAYS = 7


@dataclass
class CandidateLifecyclePlan:
    """Task-local lifecycle projection plus ordered events for one Sleep cycle."""

    entry_states: dict[str, dict[str, Any]]
    known_history_event_ids: set[str]
    events: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_lifecycle_state(
        cls,
        lifecycle_state: Mapping[str, Any],
        *,
        known_history_event_ids: set[str],
    ) -> "CandidateLifecyclePlan":
        entries = lifecycle_state.get("entries", {})
        return cls(
            entry_states={
                str(entry_id): dict(state)
                for entry_id, state in (
                    entries.items() if isinstance(entries, Mapping) else []
                )
                if isinstance(state, Mapping)
            },
            known_history_event_ids=set(known_history_event_ids),
        )

    def stage_transition(self, **kwargs: Any) -> str:
        event = build_entry_transition_event(**kwargs)
        self.events.append(event)
        entry_id = str(event.get("item_id") or "")
        prior = dict(self.entry_states.get(entry_id, {}))
        prior.update(
            {
                "entry_id": entry_id,
                "status": str(event.get("to_state") or ""),
                "retrieval_eligible": bool(
                    event.get("retrieval_eligible", False)
                ),
                "reopen_condition": dict(
                    event.get("reopen_condition", {})
                    if isinstance(event.get("reopen_condition"), Mapping)
                    else {}
                ),
                "evidence_fingerprint": str(
                    event.get("evidence_fingerprint") or ""
                ),
                "decision_deadline": str(
                    event.get("decision_deadline") or ""
                ),
                "latest_event_id": str(
                    event.get("idempotency_key") or ""
                ),
            }
        )
        self.entry_states[entry_id] = prior
        return str(event.get("idempotency_key") or "")


def _predictive_block(observation: Mapping[str, Any]) -> dict[str, Any]:
    context = observation.get("context", {}) if isinstance(observation.get("context"), Mapping) else {}
    predictive = context.get("predictive_observation", {}) if isinstance(context.get("predictive_observation"), Mapping) else {}
    return dict(predictive)


def build_candidate_from_observation(
    observation: Mapping[str, Any],
    *,
    run_id: str,
) -> dict[str, Any]:
    observation_id = str(observation.get("event_id") or "").strip()
    target = observation.get("target", {}) if isinstance(observation.get("target"), Mapping) else {}
    predictive = _predictive_block(observation)
    route = parse_route_segments(target.get("route_hint", []))
    task_summary = str(target.get("task_summary") or "Predictive experience candidate").strip()
    # The candidate identity describes the bounded prediction, not the run or
    # observation that happened to reveal it.  Repeated evidence for the same
    # rule must converge on one candidate instead of creating a new card.
    stable = content_fingerprint(
        {
            "route": route,
            "scenario": predictive.get("scenario", ""),
            "action": predictive.get("action_taken", ""),
            "result": predictive.get("observed_result", ""),
        }
    )
    evidence = evidence_items_for_observation(observation)
    now = utc_now_iso()
    decision_deadline = (
        datetime.now(timezone.utc) + timedelta(days=CANDIDATE_DECISION_DAYS)
    ).replace(microsecond=0).isoformat()
    return {
        "id": f"cand-auto-{stable[:20]}",
        "title": task_summary[:160],
        "type": "model",
        "scope": "private",
        "domain_path": route or ["system", "knowledge-library", "unclassified"],
        "cross_index": [],
        "related_cards": [],
        "tags": sorted({segment for segment in route if segment} | {"sleep-generated"}),
        "trigger_keywords": sorted({segment for segment in route if segment}),
        "if": {"notes": str(predictive.get("scenario") or task_summary)},
        "action": {"description": str(predictive.get("action_taken") or "Review the recorded task action.")},
        "predict": {"expected_result": str(predictive.get("observed_result") or "The bounded task result repeats.")},
        "use": {
            "guidance": str(
                predictive.get("operational_use")
                or "Wait for independent evidence before relying on this candidate."
            )
        },
        "confidence": 0.5,
        "status": "candidate",
        "retrieval_eligible": False,
        "source": [
            {
                "origin": "sleep lifecycle",
                "observation_ids": [observation_id],
                "evidence_ids": [str(item.get("evidence_id") or "") for item in evidence],
                "evidence_grade": str(evidence[0].get("grade") or "weak"),
                "episode_timestamp": str(observation.get("created_at") or ""),
                "run_id": run_id,
                "evidence_fingerprint": stable,
            }
        ],
        "decision_deadline": decision_deadline,
        "created_at": now,
        "updated_at": now,
    }


def create_or_reuse_candidate(
    repo_root: Path,
    observation: Mapping[str, Any],
    *,
    run_id: str,
    evidence_grade: str,
    lifecycle_plan: CandidateLifecyclePlan,
    staged_upserts: dict[str, dict[str, Any]] | None = None,
    deferred_history_events: list[dict[str, Any]] | None = None,
    catalog_entries: Sequence[Any] | None = None,
) -> dict[str, Any]:
    entry = build_candidate_from_observation(observation, run_id=run_id)
    target_path = candidate_dir(repo_root) / f"{entry['id']}.yaml"
    existing_data: dict[str, Any] | None = None
    existing_path: Path | None = None
    from local_kb.model_maintenance import load_current_model_entries

    if catalog_entries is None:
        current_entries, _current_generation = load_current_model_entries(repo_root)
    else:
        current_entries = catalog_entries
    if target_path.exists():
        match = next((item for item in current_entries if item.path == target_path), None)
        if match is not None:
            existing_data = dict(match.data)
            existing_path = match.path
    if existing_data is None:
        for staged_path, staged in (staged_upserts or {}).items():
            if str(staged.get("id") or "") == str(entry["id"]):
                existing_data = dict(staged)
                existing_path = repo_root / staged_path
                break
    if existing_data is None:
        for candidate in current_entries:
            if str(candidate.data.get("id") or "") == str(entry["id"]):
                existing_data = dict(candidate.data)
                existing_path = candidate.path
                break
    created = False
    if existing_data is not None and existing_path is not None:
        entry_id = str(existing_data.get("id") or entry["id"])
        entry_path = str(existing_path.relative_to(repo_root)).replace("\\", "/")
        decision_deadline = str(existing_data.get("decision_deadline") or entry["decision_deadline"])
    else:
        entry_id = str(entry["id"])
        if not target_path.exists():
            relative_target = str(target_path.relative_to(repo_root)).replace("\\", "/")
            if staged_upserts is not None:
                staged_upserts[relative_target] = dict(entry)
            else:
                from local_kb.model_maintenance import publish_sleep_model_generation

                publication = publish_sleep_model_generation(
                    repo_root,
                    reason=f"sleep-candidate:{run_id}:{entry_id}",
                    card_upserts={relative_target: entry},
                )
                if not publication.get("ok"):
                    raise RuntimeError(
                        "Candidate model publication failed: "
                        + str(publication.get("error") or publication.get("status"))
                    )
            created = True
        entry_path = str(target_path.relative_to(repo_root)).replace("\\", "/")
        decision_deadline = str(entry["decision_deadline"])
    observation_id = str(observation.get("event_id") or "")
    event_id = f"candidate-created:{entry_id}:{observation_id}"
    if created and event_id not in lifecycle_plan.known_history_event_ids:
        history_event = build_history_event(
                "candidate-created",
                event_id=event_id,
                source={"kind": "sleep-lifecycle", "agent": "kb-sleep", "run_id": run_id},
                target={
                    "kind": "candidate-entry",
                    "entry_id": entry_id,
                    "entry_path": entry_path,
                    "domain_path": entry.get("domain_path", []),
                },
                rationale="Sleep created a bounded candidate from an admitted predictive observation.",
                context={
                    "observation_ids": [observation_id],
                    "decision_deadline": decision_deadline,
                    "retrieval_eligible": False,
                },
            )
        if deferred_history_events is not None:
            deferred_history_events.append(history_event)
        else:
            record_history_event(repo_root, history_event)
        lifecycle_plan.known_history_event_ids.add(event_id)
    evidence_fingerprint = content_fingerprint([entry_id, observation_id, evidence_grade])
    state = lifecycle_plan.entry_states.get(entry_id, {})
    current_status = str(state.get("status") or "") if isinstance(state, Mapping) else ""
    prior_fingerprint = str(state.get("evidence_fingerprint") or "") if isinstance(state, Mapping) else ""
    if created or not current_status:
        lifecycle_plan.stage_transition(
            entry_id=entry_id,
            from_state="candidate",
            to_state="candidate",
            reason="Sleep created the bounded candidate pending independent validation.",
            actor=run_id,
            evidence_ids=[observation_id],
            provenance_ids=[observation_id],
            evidence_grade=evidence_grade,
            retrieval_eligible=False,
            evidence_fingerprint=evidence_fingerprint,
            decision_deadline=decision_deadline,
            event_type="entry-lifecycle-snapshot",
        )
        # A single observation is not independent promotion evidence.  Closing
        # it immediately keeps the active backlog bounded while preserving a
        # precise machine-evaluable reopen rule.
        lifecycle_plan.stage_transition(
            entry_id=entry_id,
            from_state="candidate",
            to_state="parked",
            reason="Independent current validation is still missing.",
            actor=run_id,
            evidence_ids=[observation_id],
            provenance_ids=[observation_id],
            evidence_grade=evidence_grade,
            retrieval_eligible=False,
            reopen_condition={
                "kind": "new-independent-evidence",
                "minimum_grade": "medium",
                "requires_new_fingerprint": True,
            },
            evidence_fingerprint=evidence_fingerprint,
            event_type="candidate-transition",
        )
        current_status = "parked"
    elif current_status == "parked" and evidence_grade in {"strong", "medium"} and prior_fingerprint != evidence_fingerprint:
        decision_deadline = (
            datetime.now(timezone.utc) + timedelta(days=CANDIDATE_DECISION_DAYS)
        ).replace(microsecond=0).isoformat()
        lifecycle_plan.stage_transition(
            entry_id=entry_id,
            from_state="parked",
            to_state="candidate",
            reason="Material new independent evidence satisfied the parked reopen condition.",
            actor=run_id,
            evidence_ids=[observation_id],
            provenance_ids=[observation_id],
            evidence_grade=evidence_grade,
            retrieval_eligible=False,
            evidence_fingerprint=evidence_fingerprint,
            decision_deadline=decision_deadline,
            event_type="entry-reopened",
        )
        current_status = "candidate"
    return {
        "entry_id": entry_id,
        "entry_path": entry_path,
        "created": created,
        "decision_deadline": decision_deadline,
        "status": current_status or "parked",
        "lifecycle_event_keys": [
            str(event.get("idempotency_key") or "")
            for event in lifecycle_plan.events
            if str(event.get("item_id") or "") == entry_id
        ],
    }


def _entry_structure_is_promotable(data: Mapping[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if not str(data.get("id") or "").strip():
        issues.append("missing stable id")
    if not data.get("source"):
        issues.append("missing provenance")
    if not str((data.get("if") or {}).get("notes") or "").strip():
        issues.append("missing bounded scenario")
    if not str((data.get("action") or {}).get("description") or "").strip():
        issues.append("missing action")
    if not str((data.get("predict") or {}).get("expected_result") or "").strip():
        issues.append("missing predicted result")
    if not str((data.get("use") or {}).get("guidance") or "").strip():
        issues.append("missing operational guidance")
    if not parse_route_segments(data.get("domain_path", [])):
        issues.append("missing applicability route")
    return not issues, issues


def review_entry_lifecycles(
    repo_root: Path,
    *,
    run_id: str,
    catalog_entries: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Apply deterministic promotion/downgrade/reopen decisions before indexing."""

    from local_kb.calibration import (
        build_calibration_evidence_index,
        calibrate_entry,
    )

    from local_kb.model_maintenance import load_current_model_entries

    if catalog_entries is None:
        current_entries, _current_generation = load_current_model_entries(repo_root)
    else:
        current_entries = list(catalog_entries)
    entries = {str(item.data.get("id") or ""): item for item in current_entries}
    lifecycle = load_lifecycle_state(repo_root)
    calibration_evidence_index = build_calibration_evidence_index(
        repo_root,
        lifecycle_state=lifecycle,
    )
    reviewed = promoted = downgraded = reopened = parked = 0
    unchanged_parked_skipped = 0
    unchanged_calibration_skipped = 0
    calibration_snapshot_events: list[dict[str, Any]] = []
    decision_events: list[dict[str, Any]] = []
    decision_keys: list[str] = []
    due_entry_ids: set[str] = set()
    review_now = datetime.now(timezone.utc)
    for entry_id, state in sorted(lifecycle.get("entries", {}).items()):
        if not isinstance(state, Mapping) or entry_id not in entries:
            continue
        current_status = str(state.get("status") or entries[entry_id].data.get("status") or "candidate")
        if current_status != "candidate":
            continue
        deadline_text = str(state.get("decision_deadline") or "").strip()
        try:
            deadline = datetime.fromisoformat(deadline_text.replace("Z", "+00:00")) if deadline_text else None
        except ValueError:
            deadline = None
        # A candidate without a valid deadline is already maintenance debt;
        # leaving it active forever would make Sleep appear converged while a
        # decision obligation remains unowned.
        if deadline is None or deadline <= review_now:
            due_entry_ids.add(entry_id)
    for entry_id, state in sorted(lifecycle.get("entries", {}).items()):
        if not isinstance(state, Mapping) or entry_id not in entries:
            continue
        current_status = str(state.get("status") or entries[entry_id].data.get("status") or "candidate")
        if current_status in {"merged", "rejected", "superseded", "retired", "deprecated"}:
            continue
        outcomes_by_entry = calibration_evidence_index.get(
            "outcomes_by_entry",
            {},
        )
        observations_by_entry = calibration_evidence_index.get(
            "observations_by_entry",
            {},
        )
        has_linked_evidence = bool(
            (
                outcomes_by_entry.get(entry_id, [])
                if isinstance(outcomes_by_entry, Mapping)
                else []
            )
            or (
                observations_by_entry.get(entry_id, [])
                if isinstance(observations_by_entry, Mapping)
                else []
            )
        )
        if current_status == "parked" and not has_linked_evidence:
            unchanged_parked_skipped += 1
            unchanged_calibration_skipped += 1
            continue
        calibration = calibrate_entry(
            repo_root,
            entry_id,
            prior_confidence=float(entries[entry_id].data.get("confidence") or 0.5),
            evidence_index=calibration_evidence_index,
        )
        evidence_unchanged = bool(
            str(state.get("evidence_fingerprint") or "")
            and str(state.get("evidence_fingerprint") or "")
            == str(calibration.get("evidence_digest") or "")
        )
        candidate_due = False
        if current_status == "candidate":
            deadline_text = str(state.get("decision_deadline") or "")
            try:
                candidate_due = (
                    not deadline_text
                    or datetime.fromisoformat(deadline_text.replace("Z", "+00:00"))
                    <= review_now
                )
            except ValueError:
                candidate_due = True
        if evidence_unchanged and not candidate_due:
            unchanged_calibration_skipped += 1
            if current_status == "parked":
                unchanged_parked_skipped += 1
            continue
        reviewed += 1
        if calibration["downgrade_required"] and current_status == "trusted":
            event = build_entry_transition_event(
                entry_id=entry_id,
                from_state="trusted",
                to_state="parked",
                reason="Unresolved strong contradictory outcome suspended trusted retrieval.",
                actor=run_id,
                evidence_ids=calibration.get("contradicting_evidence_ids", []),
                provenance_ids=calibration.get("evidence_references", []),
                evidence_grade="strong",
                retrieval_eligible=False,
                reopen_condition={
                    "kind": "resolving-independent-validation",
                    "minimum_grade": "strong",
                    "requires_new_fingerprint": True,
                },
                evidence_fingerprint=str(calibration.get("evidence_digest") or ""),
                decision_receipt=calibration,
            )
            decision_events.append(event)
            decision_keys.append(str(event.get("idempotency_key") or ""))
            downgraded += 1
            continue
        structure_ok, structure_issues = _entry_structure_is_promotable(entries[entry_id].data)
        if not calibration["promotion_ready"] or not structure_ok:
            if current_status == "candidate":
                deadline_text = str(state.get("decision_deadline") or "")
                try:
                    expired = not deadline_text or datetime.fromisoformat(deadline_text.replace("Z", "+00:00")) <= review_now
                except ValueError:
                    expired = True
                if expired:
                    event = build_entry_transition_event(
                        entry_id=entry_id,
                        from_state="candidate",
                        to_state="parked",
                        reason="The bounded candidate decision deadline expired without qualifying support.",
                        actor=run_id,
                        evidence_ids=calibration.get("qualifying_evidence_ids", []),
                        provenance_ids=calibration.get("evidence_references", []),
                        evidence_grade="medium" if calibration["support_by_grade"]["medium"] else "weak",
                        retrieval_eligible=False,
                        reopen_condition={
                            "kind": "new-independent-evidence",
                            "minimum_grade": "medium",
                            "requires_new_fingerprint": True,
                        },
                        evidence_fingerprint=str(calibration.get("evidence_digest") or ""),
                        decision_receipt={**calibration, "structure_issues": structure_issues},
                    )
                    decision_events.append(event)
                    decision_keys.append(
                        str(event.get("idempotency_key") or "")
                    )
                    parked += 1
                    continue
            if current_status in {"parked", "trusted", "candidate"}:
                calibration_snapshot_events.append(
                    build_entry_transition_event(
                        entry_id=entry_id,
                        from_state=current_status,
                        to_state=current_status,
                        reason="Current evidence was recalibrated without changing lifecycle or retrieval state.",
                        actor=run_id,
                        evidence_ids=calibration.get("qualifying_evidence_ids", []),
                        provenance_ids=calibration.get("evidence_references", []),
                        evidence_grade=(
                            "strong"
                            if calibration["support_by_grade"]["strong"]
                            else "medium"
                            if calibration["support_by_grade"]["medium"]
                            else "weak"
                        ),
                        retrieval_eligible=bool(state.get("retrieval_eligible", False)),
                        reopen_condition=(
                            state.get("reopen_condition", {})
                            if isinstance(state.get("reopen_condition"), Mapping)
                            else {}
                        ),
                        evidence_fingerprint=str(calibration.get("evidence_digest") or ""),
                        decision_deadline=str(state.get("decision_deadline") or ""),
                        event_type="entry-calibration-snapshot",
                        decision_receipt={**calibration, "structure_issues": structure_issues},
                    )
                )
            continue
        if current_status == "parked":
            event = build_entry_transition_event(
                entry_id=entry_id,
                from_state="parked",
                to_state="candidate",
                reason="Material independent evidence satisfied the parked reopen condition.",
                actor=run_id,
                evidence_ids=calibration.get("qualifying_evidence_ids", []),
                provenance_ids=calibration.get("evidence_references", []),
                evidence_grade="strong" if calibration["support_by_grade"]["strong"] else "medium",
                retrieval_eligible=False,
                evidence_fingerprint=str(calibration.get("evidence_digest") or ""),
                decision_deadline=(datetime.now(timezone.utc) + timedelta(days=CANDIDATE_DECISION_DAYS)).replace(microsecond=0).isoformat(),
                event_type="entry-reopened",
                decision_receipt={**calibration, "structure_issues": structure_issues},
            )
            decision_events.append(event)
            decision_keys.append(str(event.get("idempotency_key") or ""))
            reopened += 1
            current_status = "candidate"
        if current_status == "candidate":
            event = build_entry_transition_event(
                entry_id=entry_id,
                from_state="candidate",
                to_state="trusted",
                reason="Current independent evidence and semantic validation satisfy the promotion policy.",
                actor=run_id,
                evidence_ids=calibration.get("qualifying_evidence_ids", []),
                provenance_ids=calibration.get("evidence_references", []),
                evidence_grade="strong" if calibration["support_by_grade"]["strong"] else "medium",
                retrieval_eligible=False,
                evidence_fingerprint=str(calibration.get("evidence_digest") or ""),
                event_type="candidate-transition",
                decision_receipt={**calibration, "structure_issues": structure_issues},
            )
            decision_events.append(event)
            decision_keys.append(str(event.get("idempotency_key") or ""))
            promoted += 1
    staged_review_events = [*decision_events, *calibration_snapshot_events]
    calibration_snapshot_result = commit_lifecycle_events(
        repo_root,
        staged_review_events,
        expected_event_digest=str(lifecycle.get("event_digest") or ""),
        expected_last_sequence=int(lifecycle.get("last_sequence") or 0),
    ) if staged_review_events else {
        "created_count": 0,
        "reused_count": 0,
        "requested_count": 0,
        "events": [],
        "event_ids_by_key": {},
        "state": lifecycle,
        "replay_pass_count": 0,
        "atomic_batch_count": 0,
    }
    lifecycle_after = calibration_snapshot_result["state"]
    projection_validation = lifecycle_after.get("validation", {})
    projection_issues = (
        [str(item) for item in projection_validation.get("issues", [])]
        if isinstance(projection_validation, Mapping)
        else ["lifecycle projection validation is missing"]
    )
    due_remaining = sorted(
        entry_id
        for entry_id in due_entry_ids
        if str((lifecycle_after.get("entries", {}).get(entry_id, {}) or {}).get("status") or "") == "candidate"
    )
    issues = list(projection_issues)
    if due_remaining:
        issues.append(f"{len(due_remaining)} due candidate lifecycle decision(s) remain open")
    event_ids_by_key = calibration_snapshot_result.get("event_ids_by_key", {})
    created_keys = {
        str(event.get("idempotency_key") or "")
        for event in calibration_snapshot_result.get("events", [])
        if isinstance(event, Mapping)
    }
    reused_keys = {
        str(key)
        for key in calibration_snapshot_result.get("reused_keys", [])
    }
    calibration_keys = {
        str(event.get("idempotency_key") or "")
        for event in calibration_snapshot_events
    }
    decision_ids = [
        str(event_ids_by_key.get(key) or key)
        for key in decision_keys
        if key
    ]
    decision_count = promoted + downgraded + reopened + parked
    if len(decision_ids) != decision_count:
        issues.append(
            f"lifecycle decision count mismatch: {len(decision_ids)} receipt id(s) for {decision_count} transition(s)"
        )
    return {
        "ok": not issues,
        "issues": issues,
        "reviewed": reviewed,
        "unchanged_parked_skipped": unchanged_parked_skipped,
        "unchanged_calibration_skipped": unchanged_calibration_skipped,
        "calibration_snapshot_count": len(calibration_keys & created_keys),
        "calibration_snapshot_reused": len(calibration_keys & reused_keys),
        "lifecycle_batch": {
            key: int(calibration_snapshot_result.get(key) or 0)
            for key in (
                "requested_count",
                "created_count",
                "reused_count",
                "residual_count",
                "replay_pass_count",
                "atomic_batch_count",
            )
        },
        "promoted": promoted,
        "downgraded": downgraded,
        "reopened": reopened,
        "parked": parked,
        "decision_count": decision_count,
        "decision_ids": decision_ids,
        "due_at_cycle_start": len(due_entry_ids),
        "due_disposed": len(due_entry_ids) - len(due_remaining),
        "due_remaining": len(due_remaining),
        "due_remaining_entry_ids": due_remaining,
        "projection_validation": dict(projection_validation) if isinstance(projection_validation, Mapping) else {},
    }
