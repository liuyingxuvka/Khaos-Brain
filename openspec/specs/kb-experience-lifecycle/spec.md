# kb-experience-lifecycle Specification

## Purpose
TBD - created by archiving change converge-kb-learning-and-upgrade-migration. Update Purpose after archive.
## Requirements
### Requirement: Every admitted observation receives a timely disposition
The system SHALL assign every admitted observation a stable observation identifier, an admission timestamp, and exactly one machine-readable current disposition. The disposition MUST be recorded no later than the end of the first successful Sleep cycle after admission and MUST be recorded within 24 hours while the scheduled maintenance service is healthy. Supported dispositions SHALL distinguish linking or updating existing knowledge, creating or merging into a candidate, requesting bounded Dream validation, closing as one-off evidence, rejecting, and parking. Every disposition MUST record its reason, evidence grade, source references, deciding pass, decision timestamp, and any owned follow-up identifier and deadline.

#### Scenario: New observation is handled by the next healthy Sleep cycle
- **WHEN** an observation is admitted before a healthy scheduled Sleep cycle begins
- **THEN** that Sleep cycle MUST persist one disposition with all required decision metadata before advancing the observation watermark

#### Scenario: Pending validation remains explicitly owned
- **WHEN** Sleep disposes an observation as requiring Dream validation
- **THEN** the disposition MUST reference one bounded validation request, its evidence fingerprint, its owner, and the deadline for returning the result to Sleep

#### Scenario: Failed processing does not hide an observation
- **WHEN** a Sleep cycle fails before an observation disposition is durably committed
- **THEN** the system MUST leave the watermark before that observation and MUST present the observation again to the next successful cycle

### Requirement: Evidence is graded by verifiable strength
The system SHALL grade every evidence item as `strong`, `medium`, or `weak` using a versioned and auditable grading policy. Explicit user corrections or confirmations tied to a concrete episode, verified test failure or success tied to a change, and reproducible real-task outcomes SHALL qualify as strong evidence. Repeated consistent task observations or a bounded Dream result without independent real-task confirmation SHALL qualify as medium evidence. AI self-reported hits, single unverified inferences, generic advice, and observations without a scenario-action-result relation MUST remain weak evidence. The system MUST preserve each evidence item's grade, rationale, and reference rather than replacing the underlying evidence with one aggregate label.

#### Scenario: User correction receives strong grading
- **WHEN** a user correction is tied to the task, action, prior result, and corrected result that produced it
- **THEN** the system MUST grade that evidence as strong and preserve the correction as contrastive provenance

#### Scenario: AI self-assessment cannot strengthen a claim
- **WHEN** the only support for an observation is an AI-authored declaration that a card was a hit
- **THEN** the system MUST grade the support as weak and MUST NOT use it alone to promote or retain trusted status

#### Scenario: Duplicated evidence remains one support source
- **WHEN** the same evidence payload is copied into multiple files or maintenance reports
- **THEN** the system MUST identify the shared evidence fingerprint and MUST NOT count the copies as independent support

### Requirement: Knowledge records preserve end-to-end provenance
Every candidate and trusted card SHALL reference the observation identifiers and evidence identifiers that support it. Provenance MUST preserve the originating episode timestamp and, when available, the agent, task or thread, project, workspace, test receipt, user correction, and Dream experiment identifiers. A merge MUST preserve the union of non-duplicate provenance from every source record, and archival of source material MUST leave stable references that remain resolvable from the lifecycle history. A record with missing required provenance MUST remain retrieval-ineligible and MUST NOT be promoted.

#### Scenario: Candidate is created from observations
- **WHEN** Sleep creates a candidate from one or more observations
- **THEN** the candidate MUST contain stable references to every supporting observation, its graded evidence, and the maintenance decision that created it

#### Scenario: Candidate merge preserves sources
- **WHEN** several candidates are merged into one surviving candidate or trusted card
- **THEN** the surviving record MUST preserve the deduplicated provenance of every merged record and each merged record MUST reference the survivor

#### Scenario: Provenance gap blocks promotion
- **WHEN** a candidate lacks a resolvable source observation or evidence reference required by the promotion policy
- **THEN** the system MUST block promotion and MUST record the provenance gap as the decision reason

