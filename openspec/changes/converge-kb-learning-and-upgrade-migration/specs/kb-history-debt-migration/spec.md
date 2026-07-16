## ADDED Requirements

### Requirement: Versioned history-debt inventory and migration plan
The system SHALL persist a history schema version and maintenance-standard version, SHALL inventory every Chaos Brain-managed history, candidate, snapshot, index, cache, sandbox, and maintenance-workspace surface before mutation, and SHALL derive an ordered migration plan from the installed source versions to the requested target versions. The inventory SHALL classify every managed artifact as active evidence, cold evidence, safely disposable derived data, or unresolved debt, and an unclassified managed artifact MUST remain an explicit blocker rather than being silently discarded.

#### Scenario: Upgrade spans several history schema versions
- **WHEN** an installation is older than more than one registered history migration
- **THEN** the system MUST run every missing migration in declared version order and MUST record the source version, target version, migration identifiers, and inventory fingerprint before applying the first mutation

#### Scenario: Managed artifact cannot be classified safely
- **WHEN** the inventory finds a managed artifact whose ownership, evidence value, or rebuildability cannot be proven
- **THEN** the system MUST retain the artifact, classify it as unresolved debt, and MUST block successful migration until it receives an explicit disposition

### Requirement: Idempotent migration effects
Each history-debt migration step SHALL use stable item identities, content fingerprints, and persisted completion markers so rerunning the same source-to-target migration produces the same dispositions and at most one physical side effect per logical item. A completed migration SHALL be a no-op on unchanged state except for emitting a new no-delta receipt.

#### Scenario: Completed migration is run again
- **WHEN** the same target migration is invoked after it has completed and no covered input fingerprint has changed
- **THEN** the system MUST create no duplicate disposition, archive object, deletion, candidate, or index entry and MUST report the run as an idempotent no-delta result

#### Scenario: Duplicate content has different legacy paths
- **WHEN** two legacy files have identical normalized content but different paths or run identifiers
- **THEN** the system MUST retain one content-addressed object, MUST preserve both provenance references, and MUST avoid counting the second path as a second evidence item

#### Scenario: Organization maintenance proposes several merge or split decisions
- **WHEN** two decisions share the same action kind and primary card but differ in related card, split target, evidence, or another decision-relevant field
- **THEN** each action identity MUST hash the complete canonical decision payload, all action ids MUST be unique and stable, and exact proposal, selected, applied, skipped, and residual counts MUST reconcile before closure

### Requirement: Checkpointed resume and rollback
The migration SHALL quiesce Chaos Brain maintenance writers, capture a pre-migration integrity manifest and rollback reference, and commit phase checkpoints only after that phase's writes and validation are durable. An interruption SHALL resume from the last valid checkpoint without replaying committed side effects, while an invalid checkpoint or failed invariant SHALL restore the last verified state or leave the migration paused with a resumable failure record.

#### Scenario: Process stops after a committed phase
- **WHEN** the migration process is interrupted after a phase checkpoint is durably committed
- **THEN** the next run MUST verify the checkpoint fingerprint and MUST continue from the next incomplete phase without repeating already committed effects

#### Scenario: Validation fails after mutation
- **WHEN** a migration phase changes managed data and its required validation fails
- **THEN** the system MUST NOT advance the history or maintenance-standard version, MUST restore the verified pre-phase state when rollback is valid, and MUST otherwise preserve the paused resumable state and failure evidence

#### Scenario: Maintenance writer appears during migration
- **WHEN** Sleep, Dream, retrieval feedback, or another managed writer attempts a covered write while history migration owns the maintenance lock
- **THEN** the write MUST be deferred or rejected without changing the migration inventory, and the migration MUST NOT consume an untracked concurrent mutation

#### Scenario: A paused failure is later resolved
- **WHEN** a migration resumes after a recorded failure and subsequently reaches a durable checkpoint or committed state
- **THEN** the failure MUST no longer be reported as active, MUST remain preserved in append-only diagnostic history, and a committed journal that still reports an active failure MUST fail the migration check

#### Scenario: Managed debt reappears during validation or after commit
- **WHEN** a concurrent or delayed process reintroduces a Chaos Brain-managed cache, sandbox, workspace, or other physical debt after the main prune inventory was checked
- **THEN** validation MUST detect the current managed surface after all long-running integrity checks, MUST reopen the completion gate, and MUST run a versioned receipt-backed reconciliation pass that archives and prunes the new delta before installation or automation restoration can continue

#### Scenario: A managed Windows path exceeds the legacy length limit
- **WHEN** an old cache, sandbox, backup, or workspace contains a file whose absolute Windows path requires extended-length syntax
- **THEN** inventory, stat, hashing, archive, deletion, residual validation, and empty-directory cleanup MUST still see the same file, and ordinary-path absence MUST NOT be treated as evidence that the managed surface is clean

