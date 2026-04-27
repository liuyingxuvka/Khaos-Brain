from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from local_kb.config import resolve_repo_root as resolve_configured_repo_root
from local_kb.models import Entry

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: PyYAML. Install it with: pip install pyyaml"
    ) from exc


DEFAULT_SCOPES = ("public", "private", "candidates")
DEFAULT_ORGANIZATION_SCOPES = ("main",)
DEFAULT_ORGANIZATION_READ_STATUSES = ("trusted", "candidate")
ORGANIZATION_MAIN_STATUSES = ("trusted", "candidate", "deprecated", "rejected")


def local_source_scope(scope: str) -> str:
    if scope == "candidates":
        return "candidate"
    if scope in {"public", "private"}:
        return scope
    return "unknown"


def build_local_entry_source(repo_root: Path, scope: str, path: Path) -> dict[str, Any]:
    source_scope = local_source_scope(scope)
    return {
        "kind": "local",
        "source_id": "local",
        "scope": source_scope,
        "label": f"local/{source_scope}",
        "organization_id": "",
        "source_repo": "",
        "source_commit": "",
        "read_only": False,
        "editable": True,
        "contribution_eligible": source_scope in {"public", "candidate"},
        "path": os.path.relpath(path, repo_root),
    }


def organization_source_scope(scope: str, status: str = "") -> str:
    normalized_status = str(status or "").strip().lower()
    if normalized_status in {"trusted", "approved"}:
        return "trusted"
    if normalized_status in {"candidate", "deprecated", "rejected"}:
        return normalized_status
    if scope == "candidates":
        return "candidate"
    if scope == "trusted":
        return "trusted"
    if scope == "imports":
        return "candidate"
    return "unknown"


def build_organization_entry_source(
    org_root: Path,
    organization_id: str,
    scope: str,
    path: Path,
    *,
    source_repo: str = "",
    source_commit: str = "",
) -> dict[str, Any]:
    try:
        data = load_yaml_file(path)
    except Exception:
        data = {}
    source_scope = organization_source_scope(scope, str(data.get("status") or ""))
    return {
        "kind": "organization",
        "source_id": organization_id,
        "scope": source_scope,
        "label": f"org/{organization_id}/{source_scope}" if organization_id else f"org/{source_scope}",
        "organization_id": organization_id,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "read_only": True,
        "editable": False,
        "contribution_eligible": source_scope == "candidate",
        "path": os.path.relpath(path, org_root),
    }


def _organization_scope_targets(org_root: Path, scopes: Iterable[str]) -> list[tuple[str, Path]]:
    kb_root = Path(org_root) / "kb"
    targets: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for scope in tuple(scopes):
        if scope == "main":
            main = kb_root / "main"
            if main.exists():
                candidates = [("main", main)]
            else:
                candidates = [("trusted", kb_root / "trusted"), ("candidates", kb_root / "candidates")]
        else:
            candidates = [(scope, kb_root / scope)]
        for resolved_scope, target in candidates:
            normalized = target.resolve() if target.exists() else target
            if normalized in seen:
                continue
            seen.add(normalized)
            targets.append((resolved_scope, target))
    return targets


def resolve_repo_root(value: str | os.PathLike[str]) -> Path:
    return resolve_configured_repo_root(value)


def load_yaml_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def rejected_candidate_entry_ids(repo_root: Path) -> set[str]:
    path = history_events_path(repo_root)
    if not path.exists():
        return set()

    rejected_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            event_type = str(payload.get("event_type", "") or "").strip().lower()
            if event_type != "candidate-rejected":
                continue
            target = payload.get("target", {}) if isinstance(payload.get("target"), dict) else {}
            context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
            entry_id = str(target.get("entry_id") or context.get("entry_id") or "").strip()
            if entry_id:
                rejected_ids.add(entry_id)
    return rejected_ids


def load_entries(repo_root: Path, scopes: Iterable[str] = DEFAULT_SCOPES) -> list[Entry]:
    entries: list[Entry] = []
    kb_root = repo_root / "kb"
    active_scopes = tuple(scopes)
    rejected_candidates = rejected_candidate_entry_ids(repo_root) if "candidates" in active_scopes else set()
    for scope in active_scopes:
        target = kb_root / scope
        if not target.exists():
            continue
        for path in sorted(target.rglob("*.yaml")):
            data = load_yaml_file(path)
            entry_id = str(data.get("id", "") or "").strip()
            if scope == "candidates" and entry_id and entry_id in rejected_candidates:
                continue
            entries.append(Entry(path=path, data=data, source=build_local_entry_source(repo_root, scope, path)))
    return entries


def load_organization_entries(
    org_root: Path,
    organization_id: str,
    *,
    source_repo: str = "",
    source_commit: str = "",
    scopes: Iterable[str] = DEFAULT_ORGANIZATION_SCOPES,
    allowed_statuses: Iterable[str] | None = DEFAULT_ORGANIZATION_READ_STATUSES,
) -> list[Entry]:
    entries: list[Entry] = []
    status_filter = None if allowed_statuses is None else {str(item).strip().lower() for item in allowed_statuses}
    for scope, target in _organization_scope_targets(Path(org_root), scopes):
        if not target.exists():
            continue
        for path in sorted(target.rglob("*.yaml")):
            data = load_yaml_file(path)
            status = str(data.get("status") or "").strip().lower()
            if status_filter is not None and status not in status_filter:
                continue
            entries.append(
                Entry(
                    path=path,
                    data=data,
                    source=build_organization_entry_source(
                        Path(org_root),
                        organization_id,
                        scope,
                        path,
                        source_repo=source_repo,
                        source_commit=source_commit,
                    ),
                )
            )
    return entries


def write_yaml_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def history_events_path(repo_root: Path) -> Path:
    return repo_root / "kb" / "history" / "events.jsonl"


def append_timeline_event(repo_root: Path, payload: dict[str, Any]) -> Path:
    path = history_events_path(repo_root)
    append_jsonl(path, payload)
    return path


def candidate_dir(repo_root: Path) -> Path:
    path = repo_root / "kb" / "candidates"
    path.mkdir(parents=True, exist_ok=True)
    return path
