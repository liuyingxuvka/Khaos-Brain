from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Any, Mapping

from local_kb.automation_contracts import PRE_RESTORE_ASSURANCE_TIMEOUT_SECONDS
from local_kb.card_ids import load_or_create_installation_id
from local_kb.common import utc_now_iso
from local_kb.transactional_install import (
    consumer_skill_manifest,
    install_managed_runtime,
    latest_install_receipt,
    tree_manifest,
)
from local_kb.config import (
    KB_ROOT_ENV_VAR,
    default_codex_home,
    install_state_path,
    is_repo_root,
    load_install_state,
    save_install_state,
)
from local_kb.process_control import run_with_timeout_cleanup


GLOBAL_SKILL_NAME = "predictive-kb-preflight"
GLOBAL_SKILL_ROOT = Path("skills") / GLOBAL_SKILL_NAME
GLOBAL_SKILLS_ROOT = Path("skills")
REPO_SKILLS_ROOT = Path(".agents") / "skills"
TEMPLATE_ROOT = Path("templates") / GLOBAL_SKILL_NAME
AUTOMATIONS_ROOT = Path("automations")
GLOBAL_AGENTS_FILENAME = "AGENTS.md"
GLOBAL_AGENTS_BEGIN = "<!-- BEGIN MANAGED PREDICTIVE KB DEFAULTS -->"
GLOBAL_AGENTS_END = "<!-- END MANAGED PREDICTIVE KB DEFAULTS -->"
CODEX_SHELL_BIN_RELATIVE = Path("OpenAI") / "Codex" / "bin"
AUTOMATION_MODEL_POLICY = "strongest-available"
AUTOMATION_REASONING_EFFORT_POLICY = "deepest"
AUTOMATION_MODEL_ENV_VAR = "CODEX_KB_AUTOMATION_MODEL"
AUTOMATION_REASONING_EFFORT_ENV_VAR = "CODEX_KB_AUTOMATION_REASONING_EFFORT"
UPGRADE_ATTEMPT_SCHEMA = "khaos-brain.upgrade-attempt.v2"
UPGRADE_ATTEMPT_EVENT_SCHEMA = "khaos-brain.upgrade-attempt-event.v2"
UPGRADE_ATTEMPT_PROJECTION_SCHEMA = "khaos-brain.upgrade-attempt-projection.v2"
UPGRADE_ATTEMPT_HEAD_SCHEMA = "khaos-brain.upgrade-attempt-head.v1"
UPGRADE_ATTEMPT_AUTHORITY_SCHEMA = (
    "khaos-brain.upgrade-attempt-current-authority.v1"
)
UPGRADE_ATTEMPT_ROOT = Path(".khaos-brain-install") / "attempts"
UPGRADE_ATTEMPT_HEAD_MAX_BYTES = 32 * 1024
UPGRADE_ATTEMPT_CURRENT_MAX_BYTES = 256 * 1024
REASONING_EFFORT_ORDER = ("none", "minimal", "low", "medium", "high", "xhigh")
AUTOMATION_DAILY_BYDAY = "SU,MO,TU,WE,TH,FR,SA"
RETIRED_MAINTENANCE_SKILL_IDS = ("kb-architect-pass",)
RETIRED_AUTOMATION_IDS = ("kb-architect", "khaos-brain-system-update")
FLOWGUARD_VALIDATION_ROOT_ENV = "KHAOS_BRAIN_FLOWGUARD_VALIDATION_ROOT"
FLOWGUARD_VALIDATION_DIGEST_ENV = "KHAOS_BRAIN_FLOWGUARD_VALIDATION_DIGEST"
RESEARCHGUARD_LOGIC_VALIDATION_ROOT_ENV = (
    "KHAOS_BRAIN_RESEARCHGUARD_LOGIC_VALIDATION_ROOT"
)
RESEARCHGUARD_LOGIC_VALIDATION_DIGEST_ENV = (
    "KHAOS_BRAIN_RESEARCHGUARD_LOGIC_VALIDATION_DIGEST"
)
INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV = (
    "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_PRESENT"
)
INSTALLATION_IDENTITY_PYTHONPATH_VALUE_ENV = (
    "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_VALUE"
)
INSTALLATION_IDENTITY_PYTHON_EXECUTABLE_ENV = (
    "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHON_EXECUTABLE"
)
ORG_CONTRIBUTE_WINDOW = (10 * 60, 13 * 60 + 59)
ORG_MAINTENANCE_WINDOW = (14 * 60, 16 * 60)
MISTAKE_PRIORITY_MARKERS = (
    "mistake-first priority",
    "weak path",
    "correction",
    "highest-priority",
    "successful reusable",
    "contrastive fields",
)
CANONICAL_INTERFACE_MARKERS = (
    "canonical machine interfaces",
    "localized display projection",
    "encoding-stable json",
)
CURRENT_RUNTIME_ONLY_MARKERS = (
    "zero compatibility",
    "zero fallback",
    "upgrade-only direct-migration",
    "unfinished upgrade-ai work item",
    "missing current authority",
)
LOGICGUARD_NATIVE_DEFAULT_MARKERS = (
    "deterministic projection",
    "exact logicguard",
    "argumentblock",
    "grounded modelmesh",
    "sleep is the sole normal-runtime",
)
POSTFLIGHT_TIMEOUT_OWNERSHIP_MARKERS = (
    "at least 180 seconds",
    "up to 120 seconds",
    "never start a second writer",
    "same event id",
    "zero descendant processes",
)
MAINTENANCE_SKILL_SPECS = (
    {
        "name": "kb-sleep-maintenance",
        "automation_id": "kb-sleep",
        "prompt_marker": "MAINTENANCE_PROMPT.md",
    },
    {
        "name": "kb-dream-pass",
        "automation_id": "kb-dream",
        "prompt_marker": "DREAM_PROMPT.md",
    },
    {
        "name": "kb-organization-contribute",
        "automation_id": "kb-org-contribute",
        "prompt_marker": "scripts/kb_org_outbox.py",
    },
    {
        "name": "kb-organization-maintenance",
        "automation_id": "kb-org-maintenance",
        "prompt_marker": "scripts/kb_org_maintainer.py",
    },
    {
        "name": "khaos-brain-update",
        "automation_id": "",
        "execution_kind": "explicit-user-request",
        "prompt_marker": "scripts/install_codex_kb.py",
    },
)
MAINTENANCE_SKILL_NAMES = tuple(item["name"] for item in MAINTENANCE_SKILL_SPECS)


def _has_mistake_priority_wording(text: str) -> bool:
    normalized = text.lower()
    return all(marker in normalized for marker in MISTAKE_PRIORITY_MARKERS)


def _has_canonical_interface_wording(text: str) -> bool:
    normalized = text.lower()
    return all(marker in normalized for marker in CANONICAL_INTERFACE_MARKERS)


def _has_current_runtime_only_wording(text: str) -> bool:
    normalized = text.lower()
    return all(marker in normalized for marker in CURRENT_RUNTIME_ONLY_MARKERS)


def _has_logicguard_native_default_wording(text: str) -> bool:
    normalized = text.lower()
    return all(marker in normalized for marker in LOGICGUARD_NATIVE_DEFAULT_MARKERS)


def _has_postflight_timeout_ownership_wording(text: str) -> bool:
    normalized = text.lower()
    return all(
        marker in normalized
        for marker in POSTFLIGHT_TIMEOUT_OWNERSHIP_MARKERS
    )

# Chaos Brain lifecycle prompts supersede the legacy editorial prompt bodies.
# prompt bodies above.  They are intentionally compact because the Skills own
# the full workflow contract and the automations only select the entrypoint.
SLEEP_AUTOMATION_PROMPT = (
    "Use $kb-sleep-maintenance for the fully automatic local Sleep pass. Read PROJECT_SPEC.md, "
    "docs/maintenance_agent_worldview.md, and .agents/skills/local-kb-retrieve/MAINTENANCE_PROMPT.md. "
    "Run only `python scripts/run_kb_automation.py --skill kb-sleep-maintenance --json`; the target-owned "
    "runner owns lane-to-terminal orchestration, invokes the native Sleep entrypoint "
    "`.agents/skills/local-kb-retrieve/scripts/kb_sleep.py` exactly once, and validates this "
    "run's immutable native terminal receipt. Do not run the child entrypoint directly. Consume only the committed "
    "increment after the last watermark, give every admitted observation one explicit disposition, settle or park "
    "candidates with executable reopen conditions, apply evidence-driven promotion or downgrade review, and act as the "
    "sole canonical model-generation publisher. Build a LogicGuard model revision for every admitted entry, preserve "
    "explicit model gaps instead of inventing support, assemble exact revisions into a grounded ModelMesh only from "
    "qualifying provenance, consume typed Dream handoffs exactly once, and atomically publish models, meshes, "
    "deterministic projections, manifests, and the generation pointer last. Rebuild and validate the active index against that exact generation; commit the watermark only after "
    "all durable decisions succeed. On any blocker roll back the complete generation, leave the watermark unchanged, and report the machine receipt. "
    "Do not request human file review, do not start a second maintenance implementation, and do not resume another "
    "automation. Finish by marking the same Sleep run id completed or failed through kb_lane_status.py."
)

DREAM_AUTOMATION_PROMPT = (
    "Use $kb-dream-pass for one fully automatic bounded Dream pass. Read PROJECT_SPEC.md, "
    "docs/maintenance_agent_worldview.md, docs/dream_runbook.md, and "
    ".agents/skills/local-kb-retrieve/DREAM_PROMPT.md, then run only "
    "`python scripts/run_kb_automation.py --skill kb-dream-pass --json`. The target-owned runner invokes the "
    "native Dream entrypoint `.agents/skills/local-kb-retrieve/scripts/kb_dream.py` exactly once and validates this run's immutable native terminal receipt; do not "
    "run the child entrypoint directly. First pin the exact LogicGuard generation, model revision, root ArgumentBlock, "
    "and ModelMesh revision. Derive decision-relevant stable fingerprints, skip already closed unchanged evidence as "
    "no_delta_closed, execute only a small valuable route-deduplicated experiment set, and run separate applicable checks for evidence removal, "
    "assumption removal, rebuttal strengthening or counterexamples, boundary pressure, cross-edge removal, and neighbor-pin replacement. Emit typed idempotent Sleep handoffs "
    "for material model gaps with exact authority bindings. Dream may write only bounded Dream runtime/experiment artifacts "
    "and its handoff ledger; it must not directly write cards, models, meshes, candidates, confidence, predictive observations, "
    "or central KB history, and it must prove the canonical generation unchanged. A no-op is a successful convergent result."
)

ORG_CONTRIBUTE_AUTOMATION_PROMPT = (
    "Use $kb-organization-contribute to run one settings-gated organization KB contribution pass for this workspace. "
    "Use PROJECT_SPEC.md, docs/organization_mode_plan.md, and .agents/skills/local-kb-retrieve/SKILL.md "
    "as the authoritative guides. Start by reading .local/khaos_brain_desktop_settings.json through "
    "scripts/kb_org_outbox.py --automation; if the desktop settings are personal mode, missing, unvalidated, or not "
    "connected to a validated organization repository, return a successful no-op. When organization mode is valid, "
    "sync the organization mirror first, run KB preflight against system/knowledge-library/organization, then export only shareable public model and "
    "heuristic cards through the content-hash-gated outbox. Respect every exchanged hash including downloaded, used, absorbed, exported, uploaded, "
    "current local card hashes, current organization main-card hashes, and current import hashes; do not export "
    "private cards, personal preferences, credentials, raw local paths, or raw machine identifiers. When cards "
    "depend on local Skills, upload card-bound Skill bundles with bundle_id, content_hash, version_time, "
    "original_author, readonly_when_imported, and update_policy=original_author_only; if several local cards point "
    "at the same bundle_id, upload the local latest version for that bundle rather than an older card-carried copy. Use "
    "`python scripts/run_kb_automation.py --skill kb-organization-contribute --json` for the scheduled pass; "
    "the target-owned runner invokes scripts/kb_org_outbox.py --automation exactly once and validates the immutable native "
    "terminal receipt. Do not run the child entrypoint directly. The native pass should prepare an import branch under kb/imports, then revalidate the exact materialized changed paths, counts, hashes, privacy/shareability, Skill author/version/hash metadata, and base-branch rollback before any push, then push eligible import proposals automatically only after that current revalidation, open a GitHub PR when available, and apply org-kb:auto-merge only when current checks allow it "
    "while leaving movement into organization main, trust upgrades, and final merge to organization maintenance and GitHub checks. Run KB postflight after "
    "any non-skipped pass, record a "
    "structured observation, and report the settings gate, sync result, preflight entries, created and skipped proposal counts, "
    "outbox path, import branch status, push or pull request URL, postflight path, and "
    "errors."
)

ORG_MAINTENANCE_AUTOMATION_PROMPT = (
    "Use $kb-organization-maintenance to run one settings-gated organization-level Sleep-like maintenance pass for this workspace. "
    "Treat the organization KB as a shared exchange layer rather than a central truth layer: "
    "organization maintenance may maintain organization main cards and imported card content with the same editorial "
    "posture as local Sleep, while local machines keep final adoption authority. Use PROJECT_SPEC.md, "
    "docs/maintenance_agent_worldview.md, docs/organization_mode_plan.md, "
    ".agents/skills/local-kb-retrieve/SKILL.md, and organization-review guidance when available. Start by "
    "running only `python scripts/run_kb_automation.py --skill kb-organization-maintenance --json`; the "
    "target-owned runner invokes scripts/kb_org_maintainer.py --automation exactly once and validates its immutable native terminal "
    "receipt. Do not run the child entrypoint directly. The native pass first reads "
    ".local/khaos_brain_desktop_settings.json; if the "
    "desktop settings are personal mode, missing, unvalidated, or organization maintenance participation is not "
    "requested, return a successful no-op. When participation is available for a validated organization "
    "repository, run KB preflight against system/knowledge-library/organization, validate the organization "
    "manifest, expected paths, imports entry lane, main exchange lane, Skill registry, and current Git state, "
    "then run the organization card-surface map checkpoint, organization candidate intake checkpoint, content-hash checkpoint, mandatory organization "
    "similar-card merge checkpoint, mandatory organization overloaded-card split checkpoint, candidate decision "
    "checkpoint, Skill safety checkpoint, Skill bundle version checkpoint, decision-apply checkpoint, post-apply organization check, and GitHub merge-readiness checkpoint. Inspect organization trusted cards, candidates, "
    "main cards, imports, Skill registry entries, card-and-Skill bundles, privacy boundaries, and GitHub auto-merge readiness "
    "using the organization maintenance worldview and organization-review guidance when available. Treat duplicate content hashes as maintenance signals and duplicate entry ids as "
    "non-blocking handles. Trusted/shared card content maintenance is allowed when the evidence supports a "
    "Sleep-style keep, reject, watch, merge, split, rewrite, promote, demote, deprecate, or cross-link decision. "
    "For card-bound Skill bundles, group by bundle_id, approve only original-author updates "
    "on the same bundle, require sha256 content_hash and version_time, treat non-author changes as forks, and select "
    "the latest approved version by version_time for organization distribution. Use candidate, approved, and rejected "
    "as the first-pass Skill states; do not auto-install candidate, rejected, unknown, unpinned, or non-hash-verified "
    "Skills. Build an organization Sleep decision set over cleanup proposals, select-for-apply or watch each action with a reason, treat organization-review as guidance rather than an apply gate, and apply only exact selected action ids. "
    "Keep privacy and executable Skill boundaries stricter than ordinary card content. It is acceptable to skip applying a change when evidence, "
    "safety, tooling, permissions, or scope is insufficient, but the inspection and recorded decision must still "
    "happen. Run KB postflight after any non-skipped pass, record a structured observation, and report the settings "
    "gate, participation status, preflight entries, manifest status, main status counts and import counts, content-hash "
    "duplicate decisions, organization merge checkpoint decisions, organization split checkpoint decisions, "
    "candidate approval or rejection decisions, Sleep decision counts, selected action ids, apply result, post-apply check result, maintenance branch, PR, push, and auto-merge-label result, Skill dependency decisions, Skill bundle version decisions, GitHub "
    "merge-readiness result, organization-review guidance availability, recommendations, postflight path, and errors."
)

REPO_AUTOMATION_SPECS = (
    {
        "id": "kb-sleep",
        "name": "KB Sleep",
        "kind": "cron",
        "prompt": SLEEP_AUTOMATION_PROMPT,
        "skill_name": "kb-sleep-maintenance",
        "status": "ACTIVE",
        "rrule": "FREQ=WEEKLY;BYDAY=SU,MO,TU,WE,TH,FR,SA;BYHOUR=12;BYMINUTE=0",
        "model_policy": AUTOMATION_MODEL_POLICY,
        "reasoning_effort_policy": AUTOMATION_REASONING_EFFORT_POLICY,
        "execution_environment": "local",
    },
    {
        "id": "kb-dream",
        "name": "KB Dream",
        "kind": "cron",
        "prompt": DREAM_AUTOMATION_PROMPT,
        "skill_name": "kb-dream-pass",
        "status": "ACTIVE",
        "rrule": "FREQ=WEEKLY;BYDAY=SU,MO,TU,WE,TH,FR,SA;BYHOUR=13;BYMINUTE=0",
        "model_policy": AUTOMATION_MODEL_POLICY,
        "reasoning_effort_policy": AUTOMATION_REASONING_EFFORT_POLICY,
        "execution_environment": "local",
    },
    {
        "id": "kb-org-contribute",
        "name": "KB Organization Contribute",
        "kind": "cron",
        "prompt": ORG_CONTRIBUTE_AUTOMATION_PROMPT,
        "skill_name": "kb-organization-contribute",
        "status": "ACTIVE",
        "jitter_window": ORG_CONTRIBUTE_WINDOW,
        "model_policy": AUTOMATION_MODEL_POLICY,
        "reasoning_effort_policy": AUTOMATION_REASONING_EFFORT_POLICY,
        "execution_environment": "local",
    },
    {
        "id": "kb-org-maintenance",
        "name": "KB Organization Maintenance",
        "kind": "cron",
        "prompt": ORG_MAINTENANCE_AUTOMATION_PROMPT,
        "skill_name": "kb-organization-maintenance",
        "status": "ACTIVE",
        "jitter_window": ORG_MAINTENANCE_WINDOW,
        "model_policy": AUTOMATION_MODEL_POLICY,
        "reasoning_effort_policy": AUTOMATION_REASONING_EFFORT_POLICY,
        "execution_environment": "local",
    },
)

# These managed jobs were introduced after the original Sleep/Dream install
# surface.  Their absence on a legacy machine has no user state to preserve;
# it is a known new-component case, not an ambiguous deletion.  Sleep and
# Dream remain fail-closed when missing because older installations did own
# those states.
POST_LEGACY_AUTOMATION_IDS = frozenset(
    {
        "kb-org-contribute",
        "kb-org-maintenance",
    }
)


def default_local_appdata() -> Path:
    raw = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / "AppData" / "Local").resolve()


def global_skill_dir(codex_home: Path | None = None) -> Path:
    home = codex_home or default_codex_home()
    return home / GLOBAL_SKILL_ROOT


def maintenance_skill_source_dir(repo_root: Path, skill_name: str) -> Path:
    return repo_root / REPO_SKILLS_ROOT / skill_name


def maintenance_skill_install_dir(skill_name: str, codex_home: Path | None = None) -> Path:
    home = codex_home or default_codex_home()
    return home / GLOBAL_SKILLS_ROOT / skill_name


def codex_shell_bin_dir(path_env: str | None = None, local_appdata: Path | None = None) -> Path:
    active_path = str(path_env if path_env is not None else os.environ.get("PATH", "") or "")
    for raw_entry in active_path.split(os.pathsep):
        entry_text = raw_entry.strip().strip('"')
        if not entry_text:
            continue
        entry = Path(entry_text).expanduser()
        parts = [part.lower() for part in entry.parts]
        if len(parts) >= 3 and parts[-3:] == ["openai", "codex", "bin"]:
            return entry.resolve()
    base = local_appdata or default_local_appdata()
    return (base / CODEX_SHELL_BIN_RELATIVE).resolve()


