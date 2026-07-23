## Context

The active retrieval path currently depends on three separately written surfaces: readable card projections, `kb/indexes/active.json` plus `active-authority.json`, and the LogicGuard current-generation pointer. Lifecycle code writes a durable generic invalidation marker before every listed entry-transition event. Sleep then performs lifecycle publication, model/mesh/projection work, index publication, and only later writes its terminal receipt and watermark. The outer automation wrapper has a 900-second hard timeout but the native Sleep route has no earlier cooperative stop and no per-item durable checkpoint.

The July 21 and July 22 production episodes exposed the same missing behavior class. A run may make durable partial progress, exceed the launcher deadline, leave no terminal receipt, and keep a previously valid index hidden behind the generic marker. The July 22 batch contained candidate-to-parked transitions whose effective retrieval eligibility was false before and after, so event-name invalidation closed the entire knowledge library without a retrieval-safety reason.

The user selected a deliberately simpler operating model: reason in Sleep cycles, not hourly rates. Each cycle compares the prior remainder, newly eligible work since the prior Sleep boundary, completed or explicitly blocked work, and the closing remainder. A batch is finite, completed entries are marked durably, and a later attempt resumes the same batch.

Existing ownership remains unchanged:

- `local_kb.lifecycle.run_incremental_sleep` is the single public Sleep facade.
- Sleep is the sole normal-runtime LogicGuard generation publisher.
- The versioned maintenance migration is the only non-runtime publisher and the only retired-format reader. While it is converting a retired mutable index, lifecycle settlement explicitly defers exact index-impact publication to that same migration's mandatory final rebuild; this upgrade-only handoff is never available to normal runtime.
- Dream and organization lanes remain dependent consumers and never repair or publish Sleep authority.

## Goals / Non-Goals

**Goals:**

- Keep the last validated knowledge generation readable throughout ordinary Sleep planning, staging, soft stop, timeout, and pre-activation failure.
- Let the next sole writer run the model store's explicit crash-recovery protocol before continuing, so a dead writer lock or prepared journal becomes durable recovery evidence rather than a permanent manual blocker.
- Freeze a finite item batch, checkpoint each completed item durably, and resume without repeating verified work.
- Make per-Sleep backlog movement visible with simple counts rather than a continuous capacity model.
- Process a target larger than newly eligible intake when the configured safe range permits; the initial target rule is twice the newly eligible count, bounded by tested minimum and maximum item counts.
- Replace event-type-wide invalidation with exact semantic impact: no effect, additive pending, exact-entry deny, exact-entry replacement, or exact-current corruption.
- Publish one complete generation through one final current-generation pointer replacement.
- Directly migrate and retire the generic pending-rebuild marker and old publication authority without normal-runtime fallback.
- Preserve current OpenSpec, FlowGuard, SkillGuard, installation, Git, and release ownership boundaries.

**Non-Goals:**

- No hourly arrival/service-rate model, seven-day capacity estimator, or autonomous resource scaler.
- No new scheduled maintenance lane or alternate publisher.
- No vector database, embedding service, external database, or new dependency.
- No compatibility reader, dual pointer, alias, or projection/YAML fallback.
- No silent dropping of a failed batch item. It must complete or receive an explicit blocked disposition with owner and reopen condition.
- No attempt to guarantee availability when the exact current generation is itself corrupt; that remains a justified fail-closed condition.

## Decisions

### 1. One active Sleep batch with per-item durable state

Add a small `local_kb.sleep_batch` owner. The public lifecycle facade delegates batch bookkeeping to it; it does not create a second Sleep entrypoint or publisher.

Persistent state lives under `.local/khaos-brain/sleep-batches/`:

- `HEAD.json`: bounded pointer to the one open or most recently settled batch.
- `<batch-id>/plan.json`: immutable frozen item identities and input boundary.
- `<batch-id>/checkpoint.json`: atomically replaced progress projection.
- `<batch-id>/items/<item-id>.json`: immutable verified item result or explicit blocked disposition.

The plan records `previous_remaining`, `newly_eligible`, `opening_remaining`, `target_batch_size`, the exact frozen item ids, the input start/end watermark and digest, and the current generation identity. Once written, item ids and the end watermark never expand.

The checkpoint records `pending_item_ids`, `completed_item_ids`, `blocked_item_ids`, `processed_this_attempt`, `closing_remaining`, `net_reduction`, `attempt_count`, `last_progress_at`, and a digest. An item result binds its input digest and staged artifact digests. A resumed attempt reuses that result and reprocesses at most the item that had no valid item result.

Alternatives considered:

- Recompute from the prior watermark on every attempt: rejected because it repeats expensive completed work.
- Admit new arrivals into an open batch: rejected because the finish line can move indefinitely.
- Persist only aggregate counts: rejected because counts cannot prove which entries are safe to reuse.

