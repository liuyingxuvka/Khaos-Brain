---
name: kb-sleep-maintenance
description: Run the repository-managed automatic incremental KB Sleep pass. Use only for explicit Sleep maintenance or the scheduled KB Sleep automation, not ordinary retrieval or active-task write-back.
---

# KB Sleep Maintenance

Sleep is the sole knowledge-decision and canonical model-generation owner. It freezes one finite work batch, resumes that exact batch until it is settled, gives every frozen item a bounded machine-readable disposition, checkpoints verified progress, settles the candidate lifecycle, converts settled entries into exact LogicGuard model revisions, groups exact revisions into grounded scoped ModelMeshes, consumes Dream model-gap handoffs, and atomically publishes only a complete model generation. Readable cards and the active index are deterministic projections of that authority.

## Authority and entrypoint

Work from the repository root. Read `PROJECT_SPEC.md`, `docs/maintenance_agent_worldview.md`, `docs/maintenance_runbook.md`, and `.agents/skills/local-kb-retrieve/MAINTENANCE_PROMPT.md`. Current user instructions override repository defaults.

Run:

`python .agents/skills/local-kb-retrieve/scripts/kb_sleep.py --json`

The native lifecycle implementation owns all mutation, terminal validation, and its immutable run receipt. Do not create a parallel Sleep implementation or a second model writer.

## Required behavior

1. Acquire the shared `kb-sleep` maintenance lane and preserve the same run id through closure.
2. Resume the exact open frozen batch before admitting later work. If no batch is open, freeze one finite ordered `batch_plan` with immutable item identities, input watermark and digest, current-generation identity, prior convergence streak, and tested batch-size bounds. The persistent `batch_head` binds the exact plan and checkpoint digests. Later arrivals never expand that batch.
3. Give every settled frozen item exactly one verified completed disposition or one explicit blocked disposition with a named owner and executable reopen condition. Persist each item result and the batch checkpoint before continuing so a later Sleep reuses verified work and reprocesses at most the incomplete item.
4. Create or reuse one stable candidate only when a bounded scenario-action-result relation and sufficient evidence exist. Represent it immediately as a LogicGuard model revision with a root Claim, explicit Context and Method, typed support or challenge nodes, and explicit gaps. Never invent Evidence, Warrant, Assumption, Rebuttal, or Limitation merely to fill the model.
5. Keep trusted promotion evidence-dependent. Require current independent validation; weak or duplicated evidence never satisfies promotion.
6. Park unresolved candidates with a machine-evaluable reopen condition and a seven-day decision boundary. Reopen exactly once only after a material qualifying evidence delta.
7. Immediately exclude strong contradictory trusted knowledge and complete its downgrade review in this Sleep pass.
8. Consume each typed Dream model-gap handoff exactly once, record one acknowledgement, and let Dream remain an immutable simulation owner only.
9. Assemble exact model revisions into physically separated public, private, and candidate ModelMeshes. Admit a canonical cross-model relation only when qualifying non-AI provenance supports it. Co-use, lexical similarity, and retired `related_cards` values remain unresolved grounding proposals, never edges.
10. Audit each important model for missing context, action, evidence, warrant, assumption, opposition/rebuttal, and boundary conditions. Give every absence one stable open disposition, required grounded input, and machine-readable reopen condition; never invent the missing content.
11. Stage models, meshes, deterministic readable projections, the exact active index, and generation manifests away from the current generation. Validate the complete staged generation before one atomic pointer switch written last. Ordinary planning, `progress_saved`, timeout, or pre-activation failure keeps the prior validated generation readable and never treats pending work as current-generation corruption.
12. Exclude rejected, merged, superseded, parked, retired, deprecated, history-only, provenance-incomplete, and contradicted records from retrieval projection.
13. Commit the new watermark only after every frozen item is settled and dispositions, model/mesh publication, lifecycle review, handoff acknowledgements, exact index validation, and the final pointer switch are durable. `progress_saved` and failure keep the previous committed watermark unchanged.
14. Do not require a human to read files, choose cards, or approve ordinary maintenance decisions. Escalate only a real safety or authority boundary.
15. Stop starting new items at the native soft deadline, durably seal the checkpoint, release the lane, and return `progress_saved` before the outer hard timeout. One malformed item may settle as blocked only with a named owner and executable reopen condition; publish completed siblings as `completed_with_blocks`, never repeat them, and record Dream and organization descendants as `not_run`. The target-owned wrapper owns same-run terminalization; do not invoke a status helper or retry the child. A `progress_saved`, failed, open-batch, `completed_with_blocks`, or `backlog_growing` receipt records the same explicit descendant gate.

## Closure report

Return the run id; `batch_head`, `batch_plan`, and `batch_checkpoint`; `previous_remaining`, `newly_eligible`, `opening_remaining`, `target_batch_size`, `completed_this_attempt`, `blocked_this_attempt`, `closing_remaining`, `net_reduction`, and `convergence_status`; consumed range and digest; candidate create/reuse counts; promotions, downgrades, reopen decisions; Dream acknowledgements; exact LogicGuard generation/model/mesh counts; unresolved relation proposals; model-gap counts; active-index receipt and validation; `downstream_stages`; blockers; and final run state. Never infer completion from `progress_saved`, prose, readable staging files, or a missing required receipt.

## Native completion boundary

For a scheduled run, intake, planning, or proposal-only output is incomplete. Run `python scripts/run_kb_automation.py --skill kb-sleep-maintenance --json`. The target-owned wrapper invokes the native Sleep owner exactly once and accepts only its immutable terminal receipt for that exact run. `completed`, `completed_with_blocks`, a proved no-op, and a fully validated `progress_saved` checkpoint are distinct terminals; `completed_with_blocks` publishes only settled siblings and preserves named blocked work, while `progress_saved` proves resumable progress but never generation completion. Fixture or capability evidence cannot replace the concrete scheduled run.

If the native owner or any validation child times out, the run is incomplete until the target-owned launcher terminates the complete process tree, confirms zero remaining descendants, and records that cleanup.

Ordinary use is self-contained and does not read an author-maintenance contract, external receipt, router, or installed maintenance tool. Author-side checks may validate Sleep before distribution but never participate in a scheduled Sleep run.
