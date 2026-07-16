from __future__ import annotations

from pathlib import Path
from typing import Any

from local_kb.org_checks import check_organization_repository
from local_kb.org_cleanup import apply_organization_cleanup_proposal, build_organization_cleanup_proposal
from local_kb.org_outbox import organization_outbox_dir
from local_kb.org_sources import validate_organization_repo
from local_kb.skill_sharing import find_local_skill_metadata
from local_kb.store import load_organization_entries


ORGANIZATION_REVIEW_SKILL_ID = "organization-review"


def _apply_changed_paths(org_root: Path, apply_result: dict[str, Any]) -> list[str]:
    paths: set[str] = set()
    for item in apply_result.get("applied") or []:
        if not isinstance(item, dict):
            continue
        for key in ("target_path", "updated_path"):
            value = str(item.get(key) or "").strip().replace("\\", "/")
            if value:
                paths.add(value)
    audit_path = str(apply_result.get("audit_path") or "").strip()
    if audit_path:
        try:
            paths.add(Path(audit_path).resolve().relative_to(Path(org_root).resolve()).as_posix())
        except ValueError:
            pass
    return sorted(paths)


def _merge_readiness(
    *,
    changed_files: list[str],
    post_apply_check: dict[str, Any],
    exact_selected_apply: dict[str, Any],
    skill_safety_checkpoint: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    allowed_prefixes = ("kb/imports/", "kb/main/")
    allowed_exact = {"maintenance/cleanup_audit.jsonl"}
    if not changed_files:
        blockers.append("no reviewed maintenance changes")
    if "maintenance/cleanup_audit.jsonl" not in changed_files:
        blockers.append("cleanup audit receipt is missing")
    outside = [
        path
        for path in changed_files
        if not path.startswith(allowed_prefixes) and path not in allowed_exact
    ]
    if outside:
        blockers.append(f"changed paths are outside the maintenance allowlist: {outside}")
    if post_apply_check and post_apply_check.get("ok") is not True:
        blockers.append("post-apply organization check failed")
    if exact_selected_apply.get("exact") is not True:
        blockers.append("applied action ids do not exactly match the selected ids")
    if skill_safety_checkpoint.get("passed") is not True:
        blockers.append("Skill safety, author, fork, or version checkpoint failed")
    return {
        "complete": True,
        "eligible": not blockers,
        "blockers": blockers,
        "changed_files": changed_files,
        "requires_cleanup_audit": True,
        "label": "org-kb:auto-merge" if not blockers else "",
    }


def _report_layout_policy(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_layout": "main-imports",
        "incoming_lane_path": str(validation.get("incoming_lane_path") or "kb/imports"),
        "exchange_surface_path": str(validation.get("exchange_surface_path") or "kb/main"),
        "local_download_primary_path": str(validation.get("local_download_primary_path") or "kb/main"),
        "local_download_paths": validation.get("local_download_paths") or ["kb/main"],
        "local_download_excluded_paths": validation.get("local_download_excluded_paths") or ["kb/imports"],
        "contribution_writes": ["kb/imports"],
        "maintenance_moves_reviewed_cards_to": "kb/main",
        "current_layout_only": True,
    }


def build_organization_cleanup_review(proposal: dict[str, Any]) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    selected_action_ids: list[str] = []
    selected_action_types: set[str] = set()
    allow_trusted = False
    allow_delete = False
    allow_promote = False

    for action in proposal.get("actions") or []:
        if not isinstance(action, dict):
            continue
        action_id = str(action.get("action_id") or "").strip()
        action_type = str(action.get("action_type") or "").strip()
        target_path = str(action.get("target_path") or "").replace("\\", "/")
        risk = str(action.get("risk") or "").strip()
        approve = False
        decision = "watch"
        reason = ""

        if action.get("apply_supported") is False:
            source_reason = str(action.get("reason") or "").strip()
            reason = (
                f"{source_reason} Current organization tooling keeps this exact action watch-only until a concrete, reversible apply packet exists."
            ).strip()
        elif action_type == "delete-card":
            current_status = str(action.get("current_status") or "").strip()
            current_confidence = float(action.get("current_confidence") or 1.0)
            approve = (
                not target_path.startswith("kb/main/")
                and current_status in {"rejected", "deprecated"}
                and current_confidence <= 0.2
            )
            reason = (
                "Rejected or deprecated low-confidence organization card can be deleted with audit."
                if approve
                else "Deletion did not meet the audited low-confidence rejected/deprecated card rule."
            )
        elif action_type == "promote-card":
            proposed_path = str(action.get("proposed_path") or "").replace("\\", "/")
            approve = (
                str(action.get("current_status") or "") == "candidate"
                and str(action.get("proposed_status") or "") == "trusted"
                and proposed_path.startswith("kb/main/")
                and float(action.get("current_confidence") or 0.0) >= 0.85
            )
            reason = (
                "High-confidence candidate has a concrete main target path and can be promoted."
                if approve
                else "Promotion did not meet the organization Sleep promotion rule."
            )
        elif action_type == "accept-import":
            proposed_path = str(action.get("proposed_path") or "").replace("\\", "/")
            approve = (
                target_path.startswith("kb/imports/")
                and str(action.get("current_status") or "") == "candidate"
                and str(action.get("proposed_status") or "") == "candidate"
                and proposed_path.startswith("kb/main/")
            )
            reason = (
                "Imported candidate has a concrete main target path and can enter the organization exchange surface."
                if approve
                else "Import acceptance did not meet the organization Sleep main-transfer rule."
            )
        elif action_type in {"status-adjust", "confidence-adjust", "mark-duplicate"}:
            approve = True
            reason = "Deterministic organization cleanup action is selected for Sleep-style apply."
        else:
            reason = "Unknown organization cleanup action type remains watch-only."

        if approve:
            decision = "selected-for-apply"
            selected_action_ids.append(action_id)
            selected_action_types.add(action_type)
            if target_path.startswith("kb/main/"):
                allow_trusted = True
            if action_type == "delete-card":
                allow_delete = True
            if action_type in {"accept-import", "promote-card"}:
                allow_promote = True

        decisions.append(
            {
                "action_id": action_id,
                "action_type": action_type,
                "target_path": target_path,
                "decision": decision,
                "risk": risk,
                "reason": reason,
            }
        )

    return {
        "decision_count": len(decisions),
        "selected_count": len(selected_action_ids),
        "selected_action_ids": selected_action_ids,
        "selected_action_types": sorted(selected_action_types),
        "approved_count": len(selected_action_ids),
        "approved_action_ids": selected_action_ids,
        "approved_action_types": sorted(selected_action_types),
        "allow_trusted": allow_trusted,
        "allow_delete": allow_delete,
        "allow_promote": allow_promote,
        "decisions": decisions,
    }


def build_organization_maintenance_report(
    org_root: Path,
    *,
    repo_root: Path | None = None,
    organization_id: str = "",
    apply_reviewed_cleanup: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    validation = validate_organization_repo(org_root)
    if not validation.get("ok"):
        return {
            "ok": False,
            "validation": validation,
            "entry_count": 0,
            "outbox_count": 0,
            "recommendations": ["fix-organization-repository-validation"],
        }

    organization_id = organization_id or str(validation.get("organization_id") or "")
    entries = load_organization_entries(
        Path(org_root),
        organization_id,
        source_commit=str(validation.get("commit") or ""),
    )
    organization_check = check_organization_repository(org_root)
    duplicate_content_hashes = (
        organization_check.get("checks", {})
        .get("cards", {})
        .get("duplicate_content_hashes", {})
    )
    if not isinstance(duplicate_content_hashes, dict):
        duplicate_content_hashes = {}

    outbox_count = 0
    review_skill: dict[str, Any] = {
        "id": ORGANIZATION_REVIEW_SKILL_ID,
        "installed": False,
        "status": "missing",
    }
    if repo_root is not None:
        outbox_dir = organization_outbox_dir(Path(repo_root), organization_id)
        outbox_count = len(list(outbox_dir.glob("*.yaml"))) if outbox_dir.exists() else 0
        skill_metadata = find_local_skill_metadata(Path(repo_root), ORGANIZATION_REVIEW_SKILL_ID)
        if skill_metadata is not None:
            review_skill = {
                **skill_metadata,
                "installed": True,
            }

    recommendations: list[str] = []
    imports_count = int(validation.get("imports_count") or 0)
    main_active_count = int(validation.get("main_active_count") or 0)
    if imports_count:
        recommendations.append("review-organization-imports")
    if main_active_count:
        recommendations.append("review-main-exchange-surface")
    if outbox_count:
        recommendations.append("review-local-outbox-proposals")
    if validation.get("skill_count", 0):
        recommendations.append("review-skill-registry")
    if duplicate_content_hashes:
        recommendations.append("review-duplicate-card-content-hashes")
    if organization_check.get("errors"):
        recommendations.append("fix-organization-check-errors")
    cleanup_proposal = build_organization_cleanup_proposal(org_root, organization_id=organization_id)
    cleanup_actions = cleanup_proposal.get("actions") if isinstance(cleanup_proposal.get("actions"), list) else []
    card_decisions = (
        cleanup_proposal.get("card_decisions")
        if isinstance(cleanup_proposal.get("card_decisions"), list)
        else []
    )
    cleanup_review = build_organization_cleanup_review(cleanup_proposal)
    cleanup_apply: dict[str, Any] = {"attempted": False}
    post_apply_check: dict[str, Any] = {}
    post_apply_validation: dict[str, Any] = {}
    if apply_reviewed_cleanup and cleanup_review["selected_action_ids"]:
        cleanup_apply = apply_organization_cleanup_proposal(
            Path(org_root),
            cleanup_proposal,
            allow_actions=set(cleanup_review["selected_action_types"]),
            allow_action_ids=set(cleanup_review["selected_action_ids"]),
            allow_trusted=bool(cleanup_review["allow_trusted"]),
            allow_delete=bool(cleanup_review["allow_delete"]),
            allow_promote=bool(cleanup_review["allow_promote"]),
            dry_run=dry_run,
        )
        cleanup_apply["attempted"] = True
        post_validation = validate_organization_repo(org_root)
        changed_files = _apply_changed_paths(Path(org_root), cleanup_apply)
        post_check = check_organization_repository(org_root, changed_files=changed_files)
        post_apply_check = {
            "ok": bool(post_check.get("ok")),
            "validation_ok": bool(post_validation.get("ok")),
            "error_count": len(post_check.get("errors") or []),
            "warning_count": len(post_check.get("warnings") or []),
            "auto_merge_blockers": post_check.get("auto_merge_blockers") or [],
            "changed_files": changed_files,
            "privacy_scan_ok": bool(
                ((post_check.get("checks") or {}).get("privacy_scan") or {}).get("ok")
            ),
        }
        post_apply_validation = {
            "ok": bool(post_validation.get("ok")),
            "layout": post_validation.get("layout"),
            "incoming_lane_path": post_validation.get("incoming_lane_path"),
            "exchange_surface_path": post_validation.get("exchange_surface_path"),
            "main_count": post_validation.get("main_count", 0),
            "main_active_count": post_validation.get("main_active_count", 0),
            "main_status_counts": post_validation.get("main_status_counts") or {},
            "imports_count": post_validation.get("imports_count", 0),
            "imports_status_counts": post_validation.get("imports_status_counts") or {},
            "trusted_count": post_validation.get("trusted_count", 0),
            "candidate_count": post_validation.get("candidate_count", 0),
        }
    trusted_cleanup_actions = [
        action
        for action in cleanup_actions
        if str(action.get("target_path") or "").replace("\\", "/").startswith("kb/main/")
    ]
    if cleanup_actions:
        recommendations.append("review-organization-cleanup-proposals")
    if trusted_cleanup_actions:
        recommendations.append("review-trusted-organization-card-maintenance")

    merge_actions = [
        action for action in cleanup_actions if str(action.get("action_type") or "") == "merge-cards"
    ]
    split_actions = [
        action for action in cleanup_actions if str(action.get("action_type") or "") == "split-card"
    ]
    skill_actions = [
        action
        for action in cleanup_actions
        if str(action.get("action_type") or "").startswith("skill-")
    ]
    blocking_skill_actions = [
        action
        for action in skill_actions
        if str(action.get("action_type") or "")
        in {"skill-bundle-safety-block", "skill-bundle-fork-required"}
    ]
    merge_split_checkpoint = {
        "complete": True,
        "reviewed_card_count": int(cleanup_proposal.get("card_count") or 0),
        "merge_decision_ids": [str(action.get("action_id") or "") for action in merge_actions],
        "split_decision_ids": [str(action.get("action_id") or "") for action in split_actions],
        "no_merge_candidates": not merge_actions,
        "no_split_candidates": not split_actions,
    }
    card_count = int(cleanup_proposal.get("card_count") or 0)
    card_decision_ids = [
        str(item.get("decision_id") or "")
        for item in card_decisions
        if isinstance(item, dict)
    ]
    card_decision_paths = [
        str(item.get("target_path") or "")
        for item in card_decisions
        if isinstance(item, dict)
    ]
    required_dimensions = {"scenario", "action", "prediction", "route", "evidence"}
    card_decision_checkpoint = {
        "complete": (
            len(card_decisions) == card_count
            and len(card_decision_ids) == len(set(card_decision_ids))
            and len(card_decision_paths) == len(set(card_decision_paths))
            and all(
                isinstance(item, dict)
                and str(item.get("decision") or "").strip()
                and str(item.get("reason") or "").strip()
                and set(item.get("reviewed_dimensions") or []) == required_dimensions
                for item in card_decisions
            )
        ),
        "card_count": card_count,
        "decision_count": len(card_decisions),
        "decision_ids": card_decision_ids,
        "decisions": card_decisions,
        "required_dimensions": sorted(required_dimensions),
    }
    skill_registry_check = (
        (organization_check.get("checks") or {}).get("skill_registry") or {}
        if isinstance(organization_check.get("checks"), dict)
        else {}
    )
    card_check = (
        (organization_check.get("checks") or {}).get("cards") or {}
        if isinstance(organization_check.get("checks"), dict)
        else {}
    )
    skill_safety_checkpoint = {
        "complete": True,
        "passed": (
            bool(skill_registry_check.get("ok"))
            and bool(card_check.get("ok"))
            and not blocking_skill_actions
        ),
        "skill_count": int(validation.get("skill_count") or 0),
        "bundle_count": int(card_check.get("bundle_count") or 0),
        "decision_ids": [str(action.get("action_id") or "") for action in skill_actions],
        "blocking_decision_ids": [str(action.get("action_id") or "") for action in blocking_skill_actions],
        "errors": [
            *[str(item) for item in skill_registry_check.get("errors") or []],
            *[str(item) for item in card_check.get("errors") or []],
        ],
    }
    selected_ids = [str(item) for item in cleanup_review.get("selected_action_ids") or []]
    applied_ids = [str(item) for item in cleanup_apply.get("applied_action_ids") or []]
    exact_selected_apply = {
        "complete": True,
        "selected_action_ids": selected_ids,
        "applied_action_ids": applied_ids,
        "missing_selected_action_ids": sorted(set(selected_ids) - set(applied_ids)),
        "unexpected_applied_action_ids": sorted(set(applied_ids) - set(selected_ids)),
        "exact": len(selected_ids) == len(set(selected_ids)) and set(selected_ids) == set(applied_ids),
    }
    merge_readiness = _merge_readiness(
        changed_files=[str(item) for item in post_apply_check.get("changed_files") or []],
        post_apply_check=post_apply_check,
        exact_selected_apply=exact_selected_apply,
        skill_safety_checkpoint=skill_safety_checkpoint,
    )

    return {
        "ok": (
            bool(organization_check.get("ok"))
            and bool(skill_safety_checkpoint["passed"])
            and bool(card_decision_checkpoint["complete"])
        ),
        "maintenance_model": cleanup_proposal.get("maintenance_model") or {},
        "validation": validation,
        "layout_policy": _report_layout_policy(validation),
        "organization_check": {
            "ok": bool(organization_check.get("ok")),
            "error_count": len(organization_check.get("errors") or []),
            "warning_count": len(organization_check.get("warnings") or []),
            "auto_merge_eligible": bool(organization_check.get("auto_merge_eligible")),
            "auto_merge_blockers": organization_check.get("auto_merge_blockers") or [],
        },
        "cleanup": {
            "duplicate_content_hash_count": len(duplicate_content_hashes),
            "duplicate_content_hashes": duplicate_content_hashes,
            "proposal_action_count": len(cleanup_actions),
            "proposal_counts": cleanup_proposal.get("counts") or {},
            "trusted_card_action_count": len(trusted_cleanup_actions),
            "exchange_surface_action_count": len(trusted_cleanup_actions),
            "exchange_surface_maintenance": "in-scope-like-local-sleep",
            "trusted_card_maintenance": "in-scope-like-local-sleep",
            "similar_card_merge_apply": "planned",
            "weak_card_rejection_apply": "planned",
            "candidate_delete_apply": "planned",
            "skill_bundle_cleanup_apply": "partial",
            "merge_split_checkpoint": merge_split_checkpoint,
            "card_decision_checkpoint": card_decision_checkpoint,
            "skill_safety_checkpoint": skill_safety_checkpoint,
            "exact_selected_apply": exact_selected_apply,
            "github_merge_readiness": merge_readiness,
            "review": cleanup_review,
            "apply": cleanup_apply,
            "post_apply_check": post_apply_check,
            "post_apply_validation": post_apply_validation,
        },
        "organization_id": organization_id,
        "entry_count": len(entries),
        "main_count": validation.get("main_count", 0),
        "main_active_count": validation.get("main_active_count", 0),
        "main_status_counts": validation.get("main_status_counts") or {},
        "imports_count": validation.get("imports_count", 0),
        "imports_status_counts": validation.get("imports_status_counts") or {},
        "trusted_count": validation.get("trusted_count", 0),
        "candidate_count": validation.get("candidate_count", 0),
        "skill_count": validation.get("skill_count", 0),
        "outbox_count": outbox_count,
        "organization_review_skill": review_skill,
        "recommendations": recommendations,
    }
