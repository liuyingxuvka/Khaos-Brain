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

- `.local/`, including `khaos_brain_desktop_settings.json`, organization caches, exchange hash ledgers, import records, screenshots, and install identity files.
- `kb/private/`, `kb/history/`, `kb/candidates/`, `kb/outbox/`, and other ignored local KB state.
- User-created untracked files unless the user explicitly asked to remove them.
- Installed organization Skills, downloaded organization Skill bundles, and local Skill review state.
- `$CODEX_HOME/predictive-kb/install.json` and user-owned Codex configuration outside the repository-managed blocks.

The installer may refresh repository-managed global skills, repository-managed automations, and repository-managed global AGENTS blocks.

## Apply Contract

1. Work from the repository root. Confirm it contains `PROJECT_SPEC.md`, `scripts/install_codex_kb.py`, and `.agents/skills/khaos-brain-update/SKILL.md`.
2. Mark the UI-blocking state before changing files:
   `python scripts/khaos_brain_update.py --mark upgrading --json`
3. Force-close Khaos Brain desktop UI processes before changing files. Do not wait for a graceful close. On Windows, target only Khaos Brain UI processes, such as `Khaos Brain.exe`, `KhaosBrain.exe`, windows titled `Khaos Brain`, or Python command lines running `kb_desktop.py` or `open_khaos_brain_ui.py`. Do not broadly kill unrelated `python`, `node`, `electron`, or `codex` processes.
4. Inspect tracked working-tree state with Git. If tracked source files are dirty and the user did not explicitly authorize updating over local source edits, stop before fetching or pulling and report the dirty paths. Ignored private KB state is not a blocker.
5. Fetch from the configured upstream with tags and pruning.
6. Update only by fast-forward. Prefer the current branch's upstream; if no upstream exists and the repository is on `main`, use `origin/main`. Do not run `git reset --hard`, force checkout, rebase, or tag moves.
7. Run `python scripts/install_codex_kb.py --json`.
8. Run `python scripts/install_codex_kb.py --check --json`.
9. If the desktop package or shortcut changed and the installer exposes a supported refresh path, use that supported path. Do not invent a packaging step during update.
10. Mark successful completion:
    `python scripts/khaos_brain_update.py --mark current --json`

## Failure Rules

- If the fast-forward fails because local source changes exist, the branch diverged, or the remote is unavailable, stop cleanly and leave local state untouched.
- If the installer or install check fails after source update, mark failure with `python scripts/khaos_brain_update.py --mark failed --error "<short error>" --json`, report the exact failing command, and leave rollback to a separate explicit recovery action.
- Do not delete local KB cards, organization caches, hash ledgers, Skill bundles, or settings as part of update failure handling.

## Report

Report the previous revision, target revision, whether the UI was force-closed, Git update result, installer result, install-check result, update-state path if written, and any remaining manual action.
