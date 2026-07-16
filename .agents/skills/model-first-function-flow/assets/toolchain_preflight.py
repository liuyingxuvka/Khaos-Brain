"""Check whether the real flowguard package is available for a target project.

This script intentionally uses only the Python standard library so it can run
before the target project has installed flowguard.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _run_import(env: dict[str, str] | None = None) -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, "-c", "import flowguard; print(flowguard.SCHEMA_VERSION)"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    output = (completed.stdout + completed.stderr).strip()
    return completed.returncode == 0, output


def _has_flowguard_package(path: Path) -> bool:
    return (path / "flowguard" / "__init__.py").exists()


def _source_candidates(value: str | None) -> list[Path]:
    candidates: list[Path] = []
    if value:
        candidates.append(Path(value))
    env_value = os.environ.get("FLOWGUARD_SOURCE")
    if env_value:
        candidates.append(Path(env_value))
    candidates.append(Path.cwd())
    for parent in Path(__file__).resolve().parents:
        candidates.append(parent)
    return candidates


def _source_root(value: str | None) -> Path:
    candidates = _source_candidates(value)
    for candidate in candidates:
        if _has_flowguard_package(candidate):
            return candidate
    return candidates[0]


def _pythonpath_env(source: Path) -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(source) if not existing else str(source) + os.pathsep + existing
    return env


def check_toolchain(source: Path) -> dict[str, object]:
    installed_ok, installed_output = _run_import()
    if installed_ok:
        return {
            "ok": True,
            "mode": "installed",
            "schema_version": installed_output.splitlines()[-1] if installed_output else "",
            "source": str(source),
            "recommended_commands": [],
        }

    source_exists = _has_flowguard_package(source)
    pythonpath_ok = False
    pythonpath_output = ""
    if source_exists:
        pythonpath_ok, pythonpath_output = _run_import(_pythonpath_env(source))

    return {
        "ok": pythonpath_ok,
        "mode": "pythonpath_available" if pythonpath_ok else "missing",
        "schema_version": pythonpath_output.splitlines()[-1] if pythonpath_ok and pythonpath_output else "",
        "source": str(source),
        "source_exists": source_exists,
        "installed_error": installed_output,
        "recommended_commands": [
            f"python -m pip install -e {source}",
            f'$env:PYTHONPATH = "{source};$env:PYTHONPATH"',
            'python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"',
        ],
    }


def install_editable(source: Path) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-e",
            str(source),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "output": (completed.stdout + completed.stderr).strip(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="flowguard toolchain preflight")
    parser.add_argument("--source", default=None, help="Path to the FlowGuard source tree.")
    parser.add_argument("--install-editable", action="store_true", help="Install source in editable mode if import fails.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    source = _source_root(args.source).resolve()
    result = check_toolchain(source)
    if (
        args.install_editable
        and result.get("source_exists")
        and result.get("mode") != "installed"
    ):
        result["install"] = install_editable(source)
        result["after_install"] = check_toolchain(source)
        result["ok"] = bool(result["after_install"]["ok"])

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"status: {'OK' if result['ok'] else 'MISSING'}")
        print(f"mode: {result['mode']}")
        print(f"source: {result['source']}")
        for command in result.get("recommended_commands", ()):
            print(f"command: {command}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