### Requirement: Candidate lifecycle has bounded explicit outcomes
The candidate lifecycle SHALL use the explicit states `candidate`, `trusted`, `merged`, `rejected`, `superseded`, and `parked`. Every newly created or demoted `candidate` MUST receive a decision within seven days that promotes it to `trusted`, merges it into a named survivor, rejects it with a reason, supersedes it with a named replacement, or parks it with a reopen condition. `merged`, `rejected`, and `superseded` SHALL be terminal and retrieval-ineligible. A lifecycle transition MUST be committed together with its reason, prior state, target state, evidence set, actor, timestamp, and target record where the outcome requires one; lifecycle settlement MUST NOT hard-delete the evidence trail.

#### Scenario: Duplicate candidate is merged
- **WHEN** semantic review determines that a candidate expresses the same bounded prediction as an existing record
- **THEN** the system MUST mark the candidate `merged`, name the surviving record, transfer non-duplicate provenance, and remove the merged record from active retrieval

#### Scenario: Unsupported candidate is rejected
- **WHEN** a candidate is contradicted, non-predictive, non-reusable, or unsupported after its bounded review
- **THEN** the system MUST mark it `rejected`, preserve the rejection reason and evidence, and remove it from active retrieval

#### Scenario: Better knowledge supersedes an older record
- **WHEN** a newer record replaces the applicability or prediction of an older candidate or card
- **THEN** the system MUST mark the older record `superseded`, link it bidirectionally to the replacement, and remove the older record from active retrieval

#### Scenario: Candidate deadline expires without sufficient evidence
- **WHEN** a candidate reaches seven days without satisfying promotion, merge, rejection, or supersession criteria
- **THEN** the system MUST mark it `parked` with a concrete reopen condition instead of leaving it indefinitely in `candidate`

### Requirement: Promotion requires current independent support
The system SHALL promote a candidate to `trusted` only when the candidate has complete provenance, one bounded predictive scenario-action-result claim, an explicit applicability boundary, operational guidance, no unresolved strong contradiction, and current semantic validation. The evidence threshold MUST be either at least one strong evidence item plus an independent current validation receipt, or at least two independent medium evidence items from distinct episodes plus an independent current validation receipt. Weak evidence MUST NOT satisfy the promotion threshold. Each promotion MUST emit a receipt containing the policy version, qualifying evidence, validation result, prior and new confidence, and decision timestamp.

#### Scenario: Strong evidence passes promotion review
- **WHEN** a provenance-complete candidate has strong real-task evidence, an independent current validation receipt, and no unresolved strong contradiction
- **THEN** the system SHALL permit promotion and MUST persist the complete promotion receipt atomically with trusted status

#### Scenario: Weak scaffold is not promoted
- **WHEN** an auto-generated scaffold has only weak evidence or lacks a bounded predictive claim
- **THEN** the system MUST block promotion and MUST route the candidate to rewrite, merge, rejection, or parking within its lifecycle deadline

#### Scenario: Repeated copies do not satisfy independence
- **WHEN** two nominal evidence items resolve to the same episode or evidence fingerprint
- **THEN** the system MUST count them as one evidence source for promotion eligibility

### Requirement: Trusted knowledge is downgraded when support no longer holds
The system SHALL re-evaluate trusted knowledge when a user correction, verified test failure, misleading retrieval outcome, scope violation, or other contradictory evidence is linked to it. Unresolved strong contradictory evidence MUST make the card retrieval-ineligible immediately and MUST produce a downgrade decision by the end of the next successful Sleep cycle. The decision SHALL restore trusted status only with resolving evidence, or SHALL move the record to `candidate`, `parked`, `rejected`, or `superseded` according to the current evidence. Every downgrade or restoration MUST preserve the triggering evidence, confidence change, reason, and prior state.

#### Scenario: Strong contradiction suspends a trusted card
- **WHEN** a verified task outcome shows that following a trusted card caused an incorrect or harmful result within the card's declared scope
- **THEN** the system MUST exclude the card from retrieval immediately and MUST complete a documented downgrade review in the next successful Sleep cycle

