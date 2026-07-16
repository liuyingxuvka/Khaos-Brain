from __future__ import annotations

import copy
import os
from pathlib import Path
import re
from typing import Any

from local_kb.adoption import ADOPTION_KEY, adoption_state, card_exchange_hash, recorded_exchange_hashes
from local_kb.org_checks import validate_shareable_payload
from local_kb.org_sources import utc_timestamp
from local_kb.model_maintenance import load_current_model_entries
from local_kb.skill_sharing import (
    build_card_skill_dependency_manifest,
    extract_skill_dependencies,
    materialize_skill_bundle_dependencies,
)
from local_kb.store import load_organization_entries, write_yaml_file


SHAREABLE_CARD_TYPES = {"model", "heuristic"}
SHAREABLE_SCOPES = {"public"}


def organization_outbox_dir(repo_root: Path, organization_id: str) -> Path:
    safe_id = "".join(char if char.isalnum() or char in "._-" else "-" for char in organization_id).strip("-")
    return repo_root / "kb" / "outbox" / "organization" / (safe_id or "org")


def _safe_file_stem(value: Any) -> str:
    text = str(value or "").strip()
    safe = "".join(char if char.isalnum() or char in "._-" else "-" for char in text).strip("-")
    return safe or "card"


def _organization_exchange_hashes(
    organization_sources: list[dict[str, Any]] | None,
    *,
    organization_id: str,
) -> set[str]:
    hashes: set[str] = set()
    for source in organization_sources or []:
        source_org_id = str(source.get("organization_id") or source.get("id") or "").strip()
        if organization_id and source_org_id and source_org_id != organization_id:
            continue
        org_root = Path(str(source.get("path") or source.get("local_path") or ""))
        if not org_root.exists():
            continue
        for entry in load_organization_entries(
            org_root,
            source_org_id or organization_id,
            source_repo=str(source.get("source_repo") or source.get("repo_url") or ""),
            source_commit=str(source.get("source_commit") or ""),
            scopes=("main", "imports"),
            allowed_statuses=None,
        ):
            hashes.add(card_exchange_hash(entry.data))
    return hashes


