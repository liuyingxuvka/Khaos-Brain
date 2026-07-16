#!/usr/bin/env python3
"""Execute one fully automatic, explicitly prepared Chaos Brain update."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.cli_output import print_json  # noqa: E402
from local_kb.config import default_codex_home, resolve_repo_root  # noqa: E402
from local_kb.install import (  # noqa: E402
    capture_repo_automation_state_snapshot,
    pause_repo_automations,
)
from local_kb.maintenance_lanes import acquire_lane_lock, release_lane_lock  # noqa: E402
from local_kb.software_update import (  # noqa: E402
    LEGAL_SYSTEM_UPDATE_NOOP_REASONS,
    UPDATE_STATUS_CURRENT,
    UPDATE_STATUS_FAILED,
    mark_update_status,
    system_update_check,
)


def _git(repo_root: Path, *args: str, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [shutil.which("git") or "git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )


def _json_command(command: list[str], repo_root: Path, *, timeout: int) -> tuple[int, dict, str]:
    completed = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {}
    return completed.returncode, payload if isinstance(payload, dict) else {}, completed.stderr[-4000:]


def _snapshot_path(repo_root: Path) -> Path:
    return Path(repo_root) / ".local" / "khaos_brain_update_automation_snapshot.json"


def _snapshot_digest(payload: dict) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "snapshot_hash"}
    encoded = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _capture_or_load_snapshot(
    repo_root: Path,
    codex_home: Path,
    *,
    target_revision: str,
    source_revision: str,
    run_id: str,
) -> dict:
    path = _snapshot_path(repo_root)
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict) and payload.get("target_revision") == target_revision:
            if (
                payload.get("schema_version") != "khaos-brain.update-automation-snapshot.v2"
                or payload.get("snapshot_hash") != _snapshot_digest(payload)
                or not isinstance(payload.get("states"), dict)
                or not isinstance(payload.get("user_paused"), dict)
            ):
                raise RuntimeError("same-target automation snapshot is invalid or tampered")
            return {**payload, "path": str(path), "reused": True}
    capture = capture_repo_automation_state_snapshot(codex_home)
    payload = {
        "schema_version": "khaos-brain.update-automation-snapshot.v2",
        "target_revision": target_revision,
        "source_revision": source_revision,
        "capture_run_id": run_id,
        "states": capture["states"],
        "user_paused": capture["user_paused"],
        "state_sources": capture["sources"],
        "ambiguities": capture["ambiguities"],
        "ok": capture["ok"],
    }
    payload["snapshot_hash"] = _snapshot_digest(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return {**payload, "path": str(path), "reused": False}


def _fail(repo_root: Path, codex_home: Path, result: dict, message: str) -> dict:
    result["pause_after_failure"] = pause_repo_automations(codex_home)
    mark_update_status(repo_root, UPDATE_STATUS_FAILED, error=message)
    result.update({"ok": False, "status": "failed", "error": message})
    return result


def _mapping_ok(value: object) -> bool:
    return isinstance(value, dict) and value.get("ok") is True


def run_prepared_update(repo_root: Path, codex_home: Path, *, run_id: str = "") -> dict:
    resolved_run_id = str(run_id or f"system-update-{uuid4().hex}")
    lane_lock = acquire_lane_lock(
        repo_root,
        "khaos-brain-system-update",
        run_id=resolved_run_id,
        wait=False,
    )
    if lane_lock.get("acquired") is not True:
        reason = "concurrent-update"
        return {
            "ok": False,
            "status": "blocked",
            "run_id": resolved_run_id,
            "reason": reason,
            "terminal_gate": {
                "gate_id": "system-update-check",
                "evaluated": True,
                "applicable": False,
                "reason": reason,
            },
            "system_check": {"ok": True, "apply_ready": False, "reason": reason},
            "git_update": {"attempted": False, "mode": "ff-only"},
            "install": {},
            "install_check": {},
            "lane_lock": lane_lock,
        }
    gate = system_update_check(repo_root)
    result: dict = {
        "ok": True,
        "status": "no-op",
        "reason": str(gate.get("reason") or "no-update"),
        "system_check": gate,
        "git_update": {"attempted": False, "mode": "ff-only"},
        "install": {},
        "install_check": {},
        "claim_boundary": (
            "Only an explicitly prepared update may enter the fast-forward and transactional install route. "
            "A failed update leaves the installer-owned survivor automations paused."
        ),
        "run_id": resolved_run_id,
        "lane_lock": lane_lock,
    }
    try:
        if gate.get("ok") is not True:
            return _fail(
                repo_root,
                codex_home,
                result,
                str(gate.get("error") or gate.get("reason") or "system update gate failed"),
            )
        if gate.get("apply_ready") is not True:
            result["terminal_gate"] = {
                "gate_id": "system-update-check",
                "evaluated": True,
                "applicable": False,
                "reason": str(gate.get("reason") or result["reason"]),
            }
            if result["reason"] not in LEGAL_SYSTEM_UPDATE_NOOP_REASONS:
                result.update(
                    {
                        "ok": False,
                        "status": "blocked",
                        "error": (
                            "system update remains unfinished: "
                            f"{result['reason']}"
                        ),
                    }
                )
            return result

        dirty = _git(repo_root, "status", "--porcelain", "--untracked-files=no")
        if dirty.returncode != 0:
            return _fail(repo_root, codex_home, result, dirty.stderr.strip() or "git status failed")
        if dirty.stdout.strip():
            return _fail(
                repo_root,
                codex_home,
                result,
                "tracked user or peer work is dirty; automatic update refused without overwriting it",
            )
        upstream_result = _git(
            repo_root,
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{u}",
        )
        upstream = upstream_result.stdout.strip()
        if upstream_result.returncode != 0 or not upstream:
            return _fail(repo_root, codex_home, result, upstream_result.stderr.strip() or "upstream is not configured")
        before = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
        gate_state = gate.get("state") if isinstance(gate.get("state"), dict) else {}
        target_revision = str(gate_state.get("latest_revision") or "").strip()
        if not before or not target_revision:
            return _fail(repo_root, codex_home, result, "update revision binding is missing")
        snapshot = _capture_or_load_snapshot(
            repo_root,
            codex_home,
            target_revision=target_revision,
            source_revision=before,
            run_id=resolved_run_id,
        )
        result["automation_state_snapshot"] = snapshot
        if snapshot.get("ok") is not True:
            return _fail(
                repo_root,
                codex_home,
                result,
                "; ".join(str(item) for item in snapshot.get("ambiguities") or []),
            )
        pause_receipt = pause_repo_automations(codex_home)
        result["pause_before_mutation"] = pause_receipt
        if pause_receipt.get("ok") is not True:
            return _fail(repo_root, codex_home, result, "failed to pause surviving automations before update")
        merge = _git(repo_root, "merge", "--ff-only", upstream, timeout=300)
        result["git_update"] = {
            "attempted": True,
            "ok": merge.returncode == 0,
            "mode": "ff-only",
            "upstream": upstream,
            "before_revision": before,
            "after_revision": _git(repo_root, "rev-parse", "HEAD").stdout.strip(),
            "stderr": merge.stderr[-2000:],
        }
        if merge.returncode != 0:
            return _fail(repo_root, codex_home, result, merge.stderr.strip() or "git fast-forward failed")

        install_command = [
            sys.executable,
            "scripts/install_codex_kb.py",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--defer-automation-restore",
            "--automation-state-snapshot",
            str(snapshot["path"]),
            "--json",
        ]
        install_code, install, install_error = _json_command(
            install_command,
            repo_root,
            timeout=10800,
        )
        result["install"] = install
        if install_code != 0 or not install or not _mapping_ok(install.get("install_transaction")):
            return _fail(repo_root, codex_home, result, install_error or "transactional installer failed")
        check_code, install_check, check_error = _json_command(
            [
                sys.executable,
                "scripts/install_codex_kb.py",
                "--repo-root",
                str(repo_root),
                "--codex-home",
                str(codex_home),
                "--check",
                "--allow-deferred-automation-restore",
                "--json",
            ],
            repo_root,
            timeout=3600,
        )
        result["install_check"] = install_check
        install_transaction = install.get("install_transaction") if isinstance(install.get("install_transaction"), dict) else {}
        checked_transaction = install_check.get("install_transaction") if isinstance(install_check.get("install_transaction"), dict) else {}
        transaction_matches = bool(
            install_transaction.get("transaction_id")
            and install_transaction.get("transaction_id") == checked_transaction.get("transaction_id")
            and install_transaction.get("receipt_hash") == checked_transaction.get("receipt_hash")
        )
        if check_code != 0 or install_check.get("ok") is not True or not transaction_matches:
            return _fail(repo_root, codex_home, result, check_error or "post-update install health failed or transaction mismatched")
        pause_after_native = pause_repo_automations(codex_home)
        result["pause_after_native"] = pause_after_native
        if pause_after_native.get("ok") is not True:
            return _fail(repo_root, codex_home, result, "failed to keep automations paused for SkillGuard closure")
        result.update(
            {
                "ok": True,
                "status": "awaiting-skillguard",
                "reason": "prepared-update-awaiting-skillguard",
            }
        )
        return result
    finally:
        result["lock_release"] = release_lane_lock(
            repo_root,
            "khaos-brain-system-update",
            run_id=resolved_run_id,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--codex-home", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    codex_home = (
        Path(args.codex_home).expanduser().resolve()
        if args.codex_home
        else default_codex_home()
    )
    repo_root = resolve_repo_root(args.repo_root, cwd=REPO_ROOT, codex_home=codex_home)
    try:
        result = run_prepared_update(repo_root, codex_home, run_id=args.run_id)
    except (OSError, subprocess.SubprocessError) as exc:
        result = _fail(
            repo_root,
            codex_home,
            {"system_check": {}, "git_update": {}, "install": {}, "install_check": {}},
            f"{type(exc).__name__}: {exc}",
        )
    print_json(result, sort_keys=True)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
