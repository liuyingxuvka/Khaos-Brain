---
name: kb-dream-pass
description: Run one bounded repository-managed local KB Dream exploration pass. Use only when a user or automation explicitly asks for KB Dream, dream mode, bounded KB exploration, or the scheduled KB Dream automation; do not use for Sleep consolidation, Architect mechanism work, ordinary preflight, or trusted-card maintenance.
---

# KB Dream Pass

Run one bounded Dream pass for this predictive KB repository.

Dream is valuable exploration, not candidate harvesting. A successful run may create no candidates when it clarifies that evidence should stay history-only.

## Authority

Work from the repository root. Treat these files as authoritative and read them before stateful dream work:

- PROJECT_SPEC.md
- docs/maintenance_agent_worldview.md
- docs/dream_runbook.md
- .agents/skills/local-kb-retrieve/DREAM_PROMPT.md

Current user instructions still override repository files.

## Execution Contract

1. Read the shared maintenance-agent worldview and use it as the judgment model for Dream's role, sandbox evidence strength, and human-reviewable output quality.
2. Keep Dream separate from Sleep and Architect.
3. Run the dedicated dream runner:
   python .agents/skills/local-kb-retrieve/scripts/kb_dream.py --json
4. Inspect generated artifacts under kb/history/dream/<run-id>/, including preflight, plan, opportunity, experiment, execution-plan, and report files.
5. Select a small route-deduped batch of genuinely valuable grounded evidence gaps that clear the value gate, and only when each one can clarify a future retrieval, routing, card-use, or Sleep-consolidation decision.
6. If no valuable grounded gap exists, report a no-op instead of manufacturing an experiment or candidate.
7. List selected experiments in execution order, then validate them sequentially.
8. Require experiment design, validation plan, safety tier, rollback plan, and explicit success/failure/inconclusive criteria before each execution.
9. Write local sandbox experiment artifacts only under kb/history/dream/<run-id>/sandbox/.
10. Record `evidence_grade`, `sandbox_path`, `allowed_writes`, `validation_result`, `sleep_handoff`, and `architect_handoff` for each executed sandbox experiment.
11. Skip route-and-mode experiments that already passed with strong or moderate sandbox evidence in a prior Dream report; use the prior result as Sleep handoff instead of repeating it.
12. After experiments, write one run-level Dream-process observation when the run exposed a reusable process lesson; keep it separate from route-specific evidence.
13. Keep write-back history-only by default; create a candidate only when history-only is insufficient and the result has route, scenario, action, observed result, and concrete operational use.
14. If nearby search results are mostly existing candidates or low-confidence scaffolds, prefer read-only validation or Sleep handoff instead of creating another adjacent candidate.
15. Keep external-system experiments proposal-only unless a human explicitly approves them in an active task.
16. Do not rewrite trusted cards or taxonomy.
17. Do not repeat route-gap or taxonomy-change observations that merely confirm a known gap; add value by clarifying whether Sleep should ignore, reject, narrow, consolidate, or watch the signal.
18. Treat dream-created candidates as provisional until later live-task evidence confirms them.

## Report

Report the run id, retrieved preflight entries, selected evidence gaps or why no valuable gap was selected, future retrieval/use decisions clarified, experiments executed in order if any, execution-plan checkpoint status, safety tier and rollback plan, result classifications, sandbox paths, evidence grades, validation results, history events written, candidates created if any with why history-only was insufficient, Sleep/Architect handoff, and anything still needing live-task confirmation.

<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose
Bind each kb run to the declared integration mode, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers kb-dream-pass plus explicitly routed local materials; no unrelated repos, private files, external services, publication, or release claims unless requested and routed.
## Local Material Routing
Use workspace, skill directory, user files, or configured project paths; keep private machine paths local and public instructions portable.
## Entrypoint Acceptance Map
Use SkillGuard as the runtime contract executor attached to the native route/check owner: Predictive KB launcher, local KB records, and KB maintenance workflow. It enforces contract gates through that native owner before progress or closure; duplicate SkillGuard-owned execution paths are invalid. Declared gates/routes: recall or maintenance, evidence update, validation, closure.
## Use When
Use when the request matches kb-dream-pass and needs this governed workflow, materials, checks, or handoff behavior.
## Do Not Use When
Do not use outside the domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the target-owned native route/check surface, run the SkillGuard contract gates around the native workflow, collect evidence, run checks, fix failures, then report.
## Hard Gates
Do not skip phases, do not replace required evidence with prose, do not treat stale reports as current, do not weaken validation to pass, and do not claim completion when blockers remain.
## Output Requirements
Report evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary; distinguish checked, unchecked, blocked, and uncertain.
## SkillGuard Maintenance
Keep `.skillguard` contracts, checks, evidence, and ledger current; rerun SkillGuard after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
