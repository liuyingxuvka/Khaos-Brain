#!/usr/bin/env python3
"""Install or verify the cross-machine Codex integration for this predictive KB."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.config import default_codex_home, resolve_repo_root
from local_kb.install import build_installation_check, install_codex_integration


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--codex-home", default="")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    codex_home = Path(args.codex_home).expanduser().resolve() if args.codex_home else default_codex_home()
    repo_root = resolve_repo_root(args.repo_root, cwd=SCRIPT_REPO_ROOT, codex_home=codex_home)

    if args.check:
        payload = build_installation_check(repo_root=repo_root, codex_home=codex_home)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            status = "OK" if payload["ok"] else "FAILED"
            print(f"Predictive KB install check: {status}")
            print(f"repo_root: {payload['repo_root']}")
            print(f"codex_home: {payload['codex_home']}")
            print(f"skill_path: {payload['skill_path']}")
            print(f"launcher_path: {payload['launcher_path']}")
            print(f"global_agents_path: {payload['global_agents_path']}")
            print(f"install_state_path: {payload['install_state_path']}")
            print("checklist:")
            for item in payload.get("checklist", []):
                marker = "[OK]" if item.get("ok") else "[MISSING]"
                print(f"- {marker} {item.get('label')}")
                details = str(item.get("details", "") or "").strip()
                if details:
                    print(f"  details: {details}")
            if payload["warnings"]:
                print("warnings:")
                for item in payload["warnings"]:
                    print(f"- {item}")
            if payload["issues"]:
                print("issues:")
                for item in payload["issues"]:
                    print(f"- {item}")
        return 0 if payload["ok"] else 1

    payload = install_codex_integration(repo_root=repo_root, codex_home=codex_home)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Installed predictive KB Codex integration.")
        print(f"repo_root: {payload['repo_root']}")
        print(f"codex_home: {payload['codex_home']}")
        print(f"skill_path: {payload['skill_path']}")
        print(f"launcher_path: {payload['launcher_path']}")
        print(f"install_state_path: {payload['install_state_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