def share_eligibility(
    entry_data: dict[str, Any],
    *,
    proposal_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    card_type = str(entry_data.get("type") or "").strip().lower()
    card_scope = str(entry_data.get("scope") or "").strip().lower()
    reasons: list[str] = []
    if card_type not in SHAREABLE_CARD_TYPES:
        reasons.append("card type is not shareable")
    if card_scope not in SHAREABLE_SCOPES:
        reasons.append("card scope is not public")

    payload_safety = validate_shareable_payload(
        proposal_payload if proposal_payload is not None else entry_data,
        path_label=str(entry_data.get("id") or "card"),
    )
    reasons.extend(payload_safety.get("errors") or [])

    adoption = entry_data.get(ADOPTION_KEY) if isinstance(entry_data.get(ADOPTION_KEY), dict) else {}
    adoption_status = ""
    if adoption:
        adoption_status = adoption_state(entry_data)
        if adoption_status == "clean":
            reasons.append("clean adopted organization card does not need feedback")
        if adoption_status == "locally_rejected":
            reasons.append("locally rejected adopted card is not shared automatically")

    return {
        "eligible": not reasons,
        "reasons": reasons,
        "adoption_state": adoption_status,
        "payload_safety": payload_safety,
    }


def skill_dependency_evidence(entry_data: dict[str, Any]) -> dict[str, Any]:
    dependencies = extract_skill_dependencies(entry_data)
    if not dependencies:
        return {
            "applicable": False,
            "ok": True,
            "dependency_ids": [],
            "missing_fields": [],
        }
    use = entry_data.get("use") if isinstance(entry_data.get("use"), dict) else {}
    predict = entry_data.get("predict") if isinstance(entry_data.get("predict"), dict) else {}
    action = entry_data.get("action") if isinstance(entry_data.get("action"), dict) else {}
    usefulness = str(
        use.get("skill_usefulness")
        or use.get("guidance")
        or action.get("description")
        or ""
    ).strip()
    expected_outcome = str(predict.get("expected_result") or predict.get("outcome") or "").strip()
    unavailable_skill_guidance = str(use.get("unavailable_skill_guidance") or "").strip()
    missing_fields: list[str] = []
    if not usefulness:
        missing_fields.append("operational-usefulness")
    if not expected_outcome:
        missing_fields.append("expected-outcome")
    if not unavailable_skill_guidance:
        missing_fields.append("unavailable-skill-guidance")
    return {
        "applicable": True,
        "ok": not missing_fields,
        "dependency_ids": [str(item.get("id") or "") for item in dependencies],
        "missing_fields": missing_fields,
        "usefulness": usefulness,
        "expected_outcome": expected_outcome,
        "unavailable_skill_guidance": unavailable_skill_guidance,
    }


def _shareable_source_repo(value: Any) -> str:
    """Keep portable remote repository identities, never local clone paths."""

    text = str(value or "").strip()
    lowered = text.lower()
    if lowered.startswith(("https://", "http://", "ssh://", "git://")):
        return text
    if re.match(r"^[^/@\s]+@[^:\s]+:[^\s]+$", text):
        return text
    return ""


def build_organization_proposal_payload(
    entry_data: dict[str, Any],
    *,
    organization_id: str,
    source_path: str,
    created_at: str,
) -> dict[str, Any]:
    payload = copy.deepcopy(entry_data)
    adoption = payload.pop(ADOPTION_KEY, None)
    original_status = str(payload.get("status") or "").strip()
    payload["status"] = "candidate"
    payload["organization_proposal"] = {
        "organization_id": organization_id,
        "source_path": source_path,
        "created_at": created_at,
        "content_hash": card_exchange_hash(entry_data),
        "proposal_kind": "adopted-feedback" if isinstance(adoption, dict) else "new-card",
        "adoption_state": adoption_state(entry_data) if isinstance(adoption, dict) else "",
        "source_entry_id": str((adoption or {}).get("source_entry_id") or entry_data.get("id") or "").strip()
        if isinstance(adoption, dict)
        else str(entry_data.get("id") or "").strip(),
        "source_commit": str((adoption or {}).get("source_commit") or "").strip() if isinstance(adoption, dict) else "",
        "source_repo": _shareable_source_repo((adoption or {}).get("source_repo")) if isinstance(adoption, dict) else "",
        "original_status": original_status,
    }
    return payload


def build_organization_outbox(
    repo_root: Path,
    *,
    organization_id: str,
    dry_run: bool = False,
    organization_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    organization_id = str(organization_id or "").strip()
    if not organization_id:
        return {"ok": False, "errors": ["organization_id is required"], "created": [], "skipped": []}

    outbox_dir = organization_outbox_dir(repo_root, organization_id)
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    now = utc_timestamp()
    exported_hashes: set[str] = set()
    privacy_reviewed_count = 0
    privacy_blocked_count = 0
    skill_dependency_count = 0
    skill_bundle_count = 0
    skill_bundle_errors: list[str] = []
    skill_dependency_evidence_reviewed_count = 0
    skill_dependency_evidence_blocked_count = 0
    prior_exchange_hashes = recorded_exchange_hashes(repo_root, {"downloaded", "used", "absorbed", "exported", "uploaded"})
    organization_hashes = _organization_exchange_hashes(organization_sources, organization_id=organization_id)

    for entry in load_current_model_entries(repo_root)[0]:
        entry_id = str(entry.data.get("id") or entry.path.stem).strip()
        source_path = os.path.relpath(entry.path, repo_root)
        payload = build_organization_proposal_payload(
            entry.data,
            organization_id=organization_id,
            source_path=source_path,
            created_at=now,
        )
        eligibility = share_eligibility(entry.data, proposal_payload=payload)
        privacy_reviewed_count += 1
        if not eligibility["eligible"]:
            if not (eligibility.get("payload_safety") or {}).get("ok", True):
                privacy_blocked_count += 1
            skipped.append({"entry_id": entry_id, "path": source_path, "reasons": eligibility["reasons"]})
            continue
        dependency_evidence = skill_dependency_evidence(entry.data)
        if dependency_evidence["applicable"]:
            skill_dependency_evidence_reviewed_count += 1
            if not dependency_evidence["ok"]:
                skill_dependency_evidence_blocked_count += 1
                skipped.append(
                    {
                        "entry_id": entry_id,
                        "path": source_path,
                        "reasons": [
                            "Skill dependency evidence is incomplete: "
                            + ", ".join(dependency_evidence["missing_fields"])
                        ],
                    }
                )
                continue
        content_hash = card_exchange_hash(entry.data)
        if content_hash in prior_exchange_hashes:
            skipped.append({"entry_id": entry_id, "path": source_path, "reasons": ["content hash was already exchanged with organization"]})
            continue
        if content_hash in organization_hashes:
            skipped.append({"entry_id": entry_id, "path": source_path, "reasons": ["content hash already exists in organization repository"]})
            continue
        if content_hash in exported_hashes:
            skipped.append({"entry_id": entry_id, "path": source_path, "reasons": ["duplicate content hash already exported"]})
            continue

        skill_dependencies = build_card_skill_dependency_manifest(
            repo_root,
            entry.data,
            persist_bundle_metadata=not dry_run,
        )
        if skill_dependencies:
            materialized_dependencies = materialize_skill_bundle_dependencies(
                skill_dependencies,
                outbox_dir,
                dry_run=dry_run,
            )
            payload["organization_proposal"]["skill_dependencies"] = materialized_dependencies
            skill_dependency_count += len(materialized_dependencies)
            for dependency in materialized_dependencies:
                if dependency.get("sharing_mode") != "card-bound-bundle":
                    continue
                skill_bundle_count += 1
                missing = [
                    key
                    for key in (
                        "bundle_id",
                        "content_hash",
                        "version_time",
                        "original_author",
                        "bundle_path",
                    )
                    if not str(dependency.get(key) or "").strip()
                ]
                if dependency.get("readonly_when_imported") is not True:
                    missing.append("readonly_when_imported")
                if str(dependency.get("update_policy") or "") != "original_author_only":
                    missing.append("update_policy")
                if missing:
                    skill_bundle_errors.append(
                        f"{entry_id}:{dependency.get('id') or 'skill'}:{','.join(sorted(set(missing)))}"
                    )
        target_path = outbox_dir / f"{_safe_file_stem(entry_id)}.yaml"
        if not dry_run:
            write_yaml_file(target_path, payload)
        created.append(
            {
                "entry_id": entry_id,
                "path": str(target_path),
                "source_path": source_path,
                "content_hash": content_hash,
                "proposal_kind": payload["organization_proposal"]["proposal_kind"],
            }
        )
        exported_hashes.add(content_hash)

    return {
        "ok": True,
        "organization_id": organization_id,
        "outbox_dir": str(outbox_dir),
        "dry_run": dry_run,
        "organization_hash_count": len(organization_hashes),
        "created_count": len(created),
        "skipped_count": len(skipped),
        "created": created,
        "skipped": skipped,
        "privacy_checkpoint": {
            "complete": True,
            "reviewed_count": privacy_reviewed_count,
            "blocked_sensitive_count": privacy_blocked_count,
        },
        "skill_bundle_checkpoint": {
            "complete": not skill_bundle_errors,
            "dependency_count": skill_dependency_count,
            "bundle_count": skill_bundle_count,
            "errors": skill_bundle_errors,
            "dependency_evidence_reviewed_count": skill_dependency_evidence_reviewed_count,
            "dependency_evidence_blocked_count": skill_dependency_evidence_blocked_count,
        },
    }
