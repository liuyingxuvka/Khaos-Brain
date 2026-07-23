## ADDED Requirements

### Requirement: Lifecycle batch items declare retrieval impact and settlement
Every lifecycle item admitted to a Sleep batch SHALL declare exactly one retrieval impact: `none`, `additive_pending`, `entry_revoke`, `entry_replace`, or `global_current_corruption`. A completed item SHALL bind its exact lifecycle events, output digests, and retrieval effect. A blocked item SHALL bind evidence, one responsible owner, and one executable reopen condition. An item without either disposition SHALL remain pending and MUST NOT be counted as settled.

#### Scenario: A new candidate is not yet retrievable
- **WHEN** Sleep creates or parks a candidate that was absent from the current active index
- **THEN** the item declares `additive_pending`, the current generation remains readable, and the candidate becomes eligible only after a complete later activation

#### Scenario: A current indexed entry is revoked
- **WHEN** supported lifecycle evidence removes one exact indexed record from retrieval eligibility
- **THEN** the item declares `entry_revoke`, publishes an exact subtractive deny for that record before committing the transition, and does not globally block unrelated records

#### Scenario: The current generation itself is corrupt
- **WHEN** evidence identifies corruption of the exact current index generation or its bound authority
- **THEN** the item declares `global_current_corruption`, records the generation-bound evidence, and foreground retrieval fails closed until canonical repair

## MODIFIED Requirements

### Requirement: Same-cycle lifecycle transitions share one bounded publication owner
Lifecycle transitions selected by one Sleep cycle SHALL be constructed without independent publication and committed by one explicit bounded batch owner. Candidate creation, initial parking, reopening, promotion, downgrade, and same-cycle calibration decisions MUST preserve their per-entry causal order inside that owner. The owner SHALL stage item results and transitions away from the current retrieval generation, SHALL publish exact subtractive denies before any committed removal or replacement of a current indexed record, and SHALL activate one complete pointer-bound generation only after every frozen item is settled and all generation checks pass. No helper MAY silently switch to a separate successful per-event or per-candidate publisher when staged publication is selected.

#### Scenario: A new candidate is created and immediately parked
- **WHEN** one observation creates a bounded candidate that lacks independent promotion evidence
- **THEN** the candidate snapshot MUST precede its parking transition in the same ordered batch and replay MUST reconstruct the same final parked state and evidence trail

#### Scenario: A parked candidate reopens and promotes in one review
- **WHEN** material new evidence satisfies reopening and promotion conditions during one Sleep cycle
- **THEN** reopening MUST precede promotion in the same ordered batch and both transitions MUST retain their distinct reasons, evidence, actor, and idempotency identities

#### Scenario: Staged publication fails or stops
- **WHEN** the batch owner cannot validate, finish, or durably activate the planned transitions
- **THEN** callers MUST receive non-success or `progress_saved`, completed item results remain resumable, the prior validated generation remains readable unless exact current corruption was proven, and callers MUST NOT retry through an ungoverned per-event fallback
