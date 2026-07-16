---
name: kb-sleep-maintenance
description: Run the repository-managed automatic incremental KB Sleep pass. Use only for explicit Sleep maintenance or the scheduled KB Sleep automation, not ordinary retrieval or active-task write-back.
---

# KB Sleep Maintenance

Sleep is the sole knowledge-decision and canonical model-generation owner. It consumes new evidence incrementally, gives every admitted observation a bounded machine-readable disposition, settles the candidate lifecycle, converts every admitted entry into an exact LogicGuard model revision, groups exact revisions into grounded scoped ModelMeshes, consumes Dream model-gap handoffs, and atomically publishes the complete model generation. Readable cards and the active index are deterministic projections of that authority.

## Authority and entrypoint

Work from the repository root. Read `PROJECT_SPEC.md`, `docs/maintenance_agent_worldview.md`, `docs/maintenance_runbook.md`, and `.agents/skills/local-kb-retrieve/MAINTENANCE_PROMPT.md`. Current user instructions override repository defaults.

Run:

`python .agents/skills/local-kb-retrieve/scripts/kb_sleep.py --json`

The native lifecycle implementation owns all mutation. SkillGuard supervises its declared route and checks; it must not create a parallel Sleep implementation or a second model writer.

## Required behavior

1. Acquire the shared `kb-sleep` maintenance lane and preserve the same run id through closure.
2. Start from the last committed input watermark and read only the next bounded increment for decision work.
3. Admit every new observation before classification and give it exactly one current disposition in the same successful pass.
4. Create or reuse one stable candidate only when a bounded scenario-action-result relation and sufficient evidence exist. Represent it immediately as a LogicGuard model revision with a root Claim, explicit Context and Method, typed support or challenge nodes, and explicit gaps. Never invent Evidence, Warrant, Assumption, Rebuttal, or Limitation merely to fill the model.
5. Keep trusted promotion evidence-dependent. Require current independent validation; weak or duplicated evidence never satisfies promotion.
6. Park unresolved candidates with a machine-evaluable reopen condition and a seven-day decision boundary. Reopen exactly once only after a material qualifying evidence delta.
7. Immediately exclude strong contradictory trusted knowledge and complete its downgrade review in this Sleep pass.
8. Consume each typed Dream model-gap handoff exactly once, record one acknowledgement, and let Dream remain an immutable simulation owner only.
9. Assemble exact model revisions into physically separated public, private, and candidate ModelMeshes. Admit a canonical cross-model relation only when qualifying non-AI provenance supports it. Co-use, lexical similarity, and retired `related_cards` values remain unresolved grounding proposals, never edges.
10. Audit each important model for missing context, action, evidence, warrant, assumption, opposition/rebuttal, and boundary conditions. Give every absence one stable open disposition, required grounded input, and machine-readable reopen condition; never invent the missing content.
11. Publish models, meshes, deterministic readable projections, generation manifests, and the generation pointer as one rollbackable transaction. Rebuild and validate the active index against that exact generation before the pointer and watermark can close. The pointer is written last. A failed publication restores the entire prior generation.
12. Exclude rejected, merged, superseded, parked, retired, deprecated, history-only, provenance-incomplete, and contradicted records from retrieval projection.
13. Commit the new watermark only after dispositions, model/mesh publication, lifecycle review, handoff acknowledgements, and exact index validation are durable. On failure keep the previous watermark and emit a blocked receipt.
14. Do not require a human to read files, choose cards, or approve ordinary maintenance decisions. Escalate only a real safety or authority boundary.
15. Mark the lane completed only when the receipt is complete; otherwise mark it failed and leave other automations paused.

## Closure report

Return the run id, consumed range and digest, opening/new/terminal/parked/closing backlog counts, candidate create/reuse counts, promotions, downgrades, reopen decisions, Dream acknowledgements, exact LogicGuard generation/model/mesh counts, unresolved relation proposals, model-gap counts, active-index receipt and validation, rollback status, blockers, and final run state. Never infer success from prose when a required receipt is missing.

## SkillGuard completion boundary

For a scheduled run, intake, planning, or proposal-only output is incomplete. Run `python scripts/run_kb_guarded_automation.py --skill kb-sleep-maintenance --json`; do not call the child entrypoint directly. The guarded runner invokes the native Sleep owner once, writes an immutable run receipt, and requires the sole current enforced SkillGuard closure receipt for that exact run. A declared no-op counts only when the native gate receipt proves its terminal. Positive and shallow fixtures remain target-owned checks; SkillGuard supervises their exact receipts without interpreting their domain meaning. Fixture or capability evidence cannot replace the concrete scheduled run. The installed SkillGuard builder—not caller-authored fields—binds the trigger, execution id, current installation receipt id/hash plus portable receipt-root reference, and installed runtime fingerprint. SkillGuard does not create a parallel Sleep executor.

If the native owner or any validation child times out, the run is incomplete until the guarded launcher terminates the complete owned process tree, confirms zero remaining descendants, and records that cleanup under the ordered native-to-scheduled-to-aggregate timeout budget.

## SkillGuard boundary

The current authority is `.skillguard/contract-source.json` plus its declared FlowGuard model. `.skillguard/compiled-contract.json` and `.skillguard/check-manifest.json` are generated projections. No former work contract, underscore manifest, flat run record, compatibility, conversion, renewal, retirement-receipt, alias, or fallback closure route may exist. SkillGuard attaches to the native Sleep owner, preserves current evidence and failure visibility, and cannot manufacture knowledge decisions.