#### Scenario: Another AI admits observations during a long upgrade
- **WHEN** concurrent KB searches or task postflight writes admit new observations after the main logical-settlement checkpoint or after migration commit
- **THEN** the completion gate MUST reopen, MUST settle those observations through the same evidence-preserving lifecycle in a bounded post-commit loop, MUST publish a separate logical-reconciliation receipt, and MUST remain paused if new hard debt continues beyond the bounded convergence limit

### Requirement: Knowledge-debt settlement
The migration SHALL assign every unresolved observation and every legacy candidate exactly one machine-readable disposition with source evidence, rationale, disposition time, and owning target. Supported outcomes SHALL include updating an existing entry, creating or rewriting a candidate, merging into another item, promotion through the evidence-gated lifecycle, rejection, supersession, parking, and history-only treatment for one-off or non-reusable evidence. Rejected, merged, superseded, parked, and history-only items MUST leave the active unresolved queue.

#### Scenario: Unresolved observation has reusable evidence
- **WHEN** an unresolved observation contains sufficient predictive structure and evidence for an existing entry or bounded candidate
- **THEN** the migration MUST update the existing target or create or rewrite the candidate, MUST preserve the observation provenance, and MUST mark the observation disposition as closed

#### Scenario: Observation is one-off or non-reusable
- **WHEN** an unresolved observation has no defensible future action-selection value
- **THEN** the migration MUST retain its audit evidence as history-only, MUST record the reason, and MUST exclude it from the active knowledge and maintenance queues

#### Scenario: Legacy candidate is duplicate or obsolete
- **WHEN** a legacy candidate duplicates another item or has been replaced by a stronger rule
- **THEN** the migration MUST mark it merged or superseded with a target reference and MUST prevent it from remaining an independently retrievable candidate

### Requirement: Parked debt has executable reopening conditions
The migration SHALL treat `parked` as a closed active-maintenance outcome only when the item records the missing evidence, a machine-evaluable reopening condition, and the evidence fingerprint that caused parking. An unchanged parked item MUST NOT be reconsidered by routine Sleep or Dream runs, and new qualifying evidence SHALL reopen it exactly once for a fresh disposition.

#### Scenario: Evidence remains unchanged after parking
- **WHEN** a routine maintenance pass encounters a parked item with the same evidence fingerprint and an unsatisfied reopening condition
- **THEN** the system MUST leave the item parked and MUST perform no new candidate creation, Dream experiment, or history write for that decision

#### Scenario: Reopening condition becomes true
- **WHEN** new evidence changes the parked item's evidence fingerprint and satisfies its declared reopening condition
- **THEN** the system MUST reopen the item once, MUST link the new review to the prior parking decision, and MUST require a new terminal or parked disposition

### Requirement: Historical lifecycle settlement remains scale-bounded
The migration SHALL settle historical observations and entries through bounded atomic lifecycle batches rather than replaying and rewriting the complete lifecycle authority once per item. Each settlement batch SHALL load the prior authority once, append only idempotency-key-missing events, atomically publish the resulting log and projection, and replay the authority at most once before and once after that batch. The settlement receipt SHALL record requested, created, and reused event counts, replay-pass count, final sequence, and residual hard debt so a large history has an executable progress and convergence proof rather than only a correctness proof.

#### Scenario: Thousands of historical observations require settlement
- **WHEN** an old machine contains thousands of observations and candidate-worthy episodes
- **THEN** the migration MUST build their stable dispositions and entry snapshots in bounded batches, MUST NOT perform a complete lifecycle replay for every observation or transition, and MUST close every observation with no duplicate candidate identity

#### Scenario: A prior per-item settlement attempt stopped partway
- **WHEN** an upgrade resumes after some lifecycle events and candidate files were already committed by an older per-item implementation
- **THEN** the batch settlement MUST reuse their idempotency keys and stable candidate identities, MUST append only missing events, and MUST converge to the same terminal state without deleting or duplicating the partial work

### Requirement: Integrity-preserving cold archive
The migration SHALL move retention-required but non-active evidence into an immutable, content-addressed cold archive with a manifest that preserves original paths, hashes, provenance, timestamps, disposition links, and restore instructions. Cold history, including retired-lane evidence, MUST remain auditable and restorable but MUST NOT participate in active retrieval, Sleep watermarks, Dream opportunity selection, candidate aging, or upgrade readiness except through explicit archive inspection.

