## ADDED Requirements

### Requirement: Sleep freezes and resumes one bounded item batch
Before processing new actionable work, Sleep SHALL resume the exact open batch when one exists. Otherwise Sleep SHALL freeze a finite ordered item set, an inclusive input start boundary, an exclusive input end boundary, an input digest, the prior closing remainder, the newly eligible item count, and the selected target batch size. Later arrivals MUST NOT expand that batch and SHALL remain eligible for a later batch.

The default selected target SHALL be twice the newly eligible item count, constrained by one declared tested minimum and maximum and by the opening remainder. When newly eligible count is zero but carried actionable backlog exists, Sleep SHALL select at least the declared minimum unless the opening remainder is smaller.

#### Scenario: A prior batch is still open
- **WHEN** Sleep starts and a valid open batch has pending items
- **THEN** Sleep resumes that exact batch before selecting any later arrival and MUST NOT change its frozen item identities or end boundary

#### Scenario: New work arrives after batch freeze
- **WHEN** an observation or handoff becomes eligible after the current batch plan is durable
- **THEN** the current batch remains unchanged and the new work is counted as deferred input for a later batch

#### Scenario: Sleep selects a catch-up batch
- **WHEN** no batch is open, the prior remainder is nonzero, and newly eligible work exists
- **THEN** Sleep selects up to twice the newly eligible item count within the declared tested bounds and records the exact formula inputs and result

### Requirement: Sleep checkpoints each settled batch item
Sleep SHALL write a durable, digest-bound result after each frozen item reaches either a verified completed disposition or an explicit blocked disposition with a named owner and executable reopen condition. A resumed attempt MUST reuse every matching completed or blocked result and MUST reprocess at most an item whose durable result is absent, invalid, or input-mismatched.

#### Scenario: Sleep stops after some items complete
- **WHEN** Sleep reaches its cooperative stop after durable results exist for part of the frozen batch
- **THEN** it emits `progress_saved`, preserves those results, records the exact remaining item ids, and leaves the committed generation and watermark unchanged

#### Scenario: The next Sleep resumes the batch
- **WHEN** the next authorized Sleep owner validates the same plan and completed item results
- **THEN** it skips those settled items and continues with the first item lacking a valid matching result

#### Scenario: One item cannot be completed
- **WHEN** an item has a supported blocker that prevents a safe knowledge disposition
- **THEN** Sleep records the evidence, responsible owner, and executable reopen condition, keeps completed siblings publishable, and reports the blocked count separately from completed work

### Requirement: Sleep reports per-cycle remainder movement
Every Sleep attempt SHALL report `previous_remaining`, `newly_eligible`, `opening_remaining`, `target_batch_size`, `completed_this_attempt`, `blocked_this_attempt`, `closing_remaining`, and `net_reduction` under one versioned counting rule. It SHALL report `backlog_reduced` only when the closing remainder is lower than the previous remainder, `no_convergence` when it is not lower, and `backlog_growing` after two consecutive current Sleep receipts fail to reduce the remainder.

#### Scenario: Processing exceeds newly eligible intake
- **WHEN** the batch settles more actionable items than became newly eligible since the prior Sleep boundary
- **THEN** the receipt reports a lower closing remainder and `backlog_reduced`

#### Scenario: Two cycles do not reduce the remainder
- **WHEN** two consecutive current Sleep receipts have closing remainder greater than or equal to their previous remainder
- **THEN** the second receipt reports `backlog_growing`, keeps the debt visible, and dependent Dream and organization stages remain not run

### Requirement: Sleep cooperatively stops before the launcher deadline
Native Sleep SHALL stop starting new item work at its declared soft deadline, durably publish its checkpoint and attempt receipt, release its writer authority, and return before the outer hard timeout. `progress_saved` SHALL be a valid unfinished attempt state but MUST NOT be projected as generation completion, committed watermark advancement, handoff acknowledgement, or permission for dependent maintenance.

#### Scenario: Soft deadline arrives with pending items
- **WHEN** the native soft deadline is reached and the frozen batch still has pending items
- **THEN** Sleep writes a current checkpoint, returns `progress_saved`, and the last validated generation remains readable

