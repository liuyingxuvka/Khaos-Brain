from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any, Mapping, Sequence

from local_kb.maintenance_lanes import process_owner_is_alive


def _windows_process_table() -> dict[int, int]:
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        if snapshot in (0, ctypes.c_void_p(-1).value):
            return {}
        rows: dict[int, int] = {}
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        try:
            ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                rows[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
                ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(snapshot)
        return rows
    except (AttributeError, OSError, ValueError):
        return {}


def _posix_process_table() -> dict[int, int]:
    rows: dict[int, int] = {}
    proc = Path("/proc")
    if not proc.is_dir():
        return rows
    for child in proc.iterdir():
        if not child.name.isdigit():
            continue
        try:
            stat = (child / "stat").read_text(encoding="utf-8")
            fields = stat[stat.rfind(")") + 2 :].split()
            rows[int(child.name)] = int(fields[1])
        except (OSError, ValueError, IndexError):
            continue
    return rows


def process_tree_pids(root_pid: int) -> list[int]:
    """Snapshot one process tree with parents before children."""

    table = _windows_process_table() if os.name == "nt" else _posix_process_table()
    ordered = [int(root_pid)]
    seen = {int(root_pid)}
    cursor = 0
    while cursor < len(ordered):
        parent = ordered[cursor]
        cursor += 1
        for pid, parent_pid in table.items():
            if parent_pid == parent and pid not in seen:
                seen.add(pid)
                ordered.append(pid)
    return ordered


def _signal_process_tree(root_pid: int, captured_pids: list[int]) -> list[str]:
    errors: list[str] = []
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(root_pid), "/T", "/F"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode not in (0, 128):
                errors.append(
                    f"taskkill:{result.returncode}:{result.stderr[-500:]}"
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"taskkill:{type(exc).__name__}:{exc}")
        return errors
    for pid in reversed(captured_pids):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue
        except (PermissionError, OSError) as exc:
            errors.append(f"kill:{pid}:{type(exc).__name__}:{exc}")
    return errors


def _wait_for_processes_zero(
    captured_pids: list[int],
    *,
    timeout_seconds: float,
) -> list[int]:
    def remaining_processes() -> list[int]:
        if os.name == "nt":
            active = set(_windows_process_table())
            return [pid for pid in captured_pids if pid in active]
        return [pid for pid in captured_pids if process_owner_is_alive(pid)]

    deadline = time.monotonic() + max(0.1, timeout_seconds)
    remaining = remaining_processes()
    while remaining and time.monotonic() < deadline:
        time.sleep(0.05)
        remaining = remaining_processes()
    return remaining


def terminate_process_tree(
    process: subprocess.Popen[Any],
    *,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    """Terminate one owned process tree and return reusable cleanup evidence.

    Long-lived protocol workers cannot use ``Popen.communicate(timeout=...)``
    for every request because their stdin/stdout stay open between requests.
    This helper gives those owners the same descendant-tree cleanup boundary as
    ``run_with_timeout_cleanup`` without treating a timeout as a successful
    retry signal.
    """

    captured_pids = process_tree_pids(process.pid)
    termination_errors = _signal_process_tree(process.pid, captured_pids)
    try:
        process.wait(timeout=max(0.1, timeout_seconds))
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError as exc:
            termination_errors.append(
                f"root-kill:{type(exc).__name__}:{exc}"
            )
        try:
            process.wait(timeout=max(0.1, timeout_seconds))
        except subprocess.TimeoutExpired as exc:
            termination_errors.append(
                f"root-wait:{type(exc).__name__}:{exc}"
            )
    confirmation_pids = [
        pid
        for pid in captured_pids
        if pid != process.pid or process.returncode is None
    ]
    remaining = _wait_for_processes_zero(
        confirmation_pids,
        timeout_seconds=max(0.1, timeout_seconds),
    )
    return {
        "root_pid": process.pid,
        "captured_process_ids": captured_pids,
        "captured_process_count": len(captured_pids),
        "remaining_process_ids": remaining,
        "remaining_process_count": len(remaining),
        "root_reaped": process.returncode is not None,
        "cleanup_confirmed": not remaining and process.returncode is not None,
        "termination_errors": termination_errors,
    }


def run_with_timeout_cleanup(
    command: Sequence[str | os.PathLike[str]],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    capture_output: bool = False,
    text: bool = False,
    encoding: str | None = None,
    errors: str | None = None,
    timeout: float | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[Any]:
    """Run one owner and prove its captured process tree is gone on timeout."""

    popen_options: dict[str, Any] = {
        "cwd": cwd,
        "env": dict(env) if env is not None else None,
        "text": text,
        "encoding": encoding,
        "errors": errors,
    }
    if capture_output:
        popen_options.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.name == "nt":
        popen_options["creationflags"] = getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        popen_options["start_new_session"] = True
    process = subprocess.Popen(list(command), **popen_options)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        captured_pids = process_tree_pids(process.pid)
        termination_errors = _signal_process_tree(process.pid, captured_pids)
        try:
            stdout, stderr = process.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except OSError as exc:
                termination_errors.append(f"root-kill:{type(exc).__name__}:{exc}")
            stdout, stderr = process.communicate()
        confirmation_pids = [
            pid
            for pid in captured_pids
            if pid != process.pid or process.returncode is None
        ]
        remaining = _wait_for_processes_zero(
            confirmation_pids,
            timeout_seconds=10,
        )
        cleanup_receipt = {
            "root_pid": process.pid,
            "captured_process_ids": captured_pids,
            "captured_process_count": len(captured_pids),
            "remaining_process_ids": remaining,
            "remaining_process_count": len(remaining),
            "root_reaped": process.returncode is not None,
            "cleanup_confirmed": not remaining,
            "termination_errors": termination_errors,
        }
        exc = subprocess.TimeoutExpired(
            list(command),
            timeout,
            output=stdout,
            stderr=stderr,
        )
        setattr(exc, "cleanup_receipt", cleanup_receipt)
        raise exc
    completed = subprocess.CompletedProcess(
        args=list(command),
        returncode=int(process.returncode or 0),
        stdout=stdout,
        stderr=stderr,
    )
    if check and completed.returncode:
        raise subprocess.CalledProcessError(
            completed.returncode,
            completed.args,
            output=completed.stdout,
            stderr=completed.stderr,
        )
    return completed
