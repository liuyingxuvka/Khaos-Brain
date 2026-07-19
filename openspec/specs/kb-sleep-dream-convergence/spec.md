# kb-sleep-dream-convergence Specification

## Purpose
TBD - created by archiving change converge-kb-learning-and-upgrade-migration. Update Purpose after archive.
## Requirements
### Requirement: Sleep consumes history through a durable incremental watermark
Sleep SHALL process predictive-history input from a durable, monotonically increasing watermark instead of rescanning the full history as its normal path. The watermark receipt MUST identify the input generation, inclusive start position, exclusive end position, and digest of the consumed range. A retry with the same committed state and input range MUST produce the same dispositions without duplicating cards, history events, or handoffs.

#### Scenario: Sleep processes only newly eligible input
- **WHEN** Sleep starts with a committed watermark and newer eligible events exist
- **THEN** Sleep reads the new range plus explicitly carried unresolved backlog, records the range in its receipt, and leaves already settled history outside the normal processing set

#### Scenario: Sleep retries an already attempted range
- **WHEN** Sleep retries a range whose durable dispositions were already committed but whose acknowledgement was interrupted
- **THEN** Sleep recognizes the same idempotency keys, emits no duplicate knowledge mutations, and converges on the previously committed watermark

### Requirement: Failed Sleep work does not advance convergence state
Sleep MUST commit knowledge dispositions, convergence receipts, and the next watermark as one recoverable transaction. A failed, cancelled, timed-out, or partially validated run SHALL NOT advance the committed watermark or acknowledge a Dream handoff. Temporary output from an uncommitted attempt MUST remain distinguishable from durable knowledge state.

#### Scenario: Failure occurs before the transactional commit
- **WHEN** Sleep fails after reading an input range but before every required disposition and receipt is durably committed
- **THEN** the prior watermark remains authoritative, the range remains eligible for retry, and no partial result is counted as backlog reduction

#### Scenario: Validation fails for a proposed disposition
- **WHEN** a Sleep disposition fails schema, provenance, ownership, or lifecycle validation
- **THEN** Sleep records a machine-readable blocker, leaves the affected input unacknowledged, and does not advance past that input as if it were settled

### Requirement: One Sleep cycle has one final active-index validation owner
Sleep SHALL rebuild the active index only after the cycle's card and index-affecting lifecycle decisions are known. Intermediate no-delta model work MUST defer index validation to the final owner. A no-delta initial model publication MUST NOT launch the complete model-publication path again merely to finalize the index; the final owner SHALL validate the current index and rebuild that index directly only when its retrieval-affecting lifecycle projection is stale. If an earlier model publication already produced the final index generation and no later lifecycle decision changes eligibility, Sleep MUST reuse that exact current receipt instead of rebuilding or revalidating the same generation. The final receipt SHALL expose the chosen publication or reuse path and its current validation evidence.

#### Scenario: Sleep has no index-affecting delta
- **WHEN** intermediate model work is unchanged and lifecycle review produces no eligibility transition
- **THEN** Sleep MUST execute one final index validation owner, MUST NOT repeat model publication or perform a duplicate index rebuild or validation, and MUST bind that result before advancing the watermark

#### Scenario: An initial model publication remains final
- **WHEN** Sleep publishes a model generation with a current index validation and the later lifecycle review produces no index-affecting decision
- **THEN** Sleep MUST reuse the initial publication receipt as the final index evidence instead of launching an equivalent second owner

### Requirement: Successful Sleep runs reduce actionable backlog
Every Sleep run SHALL report `opening_actionable_backlog`, `newly_admitted`, `terminally_disposed`, `explicitly_parked`, and `closing_actionable_backlog` using one versioned counting rule. When the opening actionable backlog is nonzero and no declared safety blocker prevents mutation, a run reported as converged MUST make the closing actionable backlog lower than the opening actionable backlog after accounting for newly admitted work. Proposal files, action stubs, selections, reviews without disposition, and duplicate receipts MUST NOT count as backlog reduction.

#### Scenario: Actionable debt exists and the run is unblocked
- **WHEN** Sleep begins with actionable unresolved debt and can safely mutate the owned KB surfaces
- **THEN** it applies enough terminal or explicitly parked dispositions to produce a negative backlog delta and reports the exact items and counts that caused the reduction

