from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from local_kb.common import utc_now_iso
from local_kb.i18n import DEFAULT_LANGUAGE, ZH_CN, normalize_language


UPDATE_STATE_SCHEMA_VERSION = 2
UPDATE_STATE_FILENAME = "khaos_brain_update_state.json"
UPDATE_STATUS_UNAVAILABLE = "unavailable"
UPDATE_STATUS_CURRENT = "current"
UPDATE_STATUS_AVAILABLE = "available"
UPDATE_STATUS_LOCAL_AHEAD = "local_ahead"
UPDATE_STATUS_DIVERGED = "diverged"
UPDATE_STATUS_UPGRADING = "upgrading"
UPDATE_STATUS_FAILED = "failed"
UPDATE_STATUSES = {
    UPDATE_STATUS_UNAVAILABLE,
    UPDATE_STATUS_CURRENT,
    UPDATE_STATUS_AVAILABLE,
    UPDATE_STATUS_LOCAL_AHEAD,
    UPDATE_STATUS_DIVERGED,
    UPDATE_STATUS_UPGRADING,
    UPDATE_STATUS_FAILED,
}
UPDATE_STATE_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "current_version",
        "latest_version",
        "current_revision",
        "latest_revision",
        "upstream_ref",
        "ahead_count",
        "behind_count",
        "update_available",
        "last_checked_at",
        "updated_at",
        "error",
    }
)
UPDATE_STATE_OPTIONAL_FIELDS = frozenset({"started_at", "completed_at"})
UPDATE_STATE_ALLOWED_FIELDS = UPDATE_STATE_REQUIRED_FIELDS | UPDATE_STATE_OPTIONAL_FIELDS

LEGACY_UPDATE_STATE_SCHEMA_VERSION = 1
LEGACY_UPDATE_STATUSES = frozenset({"current", "available", "prepared", "upgrading", "failed"})
LEGACY_UPDATE_STATE_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "current_version",
        "latest_version",
        "current_revision",
        "latest_revision",
        "update_available",
        "user_requested",
        "last_checked_at",
        "updated_at",
        "error",
    }
)
LEGACY_UPDATE_STATE_OPTIONAL_FIELDS = frozenset({"started_at", "completed_at"})
LEGACY_UPDATE_STATE_ALLOWED_FIELDS = LEGACY_UPDATE_STATE_REQUIRED_FIELDS | LEGACY_UPDATE_STATE_OPTIONAL_FIELDS

# An explicit manual request with no available update is the only successful
# terminal no-op. UI-open, topology, authorization, and operational blockers
# remain unfinished and visible to the requesting AI/user.
LEGAL_MANUAL_UPDATE_NOOP_REASONS = frozenset({"no-update"})

UI_PROCESS_NAME_MARKERS = {
    "khaosbrain.exe",
    "khaos brain.exe",
}
UI_COMMAND_MARKERS = (
    "scripts\\kb_desktop.py",
    "scripts/kb_desktop.py",
    "open_khaos_brain_ui.py",
    "local_kb.desktop_app",
)
NON_UI_COMMAND_MARKERS = (
    "khaos_brain_update.py",
    "run_khaos_brain_manual_update.py",
    "install_codex_kb.py",
)


def update_state_path(repo_root: Path) -> Path:
    return Path(repo_root) / ".local" / UPDATE_STATE_FILENAME


def current_version(repo_root: Path) -> str:
    path = Path(repo_root) / "VERSION"
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _version_label(version: str) -> str:
    text = str(version or "").strip()
    if not text:
        return ""
    return text if text.lower().startswith("v") else f"v{text}"


