from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

from local_kb.common import utc_now_iso
from local_kb.store import load_yaml_file, write_yaml_file


ORG_LAYOUT_MIGRATION_ID = "organization-layout-direct-to-current-v1"
CURRENT_MAIN_PATH = "kb/main"
CURRENT_IMPORTS_PATH = "kb/imports"
OBSOLETE_ROOTS = ("kb/trusted", "kb/candidates")
OBSOLETE_MANIFEST_FIELDS = ("trusted_path", "candidates_path")


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _migration_receipt_path(repo_root: Path) -> Path:
    metadata_root = repo_root / ".git" if (repo_root / ".git").is_dir() else repo_root / ".khaos-brain-migrations"
    return metadata_root / "khaos-brain-migrations" / f"{ORG_LAYOUT_MIGRATION_ID}.json"


def _snapshot_root(repo_root: Path, run_id: str) -> Path:
    metadata_root = repo_root / ".git" if (repo_root / ".git").is_dir() else repo_root / ".khaos-brain-migrations"
    return metadata_root / "khaos-brain-migration-backups" / run_id


def _restore_snapshot(repo_root: Path, snapshot_root: Path) -> None:
    kb_root = repo_root / "kb"
    if kb_root.exists():
        shutil.rmtree(kb_root)
    snapshot_kb = snapshot_root / "kb"
    if snapshot_kb.exists():
        shutil.copytree(snapshot_kb, kb_root)
    manifest_snapshot = snapshot_root / "khaos_org_kb.yaml"
    if manifest_snapshot.exists():
        shutil.copy2(manifest_snapshot, repo_root / "khaos_org_kb.yaml")


def _current_manifest_shape(manifest: dict[str, Any]) -> bool:
    kb = manifest.get("kb") if isinstance(manifest.get("kb"), dict) else {}
    return bool(
        kb.get("main_path") == CURRENT_MAIN_PATH
        and kb.get("imports_path") == CURRENT_IMPORTS_PATH
        and all(field not in kb for field in OBSOLETE_MANIFEST_FIELDS)
    )


def _obsolete_manifest_shape(manifest: dict[str, Any]) -> bool:
    kb = manifest.get("kb") if isinstance(manifest.get("kb"), dict) else {}
    return bool(
        kb.get("trusted_path") == "kb/trusted"
        and kb.get("candidates_path") == "kb/candidates"
        and kb.get("imports_path") == CURRENT_IMPORTS_PATH
        and "main_path" not in kb
    )


def _migration_map(repo_root: Path) -> list[tuple[Path, Path]]:
    moves: list[tuple[Path, Path]] = []
    for source_relative, lane in (("kb/trusted", "trusted"), ("kb/candidates", "candidates")):
        source_root = repo_root / source_relative
        if not source_root.exists():
            continue
        for source in sorted(path for path in source_root.rglob("*") if path.is_file()):
            target = repo_root / CURRENT_MAIN_PATH / lane / source.relative_to(source_root)
            moves.append((source, target))
    return moves


