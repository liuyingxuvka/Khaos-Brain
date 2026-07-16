from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from logicguard import (
    MeshNodeOverride,
    MeshSimulationDelta,
    ModelPinReplacement,
    QualifiedModelRef,
    QualifiedNodeRef,
)

from local_kb.common import parse_route_segments, utc_now_iso
from local_kb.consolidate import APPLY_MODE_NONE, consolidate_history, sanitize_run_id
from local_kb.consolidate_events import (
    load_history_events,
    relative_repo_path,
)
from local_kb.lifecycle import (
    TERMINAL_ENTRY_STATES,
    content_fingerprint,
    effective_entry_status,
    load_lifecycle_state,
    record_dream_handoff,
)
from local_kb.maintenance_lanes import acquire_lane_lock, build_lane_guard, release_lane_lock, write_lane_status
from local_kb.search import render_search_payload, search_entries, search_loaded_entries
from local_kb.logicguard_models import (
    load_authority_generation,
    open_model_store,
    read_bound_argument_context,
    read_exact_mesh,
    read_exact_model,
    simulate_bound_mesh,
)
from local_kb.model_projection import binding_from_projection
from local_kb.model_maintenance import load_current_model_entries
from local_kb.taxonomy import build_taxonomy_gap_report


DREAM_SCHEMA_VERSION = 2
DREAM_REPORT_KIND = "local-kb-dream-report"
PLAN_FILENAME = "plan.json"
PREFLIGHT_FILENAME = "preflight.json"
OPPORTUNITIES_FILENAME = "opportunities.json"
EXPERIMENTS_FILENAME = "experiments.json"
EXECUTION_PLAN_FILENAME = "execution_plan.json"
REPORT_FILENAME = "report.json"
SANDBOX_DIRNAME = "sandbox"
SANDBOX_MODE_RETRIEVAL_AB = "retrieval-ab"
SANDBOX_MODE_SCENARIO_REPLAY = "scenario-replay"
SANDBOX_EXPERIMENT_MODE = SANDBOX_MODE_RETRIEVAL_AB
DREAM_SANDBOX_EXPERIMENT_MODES = {SANDBOX_MODE_RETRIEVAL_AB, SANDBOX_MODE_SCENARIO_REPLAY}
DREAM_SLEEP_HANDOFF_CLASSIFICATIONS = {
    "validated",
    "adjacent-support",
    "candidate-backlog",
    "model-gap",
}
DREAM_SLEEP_HANDOFF_EVIDENCE_GRADES = {"strong", "moderate"}

DREAM_PREFLIGHT_SEARCHES = (
    {
        "route_ref": "predictive-kb/agent-lifecycle/exploration",
        "query": (
            "Dream mode bounded exploration history-only candidate-only "
            "run-level observation prior dream process guidance"
        ),
    },
    {
        "route_ref": "kb/dream/verification",
        "query": "Dream runner verification tests bounded local experiment write-back",
    },
)

DREAM_MIN_VALUABLE_OPPORTUNITY_SCORE = 18
DREAM_MIN_VALUABLE_EXECUTABILITY_SCORE = 3
DREAM_MAX_SELECTED_EXPERIMENTS = 4
DREAM_MODEL_PERTURBATION_KINDS = (
    "evidence-removal",
    "assumption-removal",
    "rebuttal-strengthening",
    "boundary-pressure",
    "cross-edge-removal",
    "neighbor-pin-replacement",
)


def _logicguard_dream_probe(repo_root: Path, entry_data: dict[str, Any]) -> dict[str, Any]:
    """Run a bounded read-only perturbation suite on one exact model/mesh revision."""

    binding = binding_from_projection(entry_data)
    context = read_bound_argument_context(repo_root, binding)
    snapshot = read_exact_model(repo_root, binding)
    mesh = read_exact_mesh(repo_root, binding)
    model = snapshot.to_model()
    nodes_by_type: dict[str, list[str]] = {}
    for node_id, node in model.nodes.items():
        nodes_by_type.setdefault(str(node.type).lower(), []).append(str(node_id))
    for values in nodes_by_type.values():
        values.sort()

    plans: list[dict[str, Any]] = []
    if nodes_by_type.get("evidence"):
        node_id = nodes_by_type["evidence"][0]
        plans.append(
            {
                "kind": "evidence-removal",
                "node_id": node_id,
                "evidence_availability_changes": (
                    MeshNodeOverride(
                        QualifiedNodeRef(binding.model_id, binding.revision_id, node_id),
                        {"missing": True},
                    ),
                ),
            }
        )
    if nodes_by_type.get("assumption"):
        node_id = nodes_by_type["assumption"][0]
        plans.append(
            {
                "kind": "assumption-removal",
                "node_id": node_id,
                "assumption_changes": (
                    MeshNodeOverride(
                        QualifiedNodeRef(binding.model_id, binding.revision_id, node_id),
                        {"missing": True},
                    ),
                ),
            }
        )
    if nodes_by_type.get("rebuttal"):
        node_id = nodes_by_type["rebuttal"][0]
        plans.append(
            {
                "kind": "rebuttal-strengthening",
                "node_id": node_id,
                "rebuttal_changes": (
                    MeshNodeOverride(
                        QualifiedNodeRef(binding.model_id, binding.revision_id, node_id),
                        {"active": True, "confidence": 1.0},
                    ),
                ),
            }
        )

    boundary_node_id = (
        nodes_by_type.get("limitation", [""])[0]
        or nodes_by_type.get("qualifier", [""])[0]
        or binding.node_id
    )
    plans.append(
        {
            "kind": "boundary-pressure",
            "node_id": boundary_node_id,
            "provenance_overrides": (
                MeshNodeOverride(
                    QualifiedNodeRef(
                        binding.model_id,
                        binding.revision_id,
                        boundary_node_id,
                    ),
                    {"active": True, "confidence": 0.0},
                ),
            ),
        }
    )

    exact_edges = sorted(mesh.cross_model_edges, key=lambda item: str(item.id))
    if exact_edges:
        plans.append(
            {
                "kind": "cross-edge-removal",
                "edge_id": str(exact_edges[0].id),
                "edge_removals": (exact_edges[0].id,),
            }
        )

    model_store = open_model_store(repo_root, binding.authority_scope)
    for registry_entry in sorted(
        mesh.registry,
        key=lambda item: (
            str(item.model_ref.model_id),
            str(item.model_ref.revision),
        ),
    ):
        source_ref = registry_entry.model_ref
        if str(source_ref.model_id) == binding.model_id:
            continue
        prior_revisions = sorted(
            (
                item
                for item in model_store.list_revisions(source_ref.model_id)
                if str(item) != str(source_ref.revision)
            ),
            key=str,
        )
        if not prior_revisions:
            continue
        target_ref = QualifiedModelRef(source_ref.model_id, prior_revisions[-1])
        plans.append(
            {
                "kind": "neighbor-pin-replacement",
                "model_id": str(source_ref.model_id),
                "source_revision_id": str(source_ref.revision),
                "target_revision_id": str(target_ref.revision),
                "pin_replacements": (
                    ModelPinReplacement(source=source_ref, target=target_ref),
                ),
            }
        )
        break

    perturbations: list[dict[str, Any]] = []
    for plan in plans[: len(DREAM_MODEL_PERTURBATION_KINDS)]:
        kind = str(plan["kind"])
        delta = MeshSimulationDelta(
            base_mesh_id=binding.mesh_id,
            base_mesh_revision=binding.mesh_revision_id,
            pin_replacements=tuple(plan.get("pin_replacements") or ()),
            edge_removals=tuple(plan.get("edge_removals") or ()),
            provenance_overrides=tuple(plan.get("provenance_overrides") or ()),
            evidence_availability_changes=tuple(
                plan.get("evidence_availability_changes") or ()
            ),
            assumption_changes=tuple(plan.get("assumption_changes") or ()),
            rebuttal_changes=tuple(plan.get("rebuttal_changes") or ()),
            metadata={
                "owner": "kb-dream",
                "probe_kind": kind,
                "card_id": str(entry_data.get("id") or ""),
                "open_role_gaps": list(context.get("open_role_gaps") or []),
            },
        )
        simulation = simulate_bound_mesh(repo_root, binding, delta, hop_limit=1)
        materialized = simulation.materialized.to_dict()
        perturbations.append(
            {
                "kind": kind,
                "node_id": str(plan.get("node_id") or ""),
                "edge_id": str(plan.get("edge_id") or ""),
                "model_id": str(plan.get("model_id") or ""),
                "source_revision_id": str(
                    plan.get("source_revision_id") or ""
                ),
                "target_revision_id": str(
                    plan.get("target_revision_id") or ""
                ),
                "delta": simulation.delta.to_dict(),
                "simulation_receipt": simulation.receipt.to_dict(),
                "overlay": simulation.overlay.to_dict(),
                "materialization": {
                    "materialization_fingerprint": str(
                        materialized.get("materialization_fingerprint") or ""
                    ),
                    "complete": bool(materialized.get("complete")),
                    "model_read_count": int(
                        materialized.get("model_read_count") or 0
                    ),
                    "model_pin_count": len(materialized.get("model_pins") or []),
                    "cross_edge_count": len(materialized.get("cross_edges") or []),
                    "truncation_reasons": list(
                        materialized.get("truncation_reasons") or []
                    ),
                },
            }
        )

    primary = perturbations[0]
    return {
        "authority": "simulation-only",
        "authority_generation_id": str(entry_data.get("authority_generation_id") or ""),
        "binding": binding.to_dict(),
        "probe_kind": primary["kind"],
        "probe_node_id": primary["node_id"],
        "open_role_gaps": list(context.get("open_role_gaps") or []),
        "planned_perturbation_kinds": list(DREAM_MODEL_PERTURBATION_KINDS),
        "executed_perturbation_kinds": [item["kind"] for item in perturbations],
        "perturbation_count": len(perturbations),
        "perturbations": perturbations,
        "delta": primary["delta"],
        "simulation_receipt": primary["simulation_receipt"],
        "overlay": primary["overlay"],
        "materialization": primary["materialization"],
        "canonical_authority_mutated": False,
        "required_sleep_review": bool(context.get("open_role_gaps")),
    }


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def dream_run_dir(repo_root: Path, run_id: str) -> Path:
    return repo_root / "kb" / "history" / "dream" / run_id


def dream_sandbox_dir(repo_root: Path, run_id: str) -> Path:
    return dream_run_dir(repo_root, run_id) / SANDBOX_DIRNAME


