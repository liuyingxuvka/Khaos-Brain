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
import tempfile
import time
import tomllib
from pathlib import Path
from typing import Any, Mapping

from local_kb.automation_contracts import (
    PRE_RESTORE_ASSURANCE_TIMEOUT_SECONDS,
    SKILLGUARD_COMPLETION_MARKER,
    SKILLGUARD_PARTIAL_MARKER,
    validate_completion_surface,
)
from local_kb.card_ids import load_or_create_installation_id
from local_kb.common import utc_now_iso
from local_kb.transactional_install import (
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
UPGRADE_ATTEMPT_SCHEMA = "khaos-brain.upgrade-attempt.v1"
UPGRADE_ATTEMPT_ROOT = Path(".khaos-brain-install") / "attempts"
REASONING_EFFORT_ORDER = ("none", "minimal", "low", "medium", "high", "xhigh")
AUTOMATION_DAILY_BYDAY = "SU,MO,TU,WE,TH,FR,SA"
RETIRED_MAINTENANCE_SKILL_IDS = ("kb-architect-pass",)
RETIRED_AUTOMATION_IDS = ("kb-architect",)
SKILLGUARD_VALIDATION_ROOT_ENV = "KHAOS_BRAIN_SKILLGUARD_VALIDATION_ROOT"
SKILLGUARD_VALIDATION_DIGEST_ENV = "KHAOS_BRAIN_SKILLGUARD_VALIDATION_DIGEST"
FLOWGUARD_VALIDATION_ROOT_ENV = "KHAOS_BRAIN_FLOWGUARD_VALIDATION_ROOT"
FLOWGUARD_VALIDATION_DIGEST_ENV = "KHAOS_BRAIN_FLOWGUARD_VALIDATION_DIGEST"
LOGICGUARD_VALIDATION_ROOT_ENV = "KHAOS_BRAIN_LOGICGUARD_VALIDATION_ROOT"
LOGICGUARD_VALIDATION_DIGEST_ENV = "KHAOS_BRAIN_LOGICGUARD_VALIDATION_DIGEST"
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
AUTOMATION_SKILLGUARD_COMPLETION_RULE = (
    f"SkillGuard completion rule: {SKILLGUARD_PARTIAL_MARKER}; complete the native route and its "
    f"{SKILLGUARD_COMPLETION_MARKER}. A declared no-op is complete only when the native gate receipt proves its terminal. "
    "Fixture or capability evidence cannot close a scheduled run; the installed SkillGuard builder must bind the exact scheduler execution, current installation receipt id/hash plus portable receipt-root reference, and installed runtime fingerprint. "
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
        "automation_id": "khaos-brain-system-update",
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

SYSTEM_UPDATE_AUTOMATION_PROMPT = (
    "Use $khaos-brain-update only as the fully automatic system-maintenance update gate for this workspace. "
    + AUTOMATION_SKILLGUARD_COMPLETION_RULE
    +
    "Read PROJECT_SPEC.md and .agents/skills/local-kb-retrieve/SKILL.md, then run only "
    "`python scripts/run_kb_guarded_automation.py --skill khaos-brain-update --json`. The guarded runner invokes "
    "the native system-update owner and binds this exact immutable native receipt to SkillGuard; do not run only the child "
    "system-check and call it complete. If apply_ready=false, finish through the sole enforced successful terminal no-op only for "
    "no-update, waiting-for-user, or ui-running; already-upgrading, failed-awaiting-user, concurrent-update, and unknown blockers remain incomplete. "
    "If apply_ready=true, apply the explicitly prepared update through "
    "$khaos-brain-update: preserve local knowledge and settings, use Git fast-forward only, run the transactional "
    "installer and install check, retire legacy managed surfaces, and execute the versioned maintenance migration as a direct-to-current LogicGuard authority cutover. "
    "The migration must publish exact models, scoped meshes, deterministic projections, the exact active index, and the generation pointer last; "
    "it must prove zero retired authority residuals and must not add a runtime legacy reader or projection fallback. Always keep surviving automations paused—"
    "all five of them—through the prepared-update non-terminal declared-check authorization receipt (`authorization_only`, `overall_complete=false`), never a second closure profile. Then bind the preserved states, independent "
    "user_paused values, current source hashes, and exact target automation.toml hashes into a staged restoration receipt; "
    "run a fresh composed enforced SkillGuard closure over authorize+finalize before activating anything. Only after it "
    "passes may the native executor apply those exact hashes, read back every managed state, run the normal install check, "
    "mark CURRENT, and write the activation receipt. Completion means every hard gate passes. On any failure keep or return all survivors to PAUSED, preserve rollback "
    "copies, mark FAILED, and report the machine receipts."
)

# Chaos Brain lifecycle prompts supersede the legacy editorial prompt bodies.
# prompt bodies above.  They are intentionally compact because the Skills own
# the full workflow contract and the automations only select the entrypoint.
SLEEP_AUTOMATION_PROMPT = (
    "Use $kb-sleep-maintenance for the fully automatic local Sleep pass. Read PROJECT_SPEC.md, "
    + AUTOMATION_SKILLGUARD_COMPLETION_RULE
    +
    "docs/maintenance_agent_worldview.md, and .agents/skills/local-kb-retrieve/MAINTENANCE_PROMPT.md. "
    "Run only `python scripts/run_kb_guarded_automation.py --skill kb-sleep-maintenance --json`; the guarded "
    "runner owns lane-to-terminal orchestration, invokes the native Sleep entrypoint "
    "`.agents/skills/local-kb-retrieve/scripts/kb_sleep.py` exactly once, and binds this "
    "run's immutable native receipt to SkillGuard. Do not run the child entrypoint directly. Consume only the committed "
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
    + AUTOMATION_SKILLGUARD_COMPLETION_RULE
    +
    "docs/maintenance_agent_worldview.md, docs/dream_runbook.md, and "
    ".agents/skills/local-kb-retrieve/DREAM_PROMPT.md, then run only "
    "`python scripts/run_kb_guarded_automation.py --skill kb-dream-pass --json`. The guarded runner invokes the "
    "native Dream entrypoint `.agents/skills/local-kb-retrieve/scripts/kb_dream.py` exactly once and binds this run's immutable terminal receipt to SkillGuard; do not "
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
    + AUTOMATION_SKILLGUARD_COMPLETION_RULE
    +
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
    "`python scripts/run_kb_guarded_automation.py --skill kb-organization-contribute --json` for the scheduled pass; "
    "the guarded runner invokes scripts/kb_org_outbox.py --automation exactly once and binds the immutable native "
    "terminal receipt to SkillGuard. Do not run the child entrypoint directly. The native pass should prepare an import branch under kb/imports, then revalidate the exact materialized changed paths, counts, hashes, privacy/shareability, Skill author/version/hash metadata, and base-branch rollback before any push, then push eligible import proposals automatically only after that current revalidation, open a GitHub PR when available, and apply org-kb:auto-merge only when current checks allow it "
    "while leaving movement into organization main, trust upgrades, and final merge to organization maintenance and GitHub checks. Run KB postflight after "
    "any non-skipped pass, record a "
    "structured observation, and report the settings gate, sync result, preflight entries, created and skipped proposal counts, "
    "outbox path, import branch status, push or pull request URL, postflight path, and "
    "errors."
)

ORG_MAINTENANCE_AUTOMATION_PROMPT = (
    "Use $kb-organization-maintenance to run one settings-gated organization-level Sleep-like maintenance pass for this workspace. "
    + AUTOMATION_SKILLGUARD_COMPLETION_RULE
    +
    "Treat the organization KB as a shared exchange layer rather than a central truth layer: "
    "organization maintenance may maintain organization main cards and imported card content with the same editorial "
    "posture as local Sleep, while local machines keep final adoption authority. Use PROJECT_SPEC.md, "
    "docs/maintenance_agent_worldview.md, docs/organization_mode_plan.md, "
    ".agents/skills/local-kb-retrieve/SKILL.md, and organization-review guidance when available. Start by "
    "running only `python scripts/run_kb_guarded_automation.py --skill kb-organization-maintenance --json`; the "
    "guarded runner invokes scripts/kb_org_maintainer.py --automation exactly once and binds its immutable terminal "
    "receipt to SkillGuard. Do not run the child entrypoint directly. The native pass first reads "
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
        "id": "khaos-brain-system-update",
        "name": "Khaos Brain System Update",
        "kind": "cron",
        "prompt": SYSTEM_UPDATE_AUTOMATION_PROMPT,
        "skill_name": "khaos-brain-update",
        "status": "ACTIVE",
        "rrule": "FREQ=WEEKLY;BYDAY=SU,MO,TU,WE,TH,FR,SA;BYHOUR=14;BYMINUTE=0",
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
        "khaos-brain-system-update",
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
    status = (
        existing_status
        if existing_status in {"ACTIVE", "PAUSED"}
        else str(spec["status"]).upper()
    )
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


def _load_upgrade_attempt(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    supplied_hash = str(payload.get("receipt_hash") or "")
    body = dict(payload)
    body.pop("receipt_hash", None)
    if (
        payload.get("schema_version") != UPGRADE_ATTEMPT_SCHEMA
        or not supplied_hash
        or supplied_hash != _canonical_payload_hash(body)
    ):
        return {}
    return payload


def latest_upgrade_attempt(codex_home: Path) -> dict[str, Any]:
    root = codex_home / UPGRADE_ATTEMPT_ROOT
    if not root.is_dir():
        return {}
    candidates: list[tuple[int, Path, dict[str, Any]]] = []
    for current in root.glob("*/current.json"):
        payload = _load_upgrade_attempt(current)
        if payload:
            candidates.append((int(payload.get("sequence") or 0), current, payload))
    if not candidates:
        return {}
    _sequence, path, payload = max(
        candidates,
        key=lambda row: (
            str(row[2].get("updated_at") or ""),
            row[0],
            row[1].as_posix(),
        ),
    )
    return {**payload, "current_path": str(path)}


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
        "schema_version": "khaos-brain.upgrade-attempt-event.v1",
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
    current_body = {
        "schema_version": UPGRADE_ATTEMPT_SCHEMA,
        "attempt_id": attempt_id,
        "status": status,
        "phase": phase,
        "sequence": sequence,
        "started_at": started_at,
        "updated_at": now,
        "latest_event_hash": event_hash,
        "checkpoint_refs": checkpoint_refs,
        **{
            key: value
            for key, value in previous.items()
            if key
            not in {
                "schema_version",
                "attempt_id",
                "status",
                "phase",
                "sequence",
                "started_at",
                "updated_at",
                "latest_event_hash",
                "checkpoint_refs",
                "receipt_hash",
                "current_path",
            }
        },
        **dict(details or {}),
    }
    current = {**current_body, "receipt_hash": _canonical_payload_hash(current_body)}
    attempt_dir.mkdir(parents=True, exist_ok=True)
    _write_text_atomic(
        current_path,
        json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {**current, "current_path": str(current_path)}


def _start_upgrade_attempt(
    codex_home: Path,
    *,
    repo_root: Path,
    pause_before_migration: Mapping[str, Any],
    history_migration: Mapping[str, Any],
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
    for spec in REPO_AUTOMATION_SPECS:
        automation_id = str(spec["id"])
        path = automation_toml_path(automation_id, codex_home)
        payload = _load_automation_toml(path)
        status = str(payload.get("status") or "").upper()
        if payload and status in {"ACTIVE", "PAUSED"}:
            states[automation_id] = status
            user_paused[automation_id] = bool(payload.get("user_paused"))
            sources[automation_id] = "installed"
            continue
        if not path.exists() and automation_id in POST_LEGACY_AUTOMATION_IDS:
            states[automation_id] = str(spec["status"]).upper()
            user_paused[automation_id] = False
            sources[automation_id] = "new-automation-policy"
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
        # A five-file restoration is one logical activation.  Compensate a
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
    lines = [
        f"version = {int(payload['version'])}",
        f"id = {json.dumps(payload['id'], ensure_ascii=False)}",
        f"kind = {json.dumps(payload['kind'], ensure_ascii=False)}",
        f"name = {json.dumps(payload['name'], ensure_ascii=False)}",
        f"prompt = {json.dumps(payload['prompt'], ensure_ascii=False)}",
        f"status = {json.dumps(payload['status'], ensure_ascii=False)}",
        f"user_paused = {json.dumps(bool(payload.get('user_paused', False)), ensure_ascii=False).lower()}",
        f"rrule = {json.dumps(payload['rrule'], ensure_ascii=False)}",
        f"schedule_policy = {json.dumps(payload.get('schedule_policy', 'fixed'), ensure_ascii=False)}",
        f"schedule_window = {json.dumps(payload.get('schedule_window', ''), ensure_ascii=False)}",
        f"model = {json.dumps(payload['model'], ensure_ascii=False)}",
        f"reasoning_effort = {json.dumps(payload['reasoning_effort'], ensure_ascii=False)}",
        f"model_policy = {json.dumps(payload['model_policy'], ensure_ascii=False)}",
        f"reasoning_effort_policy = {json.dumps(payload['reasoning_effort_policy'], ensure_ascii=False)}",
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


def _skillguard_runtime_roots(
    codex_home: Path,
    explicit_root: Path | None = None,
) -> tuple[Path, ...]:
    roots: list[Path] = []
    environment_root = os.environ.get(SKILLGUARD_VALIDATION_ROOT_ENV, "").strip()
    for candidate in (
        explicit_root,
        Path(environment_root) if environment_root else None,
        codex_home / "skills" / "skillguard",
        default_codex_home() / "skills" / "skillguard",
    ):
        if candidate is None:
            continue
        resolved = Path(candidate).resolve()
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def _skillguard_compiler_path(
    codex_home: Path,
    skillguard_root: Path | None = None,
) -> Path:
    for root in _skillguard_runtime_roots(codex_home, skillguard_root):
        path = root / "scripts" / "skillguard_compile.py"
        if path.is_file():
            return path
    raise FileNotFoundError(
        "The current SkillGuard compiler is required before Chaos Brain managed Skills can be activated."
    )


def _freeze_skillguard_validation_toolchain(
    codex_home: Path,
    destination: Path,
    *,
    max_attempts: int = 20,
) -> dict[str, Any]:
    """Install one exact SkillGuard identity into an isolated validation home.

    The source tree is never activated in the user's real Codex home.  It is
    copied into the rollbackable Khaos upgrade attempt, installed with the
    official SkillGuard transaction owner, and bound to an official current
    installation receipt before scheduled-production validation may consume it.
    """

    inherited_root = os.environ.get(SKILLGUARD_VALIDATION_ROOT_ENV, "").strip()
    inherited_digest = os.environ.get(SKILLGUARD_VALIDATION_DIGEST_ENV, "").strip()
    if inherited_root and inherited_digest:
        root = Path(inherited_root).resolve()
        router_root = root.parent / "skillguard-global-router"
        validation_codex_home = root.parent.parent
        manifest = tree_manifest(root) if root.is_dir() else {}
        router_manifest = tree_manifest(router_root) if router_root.is_dir() else {}
        if (
            str(manifest.get("digest") or "") == inherited_digest
            and validation_codex_home.name == ".codex"
            and (root / "scripts" / "skillguard_compile.py").is_file()
            and (root / "scripts" / "skillguard.py").is_file()
            and (router_root / "SKILL.md").is_file()
            and (
                root / ".sg-runtime" / "installation" / "HEAD.json"
            ).is_file()
        ):
            receipt = {
                "schema_version": "khaos-brain.skillguard-validation-toolchain.v2",
                "ok": True,
                "status": "inherited_isolated_installation",
                "source_root": str(root),
                "source_manifest": manifest,
                "canonical_snapshot_root": str(root),
                "canonical_manifest": manifest,
                "snapshot_root": str(root),
                "manifest": manifest,
                "router_source_root": str(router_root),
                "router_source_manifest": router_manifest,
                "router_canonical_snapshot_root": str(router_root),
                "router_canonical_manifest": router_manifest,
                "router_snapshot_root": str(router_root),
                "router_manifest": router_manifest,
                "validation_codex_home": str(validation_codex_home),
                "installation_python_executable": os.environ.get(
                    INSTALLATION_IDENTITY_PYTHON_EXECUTABLE_ENV,
                    sys.executable,
                ),
                "installation_receipt_root": str(
                    root / ".sg-runtime" / "installation"
                ),
                "compiler_sha256": _file_sha256(
                    root / "scripts" / "skillguard_compile.py"
                ),
                "cli_sha256": _file_sha256(root / "scripts" / "skillguard.py"),
            }
            receipt["receipt_hash"] = _canonical_payload_hash(receipt)
            return receipt

    destination = destination.resolve()
    if not (
        destination.name == "skillguard"
        and destination.parent.name == "skills"
        and destination.parent.parent.name == ".agents"
    ):
        raise ValueError(
            "SkillGuard canonical snapshot must end with .agents/skills/skillguard"
        )
    canonical_repository_root = destination.parents[2]
    snapshot_parent = destination.parents[3]
    staging = destination.with_name(f".{destination.name}.staging")
    router_destination = destination.parent / "skillguard-global-router"
    router_staging = router_destination.with_name(
        f".{router_destination.name}.staging"
    )
    stage_root = snapshot_parent / "stage" / ".codex" / "skills" / "skillguard"
    validation_codex_home = snapshot_parent / "installed" / ".codex"
    last_error = "skillguard_runtime_missing"
    for attempt in range(1, max_attempts + 1):
        source = next(
            (
                root
                for root in _skillguard_runtime_roots(codex_home)
                if (root / "scripts" / "skillguard_compile.py").is_file()
                and (root / "scripts" / "skillguard.py").is_file()
            ),
            None,
        )
        if source is None:
            last_error = "skillguard_runtime_missing"
            time.sleep(0.5)
            continue
        source_router = source.parent / "skillguard-global-router"
        if not (source_router / "SKILL.md").is_file():
            last_error = "skillguard_global_router_runtime_missing"
            time.sleep(0.5)
            continue
        try:
            before = tree_manifest(source)
            router_before = tree_manifest(source_router)
            if staging.exists():
                shutil.rmtree(staging)
            if router_staging.exists():
                shutil.rmtree(router_staging)
            staging.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                source,
                staging,
                ignore=shutil.ignore_patterns(
                    "__pycache__",
                    "*.pyc",
                    "*.pyo",
                    "runs",
                    "locks",
                    "bootstrap",
                    "test-results",
                    ".sg-runtime",
                ),
            )
            shutil.copytree(
                source_router,
                router_staging,
                ignore=shutil.ignore_patterns(
                    "__pycache__",
                    "*.pyc",
                    "*.pyo",
                    "runs",
                    "locks",
                    "bootstrap",
                    "test-results",
                    ".sg-runtime",
                ),
            )
            after = tree_manifest(source)
            router_after = tree_manifest(source_router)
            snapshot = tree_manifest(staging)
            router_snapshot = tree_manifest(router_staging)
            portable_source_rows = [
                row
                for row in list(before.get("files") or [])
                if not str(row.get("path") or "").startswith(".sg-runtime/")
            ]
            if not (
                before == after
                and portable_source_rows == list(snapshot.get("files") or [])
                and router_before == router_after == router_snapshot
                and (staging / "scripts" / "skillguard_compile.py").is_file()
                and (staging / "scripts" / "skillguard.py").is_file()
                and (staging / "scripts" / "skillguard_install.py").is_file()
                and (router_staging / "SKILL.md").is_file()
            ):
                last_error = "skillguard_source_changed_during_snapshot"
                shutil.rmtree(staging, ignore_errors=True)
                shutil.rmtree(router_staging, ignore_errors=True)
                time.sleep(0.5)
                continue
            if destination.exists():
                shutil.rmtree(destination)
            if router_destination.exists():
                shutil.rmtree(router_destination)
            os.replace(staging, destination)
            os.replace(router_staging, router_destination)

            for controlled_root in (stage_root.parents[2], validation_codex_home.parent):
                try:
                    controlled_root.relative_to(snapshot_parent)
                except ValueError as exc:
                    raise RuntimeError(
                        "isolated SkillGuard validation root escaped its upgrade attempt"
                    ) from exc
                if controlled_root.exists():
                    shutil.rmtree(controlled_root)

            installer = destination / "scripts" / "skillguard_install.py"
            install_process = subprocess.run(
                [
                    sys.executable,
                    str(installer),
                    "--canonical-skill-root",
                    str(destination),
                    "--stage-root",
                    str(stage_root),
                    "--codex-home",
                    str(validation_codex_home),
                    "--prepare",
                    "--activate",
                ],
                cwd=str(canonical_repository_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
                check=False,
            )
            try:
                install_report = json.loads(install_process.stdout)
            except json.JSONDecodeError:
                install_report = {}
            if (
                install_process.returncode != 0
                or str(install_report.get("status") or "") != "passed"
            ):
                detail = install_report or install_process.stderr or install_process.stdout
                raise RuntimeError(
                    "Isolated SkillGuard transaction installation failed: " + str(detail)
                )

            installed_root = validation_codex_home / "skills" / "skillguard"
            installed_router_root = (
                validation_codex_home / "skills" / "skillguard-global-router"
            )
            installed_cli = installed_root / "scripts" / "skillguard.py"
            command_prefix = [
                sys.executable,
                str(installed_cli),
            ]
            common_receipt_arguments = [
                "--repository-root",
                str(canonical_repository_root),
                "--canonical-skill-root",
                ".agents/skills/skillguard",
                "--codex-home",
                str(validation_codex_home),
                "--output",
                "-",
            ]
            capture_process = subprocess.run(
                [
                    *command_prefix,
                    "capture-installation-receipt",
                    *common_receipt_arguments,
                ],
                cwd=str(canonical_repository_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            try:
                capture_report = json.loads(capture_process.stdout)
            except json.JSONDecodeError:
                capture_report = {}
            if (
                capture_process.returncode != 0
                or str(capture_report.get("status") or "") != "passed"
            ):
                detail = capture_report or capture_process.stderr or capture_process.stdout
                raise RuntimeError(
                    "Isolated SkillGuard installation receipt capture failed: "
                    + str(detail)
                )
            verify_process = subprocess.run(
                [
                    *command_prefix,
                    "verify-installation-receipt",
                    *common_receipt_arguments,
                    "--require-current-installed-parity",
                ],
                cwd=str(canonical_repository_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            try:
                verify_report = json.loads(verify_process.stdout)
            except json.JSONDecodeError:
                verify_report = {}
            if (
                verify_process.returncode != 0
                or str(verify_report.get("status") or "") != "passed"
            ):
                detail = verify_report or verify_process.stderr or verify_process.stdout
                raise RuntimeError(
                    "Isolated SkillGuard installation receipt verification failed: "
                    + str(detail)
                )

            installation_receipt_root = (
                installed_root / ".sg-runtime" / "installation"
            )
            if not (installation_receipt_root / "HEAD.json").is_file():
                raise RuntimeError(
                    "Isolated SkillGuard current installation receipt is unavailable"
                )
            installed_manifest = tree_manifest(installed_root)
            installed_router_manifest = tree_manifest(installed_router_root)
            canonical_manifest = tree_manifest(destination)
            canonical_router_manifest = tree_manifest(router_destination)
            if not (
                before == tree_manifest(source)
                and router_before == tree_manifest(source_router)
                and canonical_manifest == snapshot
                and canonical_router_manifest == router_snapshot
            ):
                raise RuntimeError(
                    "SkillGuard source or canonical validation snapshot changed during isolated installation"
                )
            receipt = {
                "schema_version": "khaos-brain.skillguard-validation-toolchain.v2",
                "ok": True,
                "status": "isolated_installed_current",
                "attempt_count": attempt,
                "source_root": str(source),
                "source_manifest": before,
                "canonical_snapshot_root": str(destination),
                "canonical_manifest": canonical_manifest,
                "snapshot_root": str(installed_root),
                "manifest": installed_manifest,
                "router_source_root": str(source_router),
                "router_source_manifest": router_before,
                "router_canonical_snapshot_root": str(router_destination),
                "router_canonical_manifest": canonical_router_manifest,
                "router_snapshot_root": str(installed_router_root),
                "router_manifest": installed_router_manifest,
                "validation_codex_home": str(validation_codex_home),
                "installation_python_executable": sys.executable,
                "installation_receipt_root": str(installation_receipt_root),
                "installation_transaction_id": str(
                    ((install_report.get("reports") or [{}])[-1]).get(
                        "transaction_id"
                    )
                    or ""
                ),
                "installation_receipt_id": str(
                    capture_report.get("receipt_id") or ""
                ),
                "installation_receipt_hash": str(
                    capture_report.get("receipt_hash") or ""
                ),
                "compiler_sha256": _file_sha256(
                    installed_root / "scripts" / "skillguard_compile.py"
                ),
                "cli_sha256": _file_sha256(
                    installed_root / "scripts" / "skillguard.py"
                ),
            }
            receipt["receipt_hash"] = _canonical_payload_hash(receipt)
            receipt_path = destination.parent / "skillguard-validation-toolchain.json"
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
            shutil.rmtree(router_staging, ignore_errors=True)
            time.sleep(0.5)
    raise RuntimeError(
        "Unable to freeze one current SkillGuard validation toolchain: " + last_error
    )


def _require_live_skillguard_matches_snapshot(receipt: Mapping[str, Any]) -> None:
    source = Path(str(receipt.get("source_root") or ""))
    expected = str((receipt.get("source_manifest") or {}).get("digest") or "")
    actual = tree_manifest(source) if source.is_dir() else {}
    if not expected or str(actual.get("digest") or "") != expected:
        raise RuntimeError(
            "Live SkillGuard identity changed after validation snapshot; "
            "restart the idempotent upgrade against one current toolchain identity."
        )
    router_source = Path(str(receipt.get("router_source_root") or ""))
    expected_router = str(
        (receipt.get("router_source_manifest") or {}).get("digest") or ""
    )
    actual_router = tree_manifest(router_source) if router_source.is_dir() else {}
    if (
        not expected_router
        or str(actual_router.get("digest") or "") != expected_router
    ):
        raise RuntimeError(
            "Live SkillGuard global-router identity changed after validation snapshot; "
            "restart the idempotent upgrade against one current toolchain identity."
        )
    snapshot_root = Path(str(receipt.get("snapshot_root") or ""))
    expected_snapshot = str((receipt.get("manifest") or {}).get("digest") or "")
    actual_snapshot = tree_manifest(snapshot_root) if snapshot_root.is_dir() else {}
    router_snapshot_root = Path(str(receipt.get("router_snapshot_root") or ""))
    expected_router_snapshot = str(
        (receipt.get("router_manifest") or {}).get("digest") or ""
    )
    actual_router_snapshot = (
        tree_manifest(router_snapshot_root) if router_snapshot_root.is_dir() else {}
    )
    if (
        not expected_snapshot
        or str(actual_snapshot.get("digest") or "") != expected_snapshot
        or not expected_router_snapshot
        or str(actual_router_snapshot.get("digest") or "")
        != expected_router_snapshot
    ):
        raise RuntimeError(
            "Isolated installed SkillGuard validation identity changed after receipt capture; "
            "restart the idempotent upgrade."
        )


def _cleanup_ephemeral_skillguard_validation_toolchain(
    declared_root: Path | None,
) -> dict[str, Any]:
    if declared_root is None:
        return {"ok": True, "status": "not_required", "removed": False}
    root = Path(declared_root).resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if root.parent != temp_root or not root.name.startswith("khaos-sg-"):
        raise RuntimeError(
            "Refusing to clean a SkillGuard validation root outside the exact Khaos temp namespace"
        )
    if root.exists():
        shutil.rmtree(root)
    return {
        "ok": not root.exists(),
        "status": "removed" if not root.exists() else "failed",
        "removed": not root.exists(),
        "root": str(root),
    }


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


def _freeze_logicguard_validation_toolchain(
    destination: Path,
    *,
    source_root: Path | None = None,
    max_attempts: int = 20,
) -> dict[str, Any]:
    """Freeze the exact LogicGuard package that owns current model authority."""

    inherited_root = os.environ.get(LOGICGUARD_VALIDATION_ROOT_ENV, "").strip()
    inherited_digest = os.environ.get(LOGICGUARD_VALIDATION_DIGEST_ENV, "").strip()
    if source_root is None and inherited_root and inherited_digest:
        root = Path(inherited_root).resolve()
        manifest = tree_manifest(root) if root.is_dir() else {}
        if (
            str(manifest.get("digest") or "") == inherited_digest
            and (root / "__init__.py").is_file()
        ):
            receipt = {
                "schema_version": "khaos-brain.logicguard-validation-toolchain.v1",
                "ok": True,
                "status": "inherited_frozen",
                "source_root": str(root),
                "snapshot_root": str(root),
                "manifest": manifest,
            }
            receipt["receipt_hash"] = _canonical_payload_hash(receipt)
            return receipt

    dependency: dict[str, Any] = {}
    if source_root is None:
        from local_kb.logicguard_models import logicguard_dependency_preflight

        dependency = logicguard_dependency_preflight()
        module = importlib.import_module("logicguard")
        source_root = Path(str(module.__file__)).resolve().parent
    source = Path(source_root).resolve() if source_root is not None else None
    if source is None or not (source / "__init__.py").is_file():
        raise RuntimeError("Current LogicGuard package is unavailable for validation freeze")

    destination = destination.resolve()
    staging = destination.with_name(f".{destination.name}.staging")
    last_error = "logicguard_source_unavailable"
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
                last_error = "logicguard_source_changed_during_snapshot"
                shutil.rmtree(staging, ignore_errors=True)
                time.sleep(0.5)
                continue
            if destination.exists():
                shutil.rmtree(destination)
            os.replace(staging, destination)
            receipt = {
                "schema_version": "khaos-brain.logicguard-validation-toolchain.v1",
                "ok": True,
                "status": "frozen",
                "attempt_count": attempt,
                "source_root": str(source),
                "snapshot_root": str(destination),
                "manifest": snapshot,
                "dependency": dependency,
            }
            receipt["receipt_hash"] = _canonical_payload_hash(receipt)
            receipt_path = destination.parent / "logicguard-validation-toolchain.json"
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
        "Unable to freeze one current LogicGuard validation toolchain: " + last_error
    )


def _require_live_logicguard_matches_snapshot(receipt: Mapping[str, Any]) -> None:
    source = Path(str(receipt.get("source_root") or ""))
    expected = str((receipt.get("manifest") or {}).get("digest") or "")
    actual = tree_manifest(source) if source.is_dir() else {}
    if not expected or str(actual.get("digest") or "") != expected:
        raise RuntimeError(
            "Live LogicGuard identity changed after validation snapshot; "
            "restart the idempotent upgrade against one current toolchain identity."
        )


def _transaction_receipt_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise RuntimeError(f"Validation identity is unavailable: {path}: {exc}") from exc


def _require_unchanged_validation_file(
    path: Path, expected_sha256: str, *, identity: str
) -> None:
    actual_sha256 = _file_sha256(path)
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            f"Validation identity changed during source validation: {identity}: "
            f"expected={expected_sha256} actual={actual_sha256}"
        )


def _check_repo_skillguard_current_sources(
    repo_root: Path,
    codex_home: Path,
    *,
    skillguard_root: Path | None = None,
) -> list[dict[str, Any]]:
    compiler = _skillguard_compiler_path(codex_home, skillguard_root)
    generator = repo_root / "scripts" / "build_kb_automation_skillguard_contracts.py"
    generator_sha256 = _file_sha256(generator)
    compiler_sha256 = _file_sha256(compiler)
    generator_process = subprocess.run(
        [sys.executable, str(generator), "--check", "--json"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    _require_unchanged_validation_file(
        generator, generator_sha256, identity="target-owned-generator"
    )
    _require_unchanged_validation_file(
        compiler, compiler_sha256, identity="current-skillguard-compiler"
    )
    try:
        generator_report = json.loads(generator_process.stdout)
    except json.JSONDecodeError:
        generator_report = {}
    if generator_process.returncode != 0 or not bool(generator_report.get("ok")):
        detail = generator_report or generator_process.stderr or generator_process.stdout
        raise RuntimeError(f"Target-owned SkillGuard generation parity failed: {detail}")
    generator_check_hash = _transaction_receipt_hash(generator_report)

    checks: list[dict[str, Any]] = []
    for spec in MAINTENANCE_SKILL_SPECS:
        skill_name = str(spec["name"])
        skill_root = maintenance_skill_source_dir(repo_root, skill_name)
        for relative in (
            "SKILL.md",
            ".skillguard/contract-source.json",
            ".skillguard/compiled-contract.json",
            ".skillguard/check-manifest.json",
        ):
                path = skill_root / relative
                if not path.is_file():
                    raise FileNotFoundError(f"Managed Skill current authority is missing: {path}")
        before_manifest = tree_manifest(skill_root)
        _require_unchanged_validation_file(
            compiler,
            compiler_sha256,
            identity=f"current-skillguard-compiler:before:{skill_name}",
        )
        process = subprocess.run(
            [
                sys.executable,
                str(compiler),
                str(skill_root),
                "--repository-root",
                str(repo_root),
                "--check",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        _require_unchanged_validation_file(
            compiler,
            compiler_sha256,
            identity=f"current-skillguard-compiler:after:{skill_name}",
        )
        _require_unchanged_validation_file(
            generator,
            generator_sha256,
            identity=f"target-owned-generator:after:{skill_name}",
        )
        manifest = tree_manifest(skill_root)
        if manifest.get("digest") != before_manifest.get("digest"):
            raise RuntimeError(
                f"Managed Skill source changed during current validation: {skill_name}: "
                f"before={before_manifest.get('digest')} after={manifest.get('digest')}"
            )
        try:
            payload = json.loads(process.stdout)
        except json.JSONDecodeError:
            payload = {}
        if process.returncode != 0 or not bool(payload.get("ok")):
            detail = payload.get("findings") or process.stderr or process.stdout
            raise RuntimeError(f"SkillGuard current parity failed for {skill_name}: {detail}")
        receipt: dict[str, Any] = {
            "schema_version": "chaos_brain.skillguard_source_validation.v1",
            "skill_id": skill_name,
            "status": "current",
            "ok": True,
            "source_tree_digest": str(manifest.get("digest") or ""),
            "contract_hash": str(payload.get("contract_hash") or ""),
            "manifest_hash": str(payload.get("manifest_hash") or ""),
            "contract_source_sha256": hashlib.sha256(
                (skill_root / ".skillguard" / "contract-source.json").read_bytes()
            ).hexdigest(),
            "compiled_contract_sha256": hashlib.sha256(
                (skill_root / ".skillguard" / "compiled-contract.json").read_bytes()
            ).hexdigest(),
            "check_manifest_sha256": hashlib.sha256(
                (skill_root / ".skillguard" / "check-manifest.json").read_bytes()
            ).hexdigest(),
            "compiler_sha256": compiler_sha256,
            "generator_sha256": generator_sha256,
            "generator_check_hash": generator_check_hash,
        }
        receipt["validation_input_hash"] = _transaction_receipt_hash(receipt)
        receipt["receipt_hash"] = _transaction_receipt_hash(receipt)
        checks.append(receipt)
    _require_unchanged_validation_file(
        compiler, compiler_sha256, identity="current-skillguard-compiler:final"
    )
    _require_unchanged_validation_file(
        generator, generator_sha256, identity="target-owned-generator:final"
    )
    return checks


def _refresh_skillguard_global_router(codex_home: Path) -> dict[str, Any]:
    cli_candidates = tuple(
        root / "scripts" / "skillguard.py"
        for root in _skillguard_runtime_roots(codex_home)
    )
    cli = next((path for path in cli_candidates if path.is_file()), None)
    if cli is None:
        raise FileNotFoundError("SkillGuard CLI is required to refresh the global router after retirement.")
    process = subprocess.run(
        [
            sys.executable,
            str(cli),
            "refresh-global-router",
            "--codex-home",
            str(codex_home),
            "--output",
            "-",
        ],
        cwd=str(codex_home),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
        check=False,
    )
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError:
        payload = {}
    if process.returncode != 0 or str(payload.get("decision") or "") != "pass":
        raise RuntimeError(
            "SkillGuard global-router refresh failed: "
            + str(payload.get("failures") or process.stderr or process.stdout)
        )
    return payload


def _skillguard_router_surface(codex_home: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for skill_name in ("skillguard", "skillguard-global-router"):
        root = codex_home / "skills" / skill_name
        if not root.is_dir():
            rows.append({"skill_name": skill_name, "present": False, "digest": ""})
            continue
        manifest = tree_manifest(root)
        rows.append(
            {
                "skill_name": skill_name,
                "present": True,
                "digest": str(manifest.get("digest") or ""),
                "file_count": int(manifest.get("file_count") or 0),
            }
        )
    return {
        "rows": rows,
        "surface_hash": _canonical_payload_hash({"rows": rows}),
    }


def _run_skillguard_router_check(
    codex_home: Path,
    *,
    command: str,
    registry_path: Path,
) -> dict[str, Any]:
    cli_candidates = tuple(
        root / "scripts" / "skillguard.py"
        for root in _skillguard_runtime_roots(codex_home)
    )
    cli = next((path for path in cli_candidates if path.is_file()), None)
    if cli is None:
        return {
            "ok": False,
            "decision": "block",
            "command": command,
            "blockers": ["skillguard_cli_missing"],
        }
    arguments = [
        sys.executable,
        str(cli),
        command,
        "--registry",
        str(registry_path),
    ]
    arguments.extend(
        [
            "--codex-home",
            str(codex_home),
            "--output",
            "-",
        ]
    )
    process = subprocess.run(
        arguments,
        cwd=str(codex_home),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
        check=False,
    )
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError:
        payload = {}
    return {
        **(payload if isinstance(payload, dict) else {}),
        "ok": process.returncode == 0
        and str(payload.get("decision") or "") == "pass",
        "exit_code": process.returncode,
        "command": command,
        "stderr_tail": process.stderr[-2000:],
    }


def _verify_skillguard_global_router(
    codex_home: Path,
    refresh_payload: Mapping[str, Any],
) -> dict[str, Any]:
    registry_text = str(refresh_payload.get("registry_path") or "").strip()
    canonical_registry = (
        codex_home / ".skillguard" / "global-router" / "global_registry.json"
    ).resolve()
    display_registry = Path(registry_text).expanduser() if registry_text else Path()
    registry_candidates = [
        canonical_registry,
        display_registry.resolve() if registry_text and display_registry.is_absolute() else Path(),
        (Path.home() / display_registry).resolve() if registry_text else Path(),
        (codex_home / display_registry).resolve() if registry_text else Path(),
    ]
    registry_path = next(
        (candidate for candidate in registry_candidates if candidate.is_file()),
        canonical_registry,
    )
    registry = _run_skillguard_router_check(
        codex_home,
        command="check-global-registry",
        registry_path=registry_path,
    )
    prompt = _run_skillguard_router_check(
        codex_home,
        command="check-global-prompt",
        registry_path=registry_path,
    )
    return {
        "ok": bool(registry.get("ok") and prompt.get("ok")),
        "registry_path": str(registry_path),
        "registry_hash": str(refresh_payload.get("registry_hash") or ""),
        "registry_check": registry,
        "prompt_check": prompt,
        "checked_at": utc_now_iso(),
        "claim_boundary": (
            "Current official registry and managed-prompt freshness against the active "
            "SkillGuard/skill roots only."
        ),
    }


def _refresh_and_verify_skillguard_global_router(
    codex_home: Path,
    *,
    max_attempts: int = 2,
) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for attempt_number in range(1, max_attempts + 1):
        refresh = _refresh_skillguard_global_router(codex_home)
        surface_after_refresh = _skillguard_router_surface(codex_home)
        live = _verify_skillguard_global_router(codex_home, refresh)
        surface_after_check = _skillguard_router_surface(codex_home)
        stable = (
            surface_after_refresh.get("surface_hash")
            == surface_after_check.get("surface_hash")
        )
        last = {
            "ok": bool(live.get("ok") and stable),
            "attempt_number": attempt_number,
            "refresh": refresh,
            "live_freshness": live,
            "surface_after_refresh": surface_after_refresh,
            "surface_after_check": surface_after_check,
            "surface_stable": stable,
        }
        if last["ok"]:
            return last
    raise RuntimeError(
        "SkillGuard global router did not remain current after refresh: "
        + str(
            last.get("live_freshness", {}).get("registry_check", {}).get("failures")
            or last.get("live_freshness", {}).get("registry_check", {}).get("blockers")
            or last.get("live_freshness", {}).get("prompt_check", {}).get("failures")
            or last.get("live_freshness", {}).get("prompt_check", {}).get("blockers")
            or "active SkillGuard surface changed during verification"
        )
    )


def _run_pre_restore_upgrade_assurance(
    repo_root: Path,
    codex_home: Path,
    *,
    skillguard_validation_toolchain: Mapping[str, Any],
    flowguard_validation_toolchain: Mapping[str, Any],
    logicguard_validation_toolchain: Mapping[str, Any],
) -> dict[str, Any]:
    script = repo_root / "scripts" / "check_chaos_brain_readiness.py"
    environment = os.environ.copy()
    environment[SKILLGUARD_VALIDATION_ROOT_ENV] = str(
        skillguard_validation_toolchain.get("snapshot_root") or ""
    )
    environment[SKILLGUARD_VALIDATION_DIGEST_ENV] = str(
        (skillguard_validation_toolchain.get("manifest") or {}).get("digest") or ""
    )
    environment[INSTALLATION_IDENTITY_PYTHON_EXECUTABLE_ENV] = str(
        skillguard_validation_toolchain.get("installation_python_executable")
        or sys.executable
    )
    flowguard_root = Path(
        str(flowguard_validation_toolchain.get("snapshot_root") or "")
    ).resolve()
    environment[FLOWGUARD_VALIDATION_ROOT_ENV] = str(flowguard_root)
    environment[FLOWGUARD_VALIDATION_DIGEST_ENV] = str(
        (flowguard_validation_toolchain.get("manifest") or {}).get("digest") or ""
    )
    logicguard_root = Path(
        str(logicguard_validation_toolchain.get("snapshot_root") or "")
    ).resolve()
    environment[LOGICGUARD_VALIDATION_ROOT_ENV] = str(logicguard_root)
    environment[LOGICGUARD_VALIDATION_DIGEST_ENV] = str(
        (logicguard_validation_toolchain.get("manifest") or {}).get("digest") or ""
    )
    existing_pythonpath = environment.get("PYTHONPATH", "")
    if INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV not in environment:
        environment[INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV] = (
            "1" if "PYTHONPATH" in environment else "0"
        )
        environment[INSTALLATION_IDENTITY_PYTHONPATH_VALUE_ENV] = existing_pythonpath
    validation_parents = (str(flowguard_root.parent), str(logicguard_root.parent))
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
        "--pre-restore",
        "--repo-root",
        str(repo_root),
        "--codex-home",
        str(codex_home),
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
    if process.returncode != 0 or not bool(payload.get("ok")):
        failed_checks = list(payload.get("failed_checks") or [])
        entries = (
            payload.get("checks")
            if isinstance(payload.get("checks"), Mapping)
            else payload.get("entries")
            if isinstance(payload.get("entries"), Mapping)
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
                    "fallback_diagnostic": (
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


def _run_post_assurance_data_convergence(
    repo_root: Path,
    *,
    max_attempts: int = 4,
) -> dict[str, Any]:
    """Drain data admitted during long assurance and recheck dependent gates."""

    from local_kb.maintenance_migration import (
        check_migration,
        run_maintenance_migration,
    )
    from scripts.evaluate_kb_retrieval import build_report as build_retrieval_report

    root = Path(repo_root).resolve()
    attempts: list[dict[str, Any]] = []
    final_migration: dict[str, Any] = {}
    final_retrieval: dict[str, Any] = {}
    final_check: dict[str, Any] = {}
    for attempt in range(1, max_attempts + 1):
        final_migration = run_maintenance_migration(root)
        if final_migration.get("ok"):
            final_retrieval = build_retrieval_report(
                root,
                root / "tests" / "fixtures" / "kb_retrieval_eval_cases.json",
            )
            final_check = check_migration(root)
        else:
            final_retrieval = {}
            final_check = {}
        attempt_receipt = {
            "attempt": attempt,
            "migration_ok": bool(final_migration.get("ok")),
            "migration_status": str(final_migration.get("status") or ""),
            "migration_issues": list(final_migration.get("issues") or []),
            "retrieval_ok": bool(final_retrieval.get("ok")),
            "retrieval_metrics": dict(final_retrieval.get("metrics") or {}),
            "retrieval_threshold_results": dict(
                final_retrieval.get("threshold_results") or {}
            ),
            "migration_check_ok": bool(final_check.get("ok")),
            "migration_check_issues": list(final_check.get("issues") or []),
        }
        attempt_receipt["receipt_hash"] = _canonical_payload_hash(attempt_receipt)
        attempts.append(attempt_receipt)
        if (
            final_migration.get("ok")
            and final_retrieval.get("ok")
            and final_check.get("ok")
        ):
            result = {
                "schema_version": "khaos-brain.post-assurance-data-convergence.v1",
                "ok": True,
                "status": "current",
                "attempt_count": attempt,
                "attempts": attempts,
                "history_migration": final_migration,
                "retrieval_evaluation": final_retrieval,
                "migration_check": final_check,
            }
            result["receipt_hash"] = _canonical_payload_hash(result)
            return result
    result = {
        "schema_version": "khaos-brain.post-assurance-data-convergence.v1",
        "ok": False,
        "status": "paused_failed",
        "attempt_count": len(attempts),
        "attempts": attempts,
        "history_migration": final_migration,
        "retrieval_evaluation": final_retrieval,
        "migration_check": final_check,
    }
    result["receipt_hash"] = _canonical_payload_hash(result)
    return result


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
    skillguard_validation_toolchain: Mapping[str, Any] | None = None,
    flowguard_validation_toolchain: Mapping[str, Any] | None = None,
    logicguard_validation_toolchain: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    home = codex_home or default_codex_home()
    initial_history_migration = dict(history_migration or {})
    post_assurance_history_migration: dict[str, Any] = {}
    post_assurance_data_convergence: dict[str, Any] = {}
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
    validation_toolchain = dict(skillguard_validation_toolchain or {})
    validation_root = Path(str(validation_toolchain.get("snapshot_root") or ""))
    if not validation_root.is_dir():
        raise RuntimeError("Frozen SkillGuard validation toolchain is unavailable")
    flowguard_toolchain = dict(flowguard_validation_toolchain or {})
    flowguard_validation_root = Path(
        str(flowguard_toolchain.get("snapshot_root") or "")
    )
    if not (flowguard_validation_root / "__init__.py").is_file():
        raise RuntimeError("Frozen FlowGuard validation toolchain is unavailable")
    logicguard_toolchain = dict(logicguard_validation_toolchain or {})
    logicguard_validation_root = Path(
        str(logicguard_toolchain.get("snapshot_root") or "")
    )
    if not (logicguard_validation_root / "__init__.py").is_file():
        raise RuntimeError("Frozen LogicGuard validation toolchain is unavailable")
    skillguard_source_checks = _check_repo_skillguard_current_sources(
        repo_root,
        home,
        skillguard_root=validation_root,
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
        skillguard_validation_receipts={
            str(row["skill_id"]): row for row in skillguard_source_checks
        },
        automation_payloads=activation_payloads,
        automation_renderer=_automation_toml_text,
        retired_skill_ids=RETIRED_MAINTENANCE_SKILL_IDS,
        retired_automation_ids=RETIRED_AUTOMATION_IDS,
    )
    if safe_upgrade:
        paused_transaction = transaction
        from local_kb.software_update import canonicalize_obsolete_update_state

        pre_assurance_update_state_migration = canonicalize_obsolete_update_state(
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
    global_router_refresh: dict[str, Any] = {}
    global_router_live_freshness: dict[str, Any] = {}
    pre_assurance_global_router: dict[str, Any] = {}
    upgrade_assurance: dict[str, Any] = {}
    if safe_upgrade:
        pre_assurance_global_router = _refresh_and_verify_skillguard_global_router(home)
        if upgrade_attempt_id:
            _record_upgrade_attempt(
                home,
                upgrade_attempt_id,
                phase="pre_assurance_router_current",
                status="in_progress",
                details={
                    "pre_assurance_global_router": pre_assurance_global_router,
                    "survivors_must_remain_paused": True,
                },
            )
        if require_upgrade_assurance:
            # Do not spend a long aggregate campaign against a validation
            # toolchain that is already stale.  A change that happens during
            # the campaign is still caught by the identical restore-gate
            # checks below; neither case authorizes reinstalling that tool.
            _require_live_skillguard_matches_snapshot(validation_toolchain)
            _require_live_flowguard_matches_snapshot(flowguard_toolchain)
            _require_live_logicguard_matches_snapshot(logicguard_toolchain)
            upgrade_assurance = _run_pre_restore_upgrade_assurance(
                repo_root,
                home,
                skillguard_validation_toolchain=validation_toolchain,
                flowguard_validation_toolchain=flowguard_toolchain,
                logicguard_validation_toolchain=logicguard_toolchain,
            )
            if upgrade_attempt_id:
                _record_upgrade_attempt(
                    home,
                    upgrade_attempt_id,
                    phase="aggregate_assurance_passed",
                    status="in_progress",
                    details={
                        "upgrade_assurance": upgrade_assurance,
                        "survivors_must_remain_paused": True,
                    },
                )
            # Aggregate assurance is intentionally long. Peer AI work may admit
            # observations while it runs, so drain that late logical debt and
            # atomically rebuild the active index before any restore transaction.
            post_assurance_data_convergence = (
                _run_post_assurance_data_convergence(repo_root)
            )
            post_assurance_history_migration = dict(
                post_assurance_data_convergence.get("history_migration") or {}
            )
            if not post_assurance_data_convergence.get("ok"):
                raise RuntimeError(
                    "Chaos Brain post-assurance data convergence failed: "
                    + str(
                        post_assurance_data_convergence.get("attempts")
                        or post_assurance_data_convergence.get("status")
                    )
                )
            history_migration = post_assurance_history_migration
            if upgrade_attempt_id:
                _record_upgrade_attempt(
                    home,
                    upgrade_attempt_id,
                    phase="post_assurance_history_current",
                    status="in_progress",
                    details={
                        "post_assurance_history_migration": (
                            post_assurance_history_migration
                        ),
                        "post_assurance_data_convergence": (
                            post_assurance_data_convergence
                        ),
                        "survivors_must_remain_paused": True,
                    },
                )
        # This second all-or-nothing transaction is the restore gate.  If it
        # fails, rollback returns to the already-validated paused runtime.
        final_activation_payloads = (
            activation_payloads if defer_automation_restore else automation_payloads
        )
        _require_live_skillguard_matches_snapshot(validation_toolchain)
        _require_live_flowguard_matches_snapshot(flowguard_toolchain)
        _require_live_logicguard_matches_snapshot(logicguard_toolchain)
        final_skillguard_source_checks = _check_repo_skillguard_current_sources(
            repo_root,
            home,
            skillguard_root=validation_root,
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
            skillguard_validation_receipts={
                str(row["skill_id"]): row for row in final_skillguard_source_checks
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
        # The final managed-runtime transaction can replace Skill trees after
        # the pre-assurance refresh. Refresh and check again at the true end.
        final_router = _refresh_and_verify_skillguard_global_router(home)
        global_router_refresh = dict(final_router.get("refresh") or {})
        global_router_live_freshness = dict(
            final_router.get("live_freshness") or {}
        )
        if upgrade_attempt_id:
            _record_upgrade_attempt(
                home,
                upgrade_attempt_id,
                phase="final_router_current",
                status="ready_for_install_check",
                details={
                    "global_router_refresh": global_router_refresh,
                    "global_router_live_freshness": global_router_live_freshness,
                    "global_router_surface": final_router.get(
                        "surface_after_check", {}
                    ),
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
        "skillguard_validation_toolchain": validation_toolchain,
        "flowguard_validation_toolchain": flowguard_toolchain,
        "logicguard_validation_toolchain": logicguard_toolchain,
        "skillguard_source_checks": skillguard_source_checks,
        "install_transaction": transaction,
        "paused_install_transaction": paused_transaction,
        "history_migration_required": bool(safe_upgrade),
        "history_migration": dict(history_migration or {}),
        "initial_history_migration": initial_history_migration,
        "post_assurance_history_migration": post_assurance_history_migration,
        "post_assurance_data_convergence": post_assurance_data_convergence,
        "pre_assurance_update_state_migration": (
            pre_assurance_update_state_migration
        ),
        "upgrade_assurance_required": bool(require_upgrade_assurance),
        "upgrade_assurance": upgrade_assurance,
        "global_router_refresh": global_router_refresh,
        "global_router_live_freshness": global_router_live_freshness,
        "pre_assurance_global_router": pre_assurance_global_router,
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
    original_configs = {
        str(spec["id"]): _load_automation_toml(
            automation_toml_path(str(spec["id"]), home)
        )
        for spec in REPO_AUTOMATION_SPECS
    }
    if automation_state_snapshot is not None:
        states = automation_state_snapshot.get("states")
        user_paused_states = automation_state_snapshot.get("user_paused")
        if not isinstance(states, Mapping) or not isinstance(user_paused_states, Mapping):
            raise RuntimeError("automation state snapshot is missing states or user_paused maps")
        expected_ids = {str(spec["id"]) for spec in REPO_AUTOMATION_SPECS}
        if set(states) != expected_ids or set(user_paused_states) != expected_ids:
            raise RuntimeError("automation state snapshot does not cover the exact surviving automation set")
        for automation_id in expected_ids:
            status = str(states.get(automation_id) or "").upper()
            if status not in {"ACTIVE", "PAUSED"}:
                raise RuntimeError(f"invalid automation snapshot status for {automation_id}: {status}")
            original_configs[automation_id] = {
                **original_configs.get(automation_id, {}),
                "status": status,
                "user_paused": bool(user_paused_states.get(automation_id)),
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
    validation_toolchain: dict[str, Any] = {}
    skillguard_ephemeral_root: Path | None = None
    try:
        snapshot_parent = (
            _upgrade_attempt_dir(home, attempt_id) / "validation-toolchain"
            if attempt_id
            else home / ".khaos-brain-install" / "fixture-validation-toolchain"
        )
        short_skillguard_parent = Path(
            tempfile.mkdtemp(prefix="khaos-sg-")
        ).resolve()
        skillguard_ephemeral_root = short_skillguard_parent
        try:
            validation_toolchain = _freeze_skillguard_validation_toolchain(
                home,
                short_skillguard_parent
                / "canonical-repository"
                / ".agents"
                / "skills"
                / "skillguard",
            )
        except Exception:
            shutil.rmtree(short_skillguard_parent, ignore_errors=True)
            raise
        flowguard_toolchain = _freeze_flowguard_validation_toolchain(
            snapshot_parent / "python" / "flowguard"
        )
        logicguard_toolchain = _freeze_logicguard_validation_toolchain(
            snapshot_parent / "python" / "logicguard"
        )
        if attempt_id:
            _record_upgrade_attempt(
                home,
                attempt_id,
                phase="validation_toolchain_frozen",
                status="in_progress",
                details={
                    "skillguard_validation_toolchain": validation_toolchain,
                    "flowguard_validation_toolchain": flowguard_toolchain,
                    "logicguard_validation_toolchain": logicguard_toolchain,
                    "survivors_must_remain_paused": True,
                },
            )
        previous_validation_root = os.environ.get(SKILLGUARD_VALIDATION_ROOT_ENV)
        previous_validation_digest = os.environ.get(
            SKILLGUARD_VALIDATION_DIGEST_ENV
        )
        previous_flowguard_root = os.environ.get(FLOWGUARD_VALIDATION_ROOT_ENV)
        previous_flowguard_digest = os.environ.get(
            FLOWGUARD_VALIDATION_DIGEST_ENV
        )
        previous_logicguard_root = os.environ.get(LOGICGUARD_VALIDATION_ROOT_ENV)
        previous_logicguard_digest = os.environ.get(
            LOGICGUARD_VALIDATION_DIGEST_ENV
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
        os.environ[INSTALLATION_IDENTITY_PYTHON_EXECUTABLE_ENV] = str(
            validation_toolchain.get("installation_python_executable")
            or sys.executable
        )
        os.environ[SKILLGUARD_VALIDATION_ROOT_ENV] = str(
            validation_toolchain["snapshot_root"]
        )
        os.environ[SKILLGUARD_VALIDATION_DIGEST_ENV] = str(
            validation_toolchain["manifest"]["digest"]
        )
        flowguard_root = Path(str(flowguard_toolchain["snapshot_root"])).resolve()
        os.environ[FLOWGUARD_VALIDATION_ROOT_ENV] = str(flowguard_root)
        os.environ[FLOWGUARD_VALIDATION_DIGEST_ENV] = str(
            flowguard_toolchain["manifest"]["digest"]
        )
        logicguard_root = Path(
            str(logicguard_toolchain["snapshot_root"])
        ).resolve()
        os.environ[LOGICGUARD_VALIDATION_ROOT_ENV] = str(logicguard_root)
        os.environ[LOGICGUARD_VALIDATION_DIGEST_ENV] = str(
            logicguard_toolchain["manifest"]["digest"]
        )
        os.environ["PYTHONPATH"] = os.pathsep.join(
            dict.fromkeys(
                part
                for part in (
                    str(flowguard_root.parent),
                    str(logicguard_root.parent),
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
                skillguard_validation_toolchain=validation_toolchain,
                flowguard_validation_toolchain=flowguard_toolchain,
                logicguard_validation_toolchain=logicguard_toolchain,
            )
        finally:
            if previous_validation_root is None:
                os.environ.pop(SKILLGUARD_VALIDATION_ROOT_ENV, None)
            else:
                os.environ[SKILLGUARD_VALIDATION_ROOT_ENV] = (
                    previous_validation_root
                )
            if previous_validation_digest is None:
                os.environ.pop(SKILLGUARD_VALIDATION_DIGEST_ENV, None)
            else:
                os.environ[SKILLGUARD_VALIDATION_DIGEST_ENV] = (
                    previous_validation_digest
                )
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
            if previous_logicguard_root is None:
                os.environ.pop(LOGICGUARD_VALIDATION_ROOT_ENV, None)
            else:
                os.environ[LOGICGUARD_VALIDATION_ROOT_ENV] = previous_logicguard_root
            if previous_logicguard_digest is None:
                os.environ.pop(LOGICGUARD_VALIDATION_DIGEST_ENV, None)
            else:
                os.environ[LOGICGUARD_VALIDATION_DIGEST_ENV] = (
                    previous_logicguard_digest
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
            from local_kb.software_update import canonicalize_obsolete_update_state

            obsolete_update_state_migration = canonicalize_obsolete_update_state(
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
                    "global_router_refresh": payload.get(
                        "global_router_refresh", {}
                    ),
                    "global_router_live_freshness": payload.get(
                        "global_router_live_freshness", {}
                    ),
                    "survivors_must_remain_paused": bool(
                        defer_automation_restore
                    ),
                },
            )
            payload["upgrade_attempt"] = upgrade_attempt
        payload["skillguard_validation_toolchain_cleanup"] = (
            _cleanup_ephemeral_skillguard_validation_toolchain(
                skillguard_ephemeral_root
            )
        )
        manifest_path = save_install_state(payload, home)
        payload["install_state_path"] = str(manifest_path)
        return payload
    except Exception as exc:
        cleanup = _cleanup_ephemeral_skillguard_validation_toolchain(
            skillguard_ephemeral_root
        )
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
                        "skillguard_validation_toolchain_cleanup": cleanup,
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
    latest_attempt = latest_upgrade_attempt(home)
    active_upgrade_attempt = dict(manifest_attempt)
    if latest_attempt and (
        not active_upgrade_attempt
        or str(latest_attempt.get("updated_at") or "")
        >= str(active_upgrade_attempt.get("updated_at") or "")
    ):
        active_upgrade_attempt = latest_attempt
    manifest_root_raw = str(manifest.get("repo_root", "") or "").strip()
    env_value = os.environ.get(KB_ROOT_ENV_VAR, "").strip()
    managed_automations = manifest.get("automations", [])
    restore_deferred = manifest.get("automation_restore_deferred") is True
    managed_maintenance_skills = manifest.get("maintenance_skills", [])
    shell_tools_manifest = manifest.get("shell_tools", {}) if isinstance(manifest.get("shell_tools"), dict) else {}

    issues: list[str] = []
    warnings: list[str] = []
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
        obsolete_update_state_settled = not bool(
            str(current_update_state.get("status") or "") == "failed"
            and str(current_update_state.get("error") or "")
            == "SkillGuard installation identity is not current"
        )
        if not obsolete_update_state_settled:
            issues.append(
                "The exact retired SkillGuard installation-identity failure remains in update state; "
                "the versioned upgrade must settle it before installation can be healthy."
            )
        from local_kb.maintenance_migration import check_migration

        history_migration_check = check_migration(expected_repo_root)
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
    upgrade_assurance_ok = bool(
        not upgrade_assurance_required or upgrade_assurance.get("ok")
    )
    if not upgrade_assurance_ok:
        issues.append(
            "Chaos Brain aggregate pre-restore assurance is missing or failed: "
            + ", ".join(
                str(item) for item in upgrade_assurance.get("failed_checks", [])
            )
        )
    manifest_router_refresh = (
        manifest.get("global_router_refresh", {})
        if isinstance(manifest.get("global_router_refresh"), dict)
        else {}
    )
    manifest_router_live = (
        manifest.get("global_router_live_freshness", {})
        if isinstance(manifest.get("global_router_live_freshness"), dict)
        else {}
    )
    attempt_router_refresh = (
        active_upgrade_attempt.get("global_router_refresh", {})
        if isinstance(active_upgrade_attempt.get("global_router_refresh"), Mapping)
        else {}
    )
    pre_assurance_router = (
        active_upgrade_attempt.get("pre_assurance_global_router", {})
        if isinstance(active_upgrade_attempt.get("pre_assurance_global_router"), Mapping)
        else {}
    )
    pre_assurance_refresh = (
        pre_assurance_router.get("refresh", {})
        if isinstance(pre_assurance_router.get("refresh"), Mapping)
        else {}
    )
    attempt_is_at_least_as_current = bool(
        active_upgrade_attempt
        and str(active_upgrade_attempt.get("updated_at") or "")
        >= str(manifest.get("installed_at") or "")
    )
    global_router_refresh = (
        dict(attempt_router_refresh or pre_assurance_refresh)
        if attempt_is_at_least_as_current
        else dict(manifest_router_refresh)
    )
    global_router_refresh_receipt_ok = bool(
        not history_migration_required
        or str(global_router_refresh.get("decision") or "") == "pass"
    )
    final_router_phase_bound = bool(
        not history_migration_required
        or (
            bool(attempt_router_refresh)
            and str(active_upgrade_attempt.get("phase") or "")
            in {
                "final_router_current",
                "post_install_check_passed",
            }
        )
        or (
            not attempt_is_at_least_as_current
            and bool(manifest_router_refresh)
            and bool(manifest_router_live.get("ok"))
        )
    )
    if not global_router_refresh_receipt_ok:
        issues.append(
            "SkillGuard global-router refresh receipt is missing or failed for the current upgrade attempt."
        )
    elif not final_router_phase_bound:
        issues.append(
            "SkillGuard router has only a pre-assurance refresh receipt; a final refresh after the "
            "last managed Skill transaction is still required."
        )
    if history_migration_required and global_router_refresh_receipt_ok:
        global_router_live_freshness = _verify_skillguard_global_router(
            home, global_router_refresh
        )
        global_router_live_freshness_ok = bool(
            global_router_live_freshness.get("ok") and final_router_phase_bound
        )
    else:
        global_router_live_freshness = {
            "ok": not history_migration_required,
            "status": "fixture_skipped" if not history_migration_required else "not_run",
        }
        global_router_live_freshness_ok = bool(not history_migration_required)
    if not global_router_live_freshness_ok:
        issues.append(
            "Current SkillGuard global registry and managed prompt are not both fresh against "
            "the active Skill trees after the final refresh."
        )
    global_router_refresh_ok = bool(
        global_router_refresh_receipt_ok
        and final_router_phase_bound
        and global_router_live_freshness_ok
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
        install_manifest = tree_manifest(install_dir) if install_dir.exists() else {}
        if source_manifest and install_manifest and source_manifest.get("digest") != install_manifest.get("digest"):
            issues_for_skill.append(
                f"Installed maintenance skill {skill_name} complete tree differs from repository source."
            )
        for authority_file in (
            ".skillguard/contract-source.json",
            ".skillguard/compiled-contract.json",
            ".skillguard/check-manifest.json",
        ):
            if not (source_dir / authority_file).is_file():
                issues_for_skill.append(f"Repository current SkillGuard authority is missing: {source_dir / authority_file}")
            if not (install_dir / authority_file).is_file():
                issues_for_skill.append(f"Installed current SkillGuard authority is missing: {install_dir / authority_file}")
        automation_prompt = next(
            (
                str(item.get("prompt") or "")
                for item in REPO_AUTOMATION_SPECS
                if str(item.get("skill_name") or "") == skill_name
            ),
            "",
        )
        source_completion_findings = validate_completion_surface(
            skill_name,
            repo_root=expected_repo_root,
            automation_prompt=automation_prompt,
            skill_text=source_skill_text,
            compiled_contract=_load_json_object(source_dir / ".skillguard" / "compiled-contract.json"),
            check_manifest=_load_json_object(source_dir / ".skillguard" / "check-manifest.json"),
        )
        installed_completion_findings = validate_completion_surface(
            skill_name,
            repo_root=expected_repo_root,
            automation_prompt=automation_prompt,
            skill_text=skill_text,
            compiled_contract=_load_json_object(install_dir / ".skillguard" / "compiled-contract.json"),
            check_manifest=_load_json_object(install_dir / ".skillguard" / "check-manifest.json"),
        )
        for finding in source_completion_findings:
            issues_for_skill.append(
                f"Repository automation SkillGuard completion contract failed: {finding.get('code')}:{finding.get('detail')}"
            )
        for finding in installed_completion_findings:
            issues_for_skill.append(
                f"Installed automation SkillGuard completion contract failed: {finding.get('code')}:{finding.get('detail')}"
            )
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
                "install_manifest_digest": str(install_manifest.get("digest") or ""),
                "source_completion_findings": source_completion_findings,
                "installed_completion_findings": installed_completion_findings,
                "issues": issues_for_skill,
            }
        )

    automation_checks: list[dict[str, Any]] = []
    automation_runtime = resolve_automation_runtime(home)
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
            user_paused = bool(payload.get("user_paused")) and payload_status == "PAUSED"
            preserved_pause_allowed = user_paused
            deferred_pause_allowed = bool(
                allow_deferred_automation_restore
                and restore_deferred
                and payload_status == "PAUSED"
            )
            if (
                payload_status != expected["status"]
                and not preserved_pause_allowed
                and not deferred_pause_allowed
            ):
                issues_for_automation.append(
                    f"Automation {expected['id']} should be status={expected['status']}."
                )
            if str(payload.get("rrule", "") or "") != expected["rrule"]:
                issues_for_automation.append(
                    f"Automation {expected['id']} should use rrule {expected['rrule']}."
                )
            if str(payload.get("schedule_policy", "") or "") != expected["schedule_policy"]:
                issues_for_automation.append(
                    f"Automation {expected['id']} should record schedule_policy={expected['schedule_policy']}."
                )
            if str(payload.get("schedule_window", "") or "") != expected["schedule_window"]:
                issues_for_automation.append(
                    f"Automation {expected['id']} should record schedule_window={expected['schedule_window']}."
                )
            if str(payload.get("model", "") or "") != expected["model"]:
                issues_for_automation.append(
                    f"Automation {expected['id']} should use model={expected['model']} from policy={expected['model_policy']}."
                )
            if str(payload.get("reasoning_effort", "") or "") != expected["reasoning_effort"]:
                issues_for_automation.append(
                    f"Automation {expected['id']} should use reasoning_effort={expected['reasoning_effort']} from policy={expected['reasoning_effort_policy']}."
                )
            if str(payload.get("model_policy", "") or "") != expected["model_policy"]:
                issues_for_automation.append(
                    f"Automation {expected['id']} should record model_policy={expected['model_policy']}."
                )
            if str(payload.get("reasoning_effort_policy", "") or "") != expected["reasoning_effort_policy"]:
                issues_for_automation.append(
                    "Automation "
                    f"{expected['id']} should record reasoning_effort_policy={expected['reasoning_effort_policy']}."
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
                "scripts/run_kb_guarded_automation.py",
                SKILLGUARD_PARTIAL_MARKER,
                SKILLGUARD_COMPLETION_MARKER,
                "immutable",
                "Fixture or capability evidence cannot close a scheduled run",
                "portable receipt-root reference",
                "installed runtime fingerprint",
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
    automation_skillguard_completion_ok = bool(maintenance_skill_checks) and all(
        not item.get("source_completion_findings")
        and not item.get("installed_completion_findings")
        for item in maintenance_skill_checks
    )
    global_skill_present = skill_path.exists() and launcher_path.exists() and openai_path.exists()
    global_skill_implicit = bool(openai_text and "allow_implicit_invocation: true" in openai_text)
    global_skill_postflight = bool(
        openai_text
        and "record a KB follow-up observation" in openai_text
        and "required default preflight" in openai_text
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
    system_update_ok = not automation_issue_map.get("khaos-brain-system-update")
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
            "Retired Architect surfaces remain active: "
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
        and global_agents_managed
        and global_agents_preflight
        and global_agents_postflight
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
        and automation_skillguard_completion_ok
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
            "automation_skillguard_completion_contracts",
            "Every retained background automation has current target-specific runtime receipts and the sole enforced SkillGuard declared-check contract",
            automation_skillguard_completion_ok,
            "; ".join(
                f"{item['name']}=source:{len(item.get('source_completion_findings', []))},installed:{len(item.get('installed_completion_findings', []))}"
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
            "skillguard_global_router_refresh_receipt",
            "A durable final SkillGuard router-refresh receipt is bound after the last managed Skill transaction",
            bool(global_router_refresh_receipt_ok and final_router_phase_bound),
            (
                f"registry={global_router_refresh.get('registry_path', '')}; "
                f"registry_hash={global_router_refresh.get('registry_hash', '')}; "
                f"agents_file={global_router_refresh.get('agents_file', '')}; "
                f"decision={global_router_refresh.get('decision', '')}"
            ),
        ),
        _checklist_item(
            "skillguard_global_router_live_freshness",
            "Current registry and managed prompt both match the active Skill trees after final refresh",
            global_router_live_freshness_ok,
            (
                f"registry={global_router_live_freshness.get('registry_path', '')}; "
                f"registry_decision={global_router_live_freshness.get('registry_check', {}).get('decision', '')}; "
                f"prompt_decision={global_router_live_freshness.get('prompt_check', {}).get('decision', '')}"
            ),
        ),
        _checklist_item(
            "skillguard_global_router_refresh",
            "Global SkillGuard routing is durably refreshed and currently fresh without the retired Architect Skill",
            global_router_refresh_ok,
            str(global_router_refresh.get("registry_path") or ""),
        ),
        _checklist_item(
            "chaos_brain_aggregate_assurance",
            "Current model, SkillGuard, retirement, retrieval, and full-regression gates passed before restore",
            upgrade_assurance_ok,
            (
                f"required={upgrade_assurance_required}; "
                f"failed={','.join(str(item) for item in upgrade_assurance.get('failed_checks', []))}"
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
            "retired_architect_surfaces",
            "Retired Architect Skill and automation surfaces are absent",
            retired_surfaces_absent,
            "; ".join(str(path) for path in [*retired_paths, *retired_source_paths]),
        ),
        _checklist_item(
            "khaos_brain_system_update_automation",
            "Khaos Brain system update automation is installed and matches the repository spec",
            system_update_ok,
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
        "global_router_refresh": global_router_refresh,
        "global_router_refresh_receipt_ok": global_router_refresh_receipt_ok,
        "global_router_final_phase_bound": final_router_phase_bound,
        "global_router_live_freshness": global_router_live_freshness,
        "global_router_live_freshness_ok": global_router_live_freshness_ok,
        "upgrade_attempt": active_upgrade_attempt,
        "install_transaction": install_transaction,
        "retired_paths": [str(path) for path in retired_paths],
        "issues": issues,
        "warnings": warnings,
    }