def migrate_organization_repo_to_current(repo_root: Path) -> dict[str, Any]:
    """One-time direct rewrite of the exact retired organization layout.

    Normal organization readers never import or call this module. The installer or
    connection upgrade boundary calls it before strict current-format validation.
    """

    from local_kb.org_sources import _run_git, current_git_commit, validate_organization_repo

    repo_root = Path(repo_root)
    manifest_path = repo_root / "khaos_org_kb.yaml"
    if not manifest_path.is_file():
        return {"ok": False, "status": "blocked", "error": "missing organization manifest"}
    manifest = load_yaml_file(manifest_path)
    if not isinstance(manifest, dict):
        return {"ok": False, "status": "blocked", "error": "organization manifest must be a mapping"}

    obsolete_roots = [relative for relative in OBSOLETE_ROOTS if (repo_root / relative).exists()]
    obsolete_fields = [
        field
        for field in OBSOLETE_MANIFEST_FIELDS
        if field in (manifest.get("kb") if isinstance(manifest.get("kb"), dict) else {})
    ]
    if _current_manifest_shape(manifest) and not obsolete_roots:
        validation = validate_organization_repo(repo_root)
        return {
            "ok": bool(validation.get("ok")),
            "status": "no_delta" if validation.get("ok") else "blocked",
            "migration_id": ORG_LAYOUT_MIGRATION_ID,
            "residual_obsolete_root_count": 0,
            "residual_obsolete_field_count": 0,
            "validation": validation,
            "error": "" if validation.get("ok") else "; ".join(validation.get("errors") or []),
        }

    if not _obsolete_manifest_shape(manifest):
        return {
            "ok": False,
            "status": "blocked",
            "migration_id": ORG_LAYOUT_MIGRATION_ID,
            "error": "organization layout is neither the exact retired format nor the sole current format",
            "obsolete_roots": obsolete_roots,
            "obsolete_fields": obsolete_fields,
        }

    git_repo = (repo_root / ".git").is_dir()
    source_commit = current_git_commit(repo_root) if git_repo else ""
    if git_repo:
        dirty = _run_git(["status", "--porcelain"], cwd=repo_root)
        if dirty.returncode != 0 or dirty.stdout.strip():
            return {
                "ok": False,
                "status": "blocked",
                "migration_id": ORG_LAYOUT_MIGRATION_ID,
                "error": "organization repository must be clean before one-time migration",
            }

    moves = _migration_map(repo_root)
    collisions: list[str] = []
    for source, target in moves:
        if target.exists() and _file_digest(source) != _file_digest(target):
            collisions.append(target.relative_to(repo_root).as_posix())
    if collisions:
        return {
            "ok": False,
            "status": "blocked",
            "migration_id": ORG_LAYOUT_MIGRATION_ID,
            "error": "organization migration has content collisions",
            "collisions": collisions,
        }

    run_id = f"{utc_now_iso().replace(':', '').replace('-', '')}-{uuid4().hex[:8]}"
    snapshot_root = _snapshot_root(repo_root, run_id)
    snapshot_root.mkdir(parents=True, exist_ok=False)
    if (repo_root / "kb").exists():
        shutil.copytree(repo_root / "kb", snapshot_root / "kb")
    shutil.copy2(manifest_path, snapshot_root / "khaos_org_kb.yaml")

    try:
        moved: list[str] = []
        deduplicated: list[str] = []
        for source, target in moves:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                deduplicated.append(source.relative_to(repo_root).as_posix())
            else:
                shutil.copy2(source, target)
                moved.append(target.relative_to(repo_root).as_posix())
        for relative in OBSOLETE_ROOTS:
            obsolete = repo_root / relative
            if obsolete.exists():
                shutil.rmtree(obsolete)
        (repo_root / CURRENT_MAIN_PATH).mkdir(parents=True, exist_ok=True)
        (repo_root / CURRENT_IMPORTS_PATH).mkdir(parents=True, exist_ok=True)

        kb = dict(manifest.get("kb") or {})
        for field in OBSOLETE_MANIFEST_FIELDS:
            kb.pop(field, None)
        kb["main_path"] = CURRENT_MAIN_PATH
        kb["imports_path"] = CURRENT_IMPORTS_PATH
        manifest["kb"] = kb
        write_yaml_file(manifest_path, manifest)

        validation = validate_organization_repo(repo_root)
        residual_roots = [relative for relative in OBSOLETE_ROOTS if (repo_root / relative).exists()]
        residual_fields = [field for field in OBSOLETE_MANIFEST_FIELDS if field in kb]
        if not validation.get("ok") or residual_roots or residual_fields:
            raise RuntimeError("; ".join(validation.get("errors") or ["obsolete organization residuals remain"]))

        target_commit = source_commit
        if git_repo:
            add = _run_git(["add", "--", "khaos_org_kb.yaml", "kb"], cwd=repo_root)
            if add.returncode != 0:
                raise RuntimeError(add.stderr.strip() or add.stdout.strip() or "git add failed")
            commit = _run_git(
                [
                    "-c", "user.name=Chaos Brain Upgrade",
                    "-c", "user.email=chaos-brain-upgrade@local.invalid",
                    "commit", "-m", "Migrate organization KB to current layout",
                ],
                cwd=repo_root,
            )
            if commit.returncode != 0:
                raise RuntimeError(commit.stderr.strip() or commit.stdout.strip() or "migration commit failed")
            target_commit = current_git_commit(repo_root)

        receipt = {
            "schema_version": 1,
            "migration_id": ORG_LAYOUT_MIGRATION_ID,
            "status": "committed",
            "migrated_at": utc_now_iso(),
            "source_commit": source_commit,
            "target_commit": target_commit,
            "moved_paths": moved,
            "deduplicated_source_paths": deduplicated,
            "residual_obsolete_root_count": 0,
            "residual_obsolete_field_count": 0,
            "rollback_snapshot": str(snapshot_root),
            "validation_ok": True,
        }
        _atomic_write_json(_migration_receipt_path(repo_root), receipt)
        return {"ok": True, "status": "committed", "migration_id": ORG_LAYOUT_MIGRATION_ID, "receipt": receipt}
    except Exception as exc:
        _restore_snapshot(repo_root, snapshot_root)
        if git_repo:
            _run_git(["reset", "--mixed", "HEAD"], cwd=repo_root)
        return {
            "ok": False,
            "status": "rolled_back",
            "migration_id": ORG_LAYOUT_MIGRATION_ID,
            "error": str(exc),
            "rollback_snapshot": str(snapshot_root),
        }