#### Scenario: Retired maintenance-lane history is retained
- **WHEN** historical evidence belongs to a retired maintenance lane and is not required by an active item
- **THEN** the migration MUST archive it with its original provenance and MUST remove it from all active maintenance and retrieval inputs

#### Scenario: Archived evidence is requested for audit
- **WHEN** an authorized audit resolves an archive manifest entry
- **THEN** the system MUST verify the stored content hash and MUST expose the original provenance without reactivating the evidence or changing active watermarks

### Requirement: Verified physical-debt cleanup
The migration SHALL deduplicate repeated snapshots and reports, compact cold evidence, and delete only Chaos Brain-owned caches, completed sandboxes, temporary outputs, and maintenance workspaces that are proven reproducible or fully covered by a retained active item, cold object, or migration receipt. Every deletion MUST be justified by ownership, content hash, retention coverage, and deletion reason; unknown, external, user-owned, or concurrently changed paths MUST NOT be deleted.

#### Scenario: Completed sandbox is fully represented by retained evidence
- **WHEN** a completed Dream or maintenance sandbox has a passing result receipt and every non-reproducible artifact is retained by content hash
- **THEN** the system MUST remove the disposable workspace, MUST record its path, byte count, hashes, and deletion reason, and MUST retain the result receipt

#### Scenario: Path changed after inventory
- **WHEN** a covered path's current fingerprint differs from the pre-migration inventory because another writer changed it
- **THEN** the system MUST leave that path untouched, MUST record a concurrent-change blocker, and MUST NOT overwrite or delete the peer writer's work

#### Scenario: Similar path is outside managed ownership
- **WHEN** a cache, backup, task artifact, or workspace resembles Chaos Brain data but is not proven to be owned by Chaos Brain
- **THEN** the system MUST exclude it from cleanup and MUST record that it was outside the mutation boundary

#### Scenario: Verified managed file has the Windows read-only attribute
- **WHEN** an inventoried Chaos Brain-owned file still matches its size, timestamp, content hash, and archive or derivation coverage but Windows denies deletion only because the read-only attribute is set
- **THEN** the migration MUST clear only that read-only attribute, MUST retry deletion once, and MUST record the original mode and attribute-clear result; any ACL denial, changed content, or unresolved ownership MUST remain a blocker

#### Scenario: Pruning stops after some files were deleted
- **WHEN** a permission or runtime failure interrupts physical pruning after earlier receipt-covered files were already removed
- **THEN** the next run MUST merge the durable partial prune records, MUST count prior deletions exactly once in final file and byte accounting, MUST revalidate every still-present file, and MUST remove superseded temporary manifests only after the complete prune manifest commits

### Requirement: Atomic active-knowledge index rebuild
After knowledge dispositions and cold archival are durable, the migration SHALL rebuild the active-knowledge index from the current eligible card and candidate surfaces rather than patching the legacy index in place. The index SHALL carry its schema version, source watermark, source fingerprints, and build receipt; it MUST exclude rejected, merged, superseded, parked, deprecated, history-only, and cold-archive items. Publication of the rebuilt index SHALL be atomic.

#### Scenario: Migration rebuilds the active index
- **WHEN** all knowledge-debt dispositions and archive writes for the target version are committed
- **THEN** the system MUST build an index from the resulting eligible active items, MUST verify every indexed identity against its source fingerprint, and MUST atomically replace the prior active index

#### Scenario: Index validation fails
- **WHEN** the rebuilt index contains an ineligible item, omits an eligible item, or fails its integrity or retrieval checks
- **THEN** the system MUST keep the prior verified index available, MUST mark the migration incomplete, and MUST NOT advance the active-index watermark

### Requirement: History migration receipt and completion boundary
Every migration attempt SHALL emit an encoding-stable machine receipt that records version transitions, inventory and plan fingerprints, checkpoints, item dispositions, archive objects, deleted and retained paths, before-and-after file and byte counts, active-index identity, validation evidence, rollback or resume state, residual debt, and final status. The system MUST report successful history migration only when every managed item is classified, every hard debt item is closed, every parked item has a valid reopening condition, the active index is current, and all required validation evidence is passing and current.

#### Scenario: Migration satisfies the target standard
- **WHEN** all migration phases and validations complete with no hard debt and only valid terminal or parked outcomes remaining
- **THEN** the system MUST issue a successful receipt, MUST advance the history and maintenance-standard versions, and MUST report the measured before-and-after storage and debt totals

#### Scenario: Residual hard debt remains
- **WHEN** any observation, candidate, artifact, deletion, archive object, or index entry lacks a valid disposition or current validation
- **THEN** the system MUST issue an incomplete or failed receipt, MUST list the residual debt and next resumable checkpoint, and MUST NOT claim that history maintenance debt is cleared