def automation_dir(codex_home: Path | None = None) -> Path:
    home = codex_home or default_codex_home()
    return home / AUTOMATIONS_ROOT


def automation_toml_path(automation_id: str, codex_home: Path | None = None) -> Path:
    return automation_dir(codex_home) / automation_id / "automation.toml"


def _rrule_for_local_minute(total_minutes: int) -> str:
    hour = max(0, min(23, int(total_minutes) // 60))
    minute = max(0, min(59, int(total_minutes) % 60))
    return f"FREQ=WEEKLY;BYDAY={AUTOMATION_DAILY_BYDAY};BYHOUR={hour};BYMINUTE={minute}"


def _stable_window_minute(repo_root: Path, automation_id: str, window: tuple[int, int]) -> int:
    start, end = int(window[0]), int(window[1])
    if end < start:
        raise ValueError(f"Invalid automation jitter window: {window}")
    installation_id = load_or_create_installation_id(repo_root)
    digest = hashlib.sha256(f"{installation_id}:{automation_id}".encode("utf-8")).digest()
    offset = int.from_bytes(digest[:8], "big") % (end - start + 1)
    return start + offset


def automation_rrule_for_spec(spec: dict[str, Any], repo_root: Path) -> str:
    window = spec.get("jitter_window")
    if isinstance(window, tuple) and len(window) == 2:
        return _rrule_for_local_minute(_stable_window_minute(repo_root, str(spec["id"]), window))
    return str(spec["rrule"])


def automation_time_window_label(spec: dict[str, Any]) -> str:
    window = spec.get("jitter_window")
    if not isinstance(window, tuple) or len(window) != 2:
        return ""
    start, end = int(window[0]), int(window[1])
    return f"{start // 60:02d}:{start % 60:02d}-{end // 60:02d}:{end % 60:02d}"


def global_agents_path(codex_home: Path | None = None) -> Path:
    home = codex_home or default_codex_home()
    return home / GLOBAL_AGENTS_FILENAME


def codex_config_path(codex_home: Path | None = None) -> Path:
    home = codex_home or default_codex_home()
    return home / "config.toml"


def models_cache_path(codex_home: Path | None = None) -> Path:
    home = codex_home or default_codex_home()
    return home / "models_cache.json"


def _load_toml_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_models_cache(codex_home: Path | None = None) -> list[dict[str, Any]]:
    path = models_cache_path(codex_home)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    models = payload.get("models", []) if isinstance(payload, dict) else []
    return [item for item in models if isinstance(item, dict)]


def _supported_reasoning_efforts(model: dict[str, Any]) -> list[str]:
    raw_levels = model.get("supported_reasoning_levels", [])
    efforts: list[str] = []
    if isinstance(raw_levels, list):
        for item in raw_levels:
            if isinstance(item, dict):
                effort = str(item.get("effort", "") or "").strip()
            else:
                effort = str(item or "").strip()
            if effort:
                efforts.append(effort)
    return efforts


def _general_model_version_key(slug: str) -> tuple[int, ...] | None:
    match = re.fullmatch(r"gpt-(\d+(?:\.\d+)*)(?:-[a-z0-9][a-z0-9-]*)?", slug.strip().lower())
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def _config_model(codex_home: Path | None = None) -> str:
    payload = _load_toml_object(codex_config_path(codex_home))
    return str(payload.get("model", "") or "").strip()


def _config_reasoning_effort(codex_home: Path | None = None) -> str:
    payload = _load_toml_object(codex_config_path(codex_home))
    return str(payload.get("model_reasoning_effort", "") or "").strip()


def resolve_automation_model(codex_home: Path | None = None) -> str:
    env_value = str(os.environ.get(AUTOMATION_MODEL_ENV_VAR, "") or "").strip()
    if env_value:
        return env_value

    models = _load_models_cache(codex_home)
    configured_model = _config_model(codex_home)
    available_slugs = [
        str(model.get("slug", "") or "").strip()
        for model in models
        if str(model.get("slug", "") or "").strip()
    ]
    if configured_model and (not available_slugs or configured_model in available_slugs):
        return configured_model
    candidates: list[tuple[tuple[int, ...], str]] = []
    for model in models:
        slug = str(model.get("slug", "") or "").strip()
        version_key = _general_model_version_key(slug)
        if version_key is None:
            continue
        candidates.append((version_key, slug))
    if candidates:
        strongest_version = max(item[0] for item in candidates)
        return next(slug for version, slug in candidates if version == strongest_version)
    if configured_model:
        raise RuntimeError(
            f"Configured automation model is not present in current provider metadata: {configured_model}"
        )
    raise RuntimeError(
        "Automation model cannot be resolved from an explicit override, current provider metadata, or current Codex configuration."
    )


def resolve_automation_reasoning_effort(
    codex_home: Path | None = None,
    *,
    model: str | None = None,
) -> str:
    env_value = str(os.environ.get(AUTOMATION_REASONING_EFFORT_ENV_VAR, "") or "").strip()
    if env_value:
        return env_value

    selected_model = str(model or resolve_automation_model(codex_home)).strip()
    models = _load_models_cache(codex_home)
    for model_payload in models:
        if str(model_payload.get("slug", "") or "").strip() != selected_model:
            continue
        supported = _supported_reasoning_efforts(model_payload)
        ranked = [item for item in REASONING_EFFORT_ORDER if item in supported]
        if ranked:
            return ranked[-1]
        raise RuntimeError(
            f"Current provider metadata declares no supported reasoning effort for automation model {selected_model}."
        )

    configured_effort = _config_reasoning_effort(codex_home)
    if configured_effort:
        return configured_effort
    raise RuntimeError(
        "Automation reasoning effort cannot be resolved from an explicit override, current provider metadata, or current Codex configuration."
    )


def resolve_automation_runtime(codex_home: Path | None = None) -> dict[str, str]:
    model = resolve_automation_model(codex_home)
    reasoning_effort = resolve_automation_reasoning_effort(codex_home, model=model)
    return {
        "model": model,
        "reasoning_effort": reasoning_effort,
        "model_policy": AUTOMATION_MODEL_POLICY,
        "reasoning_effort_policy": AUTOMATION_REASONING_EFFORT_POLICY,
        "model_env_var": AUTOMATION_MODEL_ENV_VAR,
        "reasoning_effort_env_var": AUTOMATION_REASONING_EFFORT_ENV_VAR,
    }


def _render_template(text: str, replacements: dict[str, str]) -> str:
    rendered = text
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def _read_template(repo_root: Path, relative_path: str | Path) -> str:
    path = repo_root / TEMPLATE_ROOT / relative_path
    return path.read_text(encoding="utf-8")


def _render_managed_global_agents_block(repo_root: Path) -> str:
    body = _read_template(repo_root, "AGENTS.md.template").strip()
    return f"{GLOBAL_AGENTS_BEGIN}\n{body}\n{GLOBAL_AGENTS_END}\n"


def _upsert_managed_global_agents(existing_text: str, managed_block: str) -> str:
    if GLOBAL_AGENTS_BEGIN in existing_text and GLOBAL_AGENTS_END in existing_text:
        start = existing_text.index(GLOBAL_AGENTS_BEGIN)
        end = existing_text.index(GLOBAL_AGENTS_END) + len(GLOBAL_AGENTS_END)
        prefix = existing_text[:start].rstrip()
        suffix = existing_text[end:].lstrip()
        parts = [part for part in [prefix, managed_block.strip(), suffix] if part]
        return "\n\n".join(parts).rstrip() + "\n"
    if not existing_text.strip():
        return managed_block
    return existing_text.rstrip() + "\n\n" + managed_block


def install_global_agents_defaults(repo_root: Path, codex_home: Path | None = None) -> str:
    path = global_agents_path(codex_home)
    try:
        existing_text = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        existing_text = ""
    rendered = _upsert_managed_global_agents(existing_text, _render_managed_global_agents_block(repo_root))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    return str(path)


def _checklist_item(
    item_id: str,
    label: str,
    ok: bool,
    details: str,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "label": label,
        "ok": ok,
        "required": required,
        "details": details,
    }


def _candidate_paths(*raw_paths: str | Path | None) -> list[Path]:
    seen: set[str] = set()
    candidates: list[Path] = []
    for raw_path in raw_paths:
        if raw_path is None:
            continue
        text = str(raw_path).strip().strip('"')
        if not text:
            continue
        path = Path(text).expanduser()
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(path)
    return candidates


def _path_entries(path_env: str | None = None) -> list[Path]:
    active_path = str(path_env if path_env is not None else os.environ.get("PATH", "") or "")
    return _candidate_paths(*active_path.split(os.pathsep))


def resolve_git_executable(
    *,
    shell_bin_dir: Path | None = None,
    explicit_path: str | Path | None = None,
    path_env: str | None = None,
) -> Path | None:
    if explicit_path is not None:
        path = Path(explicit_path).expanduser()
        return path.resolve() if path.exists() else None

    shell_bin = (shell_bin_dir or codex_shell_bin_dir(path_env=path_env)).resolve()
    local_appdata = default_local_appdata()
    program_files = Path(str(os.environ.get("ProgramFiles", "") or "")).expanduser()
    program_files_x86 = Path(str(os.environ.get("ProgramFiles(x86)", "") or "")).expanduser()

    candidates = _candidate_paths(
        program_files / "Git" / "cmd" / "git.exe" if str(program_files) else None,
        program_files / "Git" / "bin" / "git.exe" if str(program_files) else None,
        program_files_x86 / "Git" / "cmd" / "git.exe" if str(program_files_x86) else None,
        program_files_x86 / "Git" / "bin" / "git.exe" if str(program_files_x86) else None,
        local_appdata / "Programs" / "Git" / "cmd" / "git.exe",
        local_appdata / "Programs" / "Git" / "bin" / "git.exe",
    )
    candidates.extend(_candidate_paths(*(entry / "git.exe" for entry in _path_entries(path_env))))

    github_desktop_root = local_appdata / "GitHubDesktop"
    if github_desktop_root.exists():
        try:
            candidates.extend(
                _candidate_paths(
                    *github_desktop_root.glob("app-*\\resources\\app\\git\\cmd\\git.exe")
                )
            )
        except OSError:
            pass

    for candidate in candidates:
        if not candidate.exists():
            continue
        if candidate.resolve().parent == shell_bin:
            continue
        return candidate.resolve()
    return None


def resolve_rg_source(
    *,
    shell_bin_dir: Path | None = None,
    explicit_path: str | Path | None = None,
    path_env: str | None = None,
) -> Path | None:
    if explicit_path is not None:
        path = Path(explicit_path).expanduser()
        return path.resolve() if path.exists() else None

    shell_bin = (shell_bin_dir or codex_shell_bin_dir(path_env=path_env)).resolve()
    existing_dest = shell_bin / "rg.exe"
    if existing_dest.exists():
        return existing_dest.resolve()

    local_appdata = default_local_appdata()
    program_files = Path(str(os.environ.get("ProgramFiles", "") or "")).expanduser()

    candidates = _candidate_paths(*(entry / "rg.exe" for entry in _path_entries(path_env)))
    candidates.extend(
        _candidate_paths(
            local_appdata / "Programs" / "Microsoft VS Code" / "resources" / "app" / "node_modules.asar.unpacked" / "@vscode" / "ripgrep" / "bin" / "rg.exe",
            local_appdata / "Programs" / "cursor" / "resources" / "app" / "node_modules.asar.unpacked" / "@vscode" / "ripgrep" / "bin" / "rg.exe",
            program_files / "Microsoft VS Code" / "resources" / "app" / "node_modules.asar.unpacked" / "@vscode" / "ripgrep" / "bin" / "rg.exe" if str(program_files) else None,
            program_files / "VSCodium" / "resources" / "app" / "node_modules.asar.unpacked" / "@vscode" / "ripgrep" / "bin" / "rg.exe" if str(program_files) else None,
        )
    )

    windows_apps = program_files / "WindowsApps" if str(program_files) else None
    if windows_apps and windows_apps.exists():
        try:
            candidates.extend(
                _candidate_paths(
                    *windows_apps.glob("OpenAI.Codex_*\\app\\resources\\rg.exe")
                )
            )
        except OSError:
            pass

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def _prepend_process_path(path: Path) -> bool:
    resolved = str(path.resolve())
    current_path = str(os.environ.get("PATH", "") or "")
    entries = [entry.strip().strip('"') for entry in current_path.split(os.pathsep) if entry.strip()]
    if resolved in entries:
        return False
    os.environ["PATH"] = resolved if not current_path else f"{resolved}{os.pathsep}{current_path}"
    return True


def _persist_user_path(path: Path) -> bool:
    try:
        import winreg  # type: ignore
    except ImportError:
        return False

    resolved = str(path.resolve())
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ) as key:
            current_value, _ = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        current_value = ""
    current_text = str(current_value or "")
    entries = [entry.strip().strip('"') for entry in current_text.split(os.pathsep) if entry.strip()]
    if resolved in entries:
        return False
    updated_text = resolved if not entries else os.pathsep.join([resolved, *entries])
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, updated_text)
    return True


def install_codex_shell_tools(
    *,
    shell_bin_dir: Path | None = None,
    git_executable: str | Path | None = None,
    rg_source: str | Path | None = None,
    path_env: str | None = None,
    persist_user_path: bool = True,
) -> dict[str, Any]:
    bin_dir = (shell_bin_dir or codex_shell_bin_dir(path_env=path_env)).resolve()
    bin_dir.mkdir(parents=True, exist_ok=True)

    resolved_git = resolve_git_executable(
        shell_bin_dir=bin_dir,
        explicit_path=git_executable,
        path_env=path_env,
    )
    resolved_rg = resolve_rg_source(
        shell_bin_dir=bin_dir,
        explicit_path=rg_source,
        path_env=path_env,
    )

    issues: list[str] = []
    git_shim_path = bin_dir / "git.cmd"
    rg_path = bin_dir / "rg.exe"

    if resolved_git is None:
        issues.append("Unable to locate a Git executable for the Codex shell shim.")
    else:
        shim_command = (
            f'call "{resolved_git}" %*'
            if resolved_git.suffix.lower() in {".cmd", ".bat"}
            else f'"{resolved_git}" %*'
        )
        git_shim_path.write_text(f"@echo off\r\n{shim_command}\r\n", encoding="ascii")

    if resolved_rg is None:
        issues.append("Unable to locate an rg.exe source for the Codex shell shim.")
    elif resolved_rg.resolve() != rg_path.resolve():
        shutil.copy2(resolved_rg, rg_path)

    process_path_updated = _prepend_process_path(bin_dir)
    user_path_updated = _persist_user_path(bin_dir) if persist_user_path else False

    return {
        "shell_bin_dir": str(bin_dir),
        "git_executable": str(resolved_git) if resolved_git else "",
        "git_shim_path": str(git_shim_path),
        "git_shim_installed": git_shim_path.exists(),
        "rg_source": str(resolved_rg) if resolved_rg else "",
        "rg_path": str(rg_path),
        "rg_installed": rg_path.exists(),
        "process_path_updated": process_path_updated,
        "user_path_updated": user_path_updated,
        "issues": issues,
    }


def _automation_spec_payload(
    spec: dict[str, Any],
    repo_root: Path,
    codex_home: Path | None = None,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime = resolve_automation_runtime(codex_home)
    schedule_window = automation_time_window_label(spec)
    existing_payload = existing or {}
    existing_status = str(existing_payload.get("status", "") or "").upper()
    # Runtime status and the user's pause preference are independent.  An
    # upgrade may temporarily pause an otherwise enabled automation without
    # turning that safety pause into a permanent user preference.  Older
    # automation files did not carry ``user_paused``; the installer performs
    # this one-time direct state migration before writing the sole current form.
    user_paused = (
        bool(existing_payload.get("user_paused"))
        if "user_paused" in existing_payload
        else bool(existing_payload) and existing_status == "PAUSED"
    )
    status = (
        "PAUSED"
        if user_paused
        else str(spec["status"]).upper()
    )
    return {
        "version": 1,
        "id": spec["id"],
        "kind": spec["kind"],
        "name": spec["name"],
        "prompt": spec["prompt"],
        "status": status,
        "user_paused": user_paused,
        "rrule": automation_rrule_for_spec(spec, repo_root),
        "schedule_policy": "stable-jitter" if schedule_window else "fixed",
        "schedule_window": schedule_window,
        "model": runtime["model"],
        "reasoning_effort": runtime["reasoning_effort"],
        "model_policy": spec.get("model_policy", runtime["model_policy"]),
        "reasoning_effort_policy": spec.get(
            "reasoning_effort_policy",
            runtime["reasoning_effort_policy"],
        ),
        "execution_environment": spec["execution_environment"],
        "cwds": [str(repo_root)],
    }


def _load_automation_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_automation_toml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_automation_toml_text(payload), encoding="utf-8")


