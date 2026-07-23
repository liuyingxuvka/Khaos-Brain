## Why

Sleep currently marks the whole active index durably unavailable before it has finished candidate lifecycle and generation publication work. Two consecutive real runs exceeded the outer deadline, so a maintenance timeout left a previously validated knowledge generation unreadable and the next run still faced the same growing work surface. The prior repair bounded duplicate replay but did not guarantee per-run progress, resume completed work, or keep the previous generation available while a replacement is staged.

## What Changes

- **BREAKING** Replace normal-runtime whole-index `pending rebuild` invalidation with impact-scoped retrieval safety: no-effect and additive changes keep the previous validated generation readable; removals or replacements deny only exact affected entries; only evidence-bound corruption of the exact current generation may block the whole index.
- Add one bounded Sleep batch ledger that freezes a finite item set, records every item as pending, completed, or blocked-with-reason, and resumes the same batch before admitting a new batch.
- Make every Sleep attempt report the previous remainder, newly eligible items since the prior Sleep boundary, selected batch size, completed count, blocked count, and closing remainder. The default selection target is twice the newly eligible count, constrained by tested minimum and maximum batch bounds.
- Add durable per-item checkpoints so a soft stop or crash reuses verified completed work and reprocesses at most the incomplete item.
- Stage card/model/index work away from the current generation and activate a complete validated generation only through the existing single Sleep publication owner and one final atomic pointer switch.
- Introduce a native soft-stop boundary before the existing hard launcher timeout. A normal unfinished attempt returns `progress_saved`; it does not claim completion, advance the committed watermark, acknowledge unfinished handoffs, or run dependent Dream/organization stages.
- Report `backlog_growing` when the closing remainder fails to decrease across repeated Sleep cycles. This is a per-Sleep comparison, not a continuous or hourly capacity model.
- Directly migrate the retired invalidation, batch, watermark, and partial-publication authority to the new current format. Normal runtime retains no compatibility reader, alias, fallback, or alternate publisher.
- Update the Sleep Skill, embedded automation prompt, receipts, installer checks, FlowGuard models, TestMesh, documentation, and source/installed synchronization evidence to the same behavior.

## Capabilities

### New Capabilities

None. This change repairs and strengthens existing Sleep, lifecycle, retrieval, migration, and upgrade capabilities without creating a second maintenance route.

### Modified Capabilities

- `kb-sleep-dream-convergence`: Replace retry-from-prior-watermark behavior with a frozen resumable batch, per-item checkpoints, per-Sleep remainder accounting, soft-stop semantics, and previous-generation availability.
- `kb-experience-lifecycle`: Add exact before/after retrieval impact classification and item-level completion or blocked dispositions for frozen Sleep batches.
- `kb-retrieval-calibration`: Replace event-type-wide invalidation with no-effect, additive, exact-entry deny, and exact-current-corruption outcomes.
- `kb-history-debt-migration`: Directly migrate the large lifecycle authority and incomplete Sleep state into the resumable current shape while preserving exact history and zero normal-runtime legacy readers.
- `kb-upgrade-migration`: Require transactional installation, current-pointer activation, old-authority retirement, local installed synchronization, and current release evidence for the repaired behavior.

## Impact

- Runtime: `local_kb.lifecycle`, candidate lifecycle handling, model publication, active-index loading, automation runtime/contracts, maintenance migration, and installer health checks.
- Persistent state: Sleep batch/checkpoint receipts, lifecycle impact fields, current generation activation evidence, exact-entry deny state, and retirement of generic active-index invalidation as a normal maintenance state.
- Agent surfaces: `kb-sleep-maintenance`, the local maintenance prompt, installed consumer projection, and automation payload.
- Assurance: existing FlowGuard commitment/model ownership, repeated-timeout Model Miss, FieldLifecycleMesh, Model-Test Alignment, TestMesh, crash/restart regressions, and full release assurance.
- Release: source repository, installed skills and automations, local Git identity, version/tag, and GitHub Release must be synchronized only after the frozen release gate passes.