def _normalize_state(repo_root: Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(payload or {})
    status = str(payload.get("status") or "").strip().lower()
    if status not in UPDATE_STATUSES:
        if payload:
            raise ValueError(f"Update state status is not current: {status or '<missing>'}")
        status = UPDATE_STATUS_UNAVAILABLE
    update_available = status == UPDATE_STATUS_AVAILABLE
    now_current_version = current_version(repo_root)
    latest_version = str(payload.get("latest_version") or "").strip()
    if not latest_version:
        latest_version = now_current_version
    try:
        ahead_count = max(0, int(payload.get("ahead_count") or 0))
        behind_count = max(0, int(payload.get("behind_count") or 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("Update topology counts must be non-negative integers") from exc
    state = {
        "schema_version": UPDATE_STATE_SCHEMA_VERSION,
        "status": status,
        "current_version": now_current_version,
        "latest_version": latest_version,
        "current_revision": str(payload.get("current_revision") or "").strip(),
        "latest_revision": str(payload.get("latest_revision") or "").strip(),
        "upstream_ref": str(payload.get("upstream_ref") or "").strip(),
        "ahead_count": ahead_count,
        "behind_count": behind_count,
        "update_available": update_available,
        "last_checked_at": str(payload.get("last_checked_at") or "").strip(),
        "updated_at": str(payload.get("updated_at") or "").strip(),
        "error": str(payload.get("error") or "").strip(),
    }
    if payload.get("started_at"):
        state["started_at"] = str(payload.get("started_at") or "").strip()
    if payload.get("completed_at"):
        state["completed_at"] = str(payload.get("completed_at") or "").strip()
    return state


def load_update_state(repo_root: Path) -> dict[str, Any]:
    path = update_state_path(repo_root)
    if not path.exists():
        return _normalize_state(repo_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _normalize_state(repo_root, {"status": UPDATE_STATUS_UNAVAILABLE, "error": "Update state could not be read."})
    if not isinstance(payload, dict):
        return _normalize_state(
            repo_root,
            {"status": UPDATE_STATUS_UNAVAILABLE, "error": "Update state must be a current mapping."},
        )
    issues: list[str] = []
    if payload.get("schema_version") != UPDATE_STATE_SCHEMA_VERSION:
        issues.append("update state schema is not current")
    missing = sorted(UPDATE_STATE_REQUIRED_FIELDS - set(payload))
    extra = sorted(set(payload) - UPDATE_STATE_ALLOWED_FIELDS)
    if missing:
        issues.append("missing fields: " + ", ".join(missing))
    if extra:
        issues.append("unknown fields: " + ", ".join(extra))
    if str(payload.get("status") or "").strip().lower() not in UPDATE_STATUSES:
        issues.append("status is not current")
    for field in ("ahead_count", "behind_count"):
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            issues.append(f"{field} must be a non-negative integer")
    status = str(payload.get("status") or "").strip().lower()
    if bool(payload.get("update_available")) != (status == UPDATE_STATUS_AVAILABLE):
        issues.append("update_available does not match status")
    if issues:
        return _normalize_state(
            repo_root,
            {"status": UPDATE_STATUS_UNAVAILABLE, "error": "Update state is not current: " + "; ".join(issues)},
        )
    try:
        return _normalize_state(repo_root, payload)
    except ValueError as exc:
        return _normalize_state(
            repo_root,
            {"status": UPDATE_STATUS_UNAVAILABLE, "error": f"Update state is not current: {exc}"},
        )


def save_update_state(repo_root: Path, state: dict[str, Any]) -> Path:
    payload = _normalize_state(repo_root, state)
    payload["updated_at"] = utc_now_iso()
    path = update_state_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def migrate_obsolete_update_state(
    repo_root: Path,
    *,
    install_receipt: dict[str, Any],
) -> dict[str, Any]:
    """Directly replace an exact former update-state document during upgrade."""
    path = update_state_path(repo_root)
    if not path.exists():
        return {
            "ok": True,
            "status": "no_delta",
            "legacy_state_found": False,
            "legacy_schema_found": False,
            "dropped_user_requested": False,
            "residual_retired_state_count": 0,
        }
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Obsolete update state is unreadable and cannot be migrated: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("Obsolete update state is not a mapping and cannot be migrated")
    schema = raw.get("schema_version")
    if schema == UPDATE_STATE_SCHEMA_VERSION:
        state = load_update_state(repo_root)
        if str(state.get("error") or "").startswith("Update state is not current:"):
            raise RuntimeError(str(state["error"]))
        return {
            "ok": True,
            "status": "no_delta",
            "legacy_state_found": False,
            "legacy_schema_found": False,
            "dropped_user_requested": False,
            "residual_retired_state_count": 0,
        }
    legacy_schema_found = schema in (None, LEGACY_UPDATE_STATE_SCHEMA_VERSION)
    if not legacy_schema_found:
        raise RuntimeError(f"Unknown update state schema cannot be migrated directly: {schema}")
    required_fields = (
        LEGACY_UPDATE_STATE_REQUIRED_FIELDS - {"schema_version"}
        if schema is None
        else LEGACY_UPDATE_STATE_REQUIRED_FIELDS
    )
    allowed_fields = (
        LEGACY_UPDATE_STATE_ALLOWED_FIELDS - {"schema_version"}
        if schema is None
        else LEGACY_UPDATE_STATE_ALLOWED_FIELDS
    )
    missing = sorted(required_fields - set(raw))
    unknown = sorted(set(raw) - allowed_fields)
    legacy_status = str(raw.get("status") or "").strip().lower()
    if missing or unknown or legacy_status not in LEGACY_UPDATE_STATUSES:
        details: list[str] = []
        if missing:
            details.append("missing fields: " + ", ".join(missing))
        if unknown:
            details.append("unknown fields: " + ", ".join(unknown))
        if legacy_status not in LEGACY_UPDATE_STATUSES:
            details.append("status is not a known former value")
        raise RuntimeError("Former update state is not an exact migratable document: " + "; ".join(details))
    retired_error = "SkillGuard installation identity is not current"
    matches_retired_state = bool(
        legacy_status == UPDATE_STATUS_FAILED
        and str(raw.get("error") or "") == retired_error
    )
    if not (
        str(install_receipt.get("status") or "") == "committed"
        and str(install_receipt.get("receipt_hash") or "")
    ):
        raise RuntimeError("A committed current installation receipt is required to settle obsolete update state")

    next_status = UPDATE_STATUS_AVAILABLE if legacy_status == "prepared" else legacy_status
    if matches_retired_state:
        next_status = UPDATE_STATUS_UNAVAILABLE
    next_state = {
        "status": next_status,
        "current_version": str(raw.get("current_version") or ""),
        "latest_version": str(raw.get("latest_version") or ""),
        "current_revision": str(raw.get("current_revision") or ""),
        "latest_revision": str(raw.get("latest_revision") or ""),
        "upstream_ref": "",
        "ahead_count": 0,
        "behind_count": 1 if next_status == UPDATE_STATUS_AVAILABLE else 0,
        "update_available": next_status == UPDATE_STATUS_AVAILABLE,
        "last_checked_at": str(raw.get("last_checked_at") or ""),
        "updated_at": str(raw.get("updated_at") or ""),
        "error": "" if matches_retired_state else str(raw.get("error") or ""),
    }
    for field in ("started_at", "completed_at"):
        if raw.get(field):
            next_state[field] = str(raw[field])
    save_update_state(repo_root, next_state)
    current = load_update_state(repo_root)
    written = json.loads(path.read_text(encoding="utf-8"))
    residual = int(
        "user_requested" in written
        or str(written.get("status") or "") == "prepared"
        or int(written.get("schema_version") or 0) != UPDATE_STATE_SCHEMA_VERSION
    )
    if residual:
        raise RuntimeError("Former update authorization remains after direct migration")
    return {
        "ok": True,
        "status": "committed",
        "legacy_state_found": True,
        "legacy_schema_found": True,
        "legacy_schema_version": schema,
        "legacy_status": legacy_status,
        "current_status": current.get("status"),
        "dropped_user_requested": "user_requested" in raw,
        "retired_identity_failure_settled": matches_retired_state,
        "residual_retired_state_count": 0,
        "install_receipt_hash": str(install_receipt["receipt_hash"]),
    }


def _git_executable() -> str:
    return shutil.which("git") or shutil.which("git.cmd") or "git"


def _run_git(repo_root: Path, args: list[str], *, timeout: int = 45) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [_git_executable(), *args],
            cwd=str(repo_root),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(args=[_git_executable(), *args], returncode=127, stdout="", stderr=str(exc))


def _git_stdout(repo_root: Path, args: list[str]) -> str:
    result = _run_git(repo_root, args)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _upstream_ref(repo_root: Path) -> str:
    return _git_stdout(repo_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])


def _remote_name(upstream_ref: str) -> str:
    if "/" in upstream_ref:
        return upstream_ref.split("/", 1)[0] or "origin"
    return ""


def _topology_counts(repo_root: Path, upstream_ref: str) -> tuple[int, int] | None:
    value = _git_stdout(repo_root, ["rev-list", "--left-right", "--count", f"HEAD...{upstream_ref}"])
    parts = value.replace("\t", " ").split()
    if len(parts) != 2:
        return None
    try:
        ahead, behind = (int(parts[0]), int(parts[1]))
    except ValueError:
        return None
    if ahead < 0 or behind < 0:
        return None
    return ahead, behind


def check_remote_update(repo_root: Path, *, fetch: bool = True) -> dict[str, Any]:
    repo_root = Path(repo_root)
    state = load_update_state(repo_root)
    if state["status"] == UPDATE_STATUS_UPGRADING:
        return {**state, "remote_check_ok": False, "remote_check_errors": ["update already in progress"]}
    errors: list[str] = []
    upstream = _upstream_ref(repo_root)
    remote_name = _remote_name(upstream)
    if not upstream or not remote_name:
        errors.append("No configured Git upstream is available.")
    if fetch and not errors:
        fetch_result = _run_git(repo_root, ["fetch", "--tags", "--prune", remote_name], timeout=90)
        if fetch_result.returncode != 0:
            errors.append((fetch_result.stderr or fetch_result.stdout or "git fetch failed").strip())
    local_revision = _git_stdout(repo_root, ["rev-parse", "HEAD"])
    latest_revision = _git_stdout(repo_root, ["rev-parse", upstream]) if upstream else ""
    topology = _topology_counts(repo_root, upstream) if upstream and not errors else None
    latest_version = (
        _git_stdout(repo_root, ["show", f"{upstream}:VERSION"])
        if upstream and latest_revision
        else ""
    ) or state.get("latest_version") or current_version(repo_root)
    remote_check_ok = not errors and bool(local_revision) and bool(latest_revision) and topology is not None
    if not remote_check_ok and not errors:
        errors.append("Configured upstream revisions could not be compared.")
    ahead_count, behind_count = topology if topology is not None else (0, 0)
    if not remote_check_ok:
        status = UPDATE_STATUS_UNAVAILABLE
    elif ahead_count == 0 and behind_count == 0:
        status = UPDATE_STATUS_CURRENT
    elif ahead_count == 0 and behind_count > 0:
        status = UPDATE_STATUS_AVAILABLE
    elif ahead_count > 0 and behind_count == 0:
        status = UPDATE_STATUS_LOCAL_AHEAD
    else:
        status = UPDATE_STATUS_DIVERGED
    update_available = status == UPDATE_STATUS_AVAILABLE
    error = "; ".join(error for error in errors if error)
    next_state = {
        **state,
        "status": status,
        "current_version": current_version(repo_root),
        "latest_version": latest_version.strip(),
        "current_revision": local_revision,
        "latest_revision": latest_revision,
        "upstream_ref": upstream,
        "ahead_count": ahead_count,
        "behind_count": behind_count,
        "update_available": update_available,
        "last_checked_at": utc_now_iso(),
        "error": error,
    }
    save_update_state(repo_root, next_state)
    return {
        **load_update_state(repo_root),
        "remote_check_ok": remote_check_ok,
        "remote_check_errors": errors,
    }


def is_khaos_brain_ui_process(process: dict[str, Any]) -> bool:
    name = str(process.get("name") or process.get("Name") or "").strip().lower()
    command_line = str(process.get("command_line") or process.get("CommandLine") or "").strip().lower()
    if any(marker in command_line for marker in NON_UI_COMMAND_MARKERS):
        return False
    if name in UI_PROCESS_NAME_MARKERS:
        return True
    return any(marker.lower() in command_line for marker in UI_COMMAND_MARKERS)


def detect_khaos_brain_ui_processes() -> list[dict[str, Any]]:
    if sys.platform != "win32":
        return []
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress",
    ]
    try:
        result = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=12,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    rows = payload if isinstance(payload, list) else [payload]
    processes = [item for item in rows if isinstance(item, dict)]
    return [item for item in processes if is_khaos_brain_ui_process(item)]


def manual_update_check(
    repo_root: Path,
    *,
    explicit_user_request: bool,
    check_remote: bool = True,
    ui_processes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not explicit_user_request:
        state = load_update_state(repo_root)
        return {
            "ok": False,
            "apply_ready": False,
            "reason": "explicit-user-request-required",
            "error": "Manual update requires an explicit user request in the current invocation.",
            "ui_running": False,
            "ui_process_count": 0,
            "state_path": str(update_state_path(repo_root)),
            "state": state,
            "skill": "",
        }
    state = check_remote_update(repo_root) if check_remote else load_update_state(repo_root)
    running_processes = detect_khaos_brain_ui_processes() if ui_processes is None else [
        item for item in ui_processes if is_khaos_brain_ui_process(item)
    ]
    ui_running = bool(running_processes)
    apply_ready = False
    reason = "no-update"
    if state["status"] == UPDATE_STATUS_UPGRADING:
        reason = "already-upgrading"
    elif check_remote and state.get("remote_check_ok") is not True:
        return {
            "ok": False,
            "apply_ready": False,
            "reason": "remote-check-failed",
            "error": "; ".join(str(item) for item in state.get("remote_check_errors") or []),
            "ui_running": ui_running,
            "ui_process_count": len(running_processes),
            "state_path": str(update_state_path(repo_root)),
            "state": state,
            "skill": "",
        }
    elif state["status"] == UPDATE_STATUS_CURRENT:
        reason = "no-update"
    elif state["status"] in {UPDATE_STATUS_LOCAL_AHEAD, UPDATE_STATUS_DIVERGED}:
        reason = "non-fast-forward-topology"
    elif state["status"] == UPDATE_STATUS_UNAVAILABLE:
        reason = "remote-check-failed"
    elif state["status"] == UPDATE_STATUS_FAILED:
        reason = "previous-update-failed"
    elif ui_running:
        reason = "ui-running"
    elif state["status"] != UPDATE_STATUS_AVAILABLE or not state.get("update_available"):
        reason = "invalid-update-state"
    else:
        reason = "explicit-request-and-ui-closed"
        apply_ready = True
        state = mark_update_status(repo_root, UPDATE_STATUS_UPGRADING, error="")
    ok = reason == "no-update" or apply_ready
    return {
        "ok": ok,
        "apply_ready": apply_ready,
        "reason": reason,
        "error": "" if ok else f"Manual update is blocked: {reason}",
        "ui_running": ui_running,
        "ui_process_count": len(running_processes),
        "state_path": str(update_state_path(repo_root)),
        "state": state,
        "skill": "$khaos-brain-update" if apply_ready else "",
    }


def mark_update_status(repo_root: Path, status: str, *, error: str = "") -> dict[str, Any]:
    state = load_update_state(repo_root)
    normalized_status = status if status in UPDATE_STATUSES else UPDATE_STATUS_FAILED
    state["status"] = normalized_status
    state["error"] = error
    if normalized_status == UPDATE_STATUS_UPGRADING:
        state["started_at"] = utc_now_iso()
        state["update_available"] = False
    elif normalized_status == UPDATE_STATUS_CURRENT:
        state["completed_at"] = utc_now_iso()
        state["update_available"] = False
        state["ahead_count"] = 0
        state["behind_count"] = 0
        state["current_version"] = current_version(repo_root)
        state["latest_version"] = state["current_version"]
    elif normalized_status == UPDATE_STATUS_FAILED:
        state["completed_at"] = utc_now_iso()
        state["update_available"] = False
    save_update_state(repo_root, state)
    return load_update_state(repo_root)


def startup_block_message(repo_root: Path, *, language: str | None = None) -> str:
    state = load_update_state(repo_root)
    if state.get("status") != UPDATE_STATUS_UPGRADING:
        return ""
    selected_language = normalize_language(language or _saved_language(repo_root))
    if selected_language == ZH_CN:
        return "Khaos Brain 正在升级，现在无法打开。请稍后再试。"
    return "Khaos Brain is updating and cannot be opened right now. Please try again later."


def _saved_language(repo_root: Path) -> str:
    from local_kb.settings import load_desktop_settings

    return str(load_desktop_settings(Path(repo_root)).get("language") or DEFAULT_LANGUAGE)


def update_badge_label(state: dict[str, Any], language: str = DEFAULT_LANGUAGE) -> str:
    normalized = normalize_language(language)
    status = str(state.get("status") or UPDATE_STATUS_UNAVAILABLE)
    latest = _version_label(str(state.get("latest_version") or state.get("current_version") or ""))
    current = _version_label(str(state.get("current_version") or ""))
    upstream = str(state.get("upstream_ref") or "").strip()
    branch = upstream.split("/", 1)[1] if "/" in upstream else upstream
    branch = branch or ("上游" if normalized == ZH_CN else "Upstream")
    if status == UPDATE_STATUS_UPGRADING:
        return "正在手动更新" if normalized == ZH_CN else "Manual update running"
    if status == UPDATE_STATUS_FAILED:
        return "手动更新失败" if normalized == ZH_CN else "Manual update failed"
    if status == UPDATE_STATUS_AVAILABLE:
        return f"{branch} · 有新版本 {latest}".strip() if normalized == ZH_CN else f"{branch} · New {latest}".strip()
    if status == UPDATE_STATUS_CURRENT:
        return f"{branch} · 已是最新 {current}".strip() if normalized == ZH_CN else f"{branch} · Current {current}".strip()
    if status == UPDATE_STATUS_LOCAL_AHEAD:
        return f"{branch} · 本地领先" if normalized == ZH_CN else f"{branch} · Local ahead"
    if status == UPDATE_STATUS_DIVERGED:
        return f"{branch} · 分支有分歧" if normalized == ZH_CN else f"{branch} · Diverged"
    return f"{branch} · 无法检查更新" if normalized == ZH_CN else f"{branch} · Status unavailable"