#### Scenario: Corrected scope restores trusted status
- **WHEN** review narrows a suspended card's applicability and current evidence validates the corrected bounded claim
- **THEN** the system SHALL restore trusted status only with a receipt linking the contradiction, scope change, and resolving validation

### Requirement: Parked knowledge reopens only on material new evidence
A `parked` record SHALL contain a machine-evaluable reopen condition, the evidence fingerprint present when it was parked, and the required evidence class or event. The system MUST exclude parked records from routine retrieval and repeated semantic maintenance. When the aggregated evidence fingerprint changes but does not satisfy the reopen condition, Sleep SHALL write one same-state `entry-calibration-snapshot` that advances the evidence-review watermark without changing retrieval eligibility; a later unchanged cycle MUST reuse that watermark without another history event. It MUST reopen a parked record as `candidate` only when material new evidence satisfies its reopen condition, and reopening MUST create a new candidate decision deadline and an audit event.

#### Scenario: No new evidence leaves a record parked
- **WHEN** a maintenance cycle encounters a parked record with the same evidence fingerprint and an unsatisfied reopen condition
- **THEN** the system MUST leave the record parked without repeating semantic review or creating duplicate maintenance history

#### Scenario: New evidence does not satisfy reopening
- **WHEN** the aggregated evidence fingerprint changes but the parked record still fails its declared reopen condition
- **THEN** Sleep MUST keep the record parked, MUST persist exactly one calibration snapshot for the new fingerprint, and MUST NOT invalidate retrieval eligibility merely because calibration metadata changed

#### Scenario: New evidence reopens review
- **WHEN** a new user correction, verified task outcome, test receipt, or Dream result satisfies a parked record's declared reopen condition
- **THEN** the system MUST reopen it as `candidate`, attach the new evidence, and set a new seven-day decision deadline

### Requirement: Lifecycle history is complete and replayable
The system SHALL append one immutable lifecycle event for every observation disposition, candidate transition, promotion, downgrade, merge, rejection, supersession, parking, and reopening. Lifecycle events MUST be sufficient to reconstruct the current state from a prior snapshot, MUST reference the policy and evidence versions used, and MUST be committed atomically with the state mutation. A current state without a matching event, or an event without a matching committed state, MUST fail lifecycle validation.

#### Scenario: State transition and history event commit together
- **WHEN** a maintenance action changes an observation, candidate, or trusted-card lifecycle state
- **THEN** the system MUST commit the new state and its lifecycle event as one recoverable operation

#### Scenario: Replay detects an orphan mutation
- **WHEN** lifecycle replay finds a current state change without the required event or evidence reference
- **THEN** lifecycle validation MUST fail and MUST identify the affected record without advancing maintenance completion

### Requirement: Lifecycle mutation has one recoverable identified writer
Every lifecycle mutation and active-index activation SHALL use the same exclusive current writer-lock protocol. A physical lock MUST bind an exact process id, thread id, and unique owner token. A live owner MUST never be displaced; an active same-thread nested call MUST reuse its current ownership without self-deadlock; a recorded dead owner or an interrupted ownerless acquisition MUST be recovered after the bounded creation grace. Physical release MUST verify the same owner token, and a release failure MUST remain a visible terminal failure rather than being silently ignored.

#### Scenario: Interrupted lock acquisition leaves only a directory
- **WHEN** a writer exits after creating the lock directory but before committing its owner identity, and the bounded creation grace expires
- **THEN** the next writer MUST classify the directory as interrupted, remove only that unchanged ownerless lock, and acquire a new exact identity

#### Scenario: Recorded lifecycle writer is still alive
- **WHEN** another process or thread owns the current token and its recorded process remains alive
- **THEN** the requester MUST wait or fail visibly at its declared timeout and MUST NOT steal, rewrite, or delete the live owner's lock

#### Scenario: Lifecycle lock release is rejected by the filesystem
- **WHEN** the owner cannot remove the lock after its bounded release retries
- **THEN** the operation MUST preserve or restore the exact owner identity, report non-success, and MUST NOT claim that Sleep, Dream, postflight, or index activation completed
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