def _load_prior_fingerprint_closures(repo_root: Path, *, current_run_id: str) -> dict[str, dict[str, Any]]:
    dream_root = repo_root / "kb" / "history" / "dream"
    if not dream_root.exists():
        return {}

    prior: dict[str, dict[str, Any]] = {}
    for report_path in sorted(dream_root.glob(f"*/{REPORT_FILENAME}")):
        run_id = report_path.parent.name
        if run_id == current_run_id:
            continue
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for experiment in payload.get("experiments", []):
            if not isinstance(experiment, dict):
                continue
            evidence_fingerprint = str(experiment.get("evidence_fingerprint", "") or "")
            if not evidence_fingerprint:
                continue
            validation = experiment.get("validation_result", {})
            status = str(validation.get("status", "") or "") if isinstance(validation, dict) else ""
            grade = str(experiment.get("evidence_grade", "") or "")
            classification = str(experiment.get("classification", "") or "")
            if status not in {"passed", "failed", "inconclusive", "blocked"} and classification not in {
                "history-only",
                "already-covered",
                "sleep-owned",
                "candidate-backlog",
                "adjacent-support",
                "validated",
                "inconclusive",
                "no_delta_closed",
            }:
                continue
            prior[evidence_fingerprint] = {
                "run_id": run_id,
                "route_ref": str(experiment.get("route_ref", "") or ""),
                "kind": str(experiment.get("kind", "") or ""),
                "sandbox_mode": str(experiment.get("sandbox_mode", "") or ""),
                "evidence_grade": grade,
                "validation_status": status,
                "classification": classification,
                "evidence_fingerprint": evidence_fingerprint,
                "result_digest": str(experiment.get("result_digest", "") or ""),
                "sandbox_path": str(experiment.get("sandbox_path", "") or ""),
            }
    return prior


def _opportunity_evidence_payload(opportunity: dict[str, Any]) -> dict[str, Any]:
    source_action = opportunity.get("source_action", {})
    if not isinstance(source_action, dict):
        source_action = {}
    return {
        "fingerprint_schema_version": 2,
        "authority_pin": dict(opportunity.get("authority_pin") or {}),
        "source_logicguard_binding": dict(
            opportunity.get("source_logicguard_binding") or {}
        ),
        "planned_perturbation_kinds": list(
            opportunity.get("planned_perturbation_kinds")
            or DREAM_MODEL_PERTURBATION_KINDS
        ),
        "kind": str(opportunity.get("kind", "") or ""),
        "route_ref": str(opportunity.get("route_ref", "") or ""),
        "sandbox_mode": _sandbox_mode_for_opportunity(opportunity),
        "candidate_creation_mode": str(opportunity.get("candidate_creation_mode", "") or ""),
        "hypothesis": str(opportunity.get("hypothesis", "") or ""),
        "source_entry": {
            "id": str(opportunity.get("source_entry_id", "") or ""),
            "status": str(opportunity.get("entry_status", "") or ""),
            "confidence": opportunity.get("entry_confidence", ""),
            "scenario": str(opportunity.get("source_entry_scenario", "") or ""),
            "action": str(opportunity.get("source_entry_action", "") or ""),
            "predicted_result": str(opportunity.get("source_entry_predicted_result", "") or ""),
            "guidance": str(opportunity.get("source_entry_guidance", "") or ""),
        },
        "source_action": {
            "action_key": str(source_action.get("action_key", "") or ""),
            "event_ids": sorted(str(item) for item in source_action.get("event_ids", []) if str(item)),
            "target": source_action.get("target", {}),
            "candidate_scaffold_preview": source_action.get("candidate_scaffold_preview", {}),
        },
        "task_summaries": sorted(str(item) for item in opportunity.get("task_summaries", []) if str(item)),
        "exact_route_entry_count": int(opportunity.get("exact_route_entry_count", 0) or 0),
        "sibling_routes": sorted(str(item) for item in opportunity.get("sibling_routes", []) if str(item)),
        "sibling_status_counts": opportunity.get("sibling_status_counts", {}),
    }


def _evidence_fingerprint(opportunity: dict[str, Any]) -> str:
    return content_fingerprint(_opportunity_evidence_payload(opportunity))


def build_dream_guard(repo_root: Path) -> dict[str, Any]:
    return build_lane_guard(repo_root, "kb-dream")


def _entry_route(entry: Any) -> list[str]:
    return parse_route_segments(entry.data.get("domain_path", []))


def _exact_route_entries(entries: list[Any], route: list[str]) -> list[Any]:
    return [entry for entry in entries if _entry_route(entry) == route]


def _sibling_route_labels(entries: list[Any], route: list[str]) -> list[str]:
    if not route:
        return []
    parent = route[:-1]
    labels: set[str] = set()
    for entry in entries:
        entry_route = _entry_route(entry)
        if len(entry_route) != len(route):
            continue
        if entry_route == route:
            continue
        if entry_route[:-1] != parent:
            continue
        labels.add("/".join(entry_route))
    return sorted(labels)


def _sibling_route_status_counts(entries: list[Any], route: list[str]) -> dict[str, int]:
    if not route:
        return {}
    parent = route[:-1]
    counts: dict[str, int] = {}
    for entry in entries:
        entry_route = _entry_route(entry)
        if len(entry_route) != len(route):
            continue
        if entry_route == route:
            continue
        if entry_route[:-1] != parent:
            continue
        status = str(entry.data.get("status", "") or "").strip().lower() or "unknown"
        counts[status] = counts.get(status, 0) + 1
    return counts


def _route_title(route: list[str]) -> str:
    return " / ".join(route) if route else "root"


def _score_opportunity(
    *,
    repeated_signal: int,
    boundedness: int,
    validation_readiness: int,
    reuse_potential: int,
    execution_risk: int,
) -> int:
    return (
        (4 * repeated_signal)
        + (3 * boundedness)
        + (3 * validation_readiness)
        + (2 * reuse_potential)
        - (4 * execution_risk)
    )


def _selection_priority(opportunity: dict[str, Any]) -> int:
    if opportunity.get("kind") == "route-candidate":
        mode = str(opportunity.get("candidate_creation_mode", "") or "")
        if mode == "dream-adjacent":
            return 3
        if mode == "sleep-eligible":
            return 1
        if mode == "candidate-backlog":
            return 1
    if opportunity.get("kind") == "entry-validation":
        return 4
    if opportunity.get("kind") == "taxonomy-gap":
        return 2
    return 0


