## Context

The current lifecycle ledger contains 241,990 events and is approximately 334 MB. During the failed 2026-07-20 Sleep run, candidate creation committed an `entry-lifecycle-snapshot` and a `candidate-transition` separately for each new candidate. Each single-event commit replayed the full lifecycle authority before and after the append. Fourteen candidates therefore consumed most of the 900-second native budget, and the process terminated six seconds after the last fail-closed marker was written.

The safety behavior worked: the old index remained on disk but retrieval rejected it. The incomplete run did not advance `sleep_state.json`, publish a new LogicGuard generation pointer, or produce a successful business receipt. Recovery must retain that fail-closed behavior while eliminating the per-item replay class and preventing low-level callers from bypassing the sole-publisher boundary.

OpenSpec owns the requirements and task lifecycle for this change. Existing FlowGuard product and process models retain runtime, lifecycle, test, installation, and release ownership; no OpenSpec artifact becomes a product-runtime owner.

## Goals / Non-Goals

**Goals:**

- Bound lifecycle replay work per Sleep cycle independently of the number of candidate transitions in that cycle.
- Preserve event order, exact state transitions, stable candidate identity, idempotency, provenance, and fail-closed invalidation.
- Make partial-timeout recovery converge through a later canonical Sleep owner without duplicate candidates or events.
- Require explicit Sleep or versioned-migration authority for active-index rebuild and activation.
- Produce current model, test, install, runtime-recovery, automation, Git, and GitHub Release evidence.

**Non-Goals:**

- Do not introduce a second index, fallback reader, manual recovery CLI, compatibility alias, or alternate publisher.
- Do not weaken lifecycle validation, marker-token race checks, eligibility rules, LogicGuard binding, or watermark commit gates.
- Do not rewrite unrelated candidates, trusted cards, taxonomy, organization content, or other active OpenSpec changes.
- Do not treat background progress, historical green receipts, or readable projections as current validation.

## Decisions

### 1. Stage candidate lifecycle events and commit one bounded batch

Candidate creation and lifecycle review will build deterministic transition events without committing them individually. The Sleep owner will combine observation admission/disposition events, candidate snapshot/parking events, and review transitions into explicitly ordered batches consumed by the existing atomic lifecycle batch owner.

The batch owner remains responsible for one replay before the batch, one durable invalidation marker before any index-affecting append, one atomic log extension, and one replay/projection publication after the batch. Stable idempotency keys make already committed events reusable when a prior run timed out.

Alternative rejected: increasing the 900-second timeout. That would hide the replay-growth defect and would not create a bounded completion argument.

Alternative rejected: compacting or deleting lifecycle history inline. The history is authoritative evidence and requires its separate migration owner.

### 2. Pass the cycle's lifecycle snapshot into candidate staging

The Sleep cycle will reuse its current lifecycle snapshot while classifying and staging candidates instead of loading the full projection for every candidate. The post-batch replay remains authoritative; the snapshot is only planning context and cannot publish state.

Alternative rejected: process-local global caching. A global cache would complicate writer freshness and invalidation without fixing the transaction boundary.

### 3. Keep transition construction pure and publication centralized

Existing event builders remain the source of transition payloads. Functions that need both immediate and staged behavior will expose one explicit staged-event contract; callers must choose one owner. There is no automatic fallback from a failed batch to per-event commits.

Lifecycle review will derive decision receipt ids from the committed/reused batch result so receipt counts remain exact rather than predicting success from staged events.

### 4. Require explicit active-index writer capability

The active-index rebuild entrypoint will require a non-default writer identity. Its allowlist will contain the normal Sleep publisher and the versioned maintenance migration only. Sleep model publication, final no-delta index ownership, migration call sites, and tests must pass the exact writer identity.

The rebuild still captures the invalidation token before scanning, validates the complete candidate payload and sources, acquires the lifecycle writer lock for activation, rejects token drift or superseding publication, writes the activation authority, and only then removes the marker.

