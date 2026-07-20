## Why

The 2026-07-20 Sleep run exhausted its 900-second native budget while committing candidate lifecycle transitions one event at a time against a 334 MB lifecycle ledger. The run correctly invalidated the active index before an eligibility-changing transition, but timed out before the final index owner could rebuild and reactivate it, leaving retrieval, Dream, and organization maintenance safely but indefinitely blocked.

## What Changes

- Make Sleep stage candidate snapshot, parking, reopening, promotion, and other same-cycle lifecycle decisions into bounded atomic batches instead of replaying the complete lifecycle authority once per transition.
- Preserve stable candidate identities and idempotency keys so a new authorized Sleep owner can reconcile partial work from a timed-out predecessor without duplicating candidates, events, handoffs, or dispositions.
- Keep the durable fail-closed marker before every index-affecting batch and allow removal only after the exact rebuilt index, activation authority, current LogicGuard generation, and lifecycle digest pass validation.
- Require an explicit authorized writer capability at the active-index rebuild API boundary; normal runtime permits Sleep, while the versioned maintenance migration remains the only upgrade-time publisher.
- Extend Sleep receipts and regression evidence with bounded replay counts, staged/created/reused transition counts, recovered partial-work counts, final index-owner evidence, and timeout-safe terminal boundaries.
- Add production-scale and same-class regression coverage for candidate batching, retry convergence, marker-token races, unauthorized rebuild attempts, and fail-closed Dream/organization preflights.
- Synchronize the repaired source into the local installation, recover the active index through exactly one canonical Sleep wrapper run, restore dependent automations in order, and publish a new release after current aggregate evidence passes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `kb-sleep-dream-convergence`: Sleep lifecycle work becomes scale-bounded, recoverable after partial timeout, and accountable to one final active-index owner.
- `kb-experience-lifecycle`: same-cycle candidate lifecycle mutations use one atomic batch and bounded replay contract while preserving exact event semantics.
- `kb-retrieval-calibration`: active-index rebuild and reactivation require explicit authorized writer capability and exact current authority validation.

## Impact

- Runtime code: `local_kb/candidate_lifecycle.py`, `local_kb/lifecycle.py`, `local_kb/active_index.py`, and `local_kb/model_maintenance.py`.
- FlowGuard artifacts: existing lifecycle, LogicGuard model-mesh, retrieval authority, model-test alignment, and test-mesh owners; no parallel model boundary.
- Tests: lifecycle batching and replay accounting, Sleep timeout/retry recovery, active-index authorization and marker races, retrieval/Dream/organization fail-closed behavior, installer/current-runtime assurance.
- Operations: one foreground final regression owner, installer plus independent install check, one canonical Sleep recovery run, sequential downstream lane validation, automation activation, Git/tag/GitHub Release identities.
- Compatibility: no fallback reader, legacy alias, dual publisher, or manual marker-clearing path is introduced.
