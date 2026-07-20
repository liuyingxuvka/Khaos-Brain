## ADDED Requirements

### Requirement: Sleep candidate lifecycle work is scale-bounded and retry-convergent
Sleep SHALL stage all same-cycle candidate lifecycle events into bounded atomic lifecycle batches rather than replaying the complete lifecycle authority once per candidate or transition. Each batch MUST preserve deterministic event order, stable candidate identity, stable idempotency keys, exact transition semantics, and one fail-closed active-index invalidation before any index-affecting event is appended. The batch receipt MUST report requested, created, reused, and residual transition counts together with its lifecycle replay count. A prior timed-out run's durable partial events MUST be reused by the next authorized Sleep owner without duplicate candidates, events, handoffs, dispositions, or backlog reduction.

#### Scenario: Several candidate observations are handled in one Sleep cycle
- **WHEN** one Sleep cycle creates or reuses multiple candidates and assigns their initial lifecycle outcomes
- **THEN** their ordered snapshot and transition events MUST enter bounded atomic batches whose replay count does not grow with candidate count

#### Scenario: Sleep retries after partial candidate lifecycle commits
- **WHEN** a previous Sleep owner timed out after some candidate events became durable but before final index publication and watermark commit
- **THEN** the next authorized Sleep owner MUST reuse the existing identities and idempotency keys, append only missing events, and converge without counting or publishing the partial work twice

#### Scenario: The bounded batch cannot finish safely
- **WHEN** a lifecycle batch reaches its declared size, time, lock, validation, or authority boundary before every planned transition is committed
- **THEN** Sleep MUST keep residual work visible, preserve the fail-closed index state when eligibility may have changed, leave the committed watermark unchanged, and emit non-success rather than falling back to per-event publication

### Requirement: Sleep receipts expose the final index recovery path
Every Sleep receipt SHALL identify whether its final active-index owner reused current evidence, rebuilt the index against the current authority, or republished after a later lifecycle decision. A completed receipt MUST bind the lifecycle batch evidence, current LogicGuard generation, active-index generation and content digest, activation authority digest, lifecycle-entry digest, invalidation-marker disposition, and watermark commit. A timeout or incomplete native payload MUST NOT be reusable as successful index-recovery evidence.

#### Scenario: A durable invalidation marker exists at cycle start
- **WHEN** an authorized Sleep cycle starts with a marker left by a prior index-affecting lifecycle event
- **THEN** the final owner MUST validate or rebuild against the complete current lifecycle and LogicGuard authority, MUST remove the marker only through successful activation, and MUST bind that result before advancing the watermark

#### Scenario: Sleep terminates before its final receipt
- **WHEN** the native Sleep owner exits, is cancelled, or reaches its timeout before emitting a complete terminal payload
- **THEN** the wrapper MUST report non-success, preserve the prior watermark and marker authority, and require same-run process cleanup evidence before any later owner begins
