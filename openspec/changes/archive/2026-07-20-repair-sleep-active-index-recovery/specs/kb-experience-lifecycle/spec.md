## ADDED Requirements

### Requirement: Same-cycle lifecycle transitions share one bounded publication owner
Lifecycle transitions selected by one Sleep cycle SHALL be constructed without independent publication and committed by one explicit bounded batch owner. Candidate creation, initial parking, reopening, promotion, downgrade, and same-cycle calibration decisions MUST preserve their per-entry causal order inside that owner. No helper MAY silently switch to a separate successful per-event publisher when staged publication is selected.

#### Scenario: A new candidate is created and immediately parked
- **WHEN** one observation creates a bounded candidate that lacks independent promotion evidence
- **THEN** the candidate snapshot MUST precede its parking transition in the same ordered batch and replay MUST reconstruct the same final parked state and evidence trail

#### Scenario: A parked candidate reopens and promotes in one review
- **WHEN** material new evidence satisfies reopening and promotion conditions during one Sleep cycle
- **THEN** reopening MUST precede promotion in the same ordered batch and both transitions MUST retain their distinct reasons, evidence, actor, and idempotency identities

#### Scenario: Staged publication fails
- **WHEN** the batch owner cannot validate or durably publish the planned transitions
- **THEN** callers MUST receive non-success and MUST NOT retry those transitions through an ungoverned per-event fallback

### Requirement: Lifecycle batch evidence proves bounded replay
Every lifecycle batch receipt used for Sleep completion SHALL report the exact requested, created, reused, and residual event counts, the final sequence, and replay passes. For one batch, lifecycle authority MUST be replayed at most once before and once after publication regardless of event count. Historical progress or a count-only report without current replay evidence MUST NOT satisfy the bounded-replay claim.

#### Scenario: The lifecycle ledger is production-scale
- **WHEN** a batch is committed against the declared large-ledger regression fixture or current production-scale evidence
- **THEN** its receipt MUST show bounded replay passes and exact event accounting without one complete replay per transition
