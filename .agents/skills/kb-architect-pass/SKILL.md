---
name: kb-architect-pass
description: Run one repository-managed KB Architect mechanism-maintenance pass. Use only when a user or automation explicitly asks for KB Architect, architecture maintenance, automation/runbook/installer/proposal-queue maintenance, or the scheduled KB Architect automation; do not use for ordinary card content maintenance, Sleep consolidation, or Dream exploration.
---

# KB Architect Pass

Run one Architect pass for the KB system's operating mechanisms.

## Authority

Work from the repository root. Treat these files as authoritative and read them before stateful mechanism work:

- `PROJECT_SPEC.md`
- `docs/architecture_runbook.md`
- `.agents/skills/local-kb-retrieve/ARCHITECT_PROMPT.md`

Current user instructions still override repository files.

## Scope

In scope: Sleep/Dream/Architect prompts, runbooks, automation specs, installer checks, rollback/snapshot/validation workflow, proposal queue governance, and narrow tests for those mechanisms.

Out of scope: trusted-card rewrites, candidate promotion, card content merge/split/deprecation, taxonomy route rewrites, user preference cards, ordinary knowledge-card maintenance, dependency installs, broad refactors, and repo-wide formatting.

## Execution Contract

1. Write a visible Architect execution plan before the first stateful command, with every checkpoint present and status-tracked.
2. Run Architect self-preflight against `system/knowledge-library/maintenance`.
3. Run the software update gate:
   `python scripts/khaos_brain_update.py --architect-check --json`
4. If the gate reports `apply_ready=true`, use `$khaos-brain-update` to apply the authorized software update while the UI is closed, report the update result, and stop this old-version Architect pass so the next run uses the updated code.
5. If the gate reports an available update that is not prepared, or a prepared update while the UI is running, leave the state for the UI and continue normal Architect maintenance.
6. Run:
   `python .agents/skills/local-kb-retrieve/scripts/kb_architect.py --json`
7. Inspect generated artifacts under `kb/history/architecture/runs/<run-id>/`.
8. Inspect `kb/history/architecture/proposal_queue.json`.
9. Use only Evidence, Impact, and Safety for mechanism proposal review.
10. Keep proposal statuses limited to `new`, `watching`, `ready-for-patch`, `ready-for-apply`, `applied`, `rejected`, and `superseded`.
11. Do not use a human-review status; long-observation items remain `watching`.
12. Apply only high-evidence high-safety mechanism changes inside prompt, runbook, validation, or proposal-queue maintenance with an immediate validation bundle.
13. Generate patch plans for medium-safety mechanism changes instead of applying them directly.
14. Confirm the runner's KB postflight observation or append one structured Architect observation if a new mechanism lesson was exposed.

## Report

Report the run id, checkpoint status for every plan item, preflight entries retrieved, software update gate result, proposal counts by status, ready-for-apply and ready-for-patch items, changes applied, validation bundle run, postflight observation status, and watching items left for long observation.
