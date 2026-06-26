---
name: kb-architect-pass
description: Run one repository-managed KB Architect mechanism-maintenance pass. Use only when a user or automation explicitly asks for KB Architect, architecture maintenance, automation/runbook/installer/proposal-queue maintenance, or the scheduled KB Architect automation; do not use for ordinary card content maintenance, Sleep consolidation, or Dream exploration.
---

# KB Architect Pass

Run one Architect pass for the KB system's operating mechanisms.

Architect owns the mechanism proposal queue. A successful pass may create no new proposal if it makes the existing queue cleaner, closes resolved items, or prevents duplicate work from being reopened.

The runner should not directly edit mechanism code. It should emit execution packets that separate narrow agent-ready work from patch/human work, then a follow-on Architect agent may act only through the packet's sandbox-trial boundary and validation plan.

## Authority

Work from the repository root. Treat these files as authoritative and read them before stateful mechanism work:

- PROJECT_SPEC.md
- docs/maintenance_agent_worldview.md
- docs/architecture_runbook.md
- .agents/skills/local-kb-retrieve/ARCHITECT_PROMPT.md

Current user instructions still override repository files.

## Scope

In scope: Sleep/Dream/Architect prompts, runbooks, automation specs, installer checks, CLI machine-output boundaries, canonical/display interface rules, rollback/snapshot/validation workflow, proposal queue governance, and narrow tests for those mechanisms.

Out of scope: trusted-card rewrites, candidate promotion, card content merge/split/deprecation, taxonomy route rewrites, user preference cards, ordinary knowledge-card maintenance, dependency installs, broad refactors, and repo-wide formatting.

## Execution Contract

1. Read the shared maintenance-agent worldview and use it as the judgment model for Architect's role, sandbox-upgrade evidence, and human-reviewable output quality.
2. Write a visible Architect execution plan before the first stateful command, with every checkpoint present and status-tracked.
3. Run Architect self-preflight against system/knowledge-library/maintenance.
4. Run the software update gate:
   python scripts/khaos_brain_update.py --architect-check --json
5. If the gate reports `apply_ready=true`, use `$khaos-brain-update` to apply the authorized software update while the UI is closed, report the update result, and stop this old-version Architect pass so the next run uses the updated code.
6. If the gate reports an available update that is not prepared, or a prepared update while the UI is running, leave the state for the UI and continue normal Architect maintenance.
7. Run:
   python .agents/skills/local-kb-retrieve/scripts/kb_architect.py --json
8. Inspect generated artifacts under kb/history/architecture/runs/<run-id>/ as incoming evidence, not as an automatic request to create or advance proposals.
9. Inspect kb/history/architecture/proposal_queue.json before acting on new signals.
10. Start with queue hygiene: merge or supersede duplicates, close resolved or obsolete items, and avoid reopening applied/rejected/superseded items unless there is a real regression or materially new failure mode. Treat same-category proposals with the same target route, target file, or same mechanism failure as one queue lane unless the current run proves they need different fixes.
11. Use only Evidence, Impact, and Safety for mechanism proposal review.
12. Keep proposal statuses limited to `new`, `watching`, `ready-for-patch`, `ready-for-apply`, `applied`, `rejected`, and `superseded`.
13. Do not use a human-review status; long-observation items remain `watching`.
14. Inspect `selected_sandbox_trial` and sandbox_trial_selection.json. If a packet is selected, run that one narrow, high-value packet in its planned sandbox path or record a concrete blocker before ending the full Architect pass.
15. Sandbox-apply only narrow, reversible, high-value mechanism changes whose execution packet is agent-ready inside prompt, runbook, validation, or proposal-queue maintenance with an immediate validation bundle and `sandbox_apply.sandbox_ready=true`.
16. Generate patch plans for medium-safety mechanism changes instead of applying them directly.
17. Create a new proposal only when the signal is not already represented by an active or terminal queue item. Repeated duplicate signals should merge evidence into the primary proposal, not become extra readiness votes.
18. After the trial, write <planned_sandbox_path>/trial_result.json with `proposal_id`, `packet_id`, `decision`, `sandbox_path`, `touched_paths`, `diff_within_allowed`, `validation_results`, `manual_check_results`, and a concrete `reason`.
19. Record the result with python .agents/skills/local-kb-retrieve/scripts/kb_architect.py --record-trial-result <planned_sandbox_path>/trial_result.json --json; do not hand-edit proposal_queue.json to close a packet.
20. When a sandbox trial succeeds and is merged, mark the proposal `applied`; when it cannot stay inside `allowed_writes`, validation fails, or the expected effect is not achieved, keep the proposal status `watching` and mark its `execution_state.state` as `blocked` with the blocker.
21. Confirm the runner's KB postflight observation or append one structured Architect observation if a new mechanism lesson was exposed.
22. Write or inspect the system-readable maintenance rollup at kb/history/architecture/maintenance_rollup.json. The rollup must keep Sleep, Dream, current Architect report, FlowGuard adoption logs, organization maintenance status, content-boundary status, and install-sync status together for the system to read.

## Report

Report the run id, checkpoint status for every plan item, preflight entries retrieved, software update gate result, proposal counts by status before and after queue hygiene, duplicate clusters merged or superseded, resolved or already-applied items closed, terminal items intentionally not reopened, ready-for-apply and ready-for-patch items, sandbox-ready packets with planned sandbox path and write boundaries, selected sandbox trial, trial-result decision, execution packets by mode, changes applied, validation bundle run, canonical-interface mechanism signals, blocked execution states, postflight observation status, system-readable maintenance rollup status, watching items left for long observation, and the system evolution route.


<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose

Use this skill for its declared kb workflow while binding each run to a route, evidence, checks, and a bounded completion claim.

## Entrypoint Scope

The entrypoint covers the installed kb-architect-pass skill and the local materials explicitly routed by its instructions. It does not expand to unrelated repositories, private files, external services, publication, or release claims unless the user request and skill workflow explicitly include them.

## Local Material Routing

Resolve local materials from the active workspace, this skill directory, user-provided files, or explicitly configured project paths. Treat private machine paths as local-only inputs and keep public-facing instructions portable.

## Entrypoint Acceptance Map

A valid run selects one declared route, follows the phase order, records direct evidence, runs required checks, reports blockers and failures, and closes only inside the claim boundary. Available routes: recall or maintenance, evidence update, validation, closure.

## Use When

Use when the user request matches the kb-architect-pass activation boundary and needs this skill's governed workflow, source material, checks, or handoff behavior.

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