#### Scenario: The outer hard timeout terminates native Sleep
- **WHEN** the launcher reaches its hard timeout before terminal native JSON
- **THEN** the wrapper reports failed non-success, preserves any independently valid checkpoint identity without inferring success, and requires confirmed descendant cleanup before a later owner starts

## MODIFIED Requirements

### Requirement: Sleep candidate lifecycle work is scale-bounded and retry-convergent
Sleep SHALL stage all same-cycle candidate lifecycle work in one bounded frozen item batch rather than replaying the complete lifecycle authority once per candidate or transition. Each batch MUST preserve deterministic item and event order, stable candidate identity, stable idempotency keys, exact transition semantics, before/after retrieval eligibility, and durable per-item completion evidence. A no-effect or additive-pending transition MUST NOT invalidate the current generation. An exact-entry removal or replacement MUST apply only an exact subtractive deny bound to the current indexed record. Only evidence-bound corruption of the exact current generation may block foreground retrieval globally. The batch receipt MUST report requested, completed, blocked, reused, and residual item/event counts together with lifecycle replay count. A prior stopped run's matching completed item results MUST be reused without duplicate candidates, events, handoffs, dispositions, or backlog reduction.

#### Scenario: Several candidate observations are handled in one Sleep cycle
- **WHEN** one Sleep cycle creates or reuses multiple candidates and assigns their initial lifecycle outcomes
- **THEN** their ordered item results and lifecycle events enter one frozen bounded batch whose replay count does not grow with candidate count

#### Scenario: Sleep resumes after partial item completion
- **WHEN** a previous Sleep owner stopped after some item results became durable but before generation activation and watermark commit
- **THEN** the next authorized Sleep owner reuses those exact item identities, inputs, results, and idempotency keys, processes only residual items, and does not count or publish completed work twice

#### Scenario: The bounded batch cannot finish safely
- **WHEN** a batch reaches its time, lock, validation, or authority boundary before every frozen item is settled
- **THEN** Sleep preserves the exact residual item ids, keeps the last validated generation readable unless that exact generation is corrupt, leaves the committed watermark unchanged, and emits `progress_saved` or a specific blocker rather than falling back to per-event publication

### Requirement: Sleep receipts expose the final index recovery path
Every Sleep receipt SHALL identify whether the attempt retained the prior current generation, saved resumable progress, activated a complete new pointer-bound index generation, or repaired exact current corruption. A completed receipt MUST bind the frozen batch plan and checkpoint, current LogicGuard generation, immutable active-index path and digest, lifecycle-entry digest, exact-entry deny digest, current-corruption disposition, ready receipt, and watermark commit. A timeout, progress-only, or incomplete native payload MUST NOT be reusable as successful generation-activation evidence.

Before a sole Sleep or migration publisher writes model or mesh authority, it SHALL invoke the current store's explicit crash-recovery protocol. A dead writer lock or prepared journal MUST be completed or rolled back according to that store's immutable evidence and recorded in the publisher result; a live writer lock or failed recovery MUST remain a visible blocker. Recovery MUST NOT select an older generation or alternate reader.

#### Scenario: Prior publisher died while holding a model-mesh lock
- **WHEN** the next sole publisher proves the recorded owner is not live
- **THEN** it uses the current store's explicit recovery operation, records the recovery receipt, and resumes the same current publication path without manual lock deletion

#### Scenario: A retired generic invalidation marker exists at cycle start
- **WHEN** an authorized Sleep cycle or versioned migration encounters a generic marker left by an older implementation
- **THEN** it classifies the covered lifecycle effects as no-effect, additive, exact-entry deny/replace, or exact-current corruption and retires the generic marker only through the current direct migration or complete activation path

#### Scenario: Sleep terminates before its final receipt
- **WHEN** the native Sleep owner exits, is cancelled, or reaches its hard timeout before emitting complete terminal JSON
- **THEN** the wrapper reports non-success, preserves the prior committed generation and watermark, exposes any valid batch checkpoint, and requires same-run process cleanup evidence before any later owner begins
