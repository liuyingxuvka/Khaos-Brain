---
name: khaos-brain-update
description: Apply one transactional Khaos Brain software update only after the user explicitly requests it in the current conversation. Never activate from UI status, persisted state, a scheduler, install health, or automated assurance.
---

# Khaos Brain Update

This is the sole manual software-update route. Use it only for an explicit user request in the current conversation. It updates repository software and installer-managed Codex integration; it does not maintain cards and it does not replace Sleep or Dream.

## Use when

- The user directly asks AI in this conversation to update Khaos Brain.
- The configured Git upstream is available and the requested action is a safe fast-forward update.

## Do not use when

- The desktop UI merely reports that an upstream version is available.
- A user clicks or hovers the read-only version status.
- A scheduled task, installer check, background retry, startup path, aggregate assurance run, or persisted file tries to trigger an update.
- The current conversation contains no explicit update request.

There is no scheduled automation, no persisted authorization, no prepared state, no compatibility alias, and no fallback update entrypoint. The exact retired `khaos-brain-system-update` task must remain absent.

## Recovery boundary

The update must still work when retrieval, desktop settings, organization state, or the UI is unhealthy. Preserve `.local/`, private/history/candidate/outbox KB state, organization caches and Skill bundles, exchange ledgers, user-created untracked files, and user-owned Codex configuration outside managed paths.

## Apply contract

1. Run only `python scripts/run_khaos_brain_manual_update.py --explicit-user-request --json`. This target-owned entrypoint rejects before run-state creation, Git mutation, installer execution, or automation-state mutation when current-request authorization is absent.
2. The manual check fetches and compares only the exact configured upstream. `no-update` is the only successful terminal no-op. Missing upstream, fetch failure, dirty tracked work, local-ahead or diverged topology, an open Khaos Brain UI, a previous failed update, concurrent execution, or any unknown state remains blocked and unfinished.
3. Use Git fast-forward only. Never reset, force checkout, rebase, move tags, overwrite dirty user/peer work, or guess another remote branch.
4. Snapshot the exact four surviving automation statuses and independent `user_paused` values, then pause those four survivors before mutation. The retired update task is not a survivor and is never restored.
5. Run the transactional installer through `python scripts/install_codex_kb.py --json`. It must run the versioned maintenance migration, settle old lifecycle debt, publish direct-to-current LogicGuard authority, prove zero retired authority residuals, retire exact `kb-architect-pass`, `kb-architect`, and `khaos-brain-system-update` managed surfaces, and preserve similarly named user assets. Every expensive assurance owner binds exact source, data, toolchain, environment, and installed-projection inputs; unchanged owners reuse one immutable terminal-success receipt and only affected owners execute. Late input drift replans only its mapped owners and never triggers an unconditional second aggregate campaign. Upgrade-attempt currentness is one bounded hash-bound `HEAD.json` plus its exact current projection; an installation check must never enumerate attempt history, use an install-manifest attempt as fallback authority, or launch migration, model, retrieval, pytest, resume, or assurance subprocesses.
6. Keep all four survivors paused while the target-owned entrypoint builds the exact restoration plan and performs the deferred installation check.
7. Only after every target-owned hard gate passes, apply that exact plan, read back all four statuses and `user_paused` values, run the zero-execution read-only installation currentness check, then mark CURRENT.
8. Any native, migration, installation, restoration, readback, or final-check failure marks FAILED and must keep surviving automations paused. A timeout is incomplete until the complete owned process tree is terminated and zero descendants are confirmed.

## Native completion boundary

Intake, planning, or proposal-only output is incomplete. An install-only result, source-only capability check, fixture, or staged plan cannot complete the live manual update. A successful terminal no-op still requires the exact native `no-update` gate receipt for that run. Ordinary use neither loads nor waits for an author-maintenance tool.

## Report

Return the explicit-request gate, configured upstream, previous and target revisions, topology, preserved four-automation state inventory, migration version and receipt, retired surfaces, source/staged/installed manifest digests, bounded upgrade-attempt `HEAD/current` authority and read budget, native result, restoration plan and hashes, activation readback, transactional and rollback receipts, deferred and normal install checks, blockers, and final status.

## Current authority

The current runtime authority is `scripts/run_khaos_brain_manual_update.py` plus the installer and update-state modules it imports. No former work contract, system-update runner, scheduled identity, prepared branch, compatibility, conversion, renewal, alias, or fallback authority may exist.
