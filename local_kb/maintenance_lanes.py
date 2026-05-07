from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from local_kb.common import utc_now_iso


LANE_STATUS_DIR = Path("kb") / "history" / "lane-status"
LANE_LOCK_DIR = LANE_STATUS_DIR / "locks"
CORE_MAINTENANCE_LANES = ("kb-sleep", "kb-dream", "kb-architect")
ORGANIZATION_MAINTENANCE_LANES = ("kb-org-contribute", "kb-org-maintenance")
MAINTENANCE_LOCK_GROUPS: dict[str, tuple[str, ...]] = {
    "local-maintenance": CORE_MAINTENANCE_LANES,
    "organization-maintenance": ORGANIZATION_MAINTENANCE_LANES,
}
DEFAULT_LOCK_POLL_SECONDS = 300
DEFAULT_STALE_AFTER_SECONDS = 12 * 60 * 60


def _safe_name(value: str) -> str:
    return value.strip().lower().replace("/", "-").replace("\\", "-")


def lane_status_path(repo_root: Path, lane: str) -> Path:
    safe_lane = _safe_name(lane)
    return repo_root / LANE_STATUS_DIR / f"{safe_lane}.json"


def lane_lock_group(lane: str) -> str:
    for group, lanes in MAINTENANCE_LOCK_GROUPS.items():
        if lane in lanes:
            return group
    return _safe_name(lane)


def lane_lock_dir(repo_root: Path, group: str) -> Path:
    return repo_root / LANE_LOCK_DIR / f"{_safe_name(group)}.lock"


def lane_lock_path(repo_root: Path, group: str) -> Path:
    return lane_lock_dir(repo_root, group) / "lock.json"


def read_lane_status(repo_root: Path, lane: str) -> dict[str, Any]:
    path = lane_status_path(repo_root, lane)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"lane": lane, "status": "unknown", "path": str(path)}
    return payload if isinstance(payload, dict) else {}


def read_lane_lock(repo_root: Path, group: str) -> dict[str, Any]:
    path = lane_lock_path(repo_root, group)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"group": group, "status": "unknown", "path": str(path)}
    if not isinstance(payload, dict):
        return {}
    payload["path"] = str(path)
    return payload


def _lock_is_stale(payload: dict[str, Any], *, stale_after_seconds: int) -> bool:
    heartbeat = payload.get("heartbeat_epoch")
    try:
        heartbeat_epoch = float(heartbeat)
    except (TypeError, ValueError):
        return True
    return (time.time() - heartbeat_epoch) > stale_after_seconds


