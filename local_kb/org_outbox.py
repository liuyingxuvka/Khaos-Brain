from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

from local_kb.adoption import ADOPTION_KEY, adoption_state, card_exchange_hash, recorded_exchange_hashes
from local_kb.org_sources import utc_timestamp
from local_kb.skill_sharing import build_card_skill_dependency_manifest, materialize_skill_bundle_dependencies
from local_kb.store import load_entries, load_organization_entries, write_yaml_file


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
            scopes=("main", "imports", "trusted", "candidates"),
            allowed_statuses=None,
        ):
            hashes.add(card_exchange_hash(entry.data))
    return hashes


def share_eligibility(entry_data: dict[str, Any]) -> dict[str, Any]:
    card_type = str(entry_data.get("type") or "").strip().lower()
    card_scope = str(entry_data.get("scope") or "").strip().lower()
    reasons: list[str] = []
    if card_type not in SHAREABLE_CARD_TYPES:
        reasons.append("card type is not shareable")
    if card_scope not in SHAREABLE_SCOPES:
        reasons.append("card scope is not public")

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
    }


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
        "source_repo": str((adoption or {}).get("source_repo") or "").strip() if isinstance(adoption, dict) else "",
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
    prior_exchange_hashes = recorded_exchange_hashes(repo_root, {"downloaded", "used", "absorbed", "exported", "uploaded"})
    organization_hashes = _organization_exchange_hashes(organization_sources, organization_id=organization_id)

    for entry in load_entries(repo_root):
        entry_id = str(entry.data.get("id") or entry.path.stem).strip()
        eligibility = share_eligibility(entry.data)
        source_path = os.path.relpath(entry.path, repo_root)
        if not eligibility["eligible"]:
            skipped.append({"entry_id": entry_id, "path": source_path, "reasons": eligibility["reasons"]})
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

        payload = build_organization_proposal_payload(
            entry.data,
            organization_id=organization_id,
            source_path=source_path,
            created_at=now,
        )
        skill_dependencies = build_card_skill_dependency_manifest(
            repo_root,
            entry.data,
            persist_bundle_metadata=not dry_run,
        )
        if skill_dependencies:
            payload["organization_proposal"]["skill_dependencies"] = materialize_skill_bundle_dependencies(
                skill_dependencies,
                outbox_dir,
                dry_run=dry_run,
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
    }