#### Scenario: Intake exceeds the completed disposition volume
- **WHEN** newly admitted work causes the closing actionable backlog to equal or exceed the opening actionable backlog
- **THEN** Sleep reports `no_convergence` or `backlog_growth`, does not label the run converged, and preserves the remaining debt for the next incremental run

#### Scenario: No eligible work exists
- **WHEN** Sleep has no new eligible input, no actionable carried backlog, and no pending Dream handoff
- **THEN** it emits a bounded no-op convergence receipt without creating proposal stubs, synthetic observations, or replacement history noise

### Requirement: Dream handoff acknowledgement follows committed model publication
Sleep SHALL contribute every pending Dream handoff's observation admission and disposition events to the same bounded atomic lifecycle batch used by other Sleep-owned observations. It MUST replay lifecycle authority at most once before and once after that batch rather than once per handoff. Each replay MUST use indexed duplicate-key membership whose work grows linearly with lifecycle event count while preserving the ordered durable key projection; a quadratic scan inside a bounded replay count is non-conforming. Sleep SHALL keep each Dream handoff pending until its selected disposition and any staged candidate/model mutation have committed to the current LogicGuard authority generation. It MUST NOT write the handoff acknowledgement before model publication succeeds. When a Sleep owner terminates without a completed receipt, the next owner SHALL use the recovered lane identity to remove only that run's uncommitted acknowledgements and retry those handoffs idempotently. A completed model publication followed by partial acknowledgement MAY be resumed without repeating committed candidate identity.

#### Scenario: Several Dream handoffs are pending together
- **WHEN** one Sleep cycle receives multiple typed Dream handoffs
- **THEN** all missing admissions and dispositions MUST enter one idempotent lifecycle batch with exactly two lifecycle replays for that batch, regardless of handoff count

#### Scenario: The lifecycle authority has accumulated many events
- **WHEN** Sleep replays a large current lifecycle ledger before or after its atomic batch
- **THEN** duplicate-key validation SHALL perform one indexed membership decision per event, preserve exact ordering and duplicate diagnostics, and SHALL NOT rescan every prior key for every event

#### Scenario: Sleep terminates during model publication
- **WHEN** a Dream handoff observation and disposition are durable but the Sleep owner terminates before model publication returns success
- **THEN** the handoff MUST remain or become pending, the incomplete run MUST have no reusable acknowledgement, and the next owner MUST retry it against the current generation

#### Scenario: Model publication succeeds
- **WHEN** all staged handoff-derived candidate/model changes commit and bind the current generation
- **THEN** Sleep MAY acknowledge each included handoff exactly once and SHALL include those acknowledgement ids in its completed receipt

### Requirement: Sleep prioritizes evidence-bearing and aging debt deterministically
Sleep SHALL use a deterministic priority policy that includes evidence quality, user correction or test evidence, item age, repeated retrieval impact, and lifecycle urgency. An item moved to a parked state MUST include a reason, reopening condition, responsible owner, and next review trigger; an indefinite review-only state SHALL remain actionable debt.

#### Scenario: Old evidence-bearing debt competes with recent low-value input
- **WHEN** the processing budget cannot settle every eligible item
- **THEN** Sleep selects work using the declared priority fields and records enough ranking evidence to reproduce the selection

#### Scenario: Sleep parks an item safely
- **WHEN** an item cannot reach a terminal disposition because a named dependency is unavailable
- **THEN** Sleep records a bounded parked disposition with its blocker and reopening trigger, and the item is excluded from actionable backlog only while that trigger remains unsatisfied

### Requirement: Dream experiments use stable evidence fingerprints
Dream SHALL derive a deterministic evidence fingerprint from canonical route, hypothesis, source identifiers, source content digests, prior applicable outcome, and other decision-relevant evidence. Volatile values including run ID, scheduling time, thread ID, model name, and prompt wording MUST NOT make identical evidence appear new. The fingerprint algorithm and schema version MUST be recorded in the Dream runtime receipt.

#### Scenario: Identical evidence is discovered in a later run
- **WHEN** Dream encounters the same canonical evidence and hypothesis that produced an earlier fingerprint
- **THEN** it resolves to the existing fingerprint and does not schedule a duplicate experiment

#### Scenario: Decision-relevant source evidence changes
- **WHEN** a source digest, relevant outcome, or canonical hypothesis changes
- **THEN** Dream produces a new fingerprint linked to the prior fingerprint and records the evidence delta that justifies reconsideration