### 2. Per-Sleep target selection, not a continuous capacity model

When no batch is open:

`target = min(opening_remaining, clamp(2 * newly_eligible, configured_min, configured_max))`

If `newly_eligible` is zero and carried backlog exists, the configured minimum is selected. The existing upper default of 250 items remains the maximum candidate until production-scale tests establish a safer lower value. The minimum and maximum are policy fields included in the receipt and installer contract, not hidden heuristics.

Every attempt reports the simple reconciliation:

`previous_remaining + newly_eligible - settled_this_cycle = closing_remaining`

`settled_this_cycle` includes completed items and only those blocked items that have a named owner and executable reopen condition. A receipt reports `backlog_reduced` when `closing_remaining < previous_remaining`, otherwise `no_convergence`; two consecutive current receipts with no reduction report `backlog_growing` and gate Dream/organization work.

Alternatives considered:

- Hourly or seven-day rates: rejected because work arrives and is governed at Sleep boundaries, and the extra estimator does not improve the immediate decision.
- Require every attempt to finish twice the intake: rejected as an absolute invariant because a cooperative soft stop may legitimately save partial progress. Twice intake is the batch-selection target; actual remainder movement remains explicit evidence.

### 3. Cooperative soft stop before the hard wrapper deadline

The outer 900-second launcher timeout remains an abnormal safety boundary. Native Sleep receives a 660-second work deadline. It stops starting new items at that boundary, atomically saves the checkpoint and an attempt receipt, releases the native writer, and returns `progress_saved`. The remaining time is reserved for bounded final validation when all items are already settled and for controlled shutdown/result transport.

`progress_saved` does not advance the committed watermark, acknowledge unfinished Dream handoffs, claim generation completion, or permit dependent maintenance. A hard timeout remains `failed`; the wrapper records any already valid checkpoint but never infers native success. No same-run retry is allowed, and another owner starts only after the prior descendant process tree is confirmed absent.

### 4. Retrieval impact is computed from before/after eligibility

Replace event-name invalidation with these exact outcomes:

- `none`: the current index cannot return the item before or after the event.
- `additive_pending`: the current index does not contain a newly eligible item; the old generation is safe but incomplete until the next activation.
- `entry_revoke`: the current generation contains an item that must no longer be returned.
- `entry_replace`: the current generation contains a record whose old content is no longer safe to return.
- `global_current_corruption`: the exact current generation, index, pointer, or subtractive deny authority is corrupt, or evidence proves current exposure may be unsafe and the affected item set cannot be bounded.

`entry_revoke` and `entry_replace` update one atomic, subtractive deny projection bound to the current generation and expected record digest. It may filter results only. `none` and `additive_pending` do not change foreground availability. Uncertain impact before any current mutation blocks that mutation and leaves the old generation readable; it does not automatically become global corruption.

The generic `active-invalidated.json` marker has no normal-runtime writer after migration. A current-corruption marker, when required, binds the exact generation/pointer digest. It stops applying automatically after a new current generation is activated.

### 5. The current generation pointer binds the immutable active index

Heavy work is written outside current paths. Each candidate generation stores its immutable active-index payload and projection manifest inside its generation directory. The current-generation pointer schema is directly upgraded so it binds the generation manifest, active-index path and digest, projection manifest digest, lifecycle checkpoint digest, committed watermark, deny projection digest, and ready receipt digest.

The current pointer is replaced only after every referenced artifact validates. Foreground retrieval reads the pointer-bound immutable index and applies the exact subtractive deny projection; it does not re-read mutable root YAML as current authority. Root YAML remains a deterministic human/Git projection refreshed from the committed generation, never a retrieval fallback.

This leaves one atomic generation activation rather than separately activating model, index, authority stamp, watermark, and marker state.

### 6. Completed and blocked items can settle a batch

One malformed or repeatedly failing item must not hold every completed item forever. A batch may finalize only when every frozen item has either:

- a verified completed result; or
- a machine-readable blocked disposition with evidence, owner, and executable reopen condition.

The blocked item remains visible as owned debt and re-enters a later batch only when its reopen condition changes. It is not silently counted as successful knowledge mutation.

### 7. Downstream maintenance uses a small readiness projection

Retrieval readiness and maintenance readiness are separate:

- Retrieval remains ready when the pointer-bound generation validates and no matching current-corruption marker exists.
- Dream and organization stages are not run after `progress_saved`, `failed`, `backlog_growing`, or an open batch.
- The wrapper returns explicit `not_run` evidence for each gated descendant rather than starting it or reporting a generic error.

### 8. Existing model and skill ownership is extended, not duplicated

