#!/usr/bin/env python3
"""Open the human-facing Khaos Brain desktop card browser."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.cli_output import print_json, print_text  # noqa: E402
from local_kb.config import resolve_repo_root  # noqa: E402
from local_kb.software_update import startup_block_message  # noqa: E402


SOURCE_RUNTIME = "source"
RELEASE_RUNTIME = "release"
CURRENT_RELEASE_EXECUTABLE = Path("dist") / "KhaosBrain.exe"


def _pythonw_executable() -> Path:
    executable = Path(sys.executable)
    if sys.platform == "win32":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            return pythonw
    return executable


def _launch_command(repo_root: Path, *, runtime: str, language: str) -> tuple[str, list[str]]:
    if runtime == SOURCE_RUNTIME:
        source_entry = repo_root / "scripts" / "kb_desktop.py"
        if not source_entry.is_file():
            raise FileNotFoundError(f"Selected source runtime is unavailable: {source_entry}")
        command = [
            str(_pythonw_executable()),
            str(source_entry),
            "--repo-root",
            str(repo_root),
        ]
    elif runtime == RELEASE_RUNTIME:
        release_entry = repo_root / CURRENT_RELEASE_EXECUTABLE
        if not release_entry.is_file():
            raise FileNotFoundError(f"Selected release runtime is unavailable: {release_entry}")
        command = [str(release_entry), "--repo-root", str(repo_root)]
    else:
        raise ValueError(f"Unknown Khaos Brain runtime: {runtime}")
    if language:
        command.extend(["--language", language])
    return runtime, command


def open_ui(repo_root: Path, *, runtime: str, language: str = "") -> dict[str, Any]:
    update_message = startup_block_message(repo_root, language=language or None)
    if update_message:
        return {
            "ok": False,
            "status": "upgrading",
            "message": update_message,
            "repo_root": str(repo_root),
        }
    try:
        mode, command = _launch_command(repo_root, runtime=runtime, language=language)
    except (FileNotFoundError, ValueError) as exc:
        return {
            "ok": False,
            "status": "runtime-unavailable",
            "runtime": runtime,
            "message": str(exc),
            "repo_root": str(repo_root),
        }
    process = subprocess.Popen(command, cwd=str(repo_root), close_fds=True)
    return {
        "ok": True,
        "mode": mode,
        "pid": process.pid,
        "command": command,
        "repo_root": str(repo_root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Open Khaos Brain's desktop card browser.")
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--language", default="", choices=["", "en", "zh-CN"])
    parser.add_argument(
        "--runtime",
        required=True,
        choices=[SOURCE_RUNTIME, RELEASE_RUNTIME],
        help="Select one current runtime explicitly; the launcher never switches runtimes.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root, cwd=SCRIPT_REPO_ROOT)
    payload = open_ui(repo_root, runtime=args.runtime, language=args.language)
    if args.json:
        print_json(payload)
    else:
        if payload.get("ok"):
            print_text(f"Opened Khaos Brain desktop UI with {payload['mode']} launcher.")
        else:
            print_text(payload.get("message") or "Khaos Brain cannot be opened right now.")
    return 0 if payload.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
