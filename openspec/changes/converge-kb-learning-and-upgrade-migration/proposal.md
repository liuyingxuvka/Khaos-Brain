## Why

Chaos Brain currently records predictive observations much faster than it converts them into reliable, reusable knowledge. Long-running Sleep, Dream, Architect, installation, and history workflows have accumulated unresolved observations, scaffold candidates, repeated no-delta experiments, stale control evidence, and more than twenty gigabytes of duplicated maintenance artifacts; the system must converge automatically instead of merely producing more maintenance reports.

## What Changes

- Make every new observation receive a bounded, machine-readable disposition and give every candidate a terminal or explicitly parked lifecycle.
- Make Sleep incremental and backlog-reducing, with evidence-prioritized decisions, promotion/demotion, merge/reject/park outcomes, and a current active-knowledge index.
- Make Dream evidence-driven and convergent: identical evidence may not produce repeated experiments or history writes, and results hand back only to Sleep.
- Bind retrieval confidence to real task outcomes, user corrections, test evidence, and no-card cases instead of AI self-reported hits alone.
- Introduce a versioned, resumable, idempotent history-debt migration that classifies unresolved knowledge debt, archives cold evidence, deduplicates snapshots, removes safe-to-rebuild workspaces, and rebuilds active indexes.
- **BREAKING** Retire KB Architect as a lane, Skill, automation, queue owner, handoff target, update gate name, and completion dependency. Historical Architect evidence becomes inert cold history.
- Make fresh installs omit Architect and make every upgrade from an older Chaos Brain installation automatically remove the managed Architect automation and Skill.
- Make install and upgrade transactional: preserve existing user pause state, stage complete Skill trees, prevent SkillGuard downgrade, verify source/install parity, emit migration receipts, and roll back or remain paused on failure.
- **BREAKING** Remove every normal-runtime compatibility and fallback authority. Older managed formats are accepted only inside one bounded direct-to-current upgrade transaction; the transaction must rewrite them once, delete their executable/readable authority, prove zero residual, and otherwise roll back or keep all retained automations paused.
- Route every retained background task through one guarded scheduled entrypoint that executes the native owner once; let SkillGuard supervise only the exact current declared-check inventory and permit terminal success only through the sole `enforced` closure over the immutable run receipt and required target artifacts, while keeping target-owned positive/shallow fixtures and capability regressions separate from per-run completion.
- Scope Architect retirement to the active registry projected by the current Codex home so unrelated historical registries cannot falsely block a clean upgrade.
- Require current FlowGuard, SkillGuard, migration, installation, retrieval, and regression evidence before the upgrade is considered complete or surviving automations are resumed.
- Preserve unrelated and concurrent workspace changes; the migration and installer may mutate only declared Chaos Brain-owned surfaces.

## Capabilities

### New Capabilities

- `kb-experience-lifecycle`: Observation evidence grading, timely disposition, candidate lifecycle, promotion/demotion, provenance, and terminal/parked outcomes.
- `kb-sleep-dream-convergence`: Incremental Sleep processing, backlog drain, Dream evidence fingerprints, no-delta closure, and Sleep-only handoff ownership.
- `kb-retrieval-calibration`: Active-status filtering, retrieval indexing, real-task outcome receipts, no-card cases, confidence calibration, and performance budgets.
- `kb-history-debt-migration`: Versioned inventory, knowledge-debt settlement, cold archival, content deduplication, temporary-artifact cleanup, resumability, and rollback.
- `kb-upgrade-migration`: Architect retirement, old-machine cleanup, fresh-install behavior, automation pause preservation, transactional install, and cross-version migration receipts.
- `kb-runtime-assurance`: FlowGuard/SkillGuard ownership, runtime receipts, current-evidence gates, model/test alignment, CI regression, and final upgrade readiness.

### Modified Capabilities

<!-- No archived canonical OpenSpec capability currently owns these requirements. Existing unarchived Sleep and canonical-interface changes are compatibility context and must be reconciled without overwriting concurrent work. -->

## Impact

- Core modules: event consolidation, candidate/card state, current-index-only search, Dream selection, maintenance lanes, organization-schema migration, snapshots, software update, installation, and desktop update state.
- Managed surfaces: Sleep/Dream Skills and prompts, retired Architect Skill/automation, organization automations, global preflight template, install manifest, and SkillGuard contracts.
- Data: `kb/history`, `kb/candidates`, active indexes, lane status, migration receipts, cold archives, and `.local` maintenance workspaces.
- Assurance: FlowGuard models, conformance replay, SkillGuard source/install parity, OpenSpec verification, unit/integration/migration/performance tests, and CI.
- Documentation: authoritative project specification, runbooks, README, AGENTS defaults, upgrade notes, and release migration guidance.