The stable FlowGuard commitment `commitment:sleep-no-delta-single-owner` and parent `LifecycleConvergenceBlock` remain the owners. The repeated timeout is recorded as `state_too_coarse` plus `evidence_overclaimed`; the model adds frozen-batch, per-item progress, previous-generation availability, impact-scope, soft-stop, and remainder-comparison states. FieldLifecycleMesh accounts every new, replaced, and retired persistent field. Model-Test Alignment and TestMesh bind the model obligations to the lifecycle/index/batch code and crash/restart tests.

The source `kb-sleep-maintenance` Skill is updated only after native behavior and tests are stable. SkillGuard supervises only its registered maintenance unit, regenerates author contracts and the clean consumer projection, and does not supply runtime evidence. Installed Skill and automation trees are refreshed transactionally by the repository installer.

### 9. Explicit activation becomes the current status authority

The upgrade attempt snapshot remains the authority for restoring the user's pre-upgrade intent during installation. It is not a permanent veto on a later, explicit current-machine activation. Once the operator activation publishes its validated receipt and HEAD pointer, installation checking resolves the four scheduled automation statuses from that receipt-bound authority. The resolver validates the exact repository and Codex-home identity, current readiness binding, four-scheduled/one-manual-only inventory, target/applied hashes, and all-ACTIVE/user-paused-false result without recursively invoking the install checker.

Before the new activation HEAD is published, the activation transaction passes its exact pending ACTIVE target directly into the final install check. Any invalid receipt, stale readiness binding, incomplete target set, failed final check, or receipt publication failure repauses all four automations. Ordinary install checks therefore accept the current explicit activation after publication, but never reinterpret an old paused upgrade snapshot as a reason to undo it.

## Risks / Trade-offs

- [Root YAML can lag while a generation is staged] → Retrieval never reads staged or mutable YAML as authority; generation activation and post-activation projection checks keep lag visible and repairable.
- [A deny projection could hide too much] → Every row binds an exact current generation, entry id, and expected indexed-record digest; it can only subtract exact matches.
- [A batch target based on item count ignores unequal item cost] → Per-item soft-stop/checkpointing prevents loss of progress; the configured maximum is reduced if representative tests cannot finish or save progress within budget. No cost estimator is introduced initially.
- [Blocked items could be used to fake backlog reduction] → Only blocked dispositions with a named owner and executable reopen condition settle; receipts report completed and blocked counts separately.
- [Two consecutive no-reduction cycles may reflect a transient issue] → The system gates dependent maintenance but does not delete input or disable future authorized Sleep; the next owner resumes the same evidence-bound batch.
- [Direct pointer/schema migration is high risk] → The versioned migration freezes inventories, keeps automations paused, writes candidate artifacts first, swaps the pointer last, verifies retrieval, proves zero retired normal-runtime authority, and rolls back before pointer activation on failure.
- [Concurrent AI edits could stale evidence] → DevelopmentProcessFlow preserves peer writes, rechecks ownership before every editing phase, and freezes one final source/tool/check inventory before aggregate validation and release.
- [An older upgrade snapshot could override a later explicit activation] → The pointer-bound operator receipt becomes the status authority only after exact readiness and inventory validation; missing or stale authority repauses rather than silently accepting ACTIVE.

## Migration Plan

1. Preserve and hash the current generation, active index/authority, lifecycle authority, Sleep state, generic invalidation marker, pending handoffs, automations, and installed Skill identities.
2. Reclassify lifecycle effects since the current index build. A false-to-false transition becomes `none`; exact active removals/replacements become deny rows; only proven current corruption becomes a generation-bound global block.
3. Convert any incomplete Sleep episode into one frozen batch with exact pending/completed item evidence. Do not infer success from files lacking a valid item or terminal receipt.
4. Build the new pointer-bound immutable active index and projection manifest from the last validated generation plus exact deny state.
5. Write and validate the ready receipt, then atomically replace the current-generation pointer.
6. Verify real foreground retrieval against the new pointer before retiring old authority.
7. Remove normal-runtime readers and writers for generic invalidation, separately current `active.json`/`active-authority.json`, legacy Sleep watermark authority, and any alternate publication caller. Retain old evidence only as migration-owned archive/fixtures.
8. Prove zero old normal-runtime residuals, current source/installed prompt parity, and current automation readback before restoring the preserved automation state.

Before the pointer swap, migration rollback restores the exact frozen state. After a successful pointer swap, the new authority is complete and the previous generation remains retained for bounded recovery; normal runtime never dual-reads it.

## Open Questions

The concrete configured minimum batch size will be selected from representative timing evidence during implementation. This does not change the required target formula, maximum boundary, checkpoint behavior, or external states.
