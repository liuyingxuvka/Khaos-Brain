---
name: khaos-brain-update
description: Apply a clean repository-managed Khaos Brain software update. Use only when a user, UI request, or Architect pass explicitly authorizes an update; this recovery-oriented skill force-closes the desktop UI, preserves local KB state, fast-forwards source code, and refreshes installer-managed Codex integration.
---

# Khaos Brain Update

Apply one clean software update for this Khaos Brain repository.

This Skill is intentionally narrow. It updates the software and Codex-side integration; it does not decide whether an update is wanted. Version discovery, user intent, UI state display, and scheduling belong to KB Architect or the UI.

## Recovery Boundary

Do not require KB preflight, desktop settings reads, organization repository reads, or card retrieval before applying this Skill. The update path must still work when the local KB, desktop settings, UI, or organization cache is broken.

If a normal healthy Architect pass invoked this Skill, Architect may already have done KB preflight. This Skill itself must not make the update depend on those higher-level systems.

## Preserve

Treat these as local state that must survive an update:

- .local/, including khaos_brain_desktop_settings.json, organization caches, exchange hash ledgers, import records, screenshots, and install identity files.
- kb/private/, kb/history/, kb/candidates/, kb/outbox/, and other ignored local KB state.
- User-created untracked files unless the user explicitly asked to remove them.
- Installed organization Skills, downloaded organization Skill bundles, and local Skill review state.
- $CODEX_HOME/predictive-kb/install.json and user-owned Codex configuration outside the repository-managed blocks.

The installer may refresh repository-managed global skills, repository-managed automations, and repository-managed global AGENTS blocks.

## Apply Contract

1. Work from the repository root. Confirm it contains PROJECT_SPEC.md, scripts/install_codex_kb.py, and .agents/skills/khaos-brain-update/SKILL.md.
2. Mark the UI-blocking state before changing files:
   python scripts/khaos_brain_update.py --mark upgrading --json
3. Force-close Khaos Brain desktop UI processes before changing files. Do not wait for a graceful close. On Windows, target only Khaos Brain UI processes, such as `Khaos Brain.exe`, `KhaosBrain.exe`, windows titled `Khaos Brain`, or Python command lines running kb_desktop.py or open_khaos_brain_ui.py. Do not broadly kill unrelated `python`, `node`, `electron`, or `codex` processes.
4. Inspect tracked working-tree state with Git. If tracked source files are dirty and the user did not explicitly authorize updating over local source edits, stop before fetching or pulling and report the dirty paths. Ignored private KB state is not a blocker.
5. Fetch from the configured upstream with tags and pruning.
6. Update only by fast-forward. Prefer the current branch's upstream; if no upstream exists and the repository is on `main`, use origin/main. Do not run `git reset --hard`, force checkout, rebase, or tag moves.
7. Run python scripts/install_codex_kb.py --json.
8. Run python scripts/install_codex_kb.py --check --json.
9. If the desktop package or shortcut changed and the installer exposes a supported refresh path, use that supported path. Do not invent a packaging step during update.
10. Mark successful completion:
    python scripts/khaos_brain_update.py --mark current --json

## Failure Rules

- If the fast-forward fails because local source changes exist, the branch diverged, or the remote is unavailable, stop cleanly and leave local state untouched.
- If the installer or install check fails after source update, mark failure with python scripts/khaos_brain_update.py --mark failed --error "<short error>" --json, report the exact failing command, and leave rollback to a separate explicit recovery action.
- Do not delete local KB cards, organization caches, hash ledgers, Skill bundles, or settings as part of update failure handling.

## Report

Report the previous revision, target revision, whether the UI was force-closed, Git update result, installer result, install-check result, update-state path if written, and any remaining manual action.


<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose

Use this skill for its declared kb workflow while binding each run to a route, evidence, checks, and a bounded completion claim.

## Entrypoint Scope

The entrypoint covers the installed khaos-brain-update skill and the local materials explicitly routed by its instructions. It does not expand to unrelated repositories, private files, external services, publication, or release claims unless the user request and skill workflow explicitly include them.

## Local Material Routing

Resolve local materials from the active workspace, this skill directory, user-provided files, or explicitly configured project paths. Treat private machine paths as local-only inputs and keep public-facing instructions portable.

## Entrypoint Acceptance Map

A valid run selects one declared route, follows the phase order, records direct evidence, runs required checks, reports blockers and failures, and closes only inside the claim boundary. Available routes: recall or maintenance, evidence update, validation, closure.

## Use When

Use when the user request matches the khaos-brain-update activation boundary and needs this skill's governed workflow, source material, checks, or handoff behavior.

## Do Not Use When

Do not use when the task is outside this skill's domain, when required local materials are unavailable, when another more specific skill owns the request, or when the user asks only for a tiny direct answer.

## Required Workflow

Select the route, inspect local materials, perform the work in phase order, collect direct evidence, run the required checks, fix failures, and only then report progress or completion.

## Hard Gates

Do not skip phases, do not replace required evidence with prose, do not treat stale reports as current, do not weaken validation to pass, and do not claim completion when blockers remain.

## Output Requirements

When reporting, include evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary. State clearly what was checked, what was not checked, and what remains blocked or uncertain.

## SkillGuard Maintenance

Keep the `.skillguard` control root, work contract, check manifest, check scripts, evidence records, and progress ledger current. Re-run SkillGuard checks after changing this entrypoint, route behavior, evidence rules, or closure wording.

<!-- END SKILLGUARD CONTRACT LAYER -->
