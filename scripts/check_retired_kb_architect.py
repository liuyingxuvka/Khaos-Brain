"""Fail closed when a retired KB Architect surface is still executable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.install import (  # noqa: E402
    MAINTENANCE_SKILL_NAMES,
    REPO_AUTOMATION_SPECS,
    RETIRED_AUTOMATION_IDS,
    RETIRED_MAINTENANCE_SKILL_IDS,
)
from local_kb.codex_registry import discover_active_registry  # noqa: E402


RETIRED_SKILL = "kb-architect-pass"
RETIRED_AUTOMATION = "kb-architect"

# These patterns intentionally name only executable/runtime model surfaces from
# the retired role.  They must not reject `architecture` paths or convergence
# tombstones such as `architect_present=False`, which are historical proof that
# retirement occurred rather than a live role or gate.
ACTIVE_ARCHITECT_PATTERNS = (
    re.compile(r"\$kb-architect-pass", re.IGNORECASE),
    re.compile(r"\bkb_architect\.py\b", re.IGNORECASE),
    re.compile(r"\bARCHITECT_PROMPT\.md\b", re.IGNORECASE),
    re.compile(r"\barchitect_update_check\s*\(", re.IGNORECASE),
    re.compile(r"\b(?:from|import)\s+local_kb\.architect\b", re.IGNORECASE),
    re.compile(r"\b(?:ArchitectRollupBlock|ArchitectOutletBlock)\b"),
    re.compile(r"\b(?:REQUIRED_ARCHITECT_REPORTS|ARCHITECT_MISSING_SOURCE_SEQUENCE)\b"),
    re.compile(r"\barchitect_(?:summary_status|patch_debt|outlet_status)\b"),
    re.compile(
        r"\barchitect_(?:collect_(?:sleep|dream|flowguard|organization|install)|"
        r"write_summary|ready_for_patch|creates_packet|records_blocker|applies_packet|stalls)\b"
    ),
    re.compile(
        r"\barchitect_(?:collected_(?:sleep|dream|flowguard|organization|install)|"
        r"sleep_report_missing|install_report_unhealthy|summary_(?:complete|incomplete)|"
        r"noop|patch_debt_opened|packet_ready|blocker_recorded|patch_stalled)\b"
    ),
    re.compile(r"\barchitect_(?:complete_requires_sources|patch_work_needs_outlet)\b"),
    re.compile(
        r"\barchitect_(?:cannot_complete_without_sources|missing_source_sequence|"
        r"execution_outlet_gap|ready_for_patch_no_outlet|ready_for_patch_stalled)\b"
    ),
    re.compile(r"\bbad_architect_summary_without_sources\b"),
    re.compile(r"\blatest_architect_run\b"),
    re.compile(
        r"\bArchitect(?:-owned)?\s+(?:report\s+aggregation|report\s+rollup|rollup|"
        r"ready-for-patch\s+work)\b",
        re.IGNORECASE,
    ),
)


def _check(check_id: str, ok: bool, details: Any) -> dict[str, Any]:
    return {"id": check_id, "ok": bool(ok), "details": details}


def _active_architect_marker_matches(text: str) -> tuple[str, ...]:
    """Return exact retired runtime/model markers found in one text fragment."""

    return tuple(pattern.pattern for pattern in ACTIVE_ARCHITECT_PATTERNS if pattern.search(text))


def _active_text_violations() -> list[dict[str, Any]]:
    roots = (
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "templates",
        REPO_ROOT / ".agents" / "skills" / "local-kb-retrieve",
        REPO_ROOT / "local_kb",
        REPO_ROOT / "scripts",
        REPO_ROOT / ".flowguard",
    )
    allowed = {
        (REPO_ROOT / "scripts" / "check_retired_kb_architect.py").resolve(),
    }
    violations: list[dict[str, Any]] = []
    for root in roots:
        files = [root] if root.is_file() else list(root.rglob("*")) if root.exists() else []
        for path in files:
            if not path.is_file() or path.resolve() in allowed:
                continue
            relative_parts = path.relative_to(REPO_ROOT).parts
            if relative_parts[:2] == (".flowguard", "evidence") or "adoption_log" in path.name:
                continue
            if path.suffix.lower() not in {".md", ".py", ".txt", ".toml", ".template"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                for pattern_text in _active_architect_marker_matches(line):
                    violations.append(
                        {
                            "path": path.relative_to(REPO_ROOT).as_posix(),
                            "line": line_number,
                            "pattern": pattern_text,
                        }
                    )
    return violations


def _registry_has_architect(registry_path: Path) -> tuple[bool, str]:
    if not registry_path.is_file():
        return False, "registry absent"
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return True, f"registry unreadable: {exc}"
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return RETIRED_SKILL in serialized, str(registry_path)


def build_report(codex_home: Path, registry_path: Path | None = None) -> dict[str, Any]:
    codex_home = Path(codex_home).resolve()
    source_paths = (
        REPO_ROOT / ".agents" / "skills" / RETIRED_SKILL,
        REPO_ROOT / ".agents" / "skills" / "local-kb-retrieve" / "ARCHITECT_PROMPT.md",
        REPO_ROOT / ".agents" / "skills" / "local-kb-retrieve" / "scripts" / "kb_architect.py",
        REPO_ROOT / "local_kb" / "architect.py",
        REPO_ROOT / "tests" / "test_kb_architect.py",
    )
    source_present = [
        str(path.relative_to(REPO_ROOT))
        for path in source_paths
        if path.is_file() or (path.is_dir() and any(item.is_file() for item in path.rglob("*")))
    ]
    skill_ids = tuple(MAINTENANCE_SKILL_NAMES)
    automation_ids = tuple(str(item.get("id") or "") for item in REPO_AUTOMATION_SPECS)
    text_violations = _active_text_violations()
    installed_paths = (
        codex_home / "skills" / RETIRED_SKILL,
        codex_home / "automations" / RETIRED_AUTOMATION,
    )
    installed_present = [str(path) for path in installed_paths if path.exists()]
    global_agents = codex_home / "AGENTS.md"
    global_route_present = False
    if global_agents.is_file():
        global_route_present = RETIRED_SKILL in global_agents.read_text(
            encoding="utf-8", errors="replace"
        )
    if registry_path is None:
        registry_path = discover_active_registry(codex_home)
    registry_present, registry_details = _registry_has_architect(registry_path)
    checks = (
        _check("repository_surfaces_absent", not source_present, source_present),
        _check(
            "exact_retired_tombstones",
            tuple(RETIRED_MAINTENANCE_SKILL_IDS) == (RETIRED_SKILL,)
            and tuple(RETIRED_AUTOMATION_IDS) == (RETIRED_AUTOMATION,),
            {
                "skills": list(RETIRED_MAINTENANCE_SKILL_IDS),
                "automations": list(RETIRED_AUTOMATION_IDS),
            },
        ),
        _check(
            "fresh_install_omits_architect",
            RETIRED_SKILL not in skill_ids and RETIRED_AUTOMATION not in automation_ids,
            {"skills": list(skill_ids), "automations": list(automation_ids)},
        ),
        _check("active_routes_absent", not text_violations, text_violations),
        _check("installed_surfaces_absent", not installed_present, installed_present),
        _check(
            "global_prompt_route_absent",
            not global_route_present,
            str(global_agents),
        ),
        _check(
            "global_registry_route_absent",
            not registry_present,
            registry_details,
        ),
    )
    return {
        "schema_version": 1,
        "check": "retired-kb-architect",
        "ok": all(item["ok"] for item in checks),
        "retired_ids": {
            "skill": RETIRED_SKILL,
            "automation": RETIRED_AUTOMATION,
        },
        "checks": list(checks),
        "claim_boundary": (
            "Exact executable source, installed surfaces, prompts, and current global "
            "router projections; inert historical provenance is intentionally allowed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--registry", type=Path)
    args = parser.parse_args()
    report = build_report(args.codex_home, args.registry)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for item in report["checks"]:
            print(("PASS" if item["ok"] else "FAIL"), item["id"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