### Requirement: Dream enforces cooldown and evidence-delta reopening
After an experiment reaches a completed, rejected, blocked, or no-delta terminal state, Dream SHALL record a cooldown and closure state for its evidence fingerprint. The passage of time alone MUST NOT reopen identical evidence; reopening MUST require a decision-relevant evidence delta or an explicit invalidation of the prior receipt with a machine-readable reason.

#### Scenario: A closed fingerprint appears during cooldown
- **WHEN** Dream sees a fingerprint that is still within its cooldown and has no evidence delta
- **THEN** it suppresses execution and reuses the existing closure without appending a new experiment, observation, or handoff

#### Scenario: Cooldown expires without new evidence
- **WHEN** the cooldown expires but the canonical evidence fingerprint remains unchanged
- **THEN** Dream keeps the opportunity closed and does not treat schedule age as permission to rerun it

#### Scenario: Prior evidence becomes invalid
- **WHEN** a named source is withdrawn, corrupted, or proven stale and the prior receipt is explicitly invalidated
- **THEN** Dream records the invalidation reason and permits a replacement experiment under a newly derived fingerprint

### Requirement: No-delta opportunities close as no_delta_closed
Dream SHALL assign `no_delta_closed` when an opportunity has no decision-relevant evidence beyond an existing closed fingerprint. The first closure receipt MUST reference the prior experiment or decision and its evidence fingerprint. Repeated scans of the same no-delta opportunity MUST reuse that closure and MUST NOT add per-run KB history, candidate, observation, or handoff records; aggregate runtime counters remain permitted in the bounded Dream receipt.

#### Scenario: Dream finds no new evidence for a known opportunity
- **WHEN** an opportunity matches an existing closed fingerprint and the computed evidence delta is empty
- **THEN** Dream records or reuses `no_delta_closed`, cites the prior outcome, and performs no experiment or KB mutation

#### Scenario: The same no-delta opportunity is scanned repeatedly
- **WHEN** later scheduled runs encounter the unchanged `no_delta_closed` opportunity
- **THEN** they increment only bounded aggregate telemetry and do not create another closure object or history event

### Requirement: Dream hands all knowledge-changing results to Sleep
Dream SHALL be a read-and-experiment producer and Sleep SHALL be the sole owner that converts Dream results into observations, candidates, card changes, confidence changes, or durable knowledge-history dispositions. Dream SHALL restrict its writes to a bounded runtime receipt, experiment evidence, and a typed Sleep handoff on Dream-owned surfaces. Every handoff MUST carry the evidence fingerprint, result digest, provenance, requested disposition class, and an idempotency key.

#### Scenario: Dream produces a result with possible reuse value
- **WHEN** a Dream experiment produces a result that could change durable KB knowledge
- **THEN** Dream emits one typed, idempotent handoff to Sleep and does not directly mutate KB cards, candidates, confidence, or predictive history

#### Scenario: Sleep receives the same handoff more than once
- **WHEN** delivery retries present an already acknowledged Dream handoff
- **THEN** Sleep reuses the prior disposition receipt and creates no duplicate observation, candidate, card mutation, or acknowledgement

#### Scenario: Sleep rejects a Dream handoff
- **WHEN** the handoff lacks required evidence, provenance, or lifecycle validity
- **THEN** Sleep records a rejection or parked disposition with a reason, and Dream does not bypass Sleep by writing the result elsewhere in durable KB state

### Requirement: Convergence receipts expose machine-verifiable progress
Each Sleep and Dream run SHALL emit a bounded, versioned, machine-readable convergence receipt. A Sleep receipt MUST include input and output watermarks, backlog counts and delta, disposition IDs, handoff acknowledgements, blockers, and final run state. A Dream receipt MUST include evaluated fingerprints, evidence deltas, suppressed duplicates, cooldown decisions, `no_delta_closed` counts, emitted handoff IDs, blockers, and final run state. A receipt MUST identify the exact policy and input digests used to produce it.

#### Scenario: Assurance evaluates a completed Sleep and Dream cycle
- **WHEN** the runtime-assurance gate inspects the latest completed maintenance cycle
- **THEN** it can reproduce whether input advanced, backlog declined, duplicate experiments were suppressed, and every handoff has exactly one Sleep disposition from the two receipts

#### Scenario: A run omits required convergence evidence
- **WHEN** a Sleep or Dream run lacks a required watermark, count, fingerprint, disposition, blocker, or digest field
- **THEN** the run is incomplete for convergence purposes and cannot satisfy the runtime completion gate