def _write_lane_lock(
    repo_root: Path,
    *,
    group: str,
    lane: str,
    run_id: str = "",
    note: str = "",
) -> dict[str, Any]:
    path = lane_lock_path(repo_root, group)
    payload = {
        "group": group,
        "lane": lane,
        "run_id": run_id,
        "note": note,
        "pid": os.getpid(),
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "heartbeat_epoch": time.time(),
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    payload["path"] = str(path)
    return payload


def heartbeat_lane_lock(
    repo_root: Path,
    lane: str,
    *,
    run_id: str = "",
    group: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    resolved_group = group or lane_lock_group(lane)
    payload = read_lane_lock(repo_root, resolved_group)
    if not payload:
        return {"group": resolved_group, "lane": lane, "status": "missing"}
    if payload.get("lane") != lane:
        return {"group": resolved_group, "lane": lane, "status": "not-owner", "lock": payload}
    if run_id and payload.get("run_id") not in ("", run_id):
        return {"group": resolved_group, "lane": lane, "status": "not-owner", "lock": payload}
    payload["updated_at"] = utc_now_iso()
    payload["heartbeat_epoch"] = time.time()
    if note:
        payload["note"] = note
    path = Path(str(payload["path"]))
    with path.open("w", encoding="utf-8") as handle:
        json.dump({key: value for key, value in payload.items() if key != "path"}, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    payload["status"] = "heartbeat"
    return payload


def acquire_lane_lock(
    repo_root: Path,
    lane: str,
    *,
    run_id: str = "",
    group: str | None = None,
    poll_seconds: int = DEFAULT_LOCK_POLL_SECONDS,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    wait: bool = True,
    note: str = "",
) -> dict[str, Any]:
    resolved_group = group or lane_lock_group(lane)
    lock_dir = lane_lock_dir(repo_root, resolved_group)
    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    waits = 0
    while True:
        try:
            lock_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            existing = read_lane_lock(repo_root, resolved_group)
            if existing.get("lane") == lane and (not run_id or existing.get("run_id") in ("", run_id)):
                heartbeat = heartbeat_lane_lock(repo_root, lane, run_id=run_id, group=resolved_group, note=note)
                heartbeat["acquired"] = True
                heartbeat["reentrant"] = True
                heartbeat["wait_count"] = waits
                return heartbeat
            if not existing or _lock_is_stale(existing, stale_after_seconds=stale_after_seconds):
                shutil.rmtree(lock_dir, ignore_errors=True)
                continue
            blocked = {
                "group": resolved_group,
                "lane": lane,
                "run_id": run_id,
                "acquired": False,
                "blocked_by": existing,
                "wait_count": waits,
            }
            if not wait:
                return blocked
            waits += 1
            time.sleep(max(0, poll_seconds))
            continue
        payload = _write_lane_lock(repo_root, group=resolved_group, lane=lane, run_id=run_id, note=note)
        payload["acquired"] = True
        payload["wait_count"] = waits
        return payload


def release_lane_lock(
    repo_root: Path,
    lane: str,
    *,
    run_id: str = "",
    group: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    resolved_group = group or lane_lock_group(lane)
    lock_dir = lane_lock_dir(repo_root, resolved_group)
    payload = read_lane_lock(repo_root, resolved_group)
    if not payload:
        return {"group": resolved_group, "lane": lane, "released": False, "reason": "missing"}
    owns_lock = payload.get("lane") == lane and (not run_id or payload.get("run_id") in ("", run_id))
    if not owns_lock and not force:
        return {"group": resolved_group, "lane": lane, "released": False, "reason": "not-owner", "lock": payload}
    shutil.rmtree(lock_dir, ignore_errors=True)
    return {"group": resolved_group, "lane": lane, "run_id": run_id, "released": True, "lock": payload}


def write_lane_status(
    repo_root: Path,
    lane: str,
    status: str,
    *,
    run_id: str = "",
    note: str = "",
) -> dict[str, Any]:
    path = lane_status_path(repo_root, lane)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "lane": lane,
        "status": status,
        "run_id": run_id,
        "note": note,
        "updated_at": utc_now_iso(),
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    payload["path"] = str(path)
    return payload


def reconcile_stale_lane_statuses(
    repo_root: Path,
    *,
    lanes: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    reconciled: list[dict[str, Any]] = []
    active_lanes = lanes or tuple(lane for group_lanes in MAINTENANCE_LOCK_GROUPS.values() for lane in group_lanes)
    for lane in active_lanes:
        payload = read_lane_status(repo_root, lane)
        if str(payload.get("status", "") or "").lower() != "running":
            continue
        group = lane_lock_group(lane)
        lock = read_lane_lock(repo_root, group)
        if lock and lock.get("lane") == lane and not _lock_is_stale(lock, stale_after_seconds=DEFAULT_STALE_AFTER_SECONDS):
            continue
        reconciled.append(
            write_lane_status(
                repo_root,
                lane,
                "stale",
                run_id=str(payload.get("run_id", "") or ""),
                note="Reconciled running status without an active lane lock.",
            )
        )
    return reconciled


def lane_is_running(repo_root: Path, lane: str) -> bool:
    status = str(read_lane_status(repo_root, lane).get("status", "") or "").lower()
    return status == "running"


def build_lane_guard(
    repo_root: Path,
    lane: str,
    *,
    lanes: tuple[str, ...] = CORE_MAINTENANCE_LANES,
) -> dict[str, Any]:
    statuses: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []
    legacy_running_without_lock: list[str] = []
    reconcile_stale_lane_statuses(repo_root, lanes=lanes)
    group = lane_lock_group(lane)
    lock = read_lane_lock(repo_root, group)
    if lock and not _lock_is_stale(lock, stale_after_seconds=DEFAULT_STALE_AFTER_SECONDS):
        lock_lane = str(lock.get("lane", "") or "")
        if lock_lane and lock_lane != lane and lock_lane in lanes:
            blockers.append(lock_lane)
    for other_lane in lanes:
        if other_lane == lane:
            continue
        payload = read_lane_status(repo_root, other_lane)
        statuses[other_lane] = payload
        if str(payload.get("status", "") or "").lower() == "running" and other_lane not in blockers:
            legacy_running_without_lock.append(other_lane)
    return {
        "lane": lane,
        "blocked": bool(blockers),
        "blocking_lanes": blockers,
        "lock_group": group,
        "active_lock": lock,
        "legacy_running_without_lock": legacy_running_without_lock,
        "statuses": statuses,
    }