Alternative rejected: stack inspection. Call-stack identity is fragile and not an auditable machine contract.

### 5. Treat the incident as a FlowGuard model miss, not a point performance patch

The primary miss is `state_too_coarse`: existing models bounded observation and Dream-handoff batching but did not model candidate-creation transitions as members of the same large-ledger replay family. A related `evidence_overclaimed` miss allowed earlier bounded-replay assurance to omit the production-scale candidate path.

The repair will extend the existing Sleep/lifecycle commitment and model-test evidence. The same-class family includes candidate creation, parking, reopening, promotion, downgrade, and calibration snapshots; each path must either join a bounded batch or have an explicit bounded exception.

### 6. Separate focused parallel checks from the final aggregate owner

Independent focused diagnostics may run in parallel when their files, mutable state, and execution owners are isolated. The final all-model and full-test gates run once in the foreground after source, toolchain, check inventory, and peer writes are frozen. A timeout invalidates that owner's evidence until its complete descendant tree is confirmed absent.

### 7. Recover and reactivate through the canonical operational sequence

After source validation, installation synchronization runs through the repository installer and independent check while preserving user pause state. With dependent automations paused, exactly one top-level Sleep wrapper run reconciles partial lifecycle work and owns final index recovery. Retrieval, Dream, organization contribution, and organization maintenance resume only after the marker is absent and exact active-index validation is current.

## Risks / Trade-offs

- **[Risk] A staged event order changes lifecycle semantics** → Preserve the current per-entry order, add transition-sequence tests, and compare replayed terminal state with the previous valid small-ledger behavior.
- **[Risk] A partial prior run has candidate files but missing lifecycle events** → Reuse stable candidate identities and append only idempotency-key-missing events; never delete the partial evidence to manufacture a clean retry.
- **[Risk] One large batch exceeds memory or lock budgets** → Keep a named finite batch size, record requested/created/reused counts and replay passes, and leave residual work visible for the next Sleep cycle.
- **[Risk] Writer-capability plumbing misses a legitimate migration call site** → Exhaust all direct rebuild call sites and add unauthorized/authorized caller tests before release.
- **[Risk] Peer AI changes stale focused evidence** → Re-read changed files, preserve peer writes, recompute affected owners, and run the final aggregate only from the frozen integrated snapshot.
- **[Risk] Installer or recovery changes runtime evidence after source validation** → Keep source, installed projection, runtime index, automation, Git, and GitHub identities as separate evidence domains and validate each explicitly.

## Migration Plan

1. Keep all four automations paused while source behavior changes and preserve the original failed receipts and marker.
2. Update existing FlowGuard models and evidence for the model-miss family before production implementation.
3. Implement staged candidate/review transitions and explicit index-writer capability; run focused model and test evidence.
4. Freeze the integrated source snapshot and run the sole final aggregate model/test owners in the foreground.
5. Run `python scripts/install_codex_kb.py --json`, followed by `python scripts/install_codex_kb.py --check --json`; retain rollback until aggregate installation validation passes.
6. Execute exactly one `python scripts/run_kb_automation.py --skill kb-sleep-maintenance --json` recovery owner. On timeout, confirm zero descendants and inspect the same run; do not retry.
7. Require completed Sleep receipt, current watermark, absent marker, exact index/authority/LogicGuard/lifecycle bindings, passing full and fast validation, and released locks.
8. Validate retrieval and run Dream, organization contribution, and organization maintenance sequentially with new run ids.
9. Restore the four automation statuses and schedules, verify installed currentness, then archive this OpenSpec change.
10. Perform release audit, create the release commit, tag it, verify the tag target, push branch and tag, and create the GitHub Release.

Rollback: source edits remain revertible by an ordinary future commit; the installer retains its transactional rollback until its aggregate validation passes; a failed Sleep recovery leaves the marker and previous watermark authoritative and keeps dependent automations paused.
