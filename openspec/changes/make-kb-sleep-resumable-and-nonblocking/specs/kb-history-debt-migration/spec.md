## ADDED Requirements

### Requirement: Upgrade directly migrates legacy active-index invalidation authority
The versioned maintenance migration SHALL inventory every legacy generic active-index invalidation marker and every incomplete historical Sleep episode. It SHALL derive one evidence-bound direct-to-current disposition for each covered lifecycle effect: `none`, `additive_pending`, `entry_revoke`, `entry_replace`, or `global_current_corruption`. It SHALL create current batch, exact-deny, corruption, immutable generation, and pointer authority as required, then remove the retired generic marker. Normal runtime MUST NOT read or preserve the legacy marker as a second authority.

#### Scenario: A generic marker covers only candidate additions
- **WHEN** migration proves every covered transition was absent from the active index and did not corrupt the current generation
- **THEN** it classifies the effects as additive pending, preserves the last validated generation, retires the marker, and leaves the new work for a bounded current Sleep batch

#### Scenario: A marker covers a revoked indexed entry
- **WHEN** migration proves one exact current indexed record lost eligibility
- **THEN** it publishes the exact subtractive deny, classifies the transition as `entry_revoke`, and keeps unrelated records readable

#### Scenario: Migration cannot derive a safe disposition
- **WHEN** evidence cannot distinguish exact-entry impact from current-generation corruption
- **THEN** the migration remains incomplete and rollbackable, the four retained automations remain paused, and no compatibility reader or silent downgrade is installed

### Requirement: Migration converts resumable work without restarting settled items
Incomplete historical Sleep episodes SHALL be reconciled into at most one current frozen batch. Matching completed results SHALL become reusable current item checkpoints; conflicting or unsupported historical outputs SHALL receive explicit direct dispositions or remain visible blockers. Migration MUST NOT rerun a settled item merely because the prior overall Sleep receipt timed out.

#### Scenario: A timed-out episode contains valid completed item evidence
- **WHEN** the migration verifies an item's input identity, output identity, lifecycle effect, and idempotency key
- **THEN** it records the item as completed in the current checkpoint and excludes it from reprocessing

## MODIFIED Requirements

### Requirement: Atomic active-knowledge index rebuild
After knowledge dispositions and cold archival are durable, the migration SHALL rebuild the active-knowledge index from the current eligible card and candidate surfaces rather than patching the legacy index in place. The index SHALL carry its schema version, source watermark, source fingerprints, lifecycle checkpoint, exact-deny digest, LogicGuard generation, and build receipt; it MUST exclude rejected, merged, superseded, parked, deprecated, history-only, cold-archive, and exactly denied items. The migration SHALL write immutable generation artifacts away from the current serving pointer, validate their complete binding, and atomically replace the current-generation pointer last.

During an upgrade from a retired index schema, lifecycle settlement MAY defer per-event current-index impact publication only to the same locked, rollbackable migration transaction. That transaction MUST complete the current immutable index rebuild before commit. Normal runtime and independently callable lifecycle writers MUST NOT use this deferral.

#### Scenario: Legacy index cannot satisfy current exact-deny reads mid-migration
- **WHEN** lifecycle debt settlement runs after the retired index has been inventoried but before the current immutable pointer exists
- **THEN** the migration records one explicit upgrade-only rebuild handoff, completes lifecycle settlement without treating the retired index as current authority, and remains blocked until its final current index rebuild validates

#### Scenario: Migration rebuilds the active index
- **WHEN** all knowledge-debt dispositions and archive writes for the target version are committed
- **THEN** the system MUST build an immutable index from the resulting eligible active items, verify every indexed identity against its source fingerprint and lifecycle authority, and atomically replace the current pointer only after all bound artifacts pass

#### Scenario: Index validation fails
- **WHEN** the rebuilt index contains an ineligible item, omits an eligible item, or fails its integrity, pointer-binding, LogicGuard, deny-projection, or retrieval checks
- **THEN** the system MUST keep the prior verified pointer and index available unless exact current corruption was independently proven, mark the migration incomplete, and MUST NOT advance the active-index watermark