def _safe_confidence(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.5


def _entry_validation_query(entry: Any) -> str:
    data = entry.data
    predict_block = data.get("predict", {})
    use_block = data.get("use", {})
    if not isinstance(predict_block, dict):
        predict_block = {}
    if not isinstance(use_block, dict):
        use_block = {}
    parts = [
        str(data.get("title", "") or "").strip(),
        str(predict_block.get("expected_result", "") or "").strip(),
        str(use_block.get("guidance", "") or "").strip(),
    ]
    return " ".join(part for part in parts if part) or _route_title(_entry_route(entry))


def _block_text(value: Any, preferred_keys: tuple[str, ...] = ()) -> str:
    if isinstance(value, dict):
        parts: list[str] = []
        keys = preferred_keys or tuple(value.keys())
        for key in keys:
            item = value.get(key, "")
            if isinstance(item, (dict, list)):
                item_text = _block_text(item)
            else:
                item_text = str(item or "").strip()
            if item_text:
                parts.append(item_text)
        return " ".join(parts).strip()
    if isinstance(value, list):
        return " ".join(_block_text(item) for item in value if _block_text(item)).strip()
    return str(value or "").strip()


def _predictive_preview_available(action: dict[str, Any]) -> bool:
    preview = action.get("candidate_scaffold_preview", {})
    if not isinstance(preview, dict):
        return False
    if_block = preview.get("if", {})
    action_block = preview.get("action", {})
    predict_block = preview.get("predict", {})
    if not isinstance(if_block, dict):
        if_block = {}
    if not isinstance(action_block, dict):
        action_block = {}
    if not isinstance(predict_block, dict):
        predict_block = {}
    return any(
        str(value or "").strip()
        for value in (
            preview.get("title"),
            if_block.get("notes"),
            action_block.get("description"),
            predict_block.get("expected_result"),
        )
    )


def build_route_candidate_opportunities(
    actions: list[dict[str, Any]],
    entries: list[Any],
) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    for action in actions:
        if action.get("action_type") != "consider-new-candidate":
            continue
        target = action.get("target", {})
        if not isinstance(target, dict) or target.get("kind") != "route":
            continue
        route_ref = str(target.get("ref", "") or "").strip()
        route = parse_route_segments(route_ref)
        if not route:
            continue

        exact_route_entry_count = len(_exact_route_entries(entries, route))
        sibling_routes = _sibling_route_labels(entries, route)
        sibling_status_counts = _sibling_route_status_counts(entries, route)
        sibling_candidate_count = int(sibling_status_counts.get("candidate", 0) or 0)
        sibling_trusted_count = int(sibling_status_counts.get("trusted", 0) or 0)
        predictive_preview = _predictive_preview_available(action)
        event_count = int(action.get("event_count", 0) or 0)
        task_summaries = list(action.get("task_summaries", []))
        apply_eligibility = action.get("apply_eligibility", {})
        if not isinstance(apply_eligibility, dict):
            apply_eligibility = {}

        candidate_creation_mode = ""
        if exact_route_entry_count == 0 and len(route) >= 3:
            if predictive_preview and sibling_candidate_count > 0 and sibling_trusted_count == 0:
                candidate_creation_mode = "candidate-backlog"
            elif apply_eligibility.get("eligible", False):
                candidate_creation_mode = "sleep-eligible"
            elif predictive_preview and sibling_routes:
                candidate_creation_mode = "dream-adjacent"

        repeated_signal = min(3, max(1, event_count))
        boundedness = min(3, len(route))
        validation_readiness = 3 if predictive_preview else (2 if task_summaries else 1)
        reuse_potential = min(3, min(len(sibling_routes), 2) + (1 if event_count >= 2 else 0))
        execution_risk = 0 if len(route) >= 3 and exact_route_entry_count == 0 else 1
        opportunity_score = _score_opportunity(
            repeated_signal=repeated_signal,
            boundedness=boundedness,
            validation_readiness=validation_readiness,
            reuse_potential=reuse_potential,
            execution_risk=execution_risk,
        )

        opportunities.append(
            {
                "kind": "route-candidate",
                "route": route,
                "route_ref": route_ref,
                "route_title": _route_title(route),
                "source_action": action,
                "task_summaries": task_summaries,
                "exact_route_entry_count": exact_route_entry_count,
                "sibling_routes": sibling_routes,
                "sibling_route_count": len(sibling_routes),
                "sibling_status_counts": sibling_status_counts,
                "candidate_creation_mode": candidate_creation_mode,
                "hypothesis": (
                    f"A bounded predictive candidate for {_route_title(route)} may be missing, and adjacent "
                    "route evidence is strong enough to justify one dream-mode validation pass."
                ),
                "allowed_action_surface": (
                    "Inspect local search results and supporting observations, then write only to history or "
                    "kb/candidates when the route is still uncovered."
                ),
                "score_components": {
                    "repeated_signal": repeated_signal,
                    "boundedness": boundedness,
                    "validation_readiness": validation_readiness,
                    "reuse_potential": reuse_potential,
                    "execution_risk": execution_risk,
                },
                "opportunity_score": opportunity_score,
            }
        )

    return opportunities


def build_taxonomy_gap_opportunities(
    repo_root: Path,
    entries: list[Any],
) -> list[dict[str, Any]]:
    report = build_taxonomy_gap_report(repo_root)
    opportunities: list[dict[str, Any]] = []
    for gap in report.get("gaps", []):
        if not isinstance(gap, dict):
            continue
        route = parse_route_segments(gap.get("route", []))
        if not route:
            continue
        exact_route_entry_count = len(_exact_route_entries(entries, route))
        sibling_routes = _sibling_route_labels(entries, route)
        observed_subtree_count = int(gap.get("observed_subtree_count", 0) or 0)
        example_routes = list(gap.get("example_observed_routes", []))

        repeated_signal = min(3, max(1, observed_subtree_count))
        boundedness = min(3, len(route))
        validation_readiness = 2 if example_routes else 1
        reuse_potential = min(3, min(len(sibling_routes), 2) + (1 if observed_subtree_count >= 2 else 0))
        execution_risk = 1 if len(route) >= 3 else 2
        opportunity_score = _score_opportunity(
            repeated_signal=repeated_signal,
            boundedness=boundedness,
            validation_readiness=validation_readiness,
            reuse_potential=reuse_potential,
            execution_risk=execution_risk,
        )

        opportunities.append(
            {
                "kind": "taxonomy-gap",
                "route": route,
                "route_ref": "/".join(route),
                "route_title": _route_title(route),
                "task_summaries": example_routes,
                "exact_route_entry_count": exact_route_entry_count,
                "sibling_routes": sibling_routes,
                "sibling_route_count": len(sibling_routes),
                "candidate_creation_mode": "",
                "hypothesis": (
                    f"The undeclared route {_route_title(route)} may deserve a bounded candidate or taxonomy review, "
                    "but dream mode should validate it without touching trusted memory."
                ),
                "allowed_action_surface": (
                    "Inspect route-local search output and leave a history note for taxonomy or candidate review; "
                    "do not rewrite trusted cards."
                ),
                "score_components": {
                    "repeated_signal": repeated_signal,
                    "boundedness": boundedness,
                    "validation_readiness": validation_readiness,
                    "reuse_potential": reuse_potential,
                    "execution_risk": execution_risk,
                },
                "opportunity_score": opportunity_score,
            }
        )

    return opportunities


def build_entry_validation_opportunities(repo_root: Path, entries: list[Any]) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    for entry in entries:
        data = entry.data
        route = _entry_route(entry)
        if not route:
            continue
        status = str(data.get("status", "candidate") or "candidate").lower()
        confidence = _safe_confidence(data.get("confidence", 0.5))
        if status != "candidate" and confidence >= 0.75:
            continue

        query = _entry_validation_query(entry)
        repeated_signal = 2 if status == "candidate" else 1
        boundedness = min(3, len(route))
        validation_readiness = 3 if query else 1
        reuse_potential = 3 if status == "candidate" else 2
        execution_risk = 0
        opportunity_score = _score_opportunity(
            repeated_signal=repeated_signal,
            boundedness=boundedness,
            validation_readiness=validation_readiness,
            reuse_potential=reuse_potential,
            execution_risk=execution_risk,
        )

        opportunities.append(
            {
                "kind": "entry-validation",
                "route": route,
                "route_ref": "/".join(route),
                "route_title": _route_title(route),
                "source_entry_id": str(data.get("id", "") or ""),
                "source_entry_path": relative_repo_path(repo_root, entry.path),
                "source_entry_title": str(data.get("title", "") or "").strip(),
                "source_entry_scenario": _block_text(data.get("if", {}), ("notes", "scenario", "conditions")),
                "source_entry_action": _block_text(data.get("action", {}), ("description", "action")),
                "source_entry_predicted_result": _block_text(data.get("predict", {}), ("expected_result", "result")),
                "source_entry_guidance": _block_text(data.get("use", {}), ("guidance", "notes")),
                "source_logicguard_binding": {
                    "authority_generation_id": str(
                        data.get("authority_generation_id") or ""
                    ),
                    "authority_scope": str(data.get("authority_scope") or ""),
                    "model_id": str(data.get("logicguard_model_id") or ""),
                    "node_id": str(data.get("logicguard_node_id") or ""),
                    "block_id": str(data.get("logicguard_block_id") or ""),
                    "revision_id": str(data.get("logicguard_revision_id") or ""),
                    "mesh_id": str(data.get("logicguard_mesh_id") or ""),
                    "mesh_revision_id": str(
                        data.get("logicguard_mesh_revision_id") or ""
                    ),
                },
                "entry_status": status,
                "entry_confidence": confidence,
                "validation_query": query,
                "task_summaries": [query],
                "exact_route_entry_count": len(_exact_route_entries(entries, route)),
                "sibling_routes": _sibling_route_labels(entries, route),
                "sibling_route_count": len(_sibling_route_labels(entries, route)),
                "candidate_creation_mode": "",
                "hypothesis": (
                    f"The existing {status} card {data.get('id', 'unknown')} under {_route_title(route)} "
                    "may deserve one direct Dream validation pass before stronger reliance."
                ),
                "allowed_action_surface": (
                    "Run read-only retrieval checks against the local KB and write the result only to history."
                ),
                "score_components": {
                    "repeated_signal": repeated_signal,
                    "boundedness": boundedness,
                    "validation_readiness": validation_readiness,
                    "reuse_potential": reuse_potential,
                    "execution_risk": execution_risk,
                },
                "opportunity_score": opportunity_score,
            }
        )
    return opportunities


def _execution_contract(opportunity: dict[str, Any]) -> dict[str, Any]:
    kind = str(opportunity.get("kind", "") or "")
    mode = str(opportunity.get("candidate_creation_mode", "") or "")
    if kind == "route-candidate" and mode == "dream-adjacent":
        safety_tier = "read-only"
        experiment_design = "Validate missing route coverage with local search and adjacent route support, then hand the evidence to Sleep."
        validation_plan = "Search the target route, require no exact route hit and at least one sibling route hit before emitting a typed Sleep handoff."
        rollback_plan = "No knowledge rollback is needed because Dream writes only experiment evidence and an idempotent Sleep handoff."
        permitted_write_back = "experiment-evidence-and-sleep-handoff"
    elif kind == "route-candidate" and mode == "candidate-backlog":
        safety_tier = "read-only"
        experiment_design = "Confirm that adjacent candidate backlog already represents the route family, then leave a Sleep handoff instead of creating another candidate."
        validation_plan = "Search the target route, inspect adjacent candidate hits, and classify the result as candidate-backlog when route coverage is missing but nearby candidate scaffolds already exist."
        rollback_plan = "No knowledge rollback is needed because Dream writes only experiment evidence and an idempotent Sleep handoff."
        permitted_write_back = "experiment-evidence-and-sleep-handoff"
    elif kind == "route-candidate" and mode == "sleep-eligible":
        safety_tier = "read-only"
        experiment_design = "Confirm that this route is already owned by sleep maintenance rather than duplicating candidate creation."
        validation_plan = "Inspect consolidation ownership and route-local search output, then emit no knowledge mutation."
        rollback_plan = "No knowledge rollback is needed because Dream writes only experiment evidence."
        permitted_write_back = "experiment-evidence-only"
    elif kind == "entry-validation":
        safety_tier = "read-only"
        experiment_design = "Replay a historical or card-derived task scenario with and without the tested candidate or low-confidence card in local search."
        validation_plan = "Compare the no-tested-card baseline against candidate-augmented retrieval, then decide whether the card improves task choice or is ready for Sleep semantic review."
        rollback_plan = "No knowledge rollback is needed because Dream writes only experiment evidence and an idempotent Sleep handoff."
        permitted_write_back = "experiment-evidence-and-sleep-handoff"
    elif kind == "taxonomy-gap":
        safety_tier = "read-only"
        experiment_design = "Inspect an observed taxonomy gap with route-local retrieval evidence before proposing taxonomy work."
        validation_plan = "Search the undeclared route and sibling routes, then hand any decision-relevant result to Sleep."
        rollback_plan = "No knowledge rollback is needed because Dream writes only experiment evidence and an idempotent Sleep handoff."
        permitted_write_back = "experiment-evidence-and-sleep-handoff"
    else:
        safety_tier = "read-only"
        experiment_design = "Inspect the opportunity with route-local retrieval evidence."
        validation_plan = "Search the route and retain one bounded experiment receipt."
        rollback_plan = "No knowledge rollback is needed because Dream writes only experiment evidence."
        permitted_write_back = "experiment-evidence-only"

    safety_allowed = safety_tier in {"read-only", "workspace-only"}
    score_components = opportunity.get("score_components", {})
    if not isinstance(score_components, dict):
        score_components = {}
    validation_readiness = int(score_components.get("validation_readiness", 0) or 0)
    execution_risk = int(score_components.get("execution_risk", 0) or 0)
    is_executable = bool(experiment_design and validation_plan and safety_allowed and validation_readiness > 0)
    blocked_reason = "" if is_executable else "No executable validation plan could be constructed inside the allowed safety tiers."

    enriched = dict(opportunity)
    enriched.update(
        {
            "experiment_design": experiment_design,
            "validation_plan": validation_plan,
            "success_criteria": "The validation produces exact or adjacent local evidence and, when decision-relevant, exactly one typed Sleep handoff.",
            "failure_criteria": "The validation finds no grounded support, discovers existing exact coverage, or identifies ownership by sleep maintenance.",
            "safety_tier": safety_tier,
            "rollback_plan": rollback_plan,
            "permitted_write_back": permitted_write_back,
            "is_executable": is_executable,
            "blocked_reason": blocked_reason,
            "executability_score": (3 * validation_readiness) - (2 * execution_risk),
            "execution_checkpoints": [
                "preflight",
                "opportunity-scan",
                "experiment-selection",
                "experiment-record",
                "validation",
                "sleep-handoff",
                "report",
            ],
        }
    )
    return enriched


def _prepare_opportunities(
    opportunities: list[dict[str, Any]],
    *,
    authority_pin: dict[str, Any],
) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for opportunity in opportunities:
        enriched = _execution_contract(opportunity)
        enriched["authority_pin"] = {
            "generation_id": str(authority_pin.get("generation_id") or ""),
            "pointer_digest": str(authority_pin.get("pointer_digest") or ""),
        }
        enriched["planned_perturbation_kinds"] = list(
            DREAM_MODEL_PERTURBATION_KINDS
        )
        enriched["evidence_fingerprint"] = _evidence_fingerprint(enriched)
        enriched["fingerprint_schema_version"] = 2
        prepared.append(enriched)
    return prepared


def _is_valuable_experiment(opportunity: dict[str, Any]) -> bool:
    if not opportunity.get("is_executable", False):
        return False
    kind = str(opportunity.get("kind", "") or "")
    if kind == "taxonomy-gap" and opportunity.get("exact_route_entry_count", 0):
        return True

    opportunity_score = int(opportunity.get("opportunity_score", 0) or 0)
    executability_score = int(opportunity.get("executability_score", 0) or 0)
    if opportunity_score < DREAM_MIN_VALUABLE_OPPORTUNITY_SCORE:
        return False
    if executability_score < DREAM_MIN_VALUABLE_EXECUTABILITY_SCORE:
        return False

    if kind == "route-candidate":
        mode = str(opportunity.get("candidate_creation_mode", "") or "")
        return mode in {"dream-adjacent", "candidate-backlog"}
    return kind in {"entry-validation", "taxonomy-gap"}


def _sandbox_mode_for_opportunity(opportunity: dict[str, Any]) -> str:
    explicit_mode = str(opportunity.get("sandbox_mode", "") or "").strip()
    if explicit_mode in DREAM_SANDBOX_EXPERIMENT_MODES:
        return explicit_mode
    if str(opportunity.get("kind", "") or "") == "entry-validation":
        return SANDBOX_MODE_SCENARIO_REPLAY
    return SANDBOX_MODE_RETRIEVAL_AB


def _opportunity_batch_key(opportunity: dict[str, Any]) -> str:
    kind = str(opportunity.get("kind", "") or "")
    route_ref = str(opportunity.get("route_ref", "") or "")
    sandbox_mode = _sandbox_mode_for_opportunity(opportunity)
    if kind == "entry-validation":
        return f"{kind}:{sandbox_mode}:{route_ref}"
    if kind == "route-candidate":
        mode = str(opportunity.get("candidate_creation_mode", "") or "")
        return f"{kind}:{sandbox_mode}:{mode}:{route_ref}"
    return f"{kind}:{sandbox_mode}:{route_ref}"


def _select_valuable_experiments(
    opportunities: list[dict[str, Any]],
    *,
    prior_successful_sandbox_keys: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    prior_successful_sandbox_keys = prior_successful_sandbox_keys or {}
    selected: list[dict[str, Any]] = []
    seen_batch_keys: set[str] = set()
    for opportunity in opportunities:
        if not opportunity.get("is_executable", False):
            continue
        if not _is_valuable_experiment(opportunity):
            continue
        batch_key = _opportunity_batch_key(opportunity)
        evidence_fingerprint = str(opportunity.get("evidence_fingerprint", "") or "")
        if batch_key in seen_batch_keys:
            continue
        if evidence_fingerprint and evidence_fingerprint in prior_successful_sandbox_keys:
            opportunity["selection_status"] = "no_delta_closed"
            opportunity["prior_closure"] = prior_successful_sandbox_keys[evidence_fingerprint]
            continue
        seen_batch_keys.add(batch_key)
        selected.append(opportunity)
        if len(selected) >= DREAM_MAX_SELECTED_EXPERIMENTS:
            break
    return selected


def _selected_experiment_plan(item: dict[str, Any], sequence_index: int) -> dict[str, Any]:
    sandbox_mode = _sandbox_mode_for_opportunity(item)
    return {
        "sequence_index": sequence_index,
        "route_ref": item["route_ref"],
        "kind": item["kind"],
        "candidate_creation_mode": str(item.get("candidate_creation_mode", "") or ""),
        "hypothesis": item["hypothesis"],
        "experiment_design": item["experiment_design"],
        "validation_plan": item["validation_plan"],
        "success_criteria": item["success_criteria"],
        "failure_criteria": item["failure_criteria"],
        "safety_tier": item["safety_tier"],
        "rollback_plan": item["rollback_plan"],
        "permitted_write_back": item["permitted_write_back"],
        "sandbox_mode": sandbox_mode,
        "opportunity_score": item["opportunity_score"],
        "executability_score": item["executability_score"],
    }


def _validation_query(opportunity: dict[str, Any]) -> str:
    validation_query = str(opportunity.get("validation_query", "") or "").strip()
    if validation_query:
        return validation_query
    task_summaries = [str(item or "").strip() for item in opportunity.get("task_summaries", []) if str(item or "").strip()]
    if task_summaries:
        return " ".join(task_summaries[:2])
    return opportunity.get("route_title", "route exploration")


def _search_context_from_results(route_ref: str, query: str, search_results: list[dict[str, Any]]) -> dict[str, Any]:
    route = parse_route_segments(route_ref)
    parent = route[:-1]
    exact_route_hits = 0
    sibling_route_hits = 0
    for item in search_results:
        item_route = parse_route_segments(item.get("domain_path", []))
        if item_route == route:
            exact_route_hits += 1
        elif parent and len(item_route) == len(route) and item_route[:-1] == parent:
            sibling_route_hits += 1

    return {
        "query": query,
        "path_hint": route_ref,
        "result_count": len(search_results),
        "exact_route_hit_count": exact_route_hits,
        "sibling_route_hit_count": sibling_route_hits,
        "results": search_results,
    }


def _search_context_from_entries(repo_root: Path, entries: list[Any], route_ref: str, query: str) -> dict[str, Any]:
    search_results = render_search_payload(
        search_loaded_entries(entries, query=query, path_hint=route_ref, top_k=5),
        repo_root,
    )
    return _search_context_from_results(route_ref, query, search_results)


def _search_context(repo_root: Path, route_ref: str, query: str) -> dict[str, Any]:
    search_results = render_search_payload(
        search_entries(repo_root, query=query, path_hint=route_ref, top_k=5),
        repo_root,
    )
    return _search_context_from_results(route_ref, query, search_results)


def _sandbox_allowed_writes(repo_root: Path, run_id: str) -> list[str]:
    return [f"{relative_repo_path(repo_root, dream_sandbox_dir(repo_root, run_id))}/"]


def _sandbox_evidence_grade(search_context: dict[str, Any], comparison_context: dict[str, Any]) -> str:
    exact_hits = int(search_context.get("exact_route_hit_count", 0) or 0)
    sibling_hits = int(search_context.get("sibling_route_hit_count", 0) or 0)
    comparison_exact_hits = int(comparison_context.get("exact_route_hit_count", 0) or 0)
    comparison_sibling_hits = int(comparison_context.get("sibling_route_hit_count", 0) or 0)
    result_count = int(search_context.get("result_count", 0) or 0)
    comparison_result_count = int(comparison_context.get("result_count", 0) or 0)

    if exact_hits or comparison_exact_hits:
        return "strong"
    if sibling_hits or comparison_sibling_hits:
        return "moderate"
    if result_count or comparison_result_count:
        return "weak"
    return "none"


def _sandbox_validation_status(evidence_grade: str) -> str:
    if evidence_grade in {"strong", "moderate"}:
        return "passed"
    if evidence_grade == "weak":
        return "inconclusive"
    return "failed"


def _sandbox_handoff(opportunity: dict[str, Any], classification: str, evidence_grade: str) -> dict[str, str]:
    kind = str(opportunity.get("kind", "") or "")
    route_title = str(opportunity.get("route_title", "") or "the route")
    if classification == "candidate-created":
        sleep = f"Sleep should review the dream-created candidate for {route_title} only after later live-task evidence confirms it."
    elif classification == "candidate-backlog":
        sleep = f"Sleep should use this sandbox evidence to merge, reject, narrow, or keep watching nearby candidates for {route_title}."
    elif classification in {"validated", "adjacent-support"}:
        sleep = f"Sleep should use this {evidence_grade} sandbox evidence when deciding whether the existing candidate for {route_title} should stay watched or be strengthened."
    elif kind == "taxonomy-gap":
        sleep = f"Sleep should keep the taxonomy-gap evidence for {route_title} history-only unless the same gap repeats."
    else:
        sleep = f"Sleep should keep {route_title} history-only unless later task evidence repeats the signal."

    return {"sleep": sleep}


def _summarize_search_variant(name: str, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "query": context["query"],
        "path_hint": context["path_hint"],
        "result_count": context["result_count"],
        "exact_route_hit_count": context["exact_route_hit_count"],
        "sibling_route_hit_count": context["sibling_route_hit_count"],
        "result_ids": [
            str(item.get("id", "") or "")
            for item in context.get("results", [])
            if str(item.get("id", "") or "").strip()
        ],
    }


def _search_result_rank(context: dict[str, Any], entry_id: str) -> int:
    if not entry_id:
        return 0
    for index, item in enumerate(context.get("results", []), start=1):
        if str(item.get("id", "") or "") == entry_id:
            return index
    return 0


def _top_choice_summary(context: dict[str, Any]) -> str:
    results = context.get("results", [])
    if not results:
        return "No local KB choice was returned."
    top = results[0]
    entry_id = str(top.get("id", "") or "unknown")
    route = "/".join(parse_route_segments(top.get("domain_path", []))) or "unrouted"
    status = str(top.get("status", "") or "unknown")
    return f"Top choice was {entry_id} on {route} with status {status}."


def _candidate_card_snapshot(opportunity: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry_id": str(opportunity.get("source_entry_id", "") or ""),
        "title": str(opportunity.get("source_entry_title", "") or ""),
        "entry_status": str(opportunity.get("entry_status", "") or ""),
        "entry_confidence": opportunity.get("entry_confidence", ""),
        "entry_path": str(opportunity.get("source_entry_path", "") or ""),
        "route_ref": str(opportunity.get("route_ref", "") or ""),
        "scenario": str(opportunity.get("source_entry_scenario", "") or ""),
        "action": str(opportunity.get("source_entry_action", "") or ""),
        "predicted_result": str(opportunity.get("source_entry_predicted_result", "") or ""),
        "guidance": str(opportunity.get("source_entry_guidance", "") or ""),
    }


def _event_route_ref(event: dict[str, Any]) -> str:
    target = event.get("target", {}) if isinstance(event.get("target"), dict) else {}
    route = parse_route_segments(target.get("route_hint", []))
    return "/".join(route)


def _matching_history_scenarios(
    history_events: list[dict[str, Any]],
    *,
    route_ref: str,
    source_entry_id: str,
    limit: int = 3,
) -> list[dict[str, str]]:
    route = parse_route_segments(route_ref)
    matched: list[dict[str, str]] = []
    for event in reversed(history_events):
        if not isinstance(event, dict):
            continue
        target = event.get("target", {}) if isinstance(event.get("target"), dict) else {}
        event_route = parse_route_segments(target.get("route_hint", []))
        entry_ids = [str(item) for item in target.get("entry_ids", [])] if isinstance(target.get("entry_ids", []), list) else []
        if source_entry_id not in entry_ids and event_route != route:
            continue
        context = event.get("context", {}) if isinstance(event.get("context"), dict) else {}
        predictive = context.get("predictive_observation", {}) if isinstance(context.get("predictive_observation"), dict) else {}
        matched.append(
            {
                "event_id": str(event.get("event_id", "") or ""),
                "route_ref": _event_route_ref(event),
                "task_summary": str(target.get("task_summary", "") or ""),
                "scenario": str(predictive.get("scenario", "") or ""),
                "action_taken": str(predictive.get("action_taken", "") or ""),
                "observed_result": str(predictive.get("observed_result", "") or ""),
                "suggested_action": str(context.get("suggested_action", "") or ""),
            }
        )
        if len(matched) >= limit:
            break
    return list(reversed(matched))


def _scenario_replay_query(opportunity: dict[str, Any], history_scenarios: list[dict[str, str]]) -> str:
    candidate = _candidate_card_snapshot(opportunity)
    history_text = " ".join(
        part
        for scenario in history_scenarios[:2]
        for part in (
            scenario.get("task_summary", ""),
            scenario.get("scenario", ""),
            scenario.get("action_taken", ""),
        )
        if str(part or "").strip()
    )
    candidate_text = " ".join(
        str(candidate.get(key, "") or "").strip()
        for key in ("title", "scenario", "action", "predicted_result", "guidance")
        if str(candidate.get(key, "") or "").strip()
    )
    return history_text or candidate_text or _validation_query(opportunity)


def _scenario_replay_decision(
    *,
    opportunity: dict[str, Any],
    baseline_context: dict[str, Any],
    candidate_context: dict[str, Any],
    history_scenarios: list[dict[str, str]],
) -> dict[str, Any]:
    source_entry_id = str(opportunity.get("source_entry_id", "") or "")
    candidate_rank = _search_result_rank(candidate_context, source_entry_id)
    baseline_exact_hits = int(baseline_context.get("exact_route_hit_count", 0) or 0)
    candidate_exact_hits = int(candidate_context.get("exact_route_hit_count", 0) or 0)
    scenario_count = len(history_scenarios)
    candidate_snapshot = _candidate_card_snapshot(opportunity)
    if any(str(candidate_snapshot.get(key, "") or "").strip() for key in ("scenario", "action", "predicted_result")):
        scenario_count += 1

    candidate_improves_choice = bool(candidate_rank and baseline_exact_hits == 0)
    candidate_competes_for_choice = bool(candidate_rank and candidate_rank <= 3)
    if candidate_improves_choice and candidate_rank == 1 and scenario_count:
        evidence_grade = "strong"
    elif candidate_improves_choice or candidate_competes_for_choice:
        evidence_grade = "moderate"
    elif candidate_rank:
        evidence_grade = "weak"
    else:
        evidence_grade = "none"
    validation_status = _sandbox_validation_status(evidence_grade)

    if candidate_improves_choice:
        next_step = (
            "semantic-review the tested candidate for strengthening, narrowing, or promotion only if later "
            "real-task evidence agrees; the replay shows it fills a task-choice gap."
        )
    elif candidate_competes_for_choice:
        next_step = (
            "semantic-review the tested candidate against the existing top choice and decide whether Sleep "
            "should merge, narrow, rewrite, or keep watching it."
        )
    elif candidate_rank:
        next_step = "keep watching the tested candidate; it appeared in replay but did not materially change the task choice."
    else:
        next_step = "do not strengthen the tested candidate from this replay; consider rewrite or rejection if later evidence stays weak."

    baseline_summary = _top_choice_summary(baseline_context)
    candidate_summary = (
        f"Tested candidate {source_entry_id or 'unknown'} ranked #{candidate_rank}."
        if candidate_rank
        else f"Tested candidate {source_entry_id or 'unknown'} did not appear in the top replay results."
    )
    reason = (
        f"Scenario replay graded {evidence_grade}: baseline exact route hits={baseline_exact_hits}, "
        f"candidate-augmented exact route hits={candidate_exact_hits}, candidate rank={candidate_rank or 'not ranked'}."
    )
    return {
        "candidate_entry_id": source_entry_id,
        "candidate_rank": candidate_rank,
        "baseline_exact_route_hit_count": baseline_exact_hits,
        "candidate_augmented_exact_route_hit_count": candidate_exact_hits,
        "candidate_improves_task_choice": candidate_improves_choice,
        "candidate_competes_for_task_choice": candidate_competes_for_choice,
        "sleep_review_ready": validation_status == "passed",
        "evidence_grade": evidence_grade,
        "validation_status": validation_status,
        "baseline_summary": baseline_summary,
        "candidate_summary": candidate_summary,
        "reason": reason,
        "sleep_next_step": next_step,
    }


def _scenario_replay_handoff(opportunity: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    route_title = str(opportunity.get("route_title", "") or "the route")
    source_entry_id = str(opportunity.get("source_entry_id", "") or "the tested card")
    rank_value = decision.get("candidate_rank") or 0
    rank_text = f"#{rank_value}" if rank_value else "not ranked"
    sleep = (
        f"Sleep should inspect scenario-replay for {source_entry_id} on {route_title}: candidate rank {rank_text}, "
        f"baseline exact hits={decision.get('baseline_exact_route_hit_count', 0)}, "
        f"candidate exact hits={decision.get('candidate_augmented_exact_route_hit_count', 0)}. "
        f"Next step: {decision.get('sleep_next_step', '')}"
    )
    return {
        "sleep": sleep,
        "detail": {
            "candidate_entry_id": source_entry_id,
            "route_ref": str(opportunity.get("route_ref", "") or ""),
            "candidate_rank": decision.get("candidate_rank", 0),
            "candidate_improves_task_choice": bool(decision.get("candidate_improves_task_choice", False)),
            "candidate_competes_for_task_choice": bool(decision.get("candidate_competes_for_task_choice", False)),
            "sleep_review_ready": bool(decision.get("sleep_review_ready", False)),
            "sleep_next_step": str(decision.get("sleep_next_step", "") or ""),
            "baseline_summary": str(decision.get("baseline_summary", "") or ""),
            "candidate_summary": str(decision.get("candidate_summary", "") or ""),
        },
    }


def _run_retrieval_ab_sandbox(
    repo_root: Path,
    *,
    run_id: str,
    generated_at: str,
    sequence_index: int,
    opportunity: dict[str, Any],
    search_context: dict[str, Any],
    classification: str,
) -> dict[str, Any]:
    route = parse_route_segments(opportunity.get("route_ref", ""))
    comparison_route_ref = "/".join(route[:-1]) if len(route) > 1 else str(opportunity.get("route_ref", "") or "")
    comparison_context = _search_context(
        repo_root,
        route_ref=comparison_route_ref,
        query=str(search_context.get("query", "") or _validation_query(opportunity)),
    )
    evidence_grade = _sandbox_evidence_grade(search_context, comparison_context)
    validation_status = _sandbox_validation_status(evidence_grade)
    handoff = _sandbox_handoff(opportunity, classification, evidence_grade)
    sandbox_dir = dream_sandbox_dir(repo_root, run_id)
    sandbox_path = sandbox_dir / f"experiment-{sequence_index:03d}-{SANDBOX_EXPERIMENT_MODE}.json"
    relative_sandbox_path = relative_repo_path(repo_root, sandbox_path)
    validation_result = {
        "status": validation_status,
        "classification": classification,
        "summary": (
            f"Retrieval A/B evidence for {opportunity['route_title']} was graded {evidence_grade} "
            f"from target-route and comparison-route local search variants."
        ),
    }
    payload = {
        "schema_version": DREAM_SCHEMA_VERSION,
        "kind": "local-kb-dream-sandbox-experiment",
        "run_id": run_id,
        "generated_at": generated_at,
        "sequence_index": sequence_index,
        "sandbox_mode": SANDBOX_EXPERIMENT_MODE,
        "route_ref": opportunity["route_ref"],
        "source_entry_id": str(opportunity.get("source_entry_id", "") or ""),
        "hypothesis": opportunity["hypothesis"],
        "allowed_writes": _sandbox_allowed_writes(repo_root, run_id),
        "trusted_card_mutation": False,
        "variants": [
            _summarize_search_variant("target-route", search_context),
            _summarize_search_variant("comparison-route", comparison_context),
        ],
        "evidence_grade": evidence_grade,
        "validation_result": validation_result,
        "sleep_handoff": handoff["sleep"],
        "sandbox_path": relative_sandbox_path,
    }
    write_json_file(sandbox_path, payload)
    return {
        "sandbox_mode": SANDBOX_EXPERIMENT_MODE,
        "sandbox_path": relative_sandbox_path,
        "source_entry_id": payload["source_entry_id"],
        "allowed_writes": payload["allowed_writes"],
        "evidence_grade": evidence_grade,
        "validation_result": validation_result,
        "sleep_handoff": handoff["sleep"],
    }


def _run_scenario_replay_sandbox(
    repo_root: Path,
    *,
    run_id: str,
    generated_at: str,
    sequence_index: int,
    opportunity: dict[str, Any],
    classification: str,
    history_events: list[dict[str, Any]],
) -> dict[str, Any]:
    source_entry_id = str(opportunity.get("source_entry_id", "") or "")
    route_ref = str(opportunity.get("route_ref", "") or "")
    history_scenarios = _matching_history_scenarios(
        history_events,
        route_ref=route_ref,
        source_entry_id=source_entry_id,
    )
    replay_query = _scenario_replay_query(opportunity, history_scenarios)
    all_entries, _authority_generation = load_current_model_entries(repo_root)
    baseline_entries = [
        entry
        for entry in all_entries
        if str(entry.data.get("id", "") or "").strip() != source_entry_id
    ]
    baseline_context = _search_context_from_entries(
        repo_root,
        baseline_entries,
        route_ref=route_ref,
        query=replay_query,
    )
    candidate_context = _search_context_from_entries(
        repo_root,
        all_entries,
        route_ref=route_ref,
        query=replay_query,
    )
    decision = _scenario_replay_decision(
        opportunity=opportunity,
        baseline_context=baseline_context,
        candidate_context=candidate_context,
        history_scenarios=history_scenarios,
    )
    evidence_grade = str(decision["evidence_grade"])
    validation_status = str(decision["validation_status"])
    handoff = _scenario_replay_handoff(opportunity, decision)
    sandbox_dir = dream_sandbox_dir(repo_root, run_id)
    sandbox_mode = SANDBOX_MODE_SCENARIO_REPLAY
    sandbox_path = sandbox_dir / f"experiment-{sequence_index:03d}-{sandbox_mode}.json"
    relative_sandbox_path = relative_repo_path(repo_root, sandbox_path)
    validation_result = {
        "status": validation_status,
        "classification": classification,
        "summary": (
            f"Scenario replay for {opportunity['route_title']} was graded {evidence_grade}: "
            f"{decision['reason']}"
        ),
    }
    scenario_replay = {
        "replay_query": replay_query,
        "candidate_card": _candidate_card_snapshot(opportunity),
        "historical_scenarios": history_scenarios,
        "baseline_without_tested_card": _summarize_search_variant("without-tested-card", baseline_context),
        "with_tested_card": _summarize_search_variant("with-tested-card", candidate_context),
        "decision_delta": decision,
    }
    payload = {
        "schema_version": DREAM_SCHEMA_VERSION,
        "kind": "local-kb-dream-sandbox-experiment",
        "run_id": run_id,
        "generated_at": generated_at,
        "sequence_index": sequence_index,
        "sandbox_mode": sandbox_mode,
        "route_ref": route_ref,
        "source_entry_id": source_entry_id,
        "hypothesis": opportunity["hypothesis"],
        "allowed_writes": _sandbox_allowed_writes(repo_root, run_id),
        "trusted_card_mutation": False,
        "variants": [
            scenario_replay["baseline_without_tested_card"],
            scenario_replay["with_tested_card"],
        ],
        "scenario_replay": scenario_replay,
        "evidence_grade": evidence_grade,
        "validation_result": validation_result,
        "sleep_handoff": handoff["sleep"],
        "sleep_handoff_detail": handoff["detail"],
        "sandbox_path": relative_sandbox_path,
    }
    write_json_file(sandbox_path, payload)
    return {
        "sandbox_mode": sandbox_mode,
        "sandbox_path": relative_sandbox_path,
        "source_entry_id": source_entry_id,
        "allowed_writes": payload["allowed_writes"],
        "evidence_grade": evidence_grade,
        "validation_result": validation_result,
        "sleep_handoff": handoff["sleep"],
        "sleep_handoff_detail": handoff["detail"],
        "scenario_replay": scenario_replay,
        "previous_action": "Replay the task scenario without the tested card available in local search.",
        "previous_result": decision["baseline_summary"],
        "revised_action": "Replay the same scenario with the tested card available in local search.",
        "revised_result": decision["candidate_summary"],
    }


def _run_dream_sandbox(
    repo_root: Path,
    *,
    run_id: str,
    generated_at: str,
    sequence_index: int,
    opportunity: dict[str, Any],
    search_context: dict[str, Any],
    classification: str,
    history_events: list[dict[str, Any]],
) -> dict[str, Any]:
    if _sandbox_mode_for_opportunity(opportunity) == SANDBOX_MODE_SCENARIO_REPLAY:
        return _run_scenario_replay_sandbox(
            repo_root,
            run_id=run_id,
            generated_at=generated_at,
            sequence_index=sequence_index,
            opportunity=opportunity,
            classification=classification,
            history_events=history_events,
        )
    return _run_retrieval_ab_sandbox(
        repo_root,
        run_id=run_id,
        generated_at=generated_at,
        sequence_index=sequence_index,
        opportunity=opportunity,
        search_context=search_context,
        classification=classification,
    )


def _entry_ids_from_search_results(search_context: dict[str, Any]) -> list[str]:
    entry_ids: list[str] = []
    seen: set[str] = set()
    for result in search_context.get("results", []):
        if not isinstance(result, dict):
            continue
        entry_id = str(result.get("id", "") or "").strip()
        if not entry_id or entry_id in seen:
            continue
        seen.add(entry_id)
        entry_ids.append(entry_id)
    return entry_ids


def _dream_handoff_entry_ids(
    opportunity: dict[str, Any],
    experiment: dict[str, Any],
    created_candidate: dict[str, Any] | None,
) -> list[str]:
    if created_candidate is not None:
        return [str(created_candidate["entry_id"])]

    if opportunity.get("kind") == "entry-validation":
        source_entry_id = str(opportunity.get("source_entry_id", "") or "").strip()
        return [source_entry_id] if source_entry_id else []

    if experiment.get("classification") in {"candidate-backlog", "adjacent-support"}:
        search_context = experiment.get("search_context", {})
        if isinstance(search_context, dict):
            return _entry_ids_from_search_results(search_context)

    return []


def _dream_suggested_action(
    opportunity: dict[str, Any],
    experiment: dict[str, Any],
    created_candidate: dict[str, Any] | None,
    entry_ids: list[str],
) -> str:
    if created_candidate is not None:
        return "new-candidate"
    if opportunity["kind"] == "taxonomy-gap":
        return "taxonomy-change"

    classification = str(experiment.get("classification", "") or "")
    evidence_grade = str(experiment.get("evidence_grade", "") or "")
    validation_result = experiment.get("validation_result", {})
    if not isinstance(validation_result, dict):
        validation_result = {}
    validation_status = str(validation_result.get("status", "") or "")
    if (
        classification in DREAM_SLEEP_HANDOFF_CLASSIFICATIONS
        and evidence_grade in DREAM_SLEEP_HANDOFF_EVIDENCE_GRADES
        and validation_status == "passed"
        and entry_ids
    ):
        return "update-card"
    return "none"


def _dream_validation_context(
    *,
    run_id: str,
    opportunity: dict[str, Any],
    experiment: dict[str, Any],
    entry_ids: list[str],
    suggested_action: str,
) -> dict[str, Any]:
    validation_result = experiment.get("validation_result", {})
    if not isinstance(validation_result, dict):
        validation_result = {}
    context = {
        "run_id": run_id,
        "opportunity_kind": str(opportunity.get("kind", "") or ""),
        "classification": str(experiment.get("classification", "") or ""),
        "evidence_grade": str(experiment.get("evidence_grade", "") or ""),
        "validation_status": str(validation_result.get("status", "") or ""),
        "sandbox_mode": str(experiment.get("sandbox_mode", "") or ""),
        "sandbox_path": str(experiment.get("sandbox_path", "") or ""),
        "source_entry_id": str(opportunity.get("source_entry_id", "") or ""),
        "entry_status": str(opportunity.get("entry_status", "") or ""),
        "entry_confidence": opportunity.get("entry_confidence", ""),
        "entry_ids": entry_ids,
        "trusted_card_mutation": False,
        "sleep_handoff": str(experiment.get("sleep_handoff", "") or ""),
        "handoff_action": suggested_action,
    }
    sleep_handoff_detail = experiment.get("sleep_handoff_detail", {})
    if isinstance(sleep_handoff_detail, dict) and sleep_handoff_detail:
        context["sleep_handoff_detail"] = sleep_handoff_detail
    scenario_replay = experiment.get("scenario_replay", {})
    if isinstance(scenario_replay, dict) and scenario_replay:
        context["scenario_replay"] = {
            "replay_query": str(scenario_replay.get("replay_query", "") or ""),
            "decision_delta": scenario_replay.get("decision_delta", {}),
        }
    return context


def _unique_entry_ids(searches: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    entry_ids: list[str] = []
    for search in searches:
        for result in search.get("results", []):
            entry_id = str(result.get("id", "") or "").strip()
            if not entry_id or entry_id in seen:
                continue
            seen.add(entry_id)
            entry_ids.append(entry_id)
    return entry_ids


def _build_dream_preflight(repo_root: Path, *, run_id: str, generated_at: str) -> dict[str, Any]:
    searches: list[dict[str, Any]] = []
    for spec in DREAM_PREFLIGHT_SEARCHES:
        route_ref = str(spec["route_ref"])
        query = str(spec["query"])
        results = render_search_payload(
            search_entries(repo_root, query=query, path_hint=route_ref, top_k=5),
            repo_root,
        )
        searches.append(
            {
                "route_ref": route_ref,
                "query": query,
                "result_count": len(results),
                "results": results,
            }
        )

    matched_entry_ids = _unique_entry_ids(searches)
    return {
        "schema_version": DREAM_SCHEMA_VERSION,
        "kind": "local-kb-dream-preflight",
        "run_id": run_id,
        "generated_at": generated_at,
        "purpose": "Recall prior Dream-process guidance before selecting bounded experiments.",
        "searches": searches,
        "matched_entry_ids": matched_entry_ids,
        "matched_entry_count": len(matched_entry_ids),
    }


def _checkpoint(checkpoint_id: str, label: str, status: str, details: str = "") -> dict[str, Any]:
    return {
        "id": checkpoint_id,
        "label": label,
        "status": status,
        "details": details,
    }


def _build_execution_plan(
    repo_root: Path,
    *,
    run_id: str,
    generated_at: str,
    opportunity_count: int,
    executable_opportunity_count: int,
    selected: list[dict[str, Any]],
    skipped_prior_sandbox_success_count: int = 0,
) -> dict[str, Any]:
    selected_experiments = [
        _selected_experiment_plan(item, sequence_index)
        for sequence_index, item in enumerate(selected, start=1)
    ]
    selected_experiment = selected_experiments[0] if selected_experiments else None

    selection_status = "completed"
    selection_details = (
        f"Selected {len(selected)} valuable executable experiment(s) for sequential validation."
        if selected
        else "No valuable executable experiment was selected; no-op is a valid Dream outcome."
    )
    return {
        "schema_version": DREAM_SCHEMA_VERSION,
        "kind": "local-kb-dream-execution-plan",
        "run_id": run_id,
        "generated_at": generated_at,
        "status": "running",
        "policy": {
            "selection_rule": "Select a bounded batch of valuable executable experiments for sequential validation; report a no-op when no opportunity clears the value gate.",
            "allowed_safety_tiers": ["read-only", "workspace-only"],
            "minimum_opportunity_score": DREAM_MIN_VALUABLE_OPPORTUNITY_SCORE,
            "minimum_executability_score": DREAM_MIN_VALUABLE_EXECUTABILITY_SCORE,
            "max_selected_experiments": DREAM_MAX_SELECTED_EXPERIMENTS,
            "dedupe_rule": "At most one experiment per stable decision-relevant evidence fingerprint.",
            "prior_fingerprint_closure_rule": (
                "Passed, failed, inconclusive, blocked, and no-delta outcomes remain closed until "
                "decision-relevant evidence changes."
            ),
            "route_candidate_modes": ["dream-adjacent", "candidate-backlog"],
            "candidate_backlog_write_back": "typed idempotent Sleep handoff",
            "sandbox_experiment_mode": SANDBOX_EXPERIMENT_MODE,
            "sandbox_experiment_modes": [SANDBOX_MODE_RETRIEVAL_AB, SANDBOX_MODE_SCENARIO_REPLAY],
            "sandbox_allowed_writes": _sandbox_allowed_writes(repo_root, run_id),
        },
        "opportunity_count": opportunity_count,
        "executable_opportunity_count": executable_opportunity_count,
        "no_delta_closed_count": skipped_prior_sandbox_success_count,
        "selected_experiment_count": len(selected),
        "selected_experiments": selected_experiments,
        "selected_experiment": selected_experiment,
        "checkpoints": [
            _checkpoint("preflight", "Prior Dream-process guidance retrieved", "completed"),
            _checkpoint("opportunity-scan", "Opportunities gathered and executable contracts attached", "completed"),
            _checkpoint("experiment-selection", "Valuable executable experiments selected", selection_status, selection_details),
            _checkpoint("experiment-record", "Experiment records written before action", "completed" if selected else "skipped", selection_details),
            _checkpoint("validation", "Selected experiments validated sequentially", "pending" if selected else "skipped", selection_details),
            _checkpoint("sleep-handoff", "Typed idempotent Sleep handoffs published", "pending" if selected else "skipped", selection_details),
            _checkpoint("report", "Dream report written", "pending"),
        ],
        "artifact_paths": {
            "run_dir": relative_repo_path(repo_root, dream_run_dir(repo_root, run_id)),
            "sandbox_dir": relative_repo_path(repo_root, dream_sandbox_dir(repo_root, run_id)),
        },
    }


def _set_checkpoint_status(
    execution_plan: dict[str, Any],
    checkpoint_id: str,
    status: str,
    details: str = "",
) -> None:
    for checkpoint in execution_plan.get("checkpoints", []):
        if checkpoint.get("id") != checkpoint_id:
            continue
        checkpoint["status"] = status
        if details:
            checkpoint["details"] = details
        return


def run_dream_maintenance(
    repo_root: Path,
    *,
    run_id: str | None = None,
    max_events: int | None = None,
) -> dict[str, Any]:
    generated_at = utc_now_iso()
    resolved_run_id = sanitize_run_id(run_id or f"kb-dream-{utc_now_compact()}")
    run_dir = dream_run_dir(repo_root, resolved_run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    lane_lock = acquire_lane_lock(repo_root, "kb-dream", run_id=resolved_run_id)
    lock_released = False
    try:
        write_lane_status(repo_root, "kb-dream", "running", run_id=resolved_run_id)

        lane_guard = build_dream_guard(repo_root)
        plan_payload = {
            "schema_version": DREAM_SCHEMA_VERSION,
            "kind": "local-kb-dream-plan",
            "run_id": resolved_run_id,
            "generated_at": generated_at,
            "lane_guard": lane_guard,
        }
        write_json_file(run_dir / PLAN_FILENAME, plan_payload)

        if lane_guard["blocked"]:
            write_lane_status(repo_root, "kb-dream", "skipped", run_id=resolved_run_id)
            result = {
                "schema_version": DREAM_SCHEMA_VERSION,
                "kind": DREAM_REPORT_KIND,
                "run_id": resolved_run_id,
                "generated_at": generated_at,
                "status": "skipped",
                "reason": "maintenance-lane-active",
                "terminal_gate": {
                    "gate_id": "maintenance-lane",
                    "evaluated": True,
                    "applicable": False,
                    "reason": "maintenance-lane-active",
                },
                "lane_guard": lane_guard,
                "history_event_ids": [],
                "artifact_paths": {
                    "run_dir": relative_repo_path(repo_root, run_dir),
                    "plan_path": relative_repo_path(repo_root, run_dir / PLAN_FILENAME),
                    "report_path": relative_repo_path(repo_root, run_dir / REPORT_FILENAME),
                },
            }
            result["lane_lock"] = lane_lock
            result["lock_release"] = release_lane_lock(repo_root, "kb-dream", run_id=resolved_run_id)
            lock_released = True
            write_json_file(run_dir / REPORT_FILENAME, result)
            return result

        authority_pin = load_authority_generation(repo_root)
        preflight = _build_dream_preflight(repo_root, run_id=resolved_run_id, generated_at=generated_at)
        write_json_file(run_dir / PREFLIGHT_FILENAME, preflight)
        plan_payload["preflight_path"] = relative_repo_path(repo_root, run_dir / PREFLIGHT_FILENAME)
        plan_payload["preflight_matched_entry_ids"] = list(preflight["matched_entry_ids"])
        plan_payload["preflight_matched_entry_count"] = int(preflight["matched_entry_count"])
        write_json_file(run_dir / PLAN_FILENAME, plan_payload)

        from local_kb.active_index import load_active_index

        active_index = load_active_index(repo_root)
        if str(active_index.get("authority_generation_id") or "") != str(
            authority_pin.get("generation_id") or ""
        ):
            raise RuntimeError("Dream active index is not bound to the pinned authority generation")
        catalog_entries, catalog_generation = load_current_model_entries(repo_root)
        if str(catalog_generation.get("pointer_digest") or "") != str(
            authority_pin.get("pointer_digest") or ""
        ):
            raise RuntimeError("Dream model catalog is not bound to the pinned authority generation")
        lifecycle_state = load_lifecycle_state(repo_root, repair_projection=False)
        entries = []
        for entry in catalog_entries:
            effective_status = effective_entry_status(
                repo_root,
                entry.data,
                lifecycle_state=lifecycle_state,
            )
            if effective_status in TERMINAL_ENTRY_STATES:
                continue
            entry.data["status"] = effective_status
            entries.append(entry)
        history_events = load_history_events(repo_root, max_events=max_events)
        consolidation = consolidate_history(
            repo_root=repo_root,
            run_id=f"{resolved_run_id}-source",
            max_events=max_events,
            apply_mode=APPLY_MODE_NONE,
        )
        opportunities = build_route_candidate_opportunities(consolidation["actions"], entries)
        opportunities.extend(build_taxonomy_gap_opportunities(repo_root, entries))
        opportunities.extend(build_entry_validation_opportunities(repo_root, entries))
        opportunities = _prepare_opportunities(
            opportunities,
            authority_pin=authority_pin,
        )
        prior_successful_sandbox_keys = _load_prior_fingerprint_closures(
            repo_root,
            current_run_id=resolved_run_id,
        )
        opportunities = sorted(
            opportunities,
            key=lambda item: (
                -int(bool(item.get("is_executable", False))),
                -_selection_priority(item),
                -int(item.get("executability_score", 0) or 0),
                -int(item["opportunity_score"]),
                item["kind"],
                item["route_ref"],
            ),
        )
        write_json_file(
            run_dir / OPPORTUNITIES_FILENAME,
            {
                "schema_version": DREAM_SCHEMA_VERSION,
                "kind": "local-kb-dream-opportunities",
                "run_id": resolved_run_id,
                "generated_at": generated_at,
                "opportunity_count": len(opportunities),
                "opportunities": opportunities,
            },
        )

        executable_opportunities = [item for item in opportunities if item.get("is_executable", False)]
        selected = _select_valuable_experiments(
            opportunities,
            prior_successful_sandbox_keys=prior_successful_sandbox_keys,
        )
        skipped_prior_success_count = sum(
            1
            for item in opportunities
            if item.get("selection_status") == "no_delta_closed"
        )
        write_json_file(
            run_dir / OPPORTUNITIES_FILENAME,
            {
                "schema_version": DREAM_SCHEMA_VERSION,
                "kind": "local-kb-dream-opportunities",
                "run_id": resolved_run_id,
                "generated_at": generated_at,
                "opportunity_count": len(opportunities),
                "prior_fingerprint_closure_count": len(prior_successful_sandbox_keys),
                "no_delta_closed_count": skipped_prior_success_count,
                "opportunities": opportunities,
            },
        )
        planned_experiments = [
            {
                "sequence_index": sequence_index,
                "route_ref": item["route_ref"],
                "kind": item["kind"],
                "candidate_creation_mode": str(item.get("candidate_creation_mode", "") or ""),
                "hypothesis": item["hypothesis"],
                "allowed_action_surface": item["allowed_action_surface"],
                "experiment_design": item["experiment_design"],
                "validation_plan": item["validation_plan"],
                "success_criteria": item["success_criteria"],
                "failure_criteria": item["failure_criteria"],
                "safety_tier": item["safety_tier"],
                "rollback_plan": item["rollback_plan"],
                "permitted_write_back": item["permitted_write_back"],
                "sandbox_mode": _sandbox_mode_for_opportunity(item),
                "evidence_fingerprint": str(item.get("evidence_fingerprint", "") or ""),
                "fingerprint_schema_version": int(item.get("fingerprint_schema_version", 1) or 1),
                "allowed_writes": _sandbox_allowed_writes(repo_root, resolved_run_id),
                "is_executable": item["is_executable"],
                "executability_score": item["executability_score"],
                "status": "planned",
            }
            for sequence_index, item in enumerate(selected, start=1)
        ]
        write_json_file(
            run_dir / EXPERIMENTS_FILENAME,
            {
                "schema_version": DREAM_SCHEMA_VERSION,
                "kind": "local-kb-dream-experiments",
                "run_id": resolved_run_id,
                "generated_at": generated_at,
                "experiment_count": len(planned_experiments),
                "experiments": planned_experiments,
            },
        )
        execution_plan = _build_execution_plan(
            repo_root,
            run_id=resolved_run_id,
            generated_at=generated_at,
            opportunity_count=len(opportunities),
            executable_opportunity_count=len(executable_opportunities),
            selected=selected,
            skipped_prior_sandbox_success_count=skipped_prior_success_count,
        )
        write_json_file(run_dir / EXECUTION_PLAN_FILENAME, execution_plan)
        plan_payload["execution_plan_path"] = relative_repo_path(repo_root, run_dir / EXECUTION_PLAN_FILENAME)
        plan_payload["executable_opportunity_count"] = len(executable_opportunities)
        plan_payload["valuable_opportunity_count"] = len(selected)
        plan_payload["no_delta_closed_count"] = skipped_prior_success_count
        write_json_file(run_dir / PLAN_FILENAME, plan_payload)

        experiment_results: list[dict[str, Any]] = []
        created_candidates: list[dict[str, Any]] = []
        history_event_ids: list[str] = []
        entries_by_id = {
            str(entry.data.get("id") or ""): entry
            for entry in entries
            if str(entry.data.get("id") or "")
        }

        for sequence_index, opportunity in enumerate(selected, start=1):
            search_context = _search_context(
                repo_root,
                route_ref=opportunity["route_ref"],
                query=_validation_query(opportunity),
            )
            probe_entry_id = str(opportunity.get("source_entry_id") or "")
            if not probe_entry_id:
                search_entry_ids = _entry_ids_from_search_results(search_context)
                probe_entry_id = search_entry_ids[0] if search_entry_ids else ""
            logicguard_simulation: dict[str, Any] = {}
            if probe_entry_id and probe_entry_id in entries_by_id:
                logicguard_simulation = _logicguard_dream_probe(
                    repo_root,
                    entries_by_id[probe_entry_id].data,
                )
            exact_coverage_exists = (
                opportunity["exact_route_entry_count"] > 0
                or search_context["exact_route_hit_count"] > 0
            )
            created_candidate: dict[str, Any] | None = None
            classification = "history-only"
            outcome = ""
            comment = ""

            if opportunity["kind"] == "route-candidate" and exact_coverage_exists:
                classification = "already-covered"
                outcome = f"Route {opportunity['route_title']} already has exact local coverage; no dream candidate was created."
                comment = "Dream validation found an exact route match, so this remained a history-only note."
            elif opportunity["kind"] == "route-candidate" and opportunity["candidate_creation_mode"] == "sleep-eligible":
                classification = "sleep-owned"
                outcome = (
                    f"Route {opportunity['route_title']} is already eligible for sleep new-candidate apply; "
                    "dream mode left candidate creation to sleep maintenance."
                )
                comment = "Dream mode did not duplicate a sleep-owned candidate action."
            elif opportunity["kind"] == "route-candidate" and opportunity["candidate_creation_mode"] == "candidate-backlog":
                classification = "candidate-backlog"
                sibling_counts = opportunity.get("sibling_status_counts", {})
                if not isinstance(sibling_counts, dict):
                    sibling_counts = {}
                outcome = (
                    f"Route {opportunity['route_title']} lacks exact local coverage, but adjacent candidate backlog "
                    f"already exists in the same route family: {sibling_counts}."
                )
                comment = (
                    "Dream mode kept this history-only and left the route family for Sleep to merge, reject, "
                    "narrow, or consolidate instead of creating another candidate."
                )
            elif opportunity["kind"] == "route-candidate" and opportunity["candidate_creation_mode"] == "dream-adjacent":
                if search_context["sibling_route_hit_count"] == 0:
                    classification = "inconclusive"
                    outcome = (
                        f"Route {opportunity['route_title']} still lacks exact coverage, but the dream validation "
                        "did not find enough adjacent search support for a scaffold."
                    )
                    comment = "Kept this run history-only because adjacent route support was weaker than expected."
                else:
                    classification = "adjacent-support"
                    outcome = (
                        f"Validated adjacent support for {opportunity['route_title']}; Sleep now owns any "
                        "candidate creation or merge decision."
                    )
                    comment = (
                        "Dream emitted experiment evidence and a typed Sleep handoff without mutating "
                        "candidate or trusted knowledge."
                    )
            elif opportunity["kind"] == "entry-validation":
                source_entry_id = str(opportunity.get("source_entry_id", "") or "unknown")
                if logicguard_simulation.get("required_sleep_review"):
                    classification = "model-gap"
                    gaps = ", ".join(logicguard_simulation.get("open_role_gaps", []))
                    outcome = f"Exact LogicGuard simulation for {source_entry_id} confirmed model gaps: {gaps}."
                    comment = "Dream kept canonical authority unchanged and handed the exact simulation receipt to Sleep."
                elif search_context["exact_route_hit_count"] > 0:
                    classification = "validated"
                    outcome = (
                        f"Validated existing card {source_entry_id} for {opportunity['route_title']} "
                        "with exact route-local retrieval evidence."
                    )
                    comment = "Dream mode treated this as read-only evidence for later sleep review."
                elif search_context["sibling_route_hit_count"] > 0:
                    classification = "adjacent-support"
                    outcome = (
                        f"Found adjacent support for existing card {source_entry_id}, but no exact route-local hit."
                    )
                    comment = "Kept this as history-only evidence because support was adjacent rather than exact."
                else:
                    classification = "inconclusive"
                    outcome = (
                        f"Validated existing card {source_entry_id}, but the local search did not find grounded support."
                    )
                    comment = "The experiment was executable, but its result should not strengthen the card."
            else:
                classification = "history-only"
                outcome = (
                    f"Inspected {opportunity['route_title']} as a dream-mode opportunity and left the result in history only."
                )
                comment = "The route stayed provisional because dream mode did not have enough grounded evidence for a candidate scaffold."

            action_taken = (
                f"Ran a bounded dream validation for {opportunity['route_title']}: local search with path hint "
                f"{opportunity['route_ref']} and query '{search_context['query']}'."
            )
            observed_result = outcome
            if opportunity["kind"] == "taxonomy-gap":
                operational_use = "Use this result to drive later taxonomy review without changing trusted memory during dream mode."
            else:
                operational_use = "Keep this result in history and revisit the route during a later live task or sleep pass."
            reuse_judgment = (
                "Reusable when the same route keeps appearing without exact card coverage but nearby sibling routes suggest the gap is meaningful."
            )

            experiment = {
                "sequence_index": sequence_index,
                "kind": opportunity["kind"],
                "route_ref": opportunity["route_ref"],
                "route_title": opportunity["route_title"],
                "candidate_creation_mode": str(opportunity.get("candidate_creation_mode", "") or ""),
                "hypothesis": opportunity["hypothesis"],
                "allowed_action_surface": opportunity["allowed_action_surface"],
                "experiment_design": opportunity["experiment_design"],
                "validation_plan": opportunity["validation_plan"],
                "success_criteria": opportunity["success_criteria"],
                "failure_criteria": opportunity["failure_criteria"],
                "safety_tier": opportunity["safety_tier"],
                "rollback_plan": opportunity["rollback_plan"],
                "permitted_write_back": opportunity["permitted_write_back"],
                "is_executable": opportunity["is_executable"],
                "executability_score": opportunity["executability_score"],
                "classification": classification,
                "search_context": search_context,
                "outcome": outcome,
                "comment": comment,
                "action_taken": action_taken,
                "observed_result": observed_result,
                "operational_use": operational_use,
                "reuse_judgment": reuse_judgment,
                "created_candidate": created_candidate,
                "logicguard_simulation": logicguard_simulation,
            }
            sandbox_result = _run_dream_sandbox(
                repo_root,
                run_id=resolved_run_id,
                generated_at=generated_at,
                sequence_index=sequence_index,
                opportunity=opportunity,
                search_context=search_context,
                classification=classification,
                history_events=history_events,
            )
            experiment.update(sandbox_result)
            experiment["evidence_fingerprint"] = str(
                opportunity.get("evidence_fingerprint", "") or ""
            )
            experiment["fingerprint_schema_version"] = int(
                opportunity.get("fingerprint_schema_version", 1) or 1
            )
            if experiment.get("sandbox_mode") == SANDBOX_MODE_SCENARIO_REPLAY:
                replay = experiment.get("scenario_replay", {})
                decision = replay.get("decision_delta", {}) if isinstance(replay, dict) else {}
                action_taken = (
                    f"Ran a scenario-replay Dream sandbox for {opportunity['route_title']}: compared local search "
                    "without the tested card against search with the tested card using a historical or card-derived task scenario."
                )
                observed_result = str(decision.get("reason", "") or observed_result)
                operational_use = (
                    "Use the scenario-replay delta as Sleep review input for the tested candidate; do not treat it "
                    "as trusted-card promotion evidence without later live-task confirmation."
                )
                experiment["action_taken"] = action_taken
                experiment["observed_result"] = observed_result
                experiment["operational_use"] = operational_use
            handoff_entry_ids = _dream_handoff_entry_ids(
                opportunity=opportunity,
                experiment=experiment,
                created_candidate=None,
            )
            suggested_action = _dream_suggested_action(
                opportunity=opportunity,
                experiment=experiment,
                created_candidate=None,
                entry_ids=handoff_entry_ids,
            )
            if suggested_action == "update-card":
                requested_disposition = "update-card"
            elif (
                opportunity.get("kind") == "route-candidate"
                and experiment.get("classification") == "adjacent-support"
            ):
                requested_disposition = "candidate"
            else:
                requested_disposition = "history_only"
            result_evidence = {
                "classification": classification,
                "evidence_grade": str(experiment.get("evidence_grade") or ""),
                "validation_result": experiment.get("validation_result", {}),
                "result_entry_ids": _entry_ids_from_search_results(search_context),
                "scenario_replay_decision": (
                    experiment.get("scenario_replay", {}).get("decision_delta", {})
                    if isinstance(experiment.get("scenario_replay"), dict)
                    else {}
                ),
                "requested_disposition": requested_disposition,
                "logicguard_simulation": logicguard_simulation,
            }
            result_digest = content_fingerprint(result_evidence)
            handoff = record_dream_handoff(
                repo_root,
                run_id=resolved_run_id,
                evidence_fingerprint=experiment["evidence_fingerprint"],
                result_digest=result_digest,
                route_ref=str(opportunity.get("route_ref") or ""),
                hypothesis=str(opportunity.get("hypothesis") or ""),
                classification=classification,
                result_summary=str(experiment.get("observed_result") or outcome),
                entry_ids=handoff_entry_ids,
                requested_disposition=requested_disposition,
                provenance={
                    "sandbox_path": str(experiment.get("sandbox_path") or ""),
                    "source_entry_id": str(opportunity.get("source_entry_id") or ""),
                    "source_action_key": str(
                        opportunity.get("source_action", {}).get("action_key", "")
                        if isinstance(opportunity.get("source_action"), dict)
                        else ""
                    ),
                    "logicguard_binding": dict(logicguard_simulation.get("binding") or {}),
                    "logicguard_simulation_receipt": dict(
                        logicguard_simulation.get("simulation_receipt") or {}
                    ),
                },
            )
            experiment["result_digest"] = result_digest
            experiment["closure_state"] = "closed"
            experiment["sleep_handoff_id"] = str(handoff.get("handoff_id") or "")
            experiment["sleep_handoff_created"] = bool(handoff.get("created"))
            experiment["history_event_id"] = ""
            experiment_results.append(experiment)

        if selected and experiment_results:
            classifications = ", ".join(sorted({item["classification"] for item in experiment_results}))
            _set_checkpoint_status(
                execution_plan,
                "validation",
                "completed",
                f"Validation completed with classifications: {classifications}.",
            )
            _set_checkpoint_status(
                execution_plan,
                "sleep-handoff",
                "completed",
                f"Published {len(experiment_results)} typed, idempotent Sleep handoff(s).",
            )
        run_observation_event_id = ""
        _set_checkpoint_status(execution_plan, "report", "completed", "Report payload prepared.")
        execution_plan["status"] = "completed"
        execution_plan["completed_at"] = utc_now_iso()
        write_json_file(run_dir / EXECUTION_PLAN_FILENAME, execution_plan)

        write_json_file(
            run_dir / EXPERIMENTS_FILENAME,
            {
                "schema_version": DREAM_SCHEMA_VERSION,
                "kind": "local-kb-dream-experiments",
                "run_id": resolved_run_id,
                "generated_at": generated_at,
                "experiment_count": len(experiment_results),
                "experiments": experiment_results,
            },
        )

        authority_after = load_authority_generation(repo_root)
        if str(authority_after.get("pointer_digest") or "") != str(
            authority_pin.get("pointer_digest") or ""
        ):
            raise RuntimeError("Dream authority generation changed during the pinned simulation run")

        result = {
            "schema_version": DREAM_SCHEMA_VERSION,
            "kind": DREAM_REPORT_KIND,
            "run_id": resolved_run_id,
            "generated_at": generated_at,
            "status": "completed",
            "authority_pin": {
                "generation_id": str(authority_pin.get("generation_id") or ""),
                "pointer_digest": str(authority_pin.get("pointer_digest") or ""),
                "unchanged_after_run": True,
            },
            "lane_guard": lane_guard,
            "preflight": preflight,
            "execution_plan": execution_plan,
            "opportunity_count": len(opportunities),
            "executable_opportunity_count": len(executable_opportunities),
            "valuable_opportunity_count": len(selected),
            "evaluated_fingerprints": [
                str(item.get("evidence_fingerprint") or "")
                for item in opportunities
                if str(item.get("evidence_fingerprint") or "")
            ],
            "evidence_deltas": [
                str(item.get("evidence_fingerprint") or "")
                for item in selected
                if str(item.get("evidence_fingerprint") or "")
            ],
            "suppressed_duplicate_count": skipped_prior_success_count,
            "no_delta_closed_count": skipped_prior_success_count,
            "cooldown_decisions": [
                {
                    "evidence_fingerprint": str(item.get("evidence_fingerprint") or ""),
                    "decision": "closed-without-delta",
                    "prior_closure": item.get("prior_closure", {}),
                }
                for item in opportunities
                if item.get("selection_status") == "no_delta_closed"
            ],
            "selected_experiment_count": len(selected),
            "created_candidate_count": 0,
            "created_candidates": [],
            "history_event_ids": history_event_ids,
            "run_observation_event_id": run_observation_event_id,
            "emitted_handoff_ids": [
                str(item.get("sleep_handoff_id") or "")
                for item in experiment_results
                if str(item.get("sleep_handoff_id") or "")
            ],
            "blockers": [],
            "final_run_state": "no_delta" if not selected else "completed",
            "policy_version": DREAM_SCHEMA_VERSION,
            "input_digest": content_fingerprint(
                [
                    str(item.get("evidence_fingerprint") or "")
                    for item in opportunities
                ]
            ),
            "experiments": experiment_results,
            "artifact_paths": {
                "run_dir": relative_repo_path(repo_root, run_dir),
                "plan_path": relative_repo_path(repo_root, run_dir / PLAN_FILENAME),
                "preflight_path": relative_repo_path(repo_root, run_dir / PREFLIGHT_FILENAME),
                "opportunities_path": relative_repo_path(repo_root, run_dir / OPPORTUNITIES_FILENAME),
                "experiments_path": relative_repo_path(repo_root, run_dir / EXPERIMENTS_FILENAME),
                "execution_plan_path": relative_repo_path(repo_root, run_dir / EXECUTION_PLAN_FILENAME),
                "sandbox_dir": relative_repo_path(repo_root, dream_sandbox_dir(repo_root, resolved_run_id)),
                "report_path": relative_repo_path(repo_root, run_dir / REPORT_FILENAME),
            },
        }
        write_json_file(run_dir / REPORT_FILENAME, result)
        write_lane_status(repo_root, "kb-dream", "completed", run_id=resolved_run_id)
        result["lock_release"] = release_lane_lock(repo_root, "kb-dream", run_id=resolved_run_id)
        lock_released = True
        write_json_file(run_dir / REPORT_FILENAME, result)
        return result
    except Exception as exc:
        write_lane_status(repo_root, "kb-dream", "failed", run_id=resolved_run_id, note=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        if not lock_released:
            release_lane_lock(repo_root, "kb-dream", run_id=resolved_run_id)
