from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _bootstrap_repo_imports() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))


_bootstrap_repo_imports()

from local_kb.cli_output import print_json  # noqa: E402
from local_kb.skill_sharing import install_approved_organization_skill, load_organization_skill_registry  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install one approved organization Skill after registry policy checks.")
    parser.add_argument("--org-root", required=True)
    parser.add_argument("--skill-id", required=True)
    parser.add_argument("--bundle-id", default="")
    parser.add_argument("--codex-home", default="")
    parser.add_argument("--cache-root", default="")
    parser.add_argument("--allow-auto-policy", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    registry = load_organization_skill_registry(Path(args.org_root))
    skill = (registry.get("by_bundle_id") or {}).get(args.bundle_id) if args.bundle_id else None
    if skill is None:
        skill = (registry.get("by_id") or {}).get(args.skill_id)
    if skill is None:
        skill = (registry.get("by_bundle_id") or {}).get(args.skill_id)
    if skill is None:
        result = {"ok": False, "skill_id": args.skill_id, "status": "missing", "errors": ["Skill is not in organization registry"]}
    else:
        result = install_approved_organization_skill(
            skill,
            codex_home=Path(args.codex_home) if args.codex_home else None,
            cache_root=Path(args.cache_root) if args.cache_root else None,
            local_policy_allows=args.allow_auto_policy,
            replace_existing=args.replace_existing,
        )
    print_json(result)
    if not result.get("ok"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