def _set_automation_status_atomic(path: Path, status: str) -> bool:
    """Change only the scheduler status line, preserving unknown future fields."""

    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    replacement = f'status = "{str(status).upper()}"'
    updated, count = re.subn(
        r'^status\s*=\s*"[A-Z]+"\s*$',
        replacement,
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        return False
    temporary = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return True


def _render_automation_state_text(
    text: str,
    status: str,
    user_paused: bool,
) -> str | None:
    normalized_status = str(status or "").upper()
    if normalized_status not in {"ACTIVE", "PAUSED"}:
        return None
    updated, status_count = re.subn(
        r'^status\s*=\s*"[A-Z]+"\s*$',
        f'status = "{normalized_status}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    updated, paused_count = re.subn(
        r"^user_paused\s*=\s*(?:true|false)\s*$",
        f"user_paused = {'true' if user_paused else 'false'}",
        updated,
        count=1,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    if paused_count == 0 and status_count == 1:
        updated, paused_count = re.subn(
            r'^(status\s*=\s*"[A-Z]+"\s*)$',
            r"\1\n" + f"user_paused = {'true' if user_paused else 'false'}",
            updated,
            count=1,
            flags=re.MULTILINE,
        )
    return updated if status_count == 1 and paused_count == 1 else None


def _write_text_atomic(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _restore_exact_file_snapshot(path: Path, *, existed: bool, content: bytes) -> None:
    """Restore one upgrade-owned file exactly, including prior absence."""

    if not existed:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{time.time_ns()}.rollback.tmp")
    with temporary.open("wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")
    ).hexdigest().upper()


def _upgrade_attempt_dir(codex_home: Path, attempt_id: str) -> Path:
    return codex_home / UPGRADE_ATTEMPT_ROOT / attempt_id


def _read_bounded_json(
    path: Path,
    *,
    max_bytes: int,
) -> tuple[dict[str, Any], bytes, str]:
    try:
        size = path.stat().st_size
    except OSError:
        return {}, b"", "missing"
    if size <= 0:
        return {}, b"", "empty"
    if size > max_bytes:
        return {}, b"", "oversized"
    try:
        with path.open("rb") as handle:
            raw = handle.read(max_bytes + 1)
        if len(raw) > max_bytes:
            return {}, raw, "oversized"
        payload = json.loads(raw.decode("utf-8"))
    except OSError:
        return {}, b"", "unreadable"
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, raw if "raw" in locals() else b"", "malformed"
    if not isinstance(payload, dict):
        return {}, raw, "not-object"
    return payload, raw, ""


def _load_upgrade_attempt(path: Path) -> dict[str, Any]:
    payload, _raw, issue = _read_bounded_json(
        path,
        max_bytes=UPGRADE_ATTEMPT_CURRENT_MAX_BYTES,
    )
    if issue:
        return {}
    supplied_hash = str(payload.get("receipt_hash") or "")
    body = dict(payload)
    body.pop("receipt_hash", None)
    if (
        payload.get("schema_version") != UPGRADE_ATTEMPT_SCHEMA
        or payload.get("projection_schema_version")
        != UPGRADE_ATTEMPT_PROJECTION_SCHEMA
        or not supplied_hash
        or supplied_hash != _canonical_payload_hash(body)
    ):
        return {}
    return payload


def _bounded_projection_strings(
    value: object,
    *,
    limit: int = 32,
    text_limit: int = 1000,
) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    projected = [str(item)[:text_limit] for item in value[:limit]]
    if len(value) > limit:
        projected.append(f"... {len(value) - limit} additional items in immutable event")
    return projected


def _tree_manifest_projection(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        key: value[key]
        for key in ("schema_version", "digest", "file_count", "total_bytes")
        if key in value
    }


def _validation_toolchain_projection(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    projected = {
        key: value[key]
        for key in (
            "schema_version",
            "ok",
            "status",
            "attempt_count",
            "snapshot_root",
            "source_root",
            "canonical_snapshot_root",
            "router_snapshot_root",
            "router_source_root",
            "router_canonical_snapshot_root",
            "validation_codex_home",
            "installation_receipt_root",
            "installation_python_executable",
            "receipt_path",
            "receipt_hash",
            "cli_sha256",
            "compiler_sha256",
        )
        if key in value
    }
    for key in (
        "manifest",
        "source_manifest",
        "canonical_manifest",
        "router_manifest",
        "router_source_manifest",
        "router_canonical_manifest",
    ):
        manifest = _tree_manifest_projection(value.get(key))
        if manifest:
            projected[key] = manifest
    dependency = value.get("dependency")
    if isinstance(dependency, Mapping):
        projected["dependency"] = {
            key: dependency[key]
            for key in (
                "package",
                "version",
                "schema_version",
                "source_root",
                "digest",
            )
            if key in dependency
        }
    return projected


def _migration_projection(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    projected = {
        key: value[key]
        for key in (
            "schema_version",
            "ok",
            "status",
            "migration_id",
            "idempotent_no_delta",
            "residual_retired_state_count",
            "attempt_count",
            "receipt_hash",
        )
        if key in value
    }
    for key in (
        "logical_debt_reconciliation",
        "maintenance_state",
        "managed_surface_reconciliation",
        "post_commit_convergence_runs",
        "validation",
    ):
        nested = value.get(key)
        if isinstance(nested, Mapping):
            projected[key] = {
                nested_key: nested_value
                for nested_key, nested_value in nested.items()
                if isinstance(nested_value, (str, int, float, bool)) or nested_value is None
            }
    issues = _bounded_projection_strings(value.get("issues"))
    if issues:
        projected["issues"] = issues
    receipt = value.get("receipt")
    if isinstance(receipt, Mapping):
        projected["receipt"] = {
            key: receipt[key]
            for key in (
                "schema_version",
                "ok",
                "status",
                "migration_id",
                "receipt_hash",
            )
            if key in receipt
        }
    return projected


def _transaction_projection(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    projected = {
        key: value[key]
        for key in (
            "schema_version",
            "ok",
            "status",
            "transaction_id",
            "receipt_hash",
            "journal_path",
            "backup_root",
        )
        if key in value
    }
    for key in ("retired_skill_ids", "retired_automation_ids"):
        rows = _bounded_projection_strings(value.get(key))
        if rows:
            projected[key] = rows
    return projected


def _upgrade_assurance_projection(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    projected = {
        key: value[key]
        for key in (
            "schema_version",
            "ok",
            "status",
            "check",
            "pre_restore",
            "evidence_run_id",
            "evidence_manifest",
            "generated_at",
            "source_stable_during_checks",
            "exact_execution_identity_counts",
            "duplicate_exact_executions",
            "verifier_fingerprint",
            "receipt_hash",
            "execution_count",
            "claim_boundary",
        )
        if key in value
    }
    owners = value.get("owners")
    if isinstance(owners, Mapping):
        projected["owner_count"] = len(owners)
    failed_checks = _bounded_projection_strings(value.get("failed_checks"))
    projected["failed_checks"] = failed_checks
    for key in ("executed_owner_ids", "reused_owner_ids"):
        rows = _bounded_projection_strings(value.get(key))
        if rows:
            projected[key] = rows
    return projected


def _upgrade_attempt_detail_projection(details: Mapping[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for key in (
        "repo_root",
        "repo_root_hash",
        "survivors_must_remain_paused",
        "post_install_check_ok",
        "projection_compacted",
        "projection_source_sequence",
        "error_type",
        "recovery_action",
    ):
        if key in details:
            projected[key] = details[key]
    if "error" in details:
        projected["error"] = str(details.get("error") or "")[-4000:]

    pause = details.get("pause_before_migration")
    if isinstance(pause, Mapping):
        projected["pause_before_migration"] = {
            key: pause[key]
            for key in ("ok", "expected_ids", "paused_ids")
            if key in pause
        }
    automation_snapshot = details.get("automation_state_snapshot")
    if isinstance(automation_snapshot, Mapping):
        projected["automation_state_snapshot"] = {
            "schema_version": str(
                automation_snapshot.get("schema_version")
                or "khaos-brain.automation-state-snapshot.v1"
            ),
            "ok": automation_snapshot.get("ok") is True,
            "states": dict(automation_snapshot.get("states") or {}),
            "user_paused": dict(
                automation_snapshot.get("user_paused") or {}
            ),
            "sources": dict(automation_snapshot.get("sources") or {}),
            "ambiguities": _bounded_projection_strings(
                automation_snapshot.get("ambiguities")
            ),
        }
    for key in ("pre_assurance_update_state_migration",):
        nested = details.get(key)
        if isinstance(nested, Mapping):
            projected[key] = {
                nested_key: nested_value
                for nested_key, nested_value in nested.items()
                if isinstance(nested_value, (str, int, float, bool))
            }
    for key in ("history_migration",):
        nested = _migration_projection(details.get(key))
        if nested:
            projected[key] = nested
    for key in (
        "flowguard_validation_toolchain",
        "researchguard_logic_validation_toolchain",
    ):
        nested = _validation_toolchain_projection(details.get(key))
        if nested:
            projected[key] = nested
    for key in ("paused_install_transaction", "install_transaction"):
        nested = _transaction_projection(details.get(key))
        if nested:
            projected[key] = nested
    assurance = _upgrade_assurance_projection(details.get("upgrade_assurance"))
    if assurance:
        projected["upgrade_assurance"] = assurance
    return projected


def current_upgrade_attempt_authority(codex_home: Path) -> dict[str, Any]:
    """Read only the bounded current HEAD and its exact current projection."""

    root = codex_home / UPGRADE_ATTEMPT_ROOT
    head_path = root / "HEAD.json"
    head, head_raw, head_issue = _read_bounded_json(
        head_path,
        max_bytes=UPGRADE_ATTEMPT_HEAD_MAX_BYTES,
    )
    issues: list[str] = []
    if head_issue:
        issues.append(f"upgrade-attempt-head-{head_issue}")
    else:
        supplied_hash = str(head.get("head_hash") or "")
        body = dict(head)
        body.pop("head_hash", None)
        if (
            head.get("schema_version") != UPGRADE_ATTEMPT_HEAD_SCHEMA
            or not supplied_hash
            or supplied_hash != _canonical_payload_hash(body)
        ):
            issues.append("upgrade-attempt-head-invalid")

    current_path: Path | None = None
    current: dict[str, Any] = {}
    current_raw = b""
    if not issues:
        ref = head.get("current_ref")
        relative = str(ref.get("relative_path") or "") if isinstance(ref, Mapping) else ""
        if not relative:
            issues.append("upgrade-attempt-current-ref-missing")
        else:
            candidate = (root / Path(relative)).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                issues.append("upgrade-attempt-current-ref-escapes-root")
            else:
                current_path = candidate
                payload, current_raw, current_issue = _read_bounded_json(
                    candidate,
                    max_bytes=UPGRADE_ATTEMPT_CURRENT_MAX_BYTES,
                )
                if current_issue:
                    issues.append(f"upgrade-attempt-current-{current_issue}")
                else:
                    current = payload
                    supplied_hash = str(current.get("receipt_hash") or "")
                    body = dict(current)
                    body.pop("receipt_hash", None)
                    if (
                        current.get("schema_version") != UPGRADE_ATTEMPT_SCHEMA
                        or current.get("projection_schema_version")
                        != UPGRADE_ATTEMPT_PROJECTION_SCHEMA
                        or not supplied_hash
                        or supplied_hash != _canonical_payload_hash(body)
                        or hashlib.sha256(current_raw).hexdigest().upper()
                        != str(ref.get("sha256") or "")
                        or supplied_hash
                        != str(head.get("current_receipt_hash") or "")
                        or current.get("attempt_id") != head.get("attempt_id")
                        or int(current.get("sequence") or 0)
                        != int(head.get("sequence") or 0)
                    ):
                        issues.append("upgrade-attempt-current-binding-invalid")

    attempt = (
        {**current, "current_path": str(current_path)}
        if not issues and current_path is not None
        else {}
    )
    return {
        "schema_version": UPGRADE_ATTEMPT_AUTHORITY_SCHEMA,
        "ok": not issues,
        "status": "current" if not issues else "blocked",
        "issues": issues,
        "head_path": str(head_path),
        "current_path": str(current_path or ""),
        "attempt": attempt,
        "read_budget": {
            "head_max_bytes": UPGRADE_ATTEMPT_HEAD_MAX_BYTES,
            "current_max_bytes": UPGRADE_ATTEMPT_CURRENT_MAX_BYTES,
            "observed_head_bytes": len(head_raw),
            "observed_current_bytes": len(current_raw),
            "history_files_scanned": 0,
        },
    }


def latest_upgrade_attempt(codex_home: Path) -> dict[str, Any]:
    """Return the sole current attempt; history is never searched."""

    authority = current_upgrade_attempt_authority(codex_home)
    return (
        dict(authority.get("attempt") or {})
        if authority.get("ok") is True
        else {}
    )


def _record_upgrade_attempt(
    codex_home: Path,
    attempt_id: str,
    *,
    phase: str,
    status: str,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    attempt_dir = _upgrade_attempt_dir(codex_home, attempt_id)
    event_dir = attempt_dir / "events"
    event_dir.mkdir(parents=True, exist_ok=True)
    current_path = attempt_dir / "current.json"
    previous = _load_upgrade_attempt(current_path) if current_path.is_file() else {}
    sequence = int(previous.get("sequence") or 0) + 1
    now = utc_now_iso()
    event_body = {
        "schema_version": UPGRADE_ATTEMPT_EVENT_SCHEMA,
        "attempt_id": attempt_id,
        "sequence": sequence,
        "phase": phase,
        "status": status,
        "details": dict(details or {}),
        "created_at": now,
        "previous_event_hash": str(previous.get("latest_event_hash") or ""),
    }
    event_hash = _canonical_payload_hash(event_body)
    event = {**event_body, "event_hash": event_hash}
    event_path = event_dir / f"{sequence:04d}-{event_hash[:16].lower()}.json"
    encoded_event = (
        json.dumps(event, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    try:
        with event_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded_event)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        if event_path.read_text(encoding="utf-8") != encoded_event:
            raise RuntimeError(f"upgrade attempt event collision: {event_path}")
    started_at = str(previous.get("started_at") or now)
    checkpoint_refs = [
        *[
            dict(item)
            for item in previous.get("checkpoint_refs", [])
            if isinstance(item, Mapping)
        ],
        {
            "sequence": sequence,
            "phase": phase,
            "status": status,
            "event_hash": event_hash,
            "relative_path": event_path.relative_to(attempt_dir).as_posix(),
        },
    ]
    previous_projection = _upgrade_attempt_detail_projection(previous)
    current_projection = _upgrade_attempt_detail_projection(dict(details or {}))
    current_body = {
        "schema_version": UPGRADE_ATTEMPT_SCHEMA,
        "projection_schema_version": UPGRADE_ATTEMPT_PROJECTION_SCHEMA,
        "attempt_id": attempt_id,
        "status": status,
        "phase": phase,
        "sequence": sequence,
        "started_at": started_at,
        "updated_at": now,
        "latest_event_hash": event_hash,
        "checkpoint_refs": checkpoint_refs,
        **previous_projection,
        **current_projection,
    }
    current = {**current_body, "receipt_hash": _canonical_payload_hash(current_body)}
    attempt_dir.mkdir(parents=True, exist_ok=True)
    _write_text_atomic(
        current_path,
        json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    current_raw = current_path.read_bytes()
    head_body = {
        "schema_version": UPGRADE_ATTEMPT_HEAD_SCHEMA,
        "attempt_id": attempt_id,
        "sequence": sequence,
        "updated_at": now,
        "current_receipt_hash": current["receipt_hash"],
        "current_ref": {
            "relative_path": current_path.relative_to(
                codex_home / UPGRADE_ATTEMPT_ROOT
            ).as_posix(),
            "sha256": hashlib.sha256(current_raw).hexdigest().upper(),
        },
    }
    head = {
        **head_body,
        "head_hash": _canonical_payload_hash(head_body),
    }
    _write_text_atomic(
        codex_home / UPGRADE_ATTEMPT_ROOT / "HEAD.json",
        json.dumps(head, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {**current, "current_path": str(current_path)}


def _start_upgrade_attempt(
    codex_home: Path,
    *,
    repo_root: Path,
    pause_before_migration: Mapping[str, Any],
    history_migration: Mapping[str, Any],
    automation_state_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    seed = f"{time.time_ns()}:{os.getpid()}:{repo_root}"
    attempt_id = (
        f"upgrade-{int(time.time() * 1000)}-"
        f"{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:10]}"
    )
    return _record_upgrade_attempt(
        codex_home,
        attempt_id,
        phase="migration_committed_automations_paused",
        status="in_progress",
        details={
            "repo_root": str(repo_root),
            "repo_root_hash": hashlib.sha256(
                str(repo_root).encode("utf-8")
            ).hexdigest().upper(),
            "pause_before_migration": dict(pause_before_migration),
            "automation_state_snapshot": dict(automation_state_snapshot),
            "history_migration": dict(history_migration),
            "survivors_must_remain_paused": True,
        },
    )


def _automation_restoration_plan_hash(plan: Mapping[str, Any]) -> str:
    body = {
        "schema_version": str(plan.get("schema_version") or ""),
        "states": dict(plan.get("states") or {}),
        "user_paused": dict(plan.get("user_paused") or {}),
        "source_states": dict(plan.get("source_states") or {}),
        "source_user_paused": dict(plan.get("source_user_paused") or {}),
        "source_hashes": dict(plan.get("source_hashes") or {}),
        "target_hashes": dict(plan.get("target_hashes") or {}),
    }
    return hashlib.sha256(
        json.dumps(
            body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest().upper()


def _committed_install_receipt_projection(
    transaction: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one successful native install transaction into migration authority."""

    receipt_hash = str(transaction.get("receipt_hash") or "")
    transaction_id = str(transaction.get("transaction_id") or "")
    if transaction.get("ok") is not True or not receipt_hash or not transaction_id:
        raise RuntimeError(
            "A successful native install transaction is required for migration authority"
        )
    return {
        "schema_version": "khaos-brain.committed-install-receipt.v1",
        "status": "committed",
        "receipt_hash": receipt_hash,
        "transaction_id": transaction_id,
    }


def _set_automation_state_atomic(
    path: Path,
    status: str,
    user_paused: bool,
) -> bool:
    """Restore status and its user-owned pause metadata as one atomic write."""

    if not path.is_file():
        return False
    updated = _render_automation_state_text(
        path.read_text(encoding="utf-8"),
        status,
        user_paused,
    )
    if updated is None:
        return False
    _write_text_atomic(path, updated)
    return True


def _pause_installed_kb_automations(codex_home: Path) -> list[str]:
    paused: list[str] = []
    for automation_id in (
        *(str(spec["id"]) for spec in REPO_AUTOMATION_SPECS),
        *RETIRED_AUTOMATION_IDS,
    ):
        if _set_automation_status_atomic(
            automation_toml_path(automation_id, codex_home), "PAUSED"
        ):
            paused.append(automation_id)
    return paused


def capture_repo_automation_states(codex_home: Path) -> dict[str, str]:
    states: dict[str, str] = {}
    for spec in REPO_AUTOMATION_SPECS:
        automation_id = str(spec["id"])
        payload = _load_automation_toml(automation_toml_path(automation_id, codex_home))
        status = str(payload.get("status") or "").upper()
        if status in {"ACTIVE", "PAUSED"}:
            states[automation_id] = status
    return states


def capture_repo_automation_state_snapshot(codex_home: Path) -> dict[str, Any]:
    """Capture exact survivor status plus user-pause ownership without guessing legacy state."""

    states: dict[str, str] = {}
    user_paused: dict[str, bool] = {}
    sources: dict[str, str] = {}
    ambiguities: list[str] = []
    clean_install = not any(
        automation_toml_path(str(spec["id"]), codex_home).exists()
        for spec in REPO_AUTOMATION_SPECS
    )
    for spec in REPO_AUTOMATION_SPECS:
        automation_id = str(spec["id"])
        path = automation_toml_path(automation_id, codex_home)
        payload = _load_automation_toml(path)
        status = str(payload.get("status") or "").upper()
        if payload and status in {"ACTIVE", "PAUSED"}:
            states[automation_id] = status
            user_paused[automation_id] = (
                bool(payload.get("user_paused"))
                if "user_paused" in payload
                else status == "PAUSED"
            )
            sources[automation_id] = (
                "installed-current"
                if "user_paused" in payload
                else "codex-status-direct-migration"
            )
            continue
        if not path.exists() and (
            clean_install or automation_id in POST_LEGACY_AUTOMATION_IDS
        ):
            states[automation_id] = str(spec["status"]).upper()
            user_paused[automation_id] = False
            sources[automation_id] = (
                "clean-install-policy"
                if clean_install
                else "new-automation-policy"
            )
            continue
        states[automation_id] = "PAUSED"
        user_paused[automation_id] = True
        sources[automation_id] = "unknown-fail-closed"
        ambiguities.append(
            f"prior automation state cannot be established: {automation_id}"
        )
    return {
        "ok": not ambiguities,
        "states": states,
        "user_paused": user_paused,
        "sources": sources,
        "ambiguities": ambiguities,
    }


def plan_repo_automation_restoration(
    codex_home: Path,
    states: Mapping[str, str],
    *,
    user_paused_states: Mapping[str, bool],
) -> dict[str, Any]:
    """Plan exact live automation bytes without activating any scheduler entry."""

    managed_ids = {str(spec["id"]) for spec in REPO_AUTOMATION_SPECS}
    issues: list[str] = []
    if set(states) != managed_ids:
        issues.append(
            f"restoration-state-set-mismatch:{sorted(managed_ids ^ set(states))}"
        )
    if set(user_paused_states) != managed_ids:
        issues.append(
            "restoration-user-pause-set-mismatch:"
            f"{sorted(managed_ids ^ set(user_paused_states))}"
        )
    normalized_states: dict[str, str] = {}
    normalized_user_paused: dict[str, bool] = {}
    source_hashes: dict[str, str] = {}
    target_hashes: dict[str, str] = {}
    source_states: dict[str, str] = {}
    source_user_paused: dict[str, bool] = {}
    for automation_id in sorted(managed_ids):
        status = str(states.get(automation_id) or "").upper()
        if status not in {"ACTIVE", "PAUSED"}:
            issues.append(f"invalid-restoration-status:{automation_id}:{status}")
            continue
        path = automation_toml_path(automation_id, codex_home)
        if not path.is_file():
            issues.append(f"restoration-source-missing:{automation_id}")
            continue
        try:
            current_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            issues.append(f"restoration-source-unreadable:{automation_id}:{type(exc).__name__}")
            continue
        user_paused = bool(user_paused_states.get(automation_id))
        current_payload = _load_automation_toml(path)
        current_status = str(current_payload.get("status") or "").upper()
        if current_status not in {"ACTIVE", "PAUSED"}:
            issues.append(f"restoration-source-status-invalid:{automation_id}")
            continue
        target_text = _render_automation_state_text(
            current_text,
            status,
            user_paused,
        )
        if target_text is None:
            issues.append(f"restoration-source-shape-invalid:{automation_id}")
            continue
        normalized_states[automation_id] = status
        normalized_user_paused[automation_id] = user_paused
        source_states[automation_id] = current_status
        source_user_paused[automation_id] = bool(current_payload.get("user_paused"))
        source_hashes[automation_id] = _text_sha256(current_text)
        target_hashes[automation_id] = _text_sha256(target_text)
    plan_body = {
        "schema_version": "khaos-brain.automation-restoration-plan.v1",
        "states": normalized_states,
        "user_paused": normalized_user_paused,
        "source_states": source_states,
        "source_user_paused": source_user_paused,
        "source_hashes": source_hashes,
        "target_hashes": target_hashes,
    }
    plan_hash = _automation_restoration_plan_hash(plan_body)
    return {
        **plan_body,
        "plan_hash": plan_hash,
        "ok": not issues
        and set(normalized_states) == managed_ids
        and set(target_hashes) == managed_ids,
        "issues": issues,
        "claim_boundary": (
            "Deterministic status/user-pause target bytes only; no live automation was activated."
        ),
    }


def apply_repo_automation_restoration_plan(
    codex_home: Path,
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply one previously authorized restoration plan and read every target back."""

    managed_ids = {str(spec["id"]) for spec in REPO_AUTOMATION_SPECS}
    states = plan.get("states") if isinstance(plan.get("states"), Mapping) else {}
    user_paused = (
        plan.get("user_paused")
        if isinstance(plan.get("user_paused"), Mapping)
        else {}
    )
    source_hashes = (
        plan.get("source_hashes")
        if isinstance(plan.get("source_hashes"), Mapping)
        else {}
    )
    target_hashes = (
        plan.get("target_hashes")
        if isinstance(plan.get("target_hashes"), Mapping)
        else {}
    )
    source_states = (
        plan.get("source_states")
        if isinstance(plan.get("source_states"), Mapping)
        else {}
    )
    source_user_paused = (
        plan.get("source_user_paused")
        if isinstance(plan.get("source_user_paused"), Mapping)
        else {}
    )
    issues: list[str] = []
    prepared_text: dict[str, str] = {}
    source_text: dict[str, str] = {}
    if plan.get("ok") is not True or any(
        set(mapping) != managed_ids
        for mapping in (
            states,
            user_paused,
            source_states,
            source_user_paused,
            source_hashes,
            target_hashes,
        )
    ):
        issues.append("restoration-plan-incomplete")
    if (
        plan.get("schema_version") != "khaos-brain.automation-restoration-plan.v1"
        or str(plan.get("plan_hash") or "") != _automation_restoration_plan_hash(plan)
    ):
        issues.append("restoration-plan-hash-mismatch")
    for automation_id in sorted(managed_ids):
        path = automation_toml_path(automation_id, codex_home)
        try:
            current_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            issues.append(f"restoration-preflight-unreadable:{automation_id}:{type(exc).__name__}")
            continue
        if _text_sha256(current_text) != str(source_hashes.get(automation_id) or ""):
            issues.append(f"restoration-source-changed:{automation_id}")
            continue
        source_text[automation_id] = current_text
        current_payload = _load_automation_toml(path)
        if (
            str(current_payload.get("status") or "").upper()
            != str(source_states.get(automation_id) or "").upper()
            or bool(current_payload.get("user_paused"))
            != bool(source_user_paused.get(automation_id))
        ):
            issues.append(f"restoration-source-state-changed:{automation_id}")
            continue
        target_text = _render_automation_state_text(
            current_text,
            str(states.get(automation_id) or ""),
            bool(user_paused.get(automation_id)),
        )
        if target_text is None or _text_sha256(target_text) != str(
            target_hashes.get(automation_id) or ""
        ):
            issues.append(f"restoration-target-hash-mismatch:{automation_id}")
            continue
        prepared_text[automation_id] = target_text
    if issues or set(prepared_text) != managed_ids:
        return {
            "ok": False,
            "restored": {},
            "restored_user_paused": {},
            "applied_hashes": {},
            "plan_hash": str(plan.get("plan_hash") or ""),
            "issues": issues or ["restoration-preflight-incomplete"],
        }
    write_failed = False
    rollback_issues: list[str] = []
    try:
        for automation_id in sorted(managed_ids):
            _write_text_atomic(
                automation_toml_path(automation_id, codex_home),
                prepared_text[automation_id],
            )
    except OSError as exc:
        write_failed = True
        issues.append(f"restoration-write-failed:{type(exc).__name__}:{exc}")
        # A four-file restoration is one logical activation. Compensate a
        # partial write immediately instead of leaving a mixed live set for a
        # caller to discover later.  The preflight source bytes are already
        # hash-bound by the authorized plan.
        for automation_id in sorted(managed_ids):
            try:
                _write_text_atomic(
                    automation_toml_path(automation_id, codex_home),
                    source_text[automation_id],
                )
            except OSError as rollback_exc:
                rollback_issues.append(
                    "restoration-rollback-write-failed:"
                    f"{automation_id}:{type(rollback_exc).__name__}:{rollback_exc}"
                )
        if rollback_issues:
            # Last-resort safety boundary: no survivor may remain active after
            # an incomplete group activation, even when exact byte rollback
            # itself encounters an I/O failure.
            for automation_id in sorted(managed_ids):
                if not _set_automation_status_atomic(
                    automation_toml_path(automation_id, codex_home), "PAUSED"
                ):
                    rollback_issues.append(
                        f"restoration-emergency-pause-failed:{automation_id}"
                    )
        issues.extend(rollback_issues)
    restored: dict[str, str] = {}
    restored_user_paused: dict[str, bool] = {}
    applied_hashes: dict[str, str] = {}
    for automation_id in sorted(managed_ids):
        path = automation_toml_path(automation_id, codex_home)
        payload = _load_automation_toml(path)
        try:
            applied_hash = _text_sha256(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            applied_hash = ""
        status = str(payload.get("status") or "").upper()
        pause_value = bool(payload.get("user_paused"))
        if (
            status != str(states.get(automation_id) or "").upper()
            or pause_value != bool(user_paused.get(automation_id))
            or applied_hash != str(target_hashes.get(automation_id) or "")
        ):
            issues.append(f"restoration-readback-mismatch:{automation_id}")
            continue
        restored[automation_id] = status
        restored_user_paused[automation_id] = pause_value
        applied_hashes[automation_id] = applied_hash
    return {
        "ok": not issues and set(restored) == managed_ids,
        "restored": restored,
        "restored_user_paused": restored_user_paused,
        "applied_hashes": applied_hashes,
        "plan_hash": str(plan.get("plan_hash") or ""),
        "issues": issues,
        "rollback": {
            "attempted": write_failed,
            "ok": write_failed and not rollback_issues,
            "issues": rollback_issues,
        },
        "claim_boundary": "Exact authorized target bytes plus immediate live readback.",
    }


def pause_repo_automations(codex_home: Path) -> dict[str, Any]:
    paused = _pause_installed_kb_automations(codex_home)
    expected = {
        automation_id
        for automation_id in (
            *(str(spec["id"]) for spec in REPO_AUTOMATION_SPECS),
            *RETIRED_AUTOMATION_IDS,
        )
        if automation_toml_path(automation_id, codex_home).is_file()
    }
    return {
        "ok": expected.issubset(set(paused)),
        "expected_ids": sorted(expected),
        "paused_ids": sorted(set(paused) & expected),
    }


def restore_repo_automation_states(
    codex_home: Path,
    states: Mapping[str, str],
    *,
    user_paused_states: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    restored: dict[str, str] = {}
    restored_user_paused: dict[str, bool] = {}
    errors: list[str] = []
    managed_ids = {str(spec["id"]) for spec in REPO_AUTOMATION_SPECS}
    for automation_id, status_value in states.items():
        if automation_id not in managed_ids:
            errors.append(f"unmanaged automation id in restoration snapshot: {automation_id}")
            continue
        status = str(status_value or "").upper()
        if status not in {"ACTIVE", "PAUSED"}:
            errors.append(f"invalid restoration status for {automation_id}: {status}")
            continue
        path = automation_toml_path(automation_id, codex_home)
        user_paused = (
            bool(user_paused_states.get(automation_id))
            if user_paused_states is not None
            else None
        )
        restored_ok = (
            _set_automation_state_atomic(path, status, user_paused)
            if user_paused is not None
            else _set_automation_status_atomic(path, status)
        )
        if not restored_ok:
            errors.append(f"failed to restore automation status: {automation_id}")
            continue
        restored[automation_id] = status
        if user_paused is not None:
            restored_user_paused[automation_id] = user_paused
    expected = {key for key in states if key in managed_ids}
    return {
        "ok": not errors and set(restored) == expected,
        "restored": restored,
        "restored_user_paused": restored_user_paused,
        "errors": errors,
    }


def _automation_toml_text(payload: Mapping[str, Any]) -> str:
    # Codex owns the live automation document schema and normalizes unknown
    # keys away. Khaos-only policy and user-pause evidence therefore belongs
    # in the attempt-bound pre-pause snapshot, while this renderer emits only
    # the durable Codex automation surface.
    lines = [
        f"version = {int(payload['version'])}",
        f"id = {json.dumps(payload['id'], ensure_ascii=False)}",
        f"kind = {json.dumps(payload['kind'], ensure_ascii=False)}",
        f"name = {json.dumps(payload['name'], ensure_ascii=False)}",
        f"prompt = {json.dumps(payload['prompt'], ensure_ascii=False)}",
        f"status = {json.dumps(payload['status'], ensure_ascii=False)}",
        f"rrule = {json.dumps(payload['rrule'], ensure_ascii=False)}",
        f"model = {json.dumps(payload['model'], ensure_ascii=False)}",
        f"reasoning_effort = {json.dumps(payload['reasoning_effort'], ensure_ascii=False)}",
        f"execution_environment = {json.dumps(payload['execution_environment'], ensure_ascii=False)}",
        f"cwds = {json.dumps(list(payload['cwds']), ensure_ascii=False)}",
        f"created_at = {int(payload['created_at'])}",
        f"updated_at = {int(payload['updated_at'])}",
    ]
    return "\n".join(lines) + "\n"


def install_repo_maintenance_skills(repo_root: Path, codex_home: Path | None = None) -> list[dict[str, Any]]:
    del repo_root, codex_home
    raise RuntimeError(
        "Partial managed-Skill installation is retired; use install_codex_integration() "
        "so Skills, automations, retirement, parity, and rollback share one transaction."
    )


def install_repo_automations(repo_root: Path, codex_home: Path | None = None) -> list[dict[str, Any]]:
    del repo_root, codex_home
    raise RuntimeError(
        "Partial managed-automation installation is retired; use install_codex_integration() "
        "so Skills, automations, retirement, parity, and rollback share one transaction."
    )


def _freeze_flowguard_validation_toolchain(
    destination: Path,
    *,
    source_root: Path | None = None,
    max_attempts: int = 20,
) -> dict[str, Any]:
    """Freeze the complete imported FlowGuard package for every child process."""

    inherited_root = os.environ.get(FLOWGUARD_VALIDATION_ROOT_ENV, "").strip()
    inherited_digest = os.environ.get(FLOWGUARD_VALIDATION_DIGEST_ENV, "").strip()
    if source_root is None and inherited_root and inherited_digest:
        root = Path(inherited_root).resolve()
        manifest = tree_manifest(root) if root.is_dir() else {}
        if (
            str(manifest.get("digest") or "") == inherited_digest
            and (root / "__init__.py").is_file()
        ):
            receipt = {
                "schema_version": "khaos-brain.flowguard-validation-toolchain.v1",
                "ok": True,
                "status": "inherited_frozen",
                "source_root": str(root),
                "snapshot_root": str(root),
                "manifest": manifest,
            }
            receipt["receipt_hash"] = _canonical_payload_hash(receipt)
            return receipt

    if source_root is None:
        spec = importlib.util.find_spec("flowguard")
        locations = list(spec.submodule_search_locations or ()) if spec else []
        source_root = Path(locations[0]).resolve() if locations else None
    source = Path(source_root).resolve() if source_root is not None else None
    if source is None or not (source / "__init__.py").is_file():
        raise RuntimeError("Current FlowGuard package is unavailable for validation freeze")

    destination = destination.resolve()
    staging = destination.with_name(f".{destination.name}.staging")
    last_error = "flowguard_source_unavailable"
    for attempt in range(1, max_attempts + 1):
        try:
            before = tree_manifest(source)
            if staging.exists():
                shutil.rmtree(staging)
            staging.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                source,
                staging,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
            after = tree_manifest(source)
            snapshot = tree_manifest(staging)
            if not (
                before == after == snapshot
                and (staging / "__init__.py").is_file()
            ):
                last_error = "flowguard_source_changed_during_snapshot"
                shutil.rmtree(staging, ignore_errors=True)
                time.sleep(0.5)
                continue
            if destination.exists():
                shutil.rmtree(destination)
            os.replace(staging, destination)
            receipt = {
                "schema_version": "khaos-brain.flowguard-validation-toolchain.v1",
                "ok": True,
                "status": "frozen",
                "attempt_count": attempt,
                "source_root": str(source),
                "snapshot_root": str(destination),
                "manifest": snapshot,
            }
            receipt["receipt_hash"] = _canonical_payload_hash(receipt)
            receipt_path = destination.parent / "flowguard-validation-toolchain.json"
            _write_text_atomic(
                receipt_path,
                json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
            )
            receipt["receipt_path"] = str(receipt_path)
            return receipt
        except OSError as exc:
            last_error = f"{type(exc).__name__}:{exc}"
            shutil.rmtree(staging, ignore_errors=True)
            time.sleep(0.5)
    raise RuntimeError(
        "Unable to freeze one current FlowGuard validation toolchain: " + last_error
    )


def _require_live_flowguard_matches_snapshot(receipt: Mapping[str, Any]) -> None:
    source = Path(str(receipt.get("source_root") or ""))
    expected = str((receipt.get("manifest") or {}).get("digest") or "")
    actual = tree_manifest(source) if source.is_dir() else {}
    if not expected or str(actual.get("digest") or "") != expected:
        raise RuntimeError(
            "Live FlowGuard identity changed after validation snapshot; "
            "restart the idempotent upgrade against one current toolchain identity."
        )


def _freeze_researchguard_logic_validation_toolchain(
    destination: Path,
    *,
    source_root: Path | None = None,
    max_attempts: int = 20,
) -> dict[str, Any]:
    """Freeze the exact ResearchGuard package that owns current logic authority."""

    dependency: dict[str, Any] = {}
    if source_root is None:
        from local_kb.logicguard_models import (
            researchguard_logic_dependency_preflight,
        )

        dependency = researchguard_logic_dependency_preflight(
            require_no_retired_standalone=True
        )

    inherited_root = os.environ.get(
        RESEARCHGUARD_LOGIC_VALIDATION_ROOT_ENV, ""
    ).strip()
    inherited_digest = os.environ.get(
        RESEARCHGUARD_LOGIC_VALIDATION_DIGEST_ENV, ""
    ).strip()
    if source_root is None and inherited_root and inherited_digest:
        root = Path(inherited_root).resolve()
        manifest = tree_manifest(root) if root.is_dir() else {}
        if (
            str(manifest.get("digest") or "") == inherited_digest
            and (root / "__init__.py").is_file()
            and (root / "logic" / "__init__.py").is_file()
        ):
            receipt = {
                "schema_version": (
                    "khaos-brain.researchguard-logic-validation-toolchain.v1"
                ),
                "ok": True,
                "status": "inherited_frozen",
                "source_root": str(root),
                "snapshot_root": str(root),
                "manifest": manifest,
                "dependency": dependency,
            }
            receipt["receipt_hash"] = _canonical_payload_hash(receipt)
            return receipt

    if source_root is None:
        module = importlib.import_module("researchguard")
        source_root = Path(str(module.__file__)).resolve().parent
    source = Path(source_root).resolve() if source_root is not None else None
    if (
        source is None
        or not (source / "__init__.py").is_file()
        or not (source / "logic" / "__init__.py").is_file()
    ):
        raise RuntimeError(
            "Current ResearchGuard package is unavailable for logic validation freeze"
        )

    destination = destination.resolve()
    staging = destination.with_name(f".{destination.name}.staging")
    last_error = "researchguard_source_unavailable"
    for attempt in range(1, max_attempts + 1):
        try:
            before = tree_manifest(source)
            if staging.exists():
                shutil.rmtree(staging)
            staging.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                source,
                staging,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
            after = tree_manifest(source)
            snapshot = tree_manifest(staging)
            if not (
                before == after == snapshot
                and (staging / "__init__.py").is_file()
                and (staging / "logic" / "__init__.py").is_file()
            ):
                last_error = "researchguard_source_changed_during_snapshot"
                shutil.rmtree(staging, ignore_errors=True)
                time.sleep(0.5)
                continue
            if destination.exists():
                shutil.rmtree(destination)
            os.replace(staging, destination)
            receipt = {
                "schema_version": (
                    "khaos-brain.researchguard-logic-validation-toolchain.v1"
                ),
                "ok": True,
                "status": "frozen",
                "attempt_count": attempt,
                "source_root": str(source),
                "snapshot_root": str(destination),
                "manifest": snapshot,
                "dependency": dependency,
            }
            receipt["receipt_hash"] = _canonical_payload_hash(receipt)
            receipt_path = (
                destination.parent
                / "researchguard-logic-validation-toolchain.json"
            )
            _write_text_atomic(
                receipt_path,
                json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
            )
            receipt["receipt_path"] = str(receipt_path)
            return receipt
        except OSError as exc:
            last_error = f"{type(exc).__name__}:{exc}"
            shutil.rmtree(staging, ignore_errors=True)
            time.sleep(0.5)
    raise RuntimeError(
        "Unable to freeze one current ResearchGuard logic validation toolchain: "
        + last_error
    )


def _require_live_researchguard_logic_matches_snapshot(
    receipt: Mapping[str, Any],
) -> None:
    source = Path(str(receipt.get("source_root") or ""))
    expected = str((receipt.get("manifest") or {}).get("digest") or "")
    actual = tree_manifest(source) if source.is_dir() else {}
    if not expected or str(actual.get("digest") or "") != expected:
        raise RuntimeError(
            "Live ResearchGuard logic identity changed after validation snapshot; "
            "restart the idempotent upgrade against one current toolchain identity."
        )


def _run_pre_restore_upgrade_assurance(
    repo_root: Path,
    codex_home: Path,
    *,
    flowguard_validation_toolchain: Mapping[str, Any],
    researchguard_logic_validation_toolchain: Mapping[str, Any],
) -> dict[str, Any]:
    script = repo_root / "scripts" / "check_consumer_install_assurance.py"
    environment = os.environ.copy()
    environment[INSTALLATION_IDENTITY_PYTHON_EXECUTABLE_ENV] = sys.executable
    flowguard_root = Path(
        str(flowguard_validation_toolchain.get("snapshot_root") or "")
    ).resolve()
    environment[FLOWGUARD_VALIDATION_ROOT_ENV] = str(flowguard_root)
    environment[FLOWGUARD_VALIDATION_DIGEST_ENV] = str(
        (flowguard_validation_toolchain.get("manifest") or {}).get("digest") or ""
    )
    researchguard_root = Path(
        str(
            researchguard_logic_validation_toolchain.get("snapshot_root")
            or ""
        )
    ).resolve()
    environment[RESEARCHGUARD_LOGIC_VALIDATION_ROOT_ENV] = str(
        researchguard_root
    )
    environment[RESEARCHGUARD_LOGIC_VALIDATION_DIGEST_ENV] = str(
        (
            researchguard_logic_validation_toolchain.get("manifest") or {}
        ).get("digest")
        or ""
    )
    existing_pythonpath = environment.get("PYTHONPATH", "")
    if INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV not in environment:
        environment[INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV] = (
            "1" if "PYTHONPATH" in environment else "0"
        )
        environment[INSTALLATION_IDENTITY_PYTHONPATH_VALUE_ENV] = existing_pythonpath
    validation_parents = (
        str(flowguard_root.parent),
        str(researchguard_root.parent),
    )
    pythonpath_parts = [part for part in existing_pythonpath.split(os.pathsep) if part]
    for parent in reversed(validation_parents):
        normalized_parent = os.path.normcase(os.path.normpath(parent))
        pythonpath_parts = [
            part
            for part in pythonpath_parts
            if os.path.normcase(os.path.normpath(part)) != normalized_parent
        ]
        pythonpath_parts.insert(0, parent)
    environment["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [
        sys.executable,
        str(script),
        "--json",
        "--repo-root",
        str(repo_root),
        "--codex-home",
        str(codex_home),
        "--evidence-root",
        str(
            codex_home
            / ".khaos-brain-install"
            / "consumer-assurance"
        ),
    ]
    try:
        process = run_with_timeout_cleanup(
            command,
            cwd=str(repo_root),
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PRE_RESTORE_ASSURANCE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        cleanup = dict(getattr(exc, "cleanup_receipt", {}) or {})
        raise RuntimeError(
            "Chaos Brain pre-restore assurance timed out; descendant cleanup: "
            + json.dumps(cleanup, ensure_ascii=False, sort_keys=True)
        ) from exc
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError:
        payload = {}
    if (
        process.returncode != 0
        or payload.get("schema_version")
        != "khaos-brain.consumer-install-assurance.v2"
        or not bool(payload.get("ok"))
    ):
        failed_checks = list(payload.get("failed_checks") or [])
        entries = (
            payload.get("owners")
            if isinstance(payload.get("owners"), Mapping)
            else {}
        )
        failure_details: dict[str, dict[str, Any]] = {}
        for name in failed_checks:
            entry = entries.get(name) if isinstance(entries, Mapping) else None
            if not isinstance(entry, Mapping):
                continue
            detail: dict[str, Any] = {
                "terminal_status": str(entry.get("terminal_status") or ""),
                "exit_code": entry.get("exit_code"),
                "timed_out": bool(entry.get("timed_out")),
                "cleanup_confirmed": entry.get("cleanup_confirmed"),
            }
            junit = entry.get("junit") if isinstance(entry.get("junit"), Mapping) else {}
            if junit:
                detail["junit"] = {
                    "testcase_count": int(junit.get("testcase_count") or 0),
                    "passed_count": len(junit.get("passed_node_ids") or []),
                    "failed_node_ids": list(junit.get("failed_node_ids") or [])[:8],
                    "errored_node_ids": list(junit.get("errored_node_ids") or [])[:8],
                    "skipped_node_ids": list(junit.get("skipped_node_ids") or [])[:8],
                    "unparsed_cases": list(junit.get("unparsed_cases") or [])[:12],
                    "parse_error": str(junit.get("parse_error") or ""),
                }
            json_payload = (
                entry.get("json_payload")
                if isinstance(entry.get("json_payload"), Mapping)
                else {}
            )
            skill_rows = (
                json_payload.get("skills")
                if isinstance(json_payload.get("skills"), Mapping)
                else {}
            )
            report_checks = (
                json_payload.get("checks")
                if isinstance(json_payload.get("checks"), list)
                else []
            )
            failed_report_check_ids = [
                str(row.get("id") or "")
                for row in report_checks
                if isinstance(row, Mapping) and row.get("ok") is not True
            ]
            if failed_report_check_ids:
                detail["failed_report_check_ids"] = failed_report_check_ids
            alignment_report = (
                entry.get("report")
                if isinstance(entry.get("report"), Mapping)
                else {}
            )
            if alignment_report:
                alignment = (
                    alignment_report.get("alignment")
                    if isinstance(alignment_report.get("alignment"), Mapping)
                    else {}
                )
                blocked_bindings = []
                for row in list(alignment.get("binding_rows") or []):
                    if not isinstance(row, Mapping) or row.get("status") == "aligned":
                        continue
                    blocked_bindings.append(
                        {
                            "model_obligation_id": str(
                                row.get("model_obligation_id") or ""
                            ),
                            "status": str(row.get("status") or ""),
                            "open_gap_codes": list(
                                row.get("open_gap_codes") or row.get("gaps") or []
                            )[:6],
                        }
                    )
                detail["alignment_report"] = {
                    "ok": alignment_report.get("ok") is True,
                    "decision": str(alignment.get("decision") or ""),
                    "summary": str(alignment.get("summary") or "")[:600],
                    "receipt_findings": list(
                        alignment_report.get("receipt_findings") or []
                    )[:12],
                    "findings": list(alignment.get("findings") or [])[:12],
                    "blocked_bindings": blocked_bindings[:12],
                }
            capability_summary: dict[str, Any] = {}
            scheduled_production_failures: dict[str, Any] = {}
            capability_count = 0
            capability_ok_count = 0
            for skill_id, skill_row in skill_rows.items():
                if not isinstance(skill_row, Mapping):
                    continue
                execution = (
                    skill_row.get("executed_supervision")
                    if isinstance(skill_row.get("executed_supervision"), Mapping)
                    else {}
                )
                scheduled_production = (
                    execution.get("scheduled_production")
                    if isinstance(execution.get("scheduled_production"), Mapping)
                    else {}
                )
                if scheduled_production and scheduled_production.get("ok") is not True:
                    scheduled_production_failures[str(skill_id)] = {
                        "exit_code": scheduled_production.get("exit_code"),
                        "status": str(scheduled_production.get("status") or ""),
                        "checkpoint": str(
                            scheduled_production.get("checkpoint") or ""
                        ),
                        "error": str(scheduled_production.get("error") or "")[:400],
                        "blockers": list(
                            scheduled_production.get("blockers") or []
                        )[:4],
                        "issues": list(scheduled_production.get("issues") or [])[:4],
                        "top_level_keys": sorted(
                            str(key) for key in scheduled_production
                        ),
                    }
                capability = (
                    execution.get("capability_regression")
                    if isinstance(execution.get("capability_regression"), Mapping)
                    else {}
                )
                if not capability:
                    continue
                capability_count += 1
                missing = list(capability.get("missing_node_ids") or [])
                unsafe = list(capability.get("unsafe_declared_node_ids") or [])
                capability_ok = capability.get("ok") is True
                if capability_ok:
                    capability_ok_count += 1
                    continue
                capability_summary[str(skill_id)] = {
                    "ok": False,
                    "receipt_terminal": bool(capability.get("receipt_terminal")),
                    "identity_current": bool(capability.get("identity_current")),
                    "proof_current": bool(capability.get("proof_current")),
                    "junit_current": bool(capability.get("junit_current")),
                    "missing_count": len(missing),
                    "missing_node_ids": missing[:4],
                    "unsafe_count": len(unsafe),
                    "unsafe_declared_node_ids": unsafe[:4],
                }
            if capability_count:
                detail["capability_count"] = capability_count
                detail["capability_ok_count"] = capability_ok_count
            if capability_summary:
                detail["capability_summary"] = capability_summary
            if scheduled_production_failures:
                detail["scheduled_production_failures"] = (
                    scheduled_production_failures
                )
            if (
                not junit
                and not capability_summary
                and not failed_report_check_ids
                and not scheduled_production_failures
                and not alignment_report
            ):
                detail["stdout_tail"] = str(entry.get("stdout_tail") or "")[-600:]
                detail["stderr_tail"] = str(entry.get("stderr_tail") or "")[-600:]
            failure_details[str(name)] = detail
        raise RuntimeError(
            "Chaos Brain pre-restore assurance failed: "
            + json.dumps(
                {
                    "failed_checks": failed_checks,
                    "failure_details": failure_details,
                    "process_diagnostic": (
                        str(process.stderr or process.stdout[-4000:])
                        if not failed_checks
                        else ""
                    ),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return payload


def _install_codex_integration_impl(
    repo_root: Path,
    codex_home: Path | None = None,
    *,
    shell_bin_dir: Path | None = None,
    git_executable: str | Path | None = None,
    rg_source: str | Path | None = None,
    persist_user_shell_path: bool = True,
    original_automation_configs: Mapping[str, Mapping[str, Any]] | None = None,
    history_migration: Mapping[str, Any] | None = None,
    safe_upgrade: bool = False,
    require_upgrade_assurance: bool = False,
    defer_automation_restore: bool = False,
    upgrade_attempt_id: str = "",
    flowguard_validation_toolchain: Mapping[str, Any] | None = None,
    researchguard_logic_validation_toolchain: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    home = codex_home or default_codex_home()
    initial_history_migration = dict(history_migration or {})
    pre_assurance_update_state_migration: dict[str, Any] = {}
    skill_dir = global_skill_dir(home)
    launcher_path = skill_dir / "kb_launch.py"
    skill_path = skill_dir / "SKILL.md"
    openai_path = skill_dir / "agents" / "openai.yaml"
    replacements = {
        "KB_ROOT": str(repo_root),
        "LAUNCHER_PATH": str(launcher_path),
        "ENV_VAR_NAME": KB_ROOT_ENV_VAR,
    }
    global_skill_files = {
        "SKILL.md": _render_template(_read_template(repo_root, "SKILL.md.template"), replacements),
        "kb_launch.py": _read_template(repo_root, "kb_launch.py"),
        "agents/openai.yaml": _read_template(repo_root, Path("agents") / "openai.yaml"),
    }
    flowguard_toolchain = dict(flowguard_validation_toolchain or {})
    flowguard_validation_root = Path(
        str(flowguard_toolchain.get("snapshot_root") or "")
    )
    if not (flowguard_validation_root / "__init__.py").is_file():
        raise RuntimeError("Frozen FlowGuard validation toolchain is unavailable")
    researchguard_logic_toolchain = dict(
        researchguard_logic_validation_toolchain or {}
    )
    researchguard_validation_root = Path(
        str(researchguard_logic_toolchain.get("snapshot_root") or "")
    )
    if not (researchguard_validation_root / "__init__.py").is_file():
        raise RuntimeError(
            "Frozen ResearchGuard logic validation toolchain is unavailable"
        )
    now_ms = int(time.time() * 1000)
    automation_payloads: dict[str, dict[str, Any]] = {}
    for spec in REPO_AUTOMATION_SPECS:
        existing = dict(
            (original_automation_configs or {}).get(str(spec["id"]), {})
        ) or _load_automation_toml(automation_toml_path(spec["id"], home))
        payload = _automation_spec_payload(spec, repo_root, codex_home=home, existing=existing)
        payload["created_at"] = int(existing.get("created_at") or now_ms)
        payload["updated_at"] = now_ms
        automation_payloads[str(spec["id"])] = payload
    paused_transaction: dict[str, Any] = {}
    activation_payloads: Mapping[str, Mapping[str, Any]] = automation_payloads
    if safe_upgrade:
        activation_payloads = {
            automation_id: {
                **payload,
                "status": "PAUSED",
            }
            for automation_id, payload in automation_payloads.items()
        }
    transaction = install_managed_runtime(
        repo_root=repo_root,
        codex_home=home,
        global_skill_name=GLOBAL_SKILL_NAME,
        global_skill_files=global_skill_files,
        skill_sources={
            str(spec["name"]): maintenance_skill_source_dir(repo_root, str(spec["name"]))
            for spec in MAINTENANCE_SKILL_SPECS
        },
        automation_payloads=activation_payloads,
        automation_renderer=_automation_toml_text,
        retired_skill_ids=RETIRED_MAINTENANCE_SKILL_IDS,
        retired_automation_ids=RETIRED_AUTOMATION_IDS,
    )
    if safe_upgrade:
        paused_transaction = transaction
        from local_kb.software_update import migrate_obsolete_update_state

        pre_assurance_update_state_migration = migrate_obsolete_update_state(
            repo_root,
            install_receipt=_committed_install_receipt_projection(
                paused_transaction
            ),
        )
        if (
            pre_assurance_update_state_migration.get("ok") is not True
            or int(
                pre_assurance_update_state_migration.get(
                    "residual_retired_state_count", 0
                )
                or 0
            )
            != 0
        ):
            raise RuntimeError(
                "Obsolete update state did not converge before aggregate assurance"
            )
        if upgrade_attempt_id:
            _record_upgrade_attempt(
                home,
                upgrade_attempt_id,
                phase="paused_install_transaction_committed",
                status="in_progress",
                details={
                    "paused_install_transaction": transaction,
                    "pre_assurance_update_state_migration": (
                        pre_assurance_update_state_migration
                    ),
                    "survivors_must_remain_paused": True,
                },
            )
    global_agents = install_global_agents_defaults(repo_root=repo_root, codex_home=home)
    maintenance_skills = [
        {
            "name": str(spec["name"]),
            "source_path": str(maintenance_skill_source_dir(repo_root, str(spec["name"]))),
            "install_path": str(maintenance_skill_install_dir(str(spec["name"]), home)),
            "skill_path": str(maintenance_skill_install_dir(str(spec["name"]), home) / "SKILL.md"),
            "openai_path": str(maintenance_skill_install_dir(str(spec["name"]), home) / "agents" / "openai.yaml"),
            "automation_id": str(spec["automation_id"]),
        }
        for spec in MAINTENANCE_SKILL_SPECS
    ]
    shell_tools = install_codex_shell_tools(
        shell_bin_dir=shell_bin_dir,
        git_executable=git_executable,
        rg_source=rg_source,
        persist_user_path=persist_user_shell_path,
    )
    upgrade_assurance: dict[str, Any] = {}
    if safe_upgrade:
        if upgrade_attempt_id:
            _record_upgrade_attempt(
                home,
                upgrade_attempt_id,
                phase="pre_assurance_consumer_projection_current",
                status="in_progress",
                details={
                    "consumer_projection_independent": True,
                    "survivors_must_remain_paused": True,
                },
            )
        if require_upgrade_assurance:
            # Do not spend a long aggregate campaign against a validation
            # toolchain that is already stale.  A change that happens during
            # the campaign is still caught by the identical restore-gate
            # checks below; neither case authorizes reinstalling that tool.
            _require_live_flowguard_matches_snapshot(flowguard_toolchain)
            _require_live_researchguard_logic_matches_snapshot(
                researchguard_logic_toolchain
            )
            upgrade_assurance = _run_pre_restore_upgrade_assurance(
                repo_root,
                home,
                flowguard_validation_toolchain=flowguard_toolchain,
                researchguard_logic_validation_toolchain=(
                    researchguard_logic_toolchain
                ),
            )
            if upgrade_attempt_id:
                _record_upgrade_attempt(
                    home,
                    upgrade_attempt_id,
                    phase="affected_assurance_stable",
                    status="in_progress",
                    details={
                        "upgrade_assurance": upgrade_assurance,
                        "survivors_must_remain_paused": True,
                    },
                )
            # The assurance planner fingerprints every declared owner input
            # before and after execution. If a concurrent writer changes one
            # of those inputs, only the affected owners are replanned inside
            # that single campaign. A second unconditional migration or
            # retrieval pass would duplicate ownership and is forbidden.
        # This second all-or-nothing transaction is the restore gate.  If it
        # fails, rollback returns to the already-validated paused runtime.
        final_activation_payloads = (
            activation_payloads if defer_automation_restore else automation_payloads
        )
        _require_live_flowguard_matches_snapshot(flowguard_toolchain)
        _require_live_researchguard_logic_matches_snapshot(
            researchguard_logic_toolchain
        )
        transaction = install_managed_runtime(
            repo_root=repo_root,
            codex_home=home,
            global_skill_name=GLOBAL_SKILL_NAME,
            global_skill_files=global_skill_files,
            skill_sources={
                str(spec["name"]): maintenance_skill_source_dir(repo_root, str(spec["name"]))
                for spec in MAINTENANCE_SKILL_SPECS
            },
            automation_payloads=final_activation_payloads,
            automation_renderer=_automation_toml_text,
            retired_skill_ids=RETIRED_MAINTENANCE_SKILL_IDS,
            retired_automation_ids=RETIRED_AUTOMATION_IDS,
        )
        if upgrade_attempt_id:
            _record_upgrade_attempt(
                home,
                upgrade_attempt_id,
                phase="final_install_transaction_committed",
                status="in_progress",
                details={
                    "install_transaction": transaction,
                    "survivors_must_remain_paused": bool(defer_automation_restore),
                },
            )
        if upgrade_attempt_id:
            _record_upgrade_attempt(
                home,
                upgrade_attempt_id,
                phase="final_consumer_projection_current",
                status="ready_for_install_check",
                details={
                    "consumer_projection_independent": True,
                    "survivors_must_remain_paused": bool(defer_automation_restore),
                },
            )
    automation_runtime = resolve_automation_runtime(home)
    automations = [
        {
            "id": automation_id,
            "kind": payload["kind"],
            "name": payload["name"],
            "path": str(automation_toml_path(automation_id, home)),
            "status": payload["status"],
            "user_paused": bool(payload.get("user_paused")),
            "rrule": payload["rrule"],
            "schedule_policy": payload["schedule_policy"],
            "schedule_window": payload["schedule_window"],
            "model": payload["model"],
            "reasoning_effort": payload["reasoning_effort"],
            "model_policy": payload["model_policy"],
            "reasoning_effort_policy": payload["reasoning_effort_policy"],
            "execution_environment": payload["execution_environment"],
            "cwds": list(payload["cwds"]),
        }
        for automation_id, payload in sorted(automation_payloads.items())
    ]
    installed_automation_statuses = {
        automation_id: str(
            (activation_payloads if defer_automation_restore else automation_payloads)[automation_id]["status"]
        )
        for automation_id in sorted(automation_payloads)
    }

    manifest = {
        "repo_root": str(repo_root),
        "codex_home": str(home),
        "skill_name": GLOBAL_SKILL_NAME,
        "skill_dir": str(skill_dir),
        "skill_path": str(skill_path),
        "launcher_path": str(launcher_path),
        "openai_path": str(openai_path),
        "global_agents_path": global_agents,
        "env_var_name": KB_ROOT_ENV_VAR,
        "maintenance_skill_names": list(MAINTENANCE_SKILL_NAMES),
        "maintenance_skills": maintenance_skills,
        "shell_tools": shell_tools,
        "automation_runtime": automation_runtime,
        "automation_ids": [item["id"] for item in automations],
        "automations": automations,
        "installed_automation_statuses": installed_automation_statuses,
        "automation_restore_deferred": bool(defer_automation_restore),
        "flowguard_validation_toolchain": flowguard_toolchain,
        "researchguard_logic_validation_toolchain": (
            researchguard_logic_toolchain
        ),
        "install_transaction": transaction,
        "paused_install_transaction": paused_transaction,
        "history_migration_required": bool(safe_upgrade),
        "history_migration": dict(history_migration or {}),
        "initial_history_migration": initial_history_migration,
        "pre_assurance_update_state_migration": (
            pre_assurance_update_state_migration
        ),
        "upgrade_assurance_required": bool(require_upgrade_assurance),
        "upgrade_assurance": upgrade_assurance,
        "upgrade_attempt": (
            latest_upgrade_attempt(home) if upgrade_attempt_id else {}
        ),
        "retired_skill_ids": list(RETIRED_MAINTENANCE_SKILL_IDS),
        "retired_automation_ids": list(RETIRED_AUTOMATION_IDS),
        "installed_at": utc_now_iso(),
    }
    return manifest


def install_codex_integration(
    repo_root: Path,
    codex_home: Path | None = None,
    *,
    shell_bin_dir: Path | None = None,
    git_executable: str | Path | None = None,
    rg_source: str | Path | None = None,
    persist_user_shell_path: bool = True,
    run_history_migration: bool = True,
    run_upgrade_assurance: bool = True,
    defer_automation_restore: bool = False,
    automation_state_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Install or upgrade Chaos Brain with migration-pause fail safety.

    The two ``False`` switches exist only for isolated installer fixtures whose
    repository root is the live source tree but whose Codex home is a temporary
    sandbox. Product entrypoints always use both default hard gates.
    """

    home = (codex_home or default_codex_home()).resolve()
    root = Path(repo_root).resolve()
    if not run_history_migration:
        if codex_home is None or home == default_codex_home().resolve():
            raise RuntimeError(
                "isolated installer fixture mode requires an explicit non-default codex_home"
            )
        if shell_bin_dir is None:
            raise RuntimeError(
                "isolated installer fixture mode requires an explicit shell_bin_dir"
            )
        if persist_user_shell_path:
            raise RuntimeError(
                "isolated installer fixture mode requires persist_user_shell_path=False"
            )
    expected_ids = {str(spec["id"]) for spec in REPO_AUTOMATION_SPECS}
    prior_attempt = latest_upgrade_attempt(home) if run_history_migration else {}
    effective_snapshot: Mapping[str, Any] | None = automation_state_snapshot
    snapshot_source = "explicit-direct-repair"
    if effective_snapshot is None:
        recovery_required = bool(
            prior_attempt.get("status") in {"failed", "in_progress"}
            and prior_attempt.get("survivors_must_remain_paused") is True
        )
        if recovery_required:
            recovered = prior_attempt.get("automation_state_snapshot")
            if not isinstance(recovered, Mapping):
                raise RuntimeError(
                    "recoverable upgrade attempt lacks its original automation "
                    "state snapshot; provide one explicit direct-repair snapshot"
                )
            effective_snapshot = recovered
            snapshot_source = "prior-upgrade-attempt"
        else:
            effective_snapshot = capture_repo_automation_state_snapshot(home)
            snapshot_source = "live-codex-runtime"
    states = effective_snapshot.get("states")
    user_paused_states = effective_snapshot.get("user_paused")
    if effective_snapshot.get("ok") is False:
        raise RuntimeError(
            "automation state snapshot is ambiguous: "
            + ", ".join(
                str(item)
                for item in list(effective_snapshot.get("ambiguities") or [])
            )
        )
    if not isinstance(states, Mapping) or not isinstance(
        user_paused_states, Mapping
    ):
        raise RuntimeError(
            "automation state snapshot is missing states or user_paused maps"
        )
    if set(states) != expected_ids or set(user_paused_states) != expected_ids:
        raise RuntimeError(
            "automation state snapshot does not cover the exact surviving automation set"
        )
    normalized_states: dict[str, str] = {}
    normalized_user_paused: dict[str, bool] = {}
    for automation_id in expected_ids:
        status = str(states.get(automation_id) or "").upper()
        if status not in {"ACTIVE", "PAUSED"}:
            raise RuntimeError(
                f"invalid automation snapshot status for {automation_id}: {status}"
            )
        if not isinstance(user_paused_states.get(automation_id), bool):
            raise RuntimeError(
                f"invalid automation user-pause intent for {automation_id}"
            )
        normalized_states[automation_id] = status
        normalized_user_paused[automation_id] = bool(
            user_paused_states[automation_id]
        )
    effective_snapshot = {
        "schema_version": "khaos-brain.automation-state-snapshot.v1",
        "ok": True,
        "states": normalized_states,
        "user_paused": normalized_user_paused,
        "sources": {
            automation_id: snapshot_source for automation_id in sorted(expected_ids)
        },
        "ambiguities": [],
    }
    original_configs: dict[str, dict[str, Any]] = {}
    for spec in REPO_AUTOMATION_SPECS:
        automation_id = str(spec["id"])
        original = _load_automation_toml(
            automation_toml_path(automation_id, home)
        )
        original_configs[automation_id] = {
            **original,
            "status": normalized_states[automation_id],
            "user_paused": normalized_user_paused[automation_id],
        }
    if defer_automation_restore and not run_history_migration:
        raise RuntimeError("deferred automation restoration requires the real migration gate")
    history_migration: dict[str, Any] = {
        "ok": False,
        "status": "fixture_skipped",
        "reason": "isolated installer fixture explicitly disabled repository migration",
    }
    paused_before_migration: list[str] = []
    pause_before_migration: dict[str, Any] = {
        "ok": True,
        "expected_ids": [],
        "paused_ids": [],
    }
    if run_history_migration:
        pause_before_migration = pause_repo_automations(home)
        paused_before_migration = list(pause_before_migration.get("paused_ids") or [])
        if pause_before_migration.get("ok") is not True:
            missing = sorted(
                set(pause_before_migration.get("expected_ids") or [])
                - set(pause_before_migration.get("paused_ids") or [])
            )
            raise RuntimeError(
                "failed to pause every installed Chaos Brain automation before migration: "
                + ", ".join(missing)
            )
        from local_kb.maintenance_migration import run_maintenance_migration

        history_migration = run_maintenance_migration(root)
        if not history_migration.get("ok"):
            raise RuntimeError(
                "Chaos Brain history migration paused failed: "
                + str(history_migration.get("error") or history_migration.get("status"))
            )
    upgrade_attempt: dict[str, Any] = {}
    if run_history_migration:
        upgrade_attempt = _start_upgrade_attempt(
            home,
            repo_root=root,
            pause_before_migration=pause_before_migration,
            history_migration=history_migration,
            automation_state_snapshot=effective_snapshot,
        )
    attempt_id = str(upgrade_attempt.get("attempt_id") or "")
    from local_kb.software_update import update_state_path

    obsolete_update_state_file = update_state_path(root)
    obsolete_update_state_before_existed = obsolete_update_state_file.is_file()
    obsolete_update_state_before_bytes = (
        obsolete_update_state_file.read_bytes()
        if obsolete_update_state_before_existed
        else b""
    )
    obsolete_update_state_settled = False
    try:
        snapshot_parent = (
            _upgrade_attempt_dir(home, attempt_id) / "validation-toolchain"
            if attempt_id
            else home / ".khaos-brain-install" / "fixture-validation-toolchain"
        )
        flowguard_toolchain = _freeze_flowguard_validation_toolchain(
            snapshot_parent / "python" / "flowguard"
        )
        researchguard_logic_toolchain = (
            _freeze_researchguard_logic_validation_toolchain(
                snapshot_parent / "python" / "researchguard"
            )
        )
        if attempt_id:
            _record_upgrade_attempt(
                home,
                attempt_id,
                phase="validation_toolchain_frozen",
                status="in_progress",
                details={
                    "flowguard_validation_toolchain": flowguard_toolchain,
                    "researchguard_logic_validation_toolchain": (
                        researchguard_logic_toolchain
                    ),
                    "consumer_skills_require_author_toolchain": False,
                    "survivors_must_remain_paused": True,
                },
            )
        previous_flowguard_root = os.environ.get(FLOWGUARD_VALIDATION_ROOT_ENV)
        previous_flowguard_digest = os.environ.get(
            FLOWGUARD_VALIDATION_DIGEST_ENV
        )
        previous_researchguard_root = os.environ.get(
            RESEARCHGUARD_LOGIC_VALIDATION_ROOT_ENV
        )
        previous_researchguard_digest = os.environ.get(
            RESEARCHGUARD_LOGIC_VALIDATION_DIGEST_ENV
        )
        previous_pythonpath = os.environ.get("PYTHONPATH")
        previous_installation_identity_pythonpath_present = os.environ.get(
            INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV
        )
        previous_installation_identity_pythonpath_value = os.environ.get(
            INSTALLATION_IDENTITY_PYTHONPATH_VALUE_ENV
        )
        previous_installation_identity_python_executable = os.environ.get(
            INSTALLATION_IDENTITY_PYTHON_EXECUTABLE_ENV
        )
        os.environ[INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV] = (
            "1" if "PYTHONPATH" in os.environ else "0"
        )
        os.environ[INSTALLATION_IDENTITY_PYTHONPATH_VALUE_ENV] = (
            previous_pythonpath or ""
        )
        os.environ[INSTALLATION_IDENTITY_PYTHON_EXECUTABLE_ENV] = sys.executable
        flowguard_root = Path(str(flowguard_toolchain["snapshot_root"])).resolve()
        os.environ[FLOWGUARD_VALIDATION_ROOT_ENV] = str(flowguard_root)
        os.environ[FLOWGUARD_VALIDATION_DIGEST_ENV] = str(
            flowguard_toolchain["manifest"]["digest"]
        )
        researchguard_root = Path(
            str(researchguard_logic_toolchain["snapshot_root"])
        ).resolve()
        os.environ[RESEARCHGUARD_LOGIC_VALIDATION_ROOT_ENV] = str(
            researchguard_root
        )
        os.environ[RESEARCHGUARD_LOGIC_VALIDATION_DIGEST_ENV] = str(
            researchguard_logic_toolchain["manifest"]["digest"]
        )
        os.environ["PYTHONPATH"] = os.pathsep.join(
            dict.fromkeys(
                part
                for part in (
                    str(flowguard_root.parent),
                    str(researchguard_root.parent),
                    previous_pythonpath or "",
                )
                if part
            )
        )
        try:
            payload = _install_codex_integration_impl(
                root,
                home,
                shell_bin_dir=shell_bin_dir,
                git_executable=git_executable,
                rg_source=rg_source,
                persist_user_shell_path=persist_user_shell_path,
                original_automation_configs=original_configs,
                history_migration=history_migration,
                safe_upgrade=run_history_migration,
                require_upgrade_assurance=(
                    run_history_migration and run_upgrade_assurance
                ),
                defer_automation_restore=defer_automation_restore,
                upgrade_attempt_id=attempt_id,
                flowguard_validation_toolchain=flowguard_toolchain,
                researchguard_logic_validation_toolchain=(
                    researchguard_logic_toolchain
                ),
            )
        finally:
            if previous_flowguard_root is None:
                os.environ.pop(FLOWGUARD_VALIDATION_ROOT_ENV, None)
            else:
                os.environ[FLOWGUARD_VALIDATION_ROOT_ENV] = previous_flowguard_root
            if previous_flowguard_digest is None:
                os.environ.pop(FLOWGUARD_VALIDATION_DIGEST_ENV, None)
            else:
                os.environ[FLOWGUARD_VALIDATION_DIGEST_ENV] = (
                    previous_flowguard_digest
                )
            if previous_researchguard_root is None:
                os.environ.pop(
                    RESEARCHGUARD_LOGIC_VALIDATION_ROOT_ENV, None
                )
            else:
                os.environ[RESEARCHGUARD_LOGIC_VALIDATION_ROOT_ENV] = (
                    previous_researchguard_root
                )
            if previous_researchguard_digest is None:
                os.environ.pop(
                    RESEARCHGUARD_LOGIC_VALIDATION_DIGEST_ENV, None
                )
            else:
                os.environ[RESEARCHGUARD_LOGIC_VALIDATION_DIGEST_ENV] = (
                    previous_researchguard_digest
                )
            if previous_pythonpath is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = previous_pythonpath
            if previous_installation_identity_pythonpath_present is None:
                os.environ.pop(
                    INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV, None
                )
            else:
                os.environ[INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV] = (
                    previous_installation_identity_pythonpath_present
                )
            if previous_installation_identity_pythonpath_value is None:
                os.environ.pop(INSTALLATION_IDENTITY_PYTHONPATH_VALUE_ENV, None)
            else:
                os.environ[INSTALLATION_IDENTITY_PYTHONPATH_VALUE_ENV] = (
                    previous_installation_identity_pythonpath_value
                )
            if previous_installation_identity_python_executable is None:
                os.environ.pop(
                    INSTALLATION_IDENTITY_PYTHON_EXECUTABLE_ENV, None
                )
            else:
                os.environ[INSTALLATION_IDENTITY_PYTHON_EXECUTABLE_ENV] = (
                    previous_installation_identity_python_executable
                )
        payload["automations_paused_before_migration"] = paused_before_migration
        payload["pause_before_migration"] = pause_before_migration
        if run_history_migration:
            from local_kb.software_update import migrate_obsolete_update_state

            obsolete_update_state_migration = migrate_obsolete_update_state(
                root,
                install_receipt=_committed_install_receipt_projection(
                    dict(payload.get("install_transaction") or {})
                ),
            )
            pre_assurance_update_state_migration = dict(
                payload.get("pre_assurance_update_state_migration") or {}
            )
            obsolete_update_state_settled = bool(
                pre_assurance_update_state_migration.get("status") == "committed"
                or obsolete_update_state_migration.get("status") == "committed"
            )
            payload["obsolete_update_state_migration"] = {
                "ok": bool(
                    pre_assurance_update_state_migration.get("ok", True)
                    and obsolete_update_state_migration.get("ok") is True
                ),
                "status": (
                    "committed"
                    if obsolete_update_state_settled
                    else str(obsolete_update_state_migration.get("status") or "no_delta")
                ),
                "pre_assurance": pre_assurance_update_state_migration,
                "post_install": obsolete_update_state_migration,
                "residual_retired_state_count": 0,
            }
            final_check = build_installation_check(
                repo_root=root,
                codex_home=home,
                allow_deferred_automation_restore=defer_automation_restore,
                manifest_override=payload,
            )
            if not final_check.get("ok"):
                raise RuntimeError(
                    "Chaos Brain post-install aggregate check failed: "
                    + "; ".join(str(item) for item in final_check.get("issues", []))
                )
            payload["post_install_check"] = final_check
            upgrade_attempt = _record_upgrade_attempt(
                home,
                attempt_id,
                phase="post_install_check_passed",
                status="completed",
                details={
                    "post_install_check_ok": True,
                    "install_transaction": payload.get("install_transaction", {}),
                    "consumer_projection_independent": True,
                    "survivors_must_remain_paused": bool(
                        defer_automation_restore
                    ),
                },
            )
            payload["upgrade_attempt"] = upgrade_attempt
        manifest_path = save_install_state(payload, home)
        payload["install_state_path"] = str(manifest_path)
        return payload
    except Exception as exc:
        if run_history_migration:
            _restore_exact_file_snapshot(
                obsolete_update_state_file,
                existed=obsolete_update_state_before_existed,
                content=obsolete_update_state_before_bytes,
            )
            _pause_installed_kb_automations(home)
            if attempt_id:
                _record_upgrade_attempt(
                    home,
                    attempt_id,
                    phase="failed_paused_recoverable",
                    status="failed",
                    details={
                        "error_type": type(exc).__name__,
                        "error": str(exc)[-4000:],
                        "survivors_must_remain_paused": True,
                        "recovery_action": (
                            "Rerun the idempotent installer after the reported hard gate is repaired."
                        ),
                    },
                )
        raise


def build_installation_check(
    repo_root: Path | None = None,
    codex_home: Path | None = None,
    *,
    allow_deferred_automation_restore: bool = False,
    manifest_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    home = codex_home or default_codex_home()
    skill_dir = global_skill_dir(home)
    skill_path = skill_dir / "SKILL.md"
    launcher_path = skill_dir / "kb_launch.py"
    openai_path = skill_dir / "agents" / "openai.yaml"
    global_agents = global_agents_path(home)
    manifest = (
        dict(manifest_override)
        if isinstance(manifest_override, Mapping)
        else load_install_state(home)
    )
    manifest_attempt = (
        manifest.get("upgrade_attempt", {})
        if isinstance(manifest.get("upgrade_attempt"), Mapping)
        else {}
    )
    upgrade_attempt_authority = current_upgrade_attempt_authority(home)
    active_upgrade_attempt = (
        dict(upgrade_attempt_authority.get("attempt") or {})
        if upgrade_attempt_authority.get("ok") is True
        else {}
    )
    manifest_root_raw = str(manifest.get("repo_root", "") or "").strip()
    env_value = os.environ.get(KB_ROOT_ENV_VAR, "").strip()
    managed_automations = manifest.get("automations", [])
    restore_deferred = manifest.get("automation_restore_deferred") is True
    managed_maintenance_skills = manifest.get("maintenance_skills", [])
    shell_tools_manifest = manifest.get("shell_tools", {}) if isinstance(manifest.get("shell_tools"), dict) else {}

    issues: list[str] = []
    warnings: list[str] = []
    from local_kb.logicguard_models import (
        retired_standalone_logicguard_residuals,
    )

    retired_standalone_logicguard = (
        retired_standalone_logicguard_residuals()
    )
    if retired_standalone_logicguard.get("ok") is not True:
        issues.append(
            "Retired standalone LogicGuard authority is still present: "
            + "; ".join(
                str(item)
                for item in retired_standalone_logicguard.get("issues", [])
            )
        )
    attempt_authority_required = bool(manifest_attempt) or Path(
        str(upgrade_attempt_authority.get("head_path") or "")
    ).is_file()
    if attempt_authority_required and upgrade_attempt_authority.get("ok") is not True:
        issues.append(
            "Upgrade-attempt current authority is not usable: "
            + ", ".join(
                str(item)
                for item in upgrade_attempt_authority.get("issues", [])
            )
        )
    if (
        manifest_override is None
        and manifest_attempt
        and active_upgrade_attempt
        and (
            str(manifest_attempt.get("attempt_id") or "")
            != str(active_upgrade_attempt.get("attempt_id") or "")
            or str(manifest_attempt.get("receipt_hash") or "")
            != str(active_upgrade_attempt.get("receipt_hash") or "")
        )
        and active_upgrade_attempt.get("status") != "failed"
    ):
        issues.append(
            "Committed install state does not bind the sole current upgrade-attempt authority."
        )
    if (
        manifest_override is None
        and active_upgrade_attempt.get("status") == "failed"
        and str(active_upgrade_attempt.get("updated_at") or "")
        > str(manifest.get("installed_at") or "")
    ):
        issues.append(
            "Latest Chaos Brain upgrade attempt failed safely and remains recoverable at "
            f"phase={active_upgrade_attempt.get('phase', '')}; all surviving automations "
            "must remain PAUSED until a complete retry passes."
        )

    resolved_manifest_root = ""
    if manifest_root_raw:
        manifest_path = Path(manifest_root_raw).expanduser().resolve()
        resolved_manifest_root = str(manifest_path)
        if not is_repo_root(manifest_path):
            issues.append(f"Manifest repo root is missing or invalid: {manifest_path}")
    else:
        issues.append("Install manifest does not define repo_root.")

    requested_repo_root = ""
    if repo_root is not None:
        requested_repo_root = str(repo_root)
        if not is_repo_root(repo_root):
            issues.append(f"Requested repo root is missing required KB markers: {repo_root}")
        elif resolved_manifest_root and resolved_manifest_root != requested_repo_root:
            warnings.append(
                "Requested repo root differs from the installed manifest path. "
                "Run the installer again if this clone should become the active KB root."
            )

    if not skill_path.exists():
        issues.append(f"Global skill file is missing: {skill_path}")
    if not launcher_path.exists():
        issues.append(f"Launcher file is missing: {launcher_path}")
    if not openai_path.exists():
        issues.append(f"Global skill openai.yaml is missing: {openai_path}")
        openai_text = ""
    else:
        try:
            openai_text = openai_path.read_text(encoding="utf-8")
        except OSError as exc:
            issues.append(f"Global skill openai.yaml could not be read: {exc}")
            openai_text = ""

    if openai_text and "allow_implicit_invocation: true" not in openai_text:
        issues.append(
            "Global skill openai.yaml does not enable implicit invocation. "
            "Re-run the installer so the installed global preflight skill can trigger automatically."
        )
    if openai_text and "record a KB follow-up observation" not in openai_text:
        issues.append(
            "Global skill default_prompt does not contain the expected KB postflight reminder. "
            "Re-run the installer to refresh the installed prompt."
        )
    if openai_text and not _has_postflight_timeout_ownership_wording(openai_text):
        issues.append(
            "Global skill default_prompt does not contain the current KB postflight timeout-ownership rule. "
            "Re-run the installer to refresh the installed prompt."
        )
    if openai_text and "skill/plugin usage lesson" not in openai_text:
        issues.append(
            "Global skill default_prompt does not mention skill/plugin usage lessons as KB signals. "
            "Re-run the installer to refresh the installed prompt."
        )
    if openai_text and "subagent/delegation usage lesson" not in openai_text:
        issues.append(
            "Global skill default_prompt does not mention subagent/delegation usage lessons as KB signals. "
            "Re-run the installer to refresh the installed prompt."
        )
    if openai_text and "phase-change KB checkpoints" not in openai_text:
        issues.append(
            "Global skill default_prompt does not mention phase-change KB checkpoints for long mixed tasks. "
            "Re-run the installer to refresh the installed prompt."
        )
    if openai_text and not _has_mistake_priority_wording(openai_text):
        issues.append(
            "Global skill default_prompt does not contain the expected mistake-first highest-priority KB postflight wording. "
            "Re-run the installer to refresh the installed prompt."
        )
    if openai_text and not _has_canonical_interface_wording(openai_text):
        issues.append(
            "Global skill default_prompt does not contain the expected canonical machine interface wording. "
            "Re-run the installer to refresh the installed prompt."
        )
    if openai_text and not _has_current_runtime_only_wording(openai_text):
        issues.append(
            "Global skill default_prompt does not contain the zero-compatibility and zero-fallback current-runtime rule. "
            "Re-run the installer to refresh the installed prompt."
        )
    if openai_text and not _has_logicguard_native_default_wording(openai_text):
        issues.append(
            "Global skill default_prompt does not contain the exact LogicGuard model/projection/ModelMesh ownership rule. "
            "Re-run the installer to refresh the installed prompt."
        )
    if not global_agents.exists():
        issues.append(
            f"Global AGENTS defaults file is missing: {global_agents}. "
            "Re-run the installer so every session inherits the predictive KB defaults."
        )
        global_agents_text = ""
    else:
        try:
            global_agents_text = global_agents.read_text(encoding="utf-8")
        except OSError as exc:
            issues.append(f"Global AGENTS defaults file could not be read: {exc}")
            global_agents_text = ""

    if global_agents_text and GLOBAL_AGENTS_BEGIN not in global_agents_text:
        issues.append(
            "Global AGENTS file is present but missing the managed predictive KB defaults block. "
            "Re-run the installer to restore the session-wide KB instructions."
        )
    if global_agents_text and "$predictive-kb-preflight" not in global_agents_text:
        issues.append(
            "Global AGENTS defaults do not mention $predictive-kb-preflight. "
            "Re-run the installer to restore the required KB preflight reminder."
        )
    if global_agents_text and "explicit KB postflight check" not in global_agents_text:
        issues.append(
            "Global AGENTS defaults do not contain the expected explicit KB postflight check wording. "
            "Re-run the installer to refresh the session-wide defaults."
        )
    if (
        global_agents_text
        and not _has_postflight_timeout_ownership_wording(global_agents_text)
    ):
        issues.append(
            "Global AGENTS defaults do not contain the current KB postflight timeout-ownership rule. "
            "Re-run the installer to refresh the session-wide defaults."
        )
    if global_agents_text and "skill/plugin usage" not in global_agents_text:
        issues.append(
            "Global AGENTS defaults do not mention skill/plugin usage lessons as KB signals. "
            "Re-run the installer to refresh the session-wide defaults."
        )
    if global_agents_text and "subagent/delegation usage" not in global_agents_text:
        issues.append(
            "Global AGENTS defaults do not mention subagent/delegation usage lessons as KB signals. "
            "Re-run the installer to refresh the session-wide defaults."
        )
    if global_agents_text and "phase-change KB checkpoints" not in global_agents_text:
        issues.append(
            "Global AGENTS defaults do not mention phase-change KB checkpoints for long mixed tasks. "
            "Re-run the installer to refresh the session-wide defaults."
        )
    if global_agents_text and not _has_mistake_priority_wording(global_agents_text):
        issues.append(
            "Global AGENTS defaults do not contain the expected mistake-first highest-priority KB postflight wording. "
            "Re-run the installer to refresh the session-wide defaults."
        )
    if global_agents_text and not _has_canonical_interface_wording(global_agents_text):
        issues.append(
            "Global AGENTS defaults do not contain the expected canonical machine interface wording. "
            "Re-run the installer to refresh the session-wide defaults."
        )
    if global_agents_text and not _has_current_runtime_only_wording(global_agents_text):
        issues.append(
            "Global AGENTS defaults do not contain the zero-compatibility and zero-fallback current-runtime rule. "
            "Re-run the installer to refresh the session-wide defaults."
        )
    if global_agents_text and not _has_logicguard_native_default_wording(global_agents_text):
        issues.append(
            "Global AGENTS defaults do not contain the exact LogicGuard model/projection/ModelMesh ownership rule. "
            "Re-run the installer to refresh the session-wide defaults."
        )

    shell_bin = Path(
        str(shell_tools_manifest.get("shell_bin_dir", "") or codex_shell_bin_dir())
    ).expanduser()
    git_shim_path = Path(
        str(shell_tools_manifest.get("git_shim_path", "") or (shell_bin / "git.cmd"))
    ).expanduser()
    rg_path = Path(
        str(shell_tools_manifest.get("rg_path", "") or (shell_bin / "rg.exe"))
    ).expanduser()
    shell_tools_required = (
        platform.system().lower() == "windows"
        or (
            bool(shell_tools_manifest.get("git_shim_installed"))
            and bool(shell_tools_manifest.get("rg_installed"))
        )
    )
    if shell_tools_required:
        if not git_shim_path.exists():
            issues.append(
                f"Codex shell Git shim is missing: {git_shim_path}. "
                "Re-run the installer to restore stable Git command resolution."
            )
        if not rg_path.exists():
            issues.append(
                f"Codex shell rg binary is missing: {rg_path}. "
                "Re-run the installer to restore stable ripgrep command resolution."
            )
    else:
        warnings.append(
            "Codex shell git/rg shim check skipped because this non-Windows install "
            "did not create Windows shell shim files."
        )

    expected_repo_root = repo_root or (Path(manifest_root_raw) if manifest_root_raw else Path("."))
    history_migration_required = bool(manifest.get("history_migration_required", True))
    if history_migration_required:
        from local_kb.software_update import load_update_state

        current_update_state = load_update_state(expected_repo_root)
        current_update_state_error = str(current_update_state.get("error") or "")
        update_state_source_current = not (
            current_update_state_error == "Update state could not be read."
            or current_update_state_error == "Update state must be a current mapping."
            or current_update_state_error.startswith("Update state is not current:")
        )
        if not update_state_source_current:
            issues.append(
                "The update-state file is not in the sole current schema; the versioned upgrade must rewrite it before installation can be healthy."
            )
        obsolete_update_state_settled = True
        from local_kb.maintenance_migration import (
            check_migration_current_authority,
        )

        history_migration_check = check_migration_current_authority(
            expected_repo_root
        )
        if not history_migration_check.get("ok"):
            issues.append(
                "Chaos Brain history-debt migration is not current and committed: "
                + "; ".join(
                    str(item) for item in history_migration_check.get("issues", [])
                )
            )
    else:
        current_update_state = {
            "schema_version": 1,
            "status": "fixture_skipped",
            "error": "",
        }
        update_state_source_current = True
        obsolete_update_state_settled = True
        history_migration_check = {
            "ok": True,
            "status": "fixture_skipped",
            "reason": "isolated installer fixture does not read or mutate live repository runtime state",
        }
    upgrade_assurance_required = bool(manifest.get("upgrade_assurance_required", True))
    upgrade_assurance = (
        manifest.get("upgrade_assurance", {})
        if isinstance(manifest.get("upgrade_assurance"), dict)
        else {}
    )
    if upgrade_assurance_required:
        from scripts.check_consumer_install_assurance import (
            audit_current_assurance,
        )

        upgrade_assurance_currentness = audit_current_assurance(
            expected_repo_root,
            home,
            expected_receipt_hash=str(
                upgrade_assurance.get("receipt_hash") or ""
            ),
        )
    else:
        upgrade_assurance_currentness = {
            "ok": True,
            "status": "fixture_skipped",
            "execution_count": 0,
            "issues": [],
        }
    upgrade_assurance_ok = bool(
        not upgrade_assurance_required
        or (
            upgrade_assurance.get("ok")
            and upgrade_assurance.get("receipt_hash")
            and upgrade_assurance_currentness.get("ok")
            and upgrade_assurance_currentness.get("execution_count") == 0
        )
    )
    if not upgrade_assurance_ok:
        issues.append(
            "Chaos Brain aggregate pre-restore assurance is missing or failed: "
            + ", ".join(
                [
                    *(
                        str(item)
                        for item in upgrade_assurance.get("failed_checks", [])
                    ),
                    *(
                        str(item)
                        for item in upgrade_assurance_currentness.get(
                            "issues", []
                        )
                    ),
                ]
            )
        )
    canonical_interface_checks: list[dict[str, Any]] = []

    def add_canonical_interface_check(check_id: str, path: Path, markers: tuple[str, ...]) -> None:
        item_issues: list[str] = []
        if not path.exists():
            item_issues.append(f"Canonical interface source is missing: {path}")
            text = ""
        else:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                item_issues.append(f"Canonical interface source could not be read: {exc}")
                text = ""
        normalized = text.lower()
        for marker in markers:
            if marker.lower() not in normalized:
                item_issues.append(f"{path} is missing canonical-interface marker: {marker}")
        if item_issues:
            issues.extend(item_issues)
        canonical_interface_checks.append(
            {
                "id": check_id,
                "path": str(path),
                "ok": not item_issues,
                "issues": item_issues,
            }
        )

    add_canonical_interface_check(
        "local_kb_skill_prompt",
        expected_repo_root / ".agents" / "skills" / "local-kb-retrieve" / "SKILL.md",
        CANONICAL_INTERFACE_MARKERS,
    )
    add_canonical_interface_check(
        "local_kb_maintenance_prompt",
        expected_repo_root / ".agents" / "skills" / "local-kb-retrieve" / "MAINTENANCE_PROMPT.md",
        ("canonical-interface checkpoint", "CLI machine JSON", "i18n.zh-CN"),
    )
    add_canonical_interface_check(
        "preflight_skill_template",
        expected_repo_root / TEMPLATE_ROOT / "SKILL.md.template",
        CANONICAL_INTERFACE_MARKERS,
    )
    add_canonical_interface_check(
        "preflight_global_agents_template",
        expected_repo_root / TEMPLATE_ROOT / f"{GLOBAL_AGENTS_FILENAME}.template",
        CANONICAL_INTERFACE_MARKERS,
    )
    add_canonical_interface_check(
        "preflight_openai_template",
        expected_repo_root / TEMPLATE_ROOT / "agents" / "openai.yaml",
        CANONICAL_INTERFACE_MARKERS,
    )
    add_canonical_interface_check(
        "preflight_launcher_template",
        expected_repo_root / TEMPLATE_ROOT / "kb_launch.py",
        ("ensure_ascii=True", "print_machine_json", "console_safe_text"),
    )

    maintenance_skill_checks: list[dict[str, Any]] = []
    for spec in MAINTENANCE_SKILL_SPECS:
        skill_name = spec["name"]
        source_dir = maintenance_skill_source_dir(expected_repo_root, skill_name)
        install_dir = maintenance_skill_install_dir(skill_name, home)
        source_skill_path = source_dir / "SKILL.md"
        install_skill_path = install_dir / "SKILL.md"
        install_openai_path = install_dir / "agents" / "openai.yaml"
        issues_for_skill: list[str] = []
        if not source_skill_path.exists():
            issues_for_skill.append(f"Repository maintenance skill source is missing: {source_skill_path}")
            source_skill_text = ""
        else:
            try:
                source_skill_text = source_skill_path.read_text(encoding="utf-8")
            except OSError as exc:
                issues_for_skill.append(f"Repository maintenance skill source could not be read: {exc}")
                source_skill_text = ""
        if not install_skill_path.exists():
            issues_for_skill.append(f"Installed maintenance skill file is missing: {install_skill_path}")
            skill_text = ""
        else:
            try:
                skill_text = install_skill_path.read_text(encoding="utf-8")
            except OSError as exc:
                issues_for_skill.append(f"Installed maintenance skill could not be read: {exc}")
                skill_text = ""
        if not install_openai_path.exists():
            issues_for_skill.append(f"Installed maintenance skill openai.yaml is missing: {install_openai_path}")
            skill_openai_text = ""
        else:
            try:
                skill_openai_text = install_openai_path.read_text(encoding="utf-8")
            except OSError as exc:
                issues_for_skill.append(f"Installed maintenance skill openai.yaml could not be read: {exc}")
                skill_openai_text = ""
        if skill_text:
            if f"name: {skill_name}" not in skill_text:
                issues_for_skill.append(f"Installed maintenance skill {skill_name} has the wrong frontmatter name.")
            if "[TODO" in skill_text:
                issues_for_skill.append(f"Installed maintenance skill {skill_name} still contains TODO scaffolding.")
            if str(spec["prompt_marker"]) not in skill_text:
                issues_for_skill.append(
                    f"Installed maintenance skill {skill_name} is missing prompt marker {spec['prompt_marker']}."
                )
            if source_skill_text and skill_text != source_skill_text:
                issues_for_skill.append(
                    f"Installed maintenance skill {skill_name} differs from repository source. "
                    "Re-run the installer to refresh it."
                )
        if skill_openai_text:
            if "allow_implicit_invocation: false" not in skill_openai_text:
                issues_for_skill.append(
                    f"Installed maintenance skill {skill_name} should disable implicit invocation."
                )
            if f"${skill_name}" not in skill_openai_text:
                issues_for_skill.append(
                    f"Installed maintenance skill {skill_name} default prompt should mention ${skill_name}."
                )
        source_manifest = tree_manifest(source_dir) if source_dir.exists() else {}
        try:
            expected_consumer_manifest = (
                consumer_skill_manifest(source_dir) if source_dir.exists() else {}
            )
        except RuntimeError as exc:
            expected_consumer_manifest = {}
            issues_for_skill.append(str(exc))
        install_manifest = tree_manifest(install_dir) if install_dir.exists() else {}
        if (
            expected_consumer_manifest
            and install_manifest
            and expected_consumer_manifest.get("digest") != install_manifest.get("digest")
        ):
            issues_for_skill.append(
                f"Installed maintenance skill {skill_name} differs from the clean consumer projection."
            )
        consumer_projection_findings: list[str] = []
        if (install_dir / ".skillguard").exists():
            consumer_projection_findings.append("installed-author-control-directory-present")
        for path in install_dir.rglob("*") if install_dir.exists() else ():
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8").lower()
            except (OSError, UnicodeDecodeError):
                continue
            if any(token in text for token in ("skillguard", ".skillguard", "skillguard.py")):
                consumer_projection_findings.append(
                    f"installed-author-control-token:{path.relative_to(install_dir).as_posix()}"
                )
        issues_for_skill.extend(consumer_projection_findings)
        if issues_for_skill:
            issues.extend(issues_for_skill)
        maintenance_skill_checks.append(
            {
                "name": skill_name,
                "source_path": str(source_dir),
                "install_path": str(install_dir),
                "exists": install_skill_path.exists(),
                "openai_exists": install_openai_path.exists(),
                "automation_id": spec["automation_id"],
                "source_manifest_digest": str(source_manifest.get("digest") or ""),
                "expected_consumer_manifest_digest": str(
                    expected_consumer_manifest.get("digest") or ""
                ),
                "install_manifest_digest": str(install_manifest.get("digest") or ""),
                "consumer_projection_findings": consumer_projection_findings,
                "issues": issues_for_skill,
            }
        )

    automation_checks: list[dict[str, Any]] = []
    automation_runtime = resolve_automation_runtime(home)
    recorded_automation_statuses = (
        manifest.get("installed_automation_statuses")
        if isinstance(manifest.get("installed_automation_statuses"), Mapping)
        else {}
    )
    for spec in REPO_AUTOMATION_SPECS:
        expected = _automation_spec_payload(spec, expected_repo_root, codex_home=home)
        path = automation_toml_path(spec["id"], home)
        payload = _load_automation_toml(path)
        issues_for_automation: list[str] = []
        if not path.exists():
            issues_for_automation.append(f"Automation file is missing: {path}")
        elif not payload:
            issues_for_automation.append(f"Automation file could not be parsed: {path}")
        else:
            if str(payload.get("id", "") or "") != expected["id"]:
                issues_for_automation.append(f"Automation id mismatch for {path}: expected {expected['id']}")
            if str(payload.get("kind", "") or "") != expected["kind"]:
                issues_for_automation.append(
                    f"Automation {expected['id']} should be kind={expected['kind']}."
                )
            if str(payload.get("name", "") or "") != expected["name"]:
                issues_for_automation.append(
                    f"Automation {expected['id']} should be named {expected['name']}."
                )
            payload_status = str(payload.get("status", "") or "")
            recorded_status = str(
                recorded_automation_statuses.get(str(spec["id"]))
                or expected["status"]
            ).upper()
            deferred_pause_allowed = bool(
                allow_deferred_automation_restore
                and restore_deferred
                and payload_status == "PAUSED"
            )
            if (
                payload_status != recorded_status
                and not deferred_pause_allowed
            ):
                issues_for_automation.append(
                    f"Automation {expected['id']} should be status={recorded_status}."
                )
            if str(payload.get("rrule", "") or "") != expected["rrule"]:
                issues_for_automation.append(
                    f"Automation {expected['id']} should use rrule {expected['rrule']}."
                )
            if str(payload.get("model", "") or "") != expected["model"]:
                issues_for_automation.append(
                    f"Automation {expected['id']} should use model={expected['model']} from policy={expected['model_policy']}."
                )
            if str(payload.get("reasoning_effort", "") or "") != expected["reasoning_effort"]:
                issues_for_automation.append(
                    f"Automation {expected['id']} should use reasoning_effort={expected['reasoning_effort']} from policy={expected['reasoning_effort_policy']}."
                )
            if str(payload.get("execution_environment", "") or "") != expected["execution_environment"]:
                issues_for_automation.append(
                    f"Automation {expected['id']} should use execution_environment={expected['execution_environment']}."
                )
            payload_cwds = [str(item) for item in payload.get("cwds", [])] if isinstance(payload.get("cwds"), list) else []
            if payload_cwds != expected["cwds"]:
                issues_for_automation.append(
                    f"Automation {expected['id']} should target cwds={expected['cwds']}."
                )
            prompt_text = str(payload.get("prompt", "") or "")
            if prompt_text != expected["prompt"]:
                issues_for_automation.append(
                    f"Automation {expected['id']} prompt differs from the repository spec."
                )
            expected_skill_name = str(spec.get("skill_name", "") or "")
            if expected_skill_name and f"${expected_skill_name}" not in prompt_text:
                issues_for_automation.append(
                    f"Automation {expected['id']} prompt must explicitly invoke ${expected_skill_name}."
                )
            required_prompt_markers = (
                ".agents/skills/local-kb-retrieve",
                "PROJECT_SPEC.md",
                "scripts/run_kb_automation.py",
                "immutable",
                "target-owned runner",
                "native terminal receipt",
            )
            for marker in required_prompt_markers:
                if marker not in prompt_text:
                    issues_for_automation.append(
                        f"Automation {expected['id']} prompt is missing required marker: {marker}"
                    )
            if expected["id"] == "kb-dream" and "kb_dream.py" not in prompt_text:
                issues_for_automation.append("Automation kb-dream prompt must reference kb_dream.py.")
            if expected["id"] == "kb-dream":
                for marker in (
                    "docs/maintenance_agent_worldview.md",
                    "stable fingerprints",
                    "no_delta_closed",
                    "pin the exact LogicGuard generation",
                    "evidence removal",
                    "assumption removal",
                    "rebuttal strengthening",
                    "typed idempotent Sleep handoffs",
                    "must not directly write cards",
                    "canonical generation unchanged",
                    "no-op is a successful convergent result",
                ):
                    if marker not in prompt_text:
                        issues_for_automation.append(
                            f"Automation kb-dream prompt is missing dream lifecycle marker: {marker}"
                        )
            if expected["id"] == "kb-sleep" and "MAINTENANCE_PROMPT.md" not in prompt_text:
                issues_for_automation.append(
                    "Automation kb-sleep prompt must reference MAINTENANCE_PROMPT.md."
                )
            if expected["id"] == "kb-sleep":
                for marker in (
                    "kb_lane_status.py",
                    "kb_sleep.py",
                    "committed increment",
                    "explicit disposition",
                    "executable reopen conditions",
                    "sole canonical model-generation publisher",
                    "LogicGuard model revision",
                    "grounded ModelMesh",
                    "explicit model gaps",
                    "typed Dream handoffs exactly once",
                    "commit the watermark only after",
                    "Do not request human file review",
                ):
                    if marker not in prompt_text:
                        issues_for_automation.append(
                            f"Automation kb-sleep prompt is missing sleep lifecycle marker: {marker}"
                        )
            if expected["id"] == "kb-org-contribute":
                for marker in (
                    "scripts/kb_org_outbox.py",
                    "desktop settings",
                    "organization mode",
                    "validated organization repository",
                    "successful no-op",
                    "sync the organization mirror first",
                    "KB preflight",
                    "content-hash-gated outbox",
                    "every exchanged hash",
                    "downloaded, used, absorbed, exported, uploaded",
                    "prepare an import branch",
                    "push eligible import proposals automatically",
                    "org-kb:auto-merge",
                    "KB postflight",
                ):
                    if marker not in prompt_text:
                        issues_for_automation.append(
                            f"Automation kb-org-contribute prompt is missing organization contribution marker: {marker}"
                        )
            if expected["id"] == "kb-org-maintenance":
                for marker in (
                    "scripts/kb_org_maintainer.py",
                    "organization-level Sleep-like maintenance",
                    "desktop settings",
                    "organization maintenance participation",
                    "successful no-op",
                    "KB preflight",
                    "organization candidate intake checkpoint",
                    "content-hash checkpoint",
                    "mandatory organization similar-card merge checkpoint",
                    "mandatory organization overloaded-card split checkpoint",
                    "candidate decision checkpoint",
                    "Skill safety checkpoint",
                    "Skill bundle version checkpoint",
                    "decision-apply checkpoint",
                    "post-apply organization check",
                    "GitHub merge-readiness checkpoint",
                    "organization-review",
                    "Skill registry",
                    "duplicate content hashes",
                    "duplicate entry ids",
                    "bundle_id",
                    "original-author updates",
                    "latest approved version by version_time",
                    "do not auto-install",
                    "organization Sleep decision set",
                    "organization-review as guidance rather than an apply gate",
                    "exact selected action ids",
                    "post-apply check result",
                    "maintenance branch, PR, push, and auto-merge-label result",
                    "KB postflight",
                ):
                    if marker not in prompt_text:
                        issues_for_automation.append(
                            f"Automation kb-org-maintenance prompt is missing organization maintenance marker: {marker}"
                        )
        if issues_for_automation:
            issues.extend(issues_for_automation)
        automation_checks.append(
            {
                "id": spec["id"],
                "path": str(path),
                "exists": path.exists(),
                "rrule": expected["rrule"],
                "schedule_policy": expected["schedule_policy"],
                "schedule_window": expected["schedule_window"],
                "issues": issues_for_automation,
            }
        )

    if not managed_automations:
        warnings.append(
            "Install manifest does not record the repository-managed KB automations. "
            "Re-run the installer to refresh automation setup."
        )
    if not managed_maintenance_skills:
        warnings.append(
            "Install manifest does not record the repository-managed KB skills. "
            "Re-run the installer to refresh skill setup."
        )

    automation_issue_map = {item["id"]: item["issues"] for item in automation_checks}
    maintenance_skill_ok = all(not item["issues"] for item in maintenance_skill_checks)
    maintenance_consumer_independence_ok = bool(maintenance_skill_checks) and all(
        not item.get("consumer_projection_findings")
        for item in maintenance_skill_checks
    )
    global_skill_present = skill_path.exists() and launcher_path.exists() and openai_path.exists()
    global_skill_implicit = bool(openai_text and "allow_implicit_invocation: true" in openai_text)
    global_skill_postflight = bool(
        openai_text
        and "record a KB follow-up observation" in openai_text
        and "required default preflight" in openai_text
    )
    global_skill_postflight_timeout_ownership = bool(
        openai_text
        and _has_postflight_timeout_ownership_wording(openai_text)
    )
    global_skill_skill_usage = bool(openai_text and "skill/plugin usage lesson" in openai_text)
    global_skill_subagent_usage = bool(openai_text and "subagent/delegation usage lesson" in openai_text)
    global_skill_phase_checkpoints = bool(openai_text and "phase-change KB checkpoints" in openai_text)
    global_skill_mistake_priority = bool(openai_text and _has_mistake_priority_wording(openai_text))
    global_skill_canonical_interface = bool(openai_text and _has_canonical_interface_wording(openai_text))
    global_skill_current_runtime_only = bool(
        openai_text and _has_current_runtime_only_wording(openai_text)
    )
    global_skill_logicguard_native = bool(
        openai_text and _has_logicguard_native_default_wording(openai_text)
    )
    global_agents_present = global_agents.exists()
    global_agents_managed = bool(
        global_agents_text
        and GLOBAL_AGENTS_BEGIN in global_agents_text
        and GLOBAL_AGENTS_END in global_agents_text
    )
    global_agents_preflight = bool(global_agents_text and "$predictive-kb-preflight" in global_agents_text)
    global_agents_postflight = bool(global_agents_text and "explicit KB postflight check" in global_agents_text)
    global_agents_postflight_timeout_ownership = bool(
        global_agents_text
        and _has_postflight_timeout_ownership_wording(global_agents_text)
    )
    global_agents_skill_usage = bool(global_agents_text and "skill/plugin usage" in global_agents_text)
    global_agents_subagent_usage = bool(global_agents_text and "subagent/delegation usage" in global_agents_text)
    global_agents_phase_checkpoints = bool(global_agents_text and "phase-change KB checkpoints" in global_agents_text)
    global_agents_mistake_priority = bool(global_agents_text and _has_mistake_priority_wording(global_agents_text))
    global_agents_canonical_interface = bool(global_agents_text and _has_canonical_interface_wording(global_agents_text))
    global_agents_current_runtime_only = bool(
        global_agents_text and _has_current_runtime_only_wording(global_agents_text)
    )
    global_agents_logicguard_native = bool(
        global_agents_text and _has_logicguard_native_default_wording(global_agents_text)
    )
    canonical_interface_ok = (
        global_skill_canonical_interface
        and global_agents_canonical_interface
        and all(item["ok"] for item in canonical_interface_checks)
    )
    kb_sleep_ok = not automation_issue_map.get("kb-sleep")
    kb_dream_ok = not automation_issue_map.get("kb-dream")
    system_update_retired_ok = not automation_toml_path("khaos-brain-system-update", home).exists()
    kb_org_contribute_ok = not automation_issue_map.get("kb-org-contribute")
    kb_org_maintenance_ok = not automation_issue_map.get("kb-org-maintenance")
    automation_check_map = {item["id"]: item for item in automation_checks}
    codex_shell_tools_ok = not shell_tools_required or (git_shim_path.exists() and rg_path.exists())
    retired_paths = [
        *(home / "skills" / item for item in RETIRED_MAINTENANCE_SKILL_IDS),
        *(home / "automations" / item for item in RETIRED_AUTOMATION_IDS),
    ]
    retired_source_paths = [
        expected_repo_root / REPO_SKILLS_ROOT / item for item in RETIRED_MAINTENANCE_SKILL_IDS
    ]
    active_retired_absent = all(not path.exists() for path in retired_paths)
    source_retired_absent = all(
        not path.exists() or int(tree_manifest(path).get("file_count") or 0) == 0
        for path in retired_source_paths
    )
    retired_surfaces_absent = active_retired_absent and source_retired_absent
    if not retired_surfaces_absent:
        issues.append(
            "Retired managed Skill or automation surfaces remain active: "
            + ", ".join(
                str(path)
                for path in retired_paths
                if path.exists()
            )
        )
    install_transaction = latest_install_receipt(home)
    transaction_committed = bool(
        install_transaction.get("status") == "committed"
        and install_transaction.get("receipt_hash")
    )
    if not transaction_committed:
        issues.append("No current committed transactional Chaos Brain install receipt is available.")
    strong_defaults_ok = (
        global_skill_implicit
        and global_skill_postflight
        and global_skill_postflight_timeout_ownership
        and global_agents_managed
        and global_agents_preflight
        and global_agents_postflight
        and global_agents_postflight_timeout_ownership
        and global_skill_skill_usage
        and global_agents_skill_usage
        and global_skill_subagent_usage
        and global_agents_subagent_usage
        and global_skill_phase_checkpoints
        and global_agents_phase_checkpoints
        and global_skill_mistake_priority
        and global_agents_mistake_priority
        and canonical_interface_ok
        and global_skill_current_runtime_only
        and global_agents_current_runtime_only
        and global_skill_logicguard_native
        and global_agents_logicguard_native
        and obsolete_update_state_settled
        and update_state_source_current
        and maintenance_skill_ok
        and maintenance_consumer_independence_ok
    )
    checklist = [
        _checklist_item(
            "global_skill_files",
            "Global predictive KB skill and launcher are installed",
            global_skill_present,
            f"skill_path={skill_path}; launcher_path={launcher_path}; openai_path={openai_path}",
        ),
        _checklist_item(
            "global_skill_implicit",
            "Global predictive KB skill enables implicit invocation",
            global_skill_implicit,
            f"openai_path={openai_path}",
        ),
        _checklist_item(
            "global_skill_postflight",
            "Global predictive KB prompt requires KB preflight and postflight reminders",
            global_skill_postflight,
            f"openai_path={openai_path}",
        ),
        _checklist_item(
            "global_skill_postflight_timeout_ownership",
            "Global predictive KB prompt preserves one postflight writer with ordered timeout headroom",
            global_skill_postflight_timeout_ownership,
            f"openai_path={openai_path}",
        ),
        _checklist_item(
            "global_skill_skill_usage",
            "Global predictive KB prompt treats skill/plugin lessons as recordable KB signals",
            global_skill_skill_usage,
            f"openai_path={openai_path}",
        ),
        _checklist_item(
            "global_skill_subagent_usage",
            "Global predictive KB prompt treats subagent/delegation lessons as recordable KB signals",
            global_skill_subagent_usage,
            f"openai_path={openai_path}",
        ),
        _checklist_item(
            "global_skill_phase_checkpoints",
            "Global predictive KB prompt requires phase-change KB checkpoints for long mixed tasks",
            global_skill_phase_checkpoints,
            f"openai_path={openai_path}",
        ),
        _checklist_item(
            "global_skill_mistake_priority",
            "Global predictive KB prompt treats mistakes, weak paths, and corrections as highest-priority postflight evidence",
            global_skill_mistake_priority,
            f"openai_path={openai_path}",
        ),
        _checklist_item(
            "global_skill_canonical_interface",
            "Global predictive KB prompt preserves canonical machine interfaces and localized display projection",
            global_skill_canonical_interface,
            f"openai_path={openai_path}",
        ),
        _checklist_item(
            "global_skill_current_runtime_only",
            "Global predictive KB prompt enforces zero compatibility and zero fallback in normal runtime",
            global_skill_current_runtime_only,
            f"openai_path={openai_path}",
        ),
        _checklist_item(
            "global_skill_logicguard_native",
            "Global predictive KB prompt enters exact LogicGuard models and keeps Sleep as the sole canonical publisher",
            global_skill_logicguard_native,
            f"openai_path={openai_path}",
        ),
        _checklist_item(
            "global_agents_file",
            "Global AGENTS defaults file exists",
            global_agents_present,
            f"global_agents_path={global_agents}",
        ),
        _checklist_item(
            "global_agents_block",
            "Global AGENTS contains the managed predictive KB defaults block",
            global_agents_managed,
            f"global_agents_path={global_agents}",
        ),
        _checklist_item(
            "global_agents_preflight",
            "Global AGENTS defaults mention $predictive-kb-preflight",
            global_agents_preflight,
            f"global_agents_path={global_agents}",
        ),
        _checklist_item(
            "global_agents_postflight",
            "Global AGENTS defaults require an explicit KB postflight check",
            global_agents_postflight,
            f"global_agents_path={global_agents}",
        ),
        _checklist_item(
            "global_agents_postflight_timeout_ownership",
            "Global AGENTS defaults preserve one postflight writer with ordered timeout headroom",
            global_agents_postflight_timeout_ownership,
            f"global_agents_path={global_agents}",
        ),
        _checklist_item(
            "global_agents_skill_usage",
            "Global AGENTS defaults treat skill/plugin lessons as recordable KB signals",
            global_agents_skill_usage,
            f"global_agents_path={global_agents}",
        ),
        _checklist_item(
            "global_agents_subagent_usage",
            "Global AGENTS defaults treat subagent/delegation lessons as recordable KB signals",
            global_agents_subagent_usage,
            f"global_agents_path={global_agents}",
        ),
        _checklist_item(
            "global_agents_phase_checkpoints",
            "Global AGENTS defaults require phase-change KB checkpoints for long mixed tasks",
            global_agents_phase_checkpoints,
            f"global_agents_path={global_agents}",
        ),
        _checklist_item(
            "global_agents_mistake_priority",
            "Global AGENTS defaults treat mistakes, weak paths, and corrections as highest-priority postflight evidence",
            global_agents_mistake_priority,
            f"global_agents_path={global_agents}",
        ),
        _checklist_item(
            "global_agents_canonical_interface",
            "Global AGENTS defaults preserve canonical machine interfaces and localized display projection",
            global_agents_canonical_interface,
            f"global_agents_path={global_agents}",
        ),
        _checklist_item(
            "global_agents_current_runtime_only",
            "Global AGENTS defaults enforce upgrade-only direct migration and visible current-authority failure",
            global_agents_current_runtime_only,
            f"global_agents_path={global_agents}",
        ),
        _checklist_item(
            "global_agents_logicguard_native",
            "Global AGENTS defaults require deterministic projections, exact LogicGuard context, and grounded ModelMesh expansion",
            global_agents_logicguard_native,
            f"global_agents_path={global_agents}",
        ),
        _checklist_item(
            "canonical_machine_interfaces",
            "Repository prompts, templates, and launcher preserve canonical machine output and localized display boundaries",
            canonical_interface_ok,
            "; ".join(f"{item['id']}={item['path']}" for item in canonical_interface_checks),
        ),
        _checklist_item(
            "repo_maintenance_skills",
            "Repository-managed KB maintenance, organization, and update skills are installed",
            maintenance_skill_ok,
            "; ".join(f"{item['name']}={item['install_path']}" for item in maintenance_skill_checks),
        ),
        _checklist_item(
            "maintenance_consumer_independence",
            "Every installed maintenance skill is the exact clean consumer projection and carries no author-side control",
            maintenance_consumer_independence_ok,
            "; ".join(
                f"{item['name']}=consumer_findings:{len(item.get('consumer_projection_findings', []))}"
                for item in maintenance_skill_checks
            ),
        ),
        _checklist_item(
            "chaos_brain_history_migration",
            "Versioned history debt is settled, archived, pruned, indexed, and committed",
            bool(history_migration_check.get("ok")),
            (
                f"required={history_migration_required}; "
                f"migration_id={history_migration_check.get('migration_id', '')}; "
                f"status={history_migration_check.get('status', history_migration_check.get('journal', {}).get('status', ''))}"
            ),
        ),
        _checklist_item(
            "obsolete_update_state_settled",
            "The exact retired update-identity failure is absent after upgrade-only settlement",
            obsolete_update_state_settled,
            f"status={current_update_state.get('status', '')}; error={current_update_state.get('error', '')}",
        ),
        _checklist_item(
            "update_state_source_current",
            "Update state uses the sole current schema and no daily compatibility reader",
            update_state_source_current,
            f"status={current_update_state.get('status', '')}; error={current_update_state.get('error', '')}",
        ),
        _checklist_item(
            "chaos_brain_aggregate_assurance",
            "Current target-owned model, retirement, retrieval, and regression gates passed before restore",
            upgrade_assurance_ok,
            (
                f"required={upgrade_assurance_required}; "
                f"failed={','.join(str(item) for item in upgrade_assurance.get('failed_checks', []))}; "
                f"receipt_hash={upgrade_assurance.get('receipt_hash', '')}; "
                f"currentness_execution_count={upgrade_assurance_currentness.get('execution_count', '')}"
            ),
        ),
        _checklist_item(
            "kb_sleep_automation",
            "KB Sleep automation is installed and matches the repository spec",
            kb_sleep_ok,
            f"path={automation_toml_path('kb-sleep', home)}",
        ),
        _checklist_item(
            "kb_dream_automation",
            "KB Dream automation is installed and matches the repository spec",
            kb_dream_ok,
            f"path={automation_toml_path('kb-dream', home)}",
        ),
        _checklist_item(
            "retired_managed_surfaces",
            "Retired Architect and automatic system-update surfaces are absent",
            retired_surfaces_absent,
            "; ".join(str(path) for path in [*retired_paths, *retired_source_paths]),
        ),
        _checklist_item(
            "retired_standalone_logicguard_absent",
            "The active Python environment has no standalone LogicGuard distribution, import origin, or loaded module",
            retired_standalone_logicguard.get("ok") is True,
            "; ".join(
                str(item)
                for item in retired_standalone_logicguard.get("issues", [])
            ),
        ),
        _checklist_item(
            "khaos_brain_system_update_retired",
            "Khaos Brain automatic system-update task is absent",
            system_update_retired_ok,
            f"path={automation_toml_path('khaos-brain-system-update', home)}",
        ),
        _checklist_item(
            "transactional_install_receipt",
            "Managed Skills and automations have a committed parity-bound install receipt",
            transaction_committed,
            str(install_transaction.get("journal_path") or ""),
        ),
        _checklist_item(
            "kb_org_contribute_automation",
            "KB Organization Contribute automation is installed and matches the repository spec",
            kb_org_contribute_ok,
            (
                f"path={automation_toml_path('kb-org-contribute', home)}; "
                f"rrule={automation_check_map.get('kb-org-contribute', {}).get('rrule', '')}; "
                f"window={automation_check_map.get('kb-org-contribute', {}).get('schedule_window', '')}"
            ),
        ),
        _checklist_item(
            "kb_org_maintenance_automation",
            "KB Organization Maintenance automation is installed and matches the repository spec",
            kb_org_maintenance_ok,
            (
                f"path={automation_toml_path('kb-org-maintenance', home)}; "
                f"rrule={automation_check_map.get('kb-org-maintenance', {}).get('rrule', '')}; "
                f"window={automation_check_map.get('kb-org-maintenance', {}).get('schedule_window', '')}"
            ),
        ),
        _checklist_item(
            "codex_shell_tools",
            "Codex shell git/rg tools are installed in a stable user-level bin",
            codex_shell_tools_ok,
            (
                f"shell_bin={shell_bin}; git_shim={git_shim_path}; rg_path={rg_path}; "
                f"required={shell_tools_required}"
            ),
        ),
        _checklist_item(
            "strong_session_defaults",
            "The strongest available session-wide KB defaults layer is installed",
            strong_defaults_ok,
            f"global_agents_path={global_agents}; openai_path={openai_path}",
        ),
    ]

    return {
        "ok": not issues,
        "repo_root": requested_repo_root,
        "manifest_repo_root": resolved_manifest_root,
        "codex_home": str(home),
        "skill_dir": str(skill_dir),
        "skill_path": str(skill_path),
        "launcher_path": str(launcher_path),
        "openai_path": str(openai_path),
        "global_agents_path": str(global_agents),
        "install_state_path": str(install_state_path(home)),
        "env_var_name": KB_ROOT_ENV_VAR,
        "env_var_value": env_value,
        "maintenance_skill_names": list(MAINTENANCE_SKILL_NAMES),
        "shell_tools": {
            "shell_bin_dir": str(shell_bin),
            "git_shim_path": str(git_shim_path),
            "rg_path": str(rg_path),
            "required": shell_tools_required,
        },
        "automation_runtime": automation_runtime,
        "retired_standalone_logicguard": retired_standalone_logicguard,
        "checklist": checklist,
        "canonical_interface_checks": canonical_interface_checks,
        "maintenance_skill_checks": maintenance_skill_checks,
        "automation_checks": automation_checks,
        "automation_restore_deferred": restore_deferred,
        "deferred_automation_restore_allowed": bool(allow_deferred_automation_restore),
        "history_migration_required": history_migration_required,
        "history_migration_check": history_migration_check,
        "obsolete_update_state_settled": obsolete_update_state_settled,
        "update_state_source_current": update_state_source_current,
        "current_update_state": current_update_state,
        "upgrade_assurance_required": upgrade_assurance_required,
        "upgrade_assurance": upgrade_assurance,
        "upgrade_assurance_currentness": upgrade_assurance_currentness,
        "upgrade_attempt_authority": upgrade_attempt_authority,
        "upgrade_attempt": active_upgrade_attempt,
        "install_transaction": install_transaction,
        "retired_paths": [str(path) for path in retired_paths],
        "issues": issues,
        "warnings": warnings,
    }
