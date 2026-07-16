from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from local_kb.common import utc_now_iso
from local_kb.i18n import DEFAULT_LANGUAGE, ZH_CN, normalize_language


UPDATE_STATE_SCHEMA_VERSION = 1
UPDATE_STATE_FILENAME = "khaos_brain_update_state.json"
UPDATE_STATUS_CURRENT = "current"
UPDATE_STATUS_AVAILABLE = "available"
UPDATE_STATUS_PREPARED = "prepared"
UPDATE_STATUS_UPGRADING = "upgrading"
UPDATE_STATUS_FAILED = "failed"
UPDATE_STATUSES = {
    UPDATE_STATUS_CURRENT,
    UPDATE_STATUS_AVAILABLE,
    UPDATE_STATUS_PREPARED,
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
        "update_available",
        "user_requested",
        "last_checked_at",
        "updated_at",
        "error",
    }
)
UPDATE_STATE_OPTIONAL_FIELDS = frozenset({"started_at", "completed_at"})
UPDATE_STATE_ALLOWED_FIELDS = UPDATE_STATE_REQUIRED_FIELDS | UPDATE_STATE_OPTIONAL_FIELDS

# These are the only gate outcomes that mean the scheduled update checked the
# current state and legitimately had no update work to perform.  Operational
# contention and failed/upgrading states remain unfinished so a later run must
# resolve them instead of reporting a successful no-op.
LEGAL_SYSTEM_UPDATE_NOOP_REASONS = frozenset(
    {
        "no-update",
        "waiting-for-user",
        "ui-running",
    }
)

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
        status = UPDATE_STATUS_CURRENT
    update_available = bool(payload.get("update_available"))
    user_requested = bool(payload.get("user_requested"))
    if status == UPDATE_STATUS_AVAILABLE:
        update_available = True
    if status == UPDATE_STATUS_PREPARED:
        update_available = True
        user_requested = True
    if status == UPDATE_STATUS_CURRENT:
        user_requested = False
    now_current_version = current_version(repo_root)
    latest_version = str(payload.get("latest_version") or "").strip()
    if not latest_version:
        latest_version = now_current_version
    state = {
        "schema_version": UPDATE_STATE_SCHEMA_VERSION,
        "status": status,
        "current_version": now_current_version,
        "latest_version": latest_version,
        "current_revision": str(payload.get("current_revision") or "").strip(),
        "latest_revision": str(payload.get("latest_revision") or "").strip(),
        "update_available": update_available,
        "user_requested": user_requested,
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
        return _normalize_state(repo_root, {"status": UPDATE_STATUS_FAILED, "error": "Update state could not be read."})
    if not isinstance(payload, dict):
        return _normalize_state(
            repo_root,
            {"status": UPDATE_STATUS_FAILED, "error": "Update state must be a current mapping."},
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
    if issues:
        return _normalize_state(
            repo_root,
            {"status": UPDATE_STATUS_FAILED, "error": "Update state is not current: " + "; ".join(issues)},
        )
    return _normalize_state(repo_root, payload)


def save_update_state(repo_root: Path, state: dict[str, Any]) -> Path:
    payload = _normalize_state(repo_root, state)
    payload["updated_at"] = utc_now_iso()
    path = update_state_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def canonicalize_obsolete_update_state(
    repo_root: Path,
    *,
    install_receipt: dict[str, Any],
) -> dict[str, Any]:
    """Settle one exact retired failure only inside a committed upgrade.

    Daily update execution must never call this function. An unrelated failure
    remains a visible failure and is not reinterpreted.
    """
    path = update_state_path(repo_root)
    if not path.exists():
        return {
            "ok": True,
            "status": "no_delta",
            "retired_state_found": False,
            "retired_schema_found": False,
            "residual_retired_state_count": 0,
        }
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Obsolete update state is unreadable and cannot be migrated: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("Obsolete update state is not a mapping and cannot be migrated")
    schema = raw.get("schema_version")
    retired_schema_found = schema is None
    if schema not in (None, UPDATE_STATE_SCHEMA_VERSION):
        raise RuntimeError(f"Unknown update state schema cannot be migrated directly: {schema}")
    if retired_schema_found:
        unknown = sorted(set(raw) - (UPDATE_STATE_ALLOWED_FIELDS - {"schema_version"}))
        if unknown:
            raise RuntimeError("Unknown retired update state fields: " + ", ".join(unknown))
        state = _normalize_state(repo_root, raw)
    else:
        state = load_update_state(repo_root)
        if str(state.get("error") or "").startswith("Update state is not current:"):
            raise RuntimeError(str(state["error"]))
    retired_error = "SkillGuard installation identity is not current"
    matches_retired_state = bool(
        str(state.get("status") or "") == UPDATE_STATUS_FAILED
        and str(state.get("error") or "") == retired_error
    )
    if not matches_retired_state and not retired_schema_found:
        return {
            "ok": True,
            "status": "no_delta",
            "retired_state_found": False,
            "retired_schema_found": False,
            "residual_retired_state_count": 0,
        }

    if not (
        str(install_receipt.get("status") or "") == "committed"
        and str(install_receipt.get("receipt_hash") or "")
    ):
        raise RuntimeError("A committed current installation receipt is required to settle obsolete update state")

    next_state = dict(state)
    if matches_retired_state:
        next_state["status"] = UPDATE_STATUS_CURRENT
        next_state["error"] = ""
    save_update_state(repo_root, next_state)
    current = load_update_state(repo_root)
    residual = int(
        str(current.get("status") or "") == UPDATE_STATUS_FAILED
        and str(current.get("error") or "") == retired_error
    )
    if residual:
        raise RuntimeError("Obsolete update identity failure remains after upgrade settlement")
    return {
        "ok": True,
        "status": "committed",
        "retired_state_found": matches_retired_state,
        "retired_schema_found": retired_schema_found,
        "residual_retired_state_count": 0,
        "install_receipt_hash": str(install_receipt["receipt_hash"]),
    }


def set_update_request(repo_root: Path, requested: bool) -> dict[str, Any]:
    state = load_update_state(repo_root)
    if state["status"] == UPDATE_STATUS_UPGRADING:
        return state
    state["user_requested"] = bool(requested and state.get("update_available"))
    if state["update_available"]:
        state["status"] = UPDATE_STATUS_PREPARED if state["user_requested"] else UPDATE_STATUS_AVAILABLE
    else:
        state["status"] = UPDATE_STATUS_CURRENT
    state["error"] = ""
    save_update_state(repo_root, state)
    return load_update_state(repo_root)


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
    upstream = _git_stdout(repo_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if upstream:
        return upstream
    branch = _git_stdout(repo_root, ["branch", "--show-current"])
    return f"origin/{branch or 'main'}"


def _remote_name(upstream_ref: str) -> str:
    if "/" in upstream_ref:
        return upstream_ref.split("/", 1)[0] or "origin"
    return "origin"


def check_remote_update(repo_root: Path, *, fetch: bool = True) -> dict[str, Any]:
    repo_root = Path(repo_root)
    state = load_update_state(repo_root)
    if state["status"] == UPDATE_STATUS_UPGRADING:
        return state
    errors: list[str] = []
    upstream = _upstream_ref(repo_root)
    if fetch:
        fetch_result = _run_git(repo_root, ["fetch", "--tags", "--prune", _remote_name(upstream)], timeout=90)
        if fetch_result.returncode != 0:
            errors.append((fetch_result.stderr or fetch_result.stdout or "git fetch failed").strip())
    local_revision = _git_stdout(repo_root, ["rev-parse", "HEAD"])
    latest_revision = _git_stdout(repo_root, ["rev-parse", upstream])
    latest_version = _git_stdout(repo_root, ["show", f"{upstream}:VERSION"]) or state.get("latest_version") or current_version(repo_root)
    remote_check_ok = not errors and bool(local_revision) and bool(latest_revision)
    if not remote_check_ok and not errors:
        errors.append("remote update revisions could not be resolved")
    update_available = bool(local_revision and latest_revision and local_revision != latest_revision)
    same_failed_target = (
        state["status"] == UPDATE_STATUS_FAILED
        and update_available
        and latest_revision
        and latest_revision == str(state.get("latest_revision") or "").strip()
    )
    failed_target_already_fast_forwarded = bool(
        state["status"] == UPDATE_STATUS_FAILED
        and local_revision
        and local_revision == str(state.get("latest_revision") or "").strip()
    )
    prepared_target_changed = bool(
        state["status"] == UPDATE_STATUS_PREPARED
        and state.get("user_requested")
        and str(state.get("latest_revision") or "").strip()
        and latest_revision
        and latest_revision != str(state.get("latest_revision") or "").strip()
    )
    if update_available:
        status = UPDATE_STATUS_FAILED if same_failed_target else (
            UPDATE_STATUS_AVAILABLE if state["status"] == UPDATE_STATUS_FAILED or prepared_target_changed else (
                UPDATE_STATUS_PREPARED if state.get("user_requested") else UPDATE_STATUS_AVAILABLE
            )
        )
    elif failed_target_already_fast_forwarded:
        status = UPDATE_STATUS_FAILED
    else:
        status = UPDATE_STATUS_CURRENT
    user_requested = bool(update_available and state.get("user_requested") and not prepared_target_changed)
    if state["status"] == UPDATE_STATUS_FAILED:
        user_requested = False
    error = "; ".join(error for error in errors if error)
    if (same_failed_target or failed_target_already_fast_forwarded) and not error:
        error = str(state.get("error") or "").strip()
    next_state = {
        **state,
        "status": status,
        "current_version": current_version(repo_root),
        "latest_version": latest_version.strip(),
        "current_revision": local_revision,
        "latest_revision": latest_revision,
        "update_available": update_available,
        "user_requested": user_requested,
        "last_checked_at": utc_now_iso(),
        "error": error,
    }
    save_update_state(repo_root, next_state)
    return {
        **load_update_state(repo_root),
        "remote_check_ok": remote_check_ok,
        "remote_check_errors": errors,
        "prepared_target_changed": prepared_target_changed,
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


def system_update_check(
    repo_root: Path,
    *,
    check_remote: bool = True,
    ui_processes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state = check_remote_update(repo_root) if check_remote else load_update_state(repo_root)
    running_processes = detect_khaos_brain_ui_processes() if ui_processes is None else [
        item for item in ui_processes if is_khaos_brain_ui_process(item)
    ]
    ui_running = bool(running_processes)
    apply_ready = False
    reason = "no-update"
    if check_remote and state.get("remote_check_ok") is not True:
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
    if state["status"] == UPDATE_STATUS_UPGRADING:
        reason = "already-upgrading"
    elif state["status"] == UPDATE_STATUS_FAILED:
        reason = "failed-awaiting-user"
        if state.get("user_requested"):
            state["user_requested"] = False
            save_update_state(repo_root, state)
            state = load_update_state(repo_root)
    elif not state.get("update_available"):
        reason = "no-update"
    elif not state.get("user_requested"):
        reason = "waiting-for-user"
    elif ui_running:
        reason = "ui-running"
    else:
        reason = "prepared-and-ui-closed"
        apply_ready = True
        state = mark_update_status(repo_root, UPDATE_STATUS_UPGRADING, error="")
    return {
        "ok": True,
        "apply_ready": apply_ready,
        "reason": reason,
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
        state["user_requested"] = True
    elif normalized_status == UPDATE_STATUS_CURRENT:
        state["completed_at"] = utc_now_iso()
        state["update_available"] = False
        state["user_requested"] = False
        state["current_version"] = current_version(repo_root)
        state["latest_version"] = state["current_version"]
    elif normalized_status == UPDATE_STATUS_FAILED:
        state["completed_at"] = utc_now_iso()
        state["user_requested"] = False
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
    status = str(state.get("status") or UPDATE_STATUS_CURRENT)
    latest = _version_label(str(state.get("latest_version") or state.get("current_version") or ""))
    current = _version_label(str(state.get("current_version") or ""))
    if status == UPDATE_STATUS_UPGRADING:
        return "正在升级" if normalized == ZH_CN else "Updating"
    if status == UPDATE_STATUS_FAILED:
        return "升级失败" if normalized == ZH_CN else "Update failed"
    if status == UPDATE_STATUS_PREPARED:
        return f"准备升级 {latest}".strip() if normalized == ZH_CN else f"Ready {latest}".strip()
    if status == UPDATE_STATUS_AVAILABLE:
        return f"可升级 {latest}".strip() if normalized == ZH_CN else f"Update {latest}".strip()
    return current


def update_badge_clickable(state: dict[str, Any]) -> bool:
    status = str(state.get("status") or "")
    return status in {UPDATE_STATUS_AVAILABLE, UPDATE_STATUS_PREPARED} or (
        status == UPDATE_STATUS_FAILED and bool(state.get("update_available"))
    )
