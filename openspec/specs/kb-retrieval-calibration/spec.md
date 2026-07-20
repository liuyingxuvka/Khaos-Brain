# kb-retrieval-calibration Specification

## Purpose
TBD - created by archiving change converge-kb-learning-and-upgrade-migration. Update Purpose after archive.
## Requirements
### Requirement: Retrieval serves only eligible active knowledge
The retrieval system SHALL generate results only from the current active-knowledge index. `trusted` records SHALL be eligible by default. A `candidate` record SHALL be eligible only when an explicit policy marks it retrieval-eligible, the query exceeds the candidate relevance threshold, and the result is visibly labeled as untrusted. Records in `merged`, `rejected`, `superseded`, `parked`, or deprecated states, provenance-incomplete records, and trusted records suspended by contradictory evidence MUST be ineligible. Eligibility filtering MUST apply during route expansion, lexical matching, related-card traversal, direct identifier lookup, and final ranking. No scan, older index, directory placement, or alternate reader may return results when current index authority is unavailable.

#### Scenario: Trusted and eligible candidate records are ranked
- **WHEN** a query matches both a trusted card and an explicitly retrieval-eligible candidate
- **THEN** the system MUST rank the trusted card with the trusted-status preference and MUST label the candidate's untrusted status in the machine result

#### Scenario: Ineligible record is excluded from every search path
- **WHEN** an ineligible record matches a route, keyword, related-card edge, or direct identifier
- **THEN** the retrieval system MUST exclude it before results are returned

### Requirement: Local authority and read-only organization visibility remain distinct
The system SHALL treat candidate lifecycle authority and candidate source visibility as separate dimensions. An ineligible local candidate MUST NOT enter predictive retrieval. A read-only organization candidate MAY be returned by an organization-source search only as explicitly untrusted, read-only input for adoption or automated validation, and MUST NOT thereby enter the local active index, gain local retrieval eligibility, or receive trusted authority. Organization-source reads MUST use only the strict current schema-version-1 manifest with the `kb/main` surface; old `kb/trusted` and `kb/candidates` roots and retired manifest fields MUST be migrated before the source can participate.

#### Scenario: Read-only organization candidate is visible but not authoritative
- **WHEN** an organization-source search strongly matches a candidate that has no local retrieval eligibility
- **THEN** the result MAY be returned with `untrusted-candidate` and read-only source labels, but it MUST NOT be present in the local active index

#### Scenario: Equivalent local candidate remains hidden
- **WHEN** an ineligible local candidate matches the same query as a visible read-only organization candidate
- **THEN** the local candidate MUST be excluded and the organization result MUST NOT transfer eligibility or confidence to it

#### Scenario: Organization candidate is adopted
- **WHEN** automated validation accepts a read-only organization candidate for local adoption
- **THEN** the adopted local identity MUST enter the normal local lifecycle and remain ineligible until its own explicit local evidence gate passes

### Requirement: Rejected and superseded knowledge has zero retrieval exposure
The system SHALL return zero `rejected` and zero `superseded` records in every user-facing and machine-facing Top-K result. This invariant MUST hold when the query exactly matches the record identifier or title or a related card points to it. A stale index MUST be rejected before serving any query and MUST NOT trigger an alternate result-producing code path.

#### Scenario: Exact rejected-card query returns no rejected record
- **WHEN** a query exactly matches the identifier, title, and route of a rejected card
- **THEN** the Top-K result MUST contain zero rejected records

#### Scenario: Superseded related card is not expanded
- **WHEN** an active card links to a superseded card that otherwise strongly matches the query
- **THEN** related-card traversal MUST omit the superseded card and MUST NOT expose its content as a result

#### Scenario: Stale index cannot bypass terminal status
- **WHEN** a card becomes rejected or superseded after the current index generation
- **THEN** retrieval MUST block or refresh the stale generation before serving any result that could contain that card

### Requirement: Active-knowledge indexing is atomic and reproducible
The system SHALL maintain a versioned active-knowledge index derived from canonical current card state, lifecycle status, provenance eligibility, route data, content identity, and confidence. A committed lifecycle or content mutation MUST atomically publish a new index generation or mark the old generation unavailable before the next query. Index rebuilds MUST be deterministic for the same canonical inputs and MUST emit the source watermark, schema version, indexed record count, excluded-status counts, content digest, build duration, and validation result. The current active index SHALL be the sole result-producing retrieval authority.

#### Scenario: Lifecycle mutation invalidates the old index generation
- **WHEN** a card transitions from trusted to rejected, superseded, parked, or retrieval-suspended
- **THEN** the old generation MUST become unavailable for new queries until a generation excluding that card is validated

#### Scenario: Index rebuild is reproducible
- **WHEN** the index is rebuilt twice from identical canonical inputs and the same schema and policy versions
- **THEN** both builds MUST produce the same content digest, eligible record set, and status-exclusion counts

#### Scenario: Interrupted index publication preserves a valid generation
- **WHEN** index construction or publication is interrupted
- **THEN** retrieval MUST continue only from the last validated eligible generation or remain unavailable and MUST NOT serve a partially built index

### Requirement: Retrieval records real-task outcome receipts
Every retrieval request SHALL emit a retrieval receipt containing a stable request identifier, timestamp, query and context fingerprint, inferred route hints, index and policy versions, returned entry identifiers with ranks and scores, the entry identifiers actually used to influence the task, and whether the system abstained with no card. When the task outcome becomes available, the system MUST append outcome evidence for test results, task success or failure, rework, user correction, misleading guidance, and other observable completion signals. A retrieved-but-unused card MUST NOT receive use credit, an unavailable outcome MUST be recorded as `unknown`, and an AI-authored hit assertion without external evidence MUST NOT be recorded as verified success.

#### Scenario: Used card receives verified outcome evidence
- **WHEN** a task uses a returned card and a linked automated test or user-confirmed result establishes the outcome
- **THEN** the outcome receipt MUST link that evidence to the used card and classify the result under the current calibration policy

#### Scenario: Visible but unused card receives no use credit
- **WHEN** a card appears in Top-K but does not influence the task decision or action
- **THEN** the receipt MUST preserve its retrieval rank but MUST NOT count it as a successful application

#### Scenario: Outcome is unavailable
- **WHEN** no test, user response, or other observable task result is available
- **THEN** the system MUST record the outcome as `unknown` and MUST NOT convert an AI self-report into positive calibration evidence

### Requirement: No-card is a first-class correct result
The retrieval system SHALL abstain and return a machine-readable no-card result when no eligible card meets the versioned relevance and confidence thresholds. A no-card result MUST contain the evaluated route, thresholds, active index generation, and reason for abstention, and MUST be preserved in the retrieval and outcome receipts. The system MUST NOT force a low-confidence or ineligible result merely to avoid an empty Top-K response.

#### Scenario: Uncovered task returns no card
- **WHEN** a task has no eligible card above the current relevance and confidence thresholds
- **THEN** retrieval MUST return no-card with an auditable abstention reason and zero forced card results

#### Scenario: No-card outcome becomes future evidence
- **WHEN** a no-card task later yields a verified reusable observation
- **THEN** the outcome receipt MUST link to that observation without retroactively claiming that an existing card was used

### Requirement: Confidence is calibrated from graded outcome evidence
The system SHALL calculate card confidence with a versioned, deterministic, and inspectable calibration policy using graded source evidence and verified outcome receipts. Verified successful use SHALL increase support only for cards actually used; user corrections, verified failures, misleading guidance, and scope violations SHALL reduce support; `unknown` outcomes and retrieved-but-unused cards SHALL not increase support. AI self-reported hits and simulated shadow decisions MUST remain distinguishable from real-task outcomes and MUST NOT independently increase confidence. Calibration output MUST include support and contradiction counts by evidence grade, effective sample size, uncertainty or confidence bounds, prior and new confidence, and the policy version. A confidence change that crosses a lifecycle threshold MUST trigger the corresponding promotion or downgrade review rather than silently changing retrieval authority.

#### Scenario: Verified success raises support for the used card
- **WHEN** a card is actually used and linked current evidence verifies a successful result within its applicability boundary
- **THEN** recalibration SHALL increase that card's support according to the evidence grade and MUST record the calculation inputs and result

#### Scenario: User correction lowers support
- **WHEN** a user correction demonstrates that a used card was misleading within its declared scope
- **THEN** recalibration MUST record strong contradictory evidence, reduce support under the current policy, and trigger downgrade review when the lifecycle threshold is crossed

#### Scenario: Simulated comparison remains non-real evidence
- **WHEN** an AI-generated shadow decision is compared with the task path but is not executed or externally verified
- **THEN** the system MUST label it simulated and MUST NOT count it as a real-task success or failure

### Requirement: Retrieval regression covers relevance, abstention, and status safety
The retrieval regression suite SHALL contain versioned cases for useful-card queries, no-card queries, candidate labeling, direct identifier lookup, route expansion, related-card traversal, contradictory evidence suspension, and stale-index terminal statuses. On the declared representative corpus, the suite MUST achieve at least 90 percent useful-card presence in Top-3 for cases with a known applicable card, fewer than 5 percent false card returns for known no-card cases, and exactly zero rejected or superseded records in all returned results. The report MUST publish case counts, corpus digest, index generation, thresholds, failures, and skipped cases; a skipped or stale suite MUST NOT satisfy an upgrade or release gate.

#### Scenario: Relevant-card regression meets the Top-3 target
- **WHEN** the current regression suite runs against cases with a known applicable eligible card
- **THEN** at least 90 percent of those cases MUST place a useful card in Top-3 and the report MUST list every miss

#### Scenario: No-card regression controls false positives
- **WHEN** the suite runs against cases explicitly labeled as having no applicable card
- **THEN** fewer than 5 percent of those cases SHALL return any card and every false positive MUST be reported

#### Scenario: Terminal-status leak fails the suite
- **WHEN** any regression case returns a rejected or superseded record
- **THEN** the suite MUST fail regardless of aggregate relevance or latency scores

### Requirement: Foreground retrieval uses a compact fail-closed authority snapshot
Routine retrieval SHALL validate the generated index, its activation receipt, and only the source records that can actually be returned. It MUST NOT rescan every inactive card or replay the complete lifecycle event log on each query. Within one process it MAY reuse only a successful exact indexed-source and LogicGuard projection validation whose key binds the repository root, active-index generation and content digest, invalidation token, active authority digest, current LogicGuard generation pointer digest, and raw content digest of every indexed source. Each query MUST compare indexed-source content signatures before and after its snapshot. A changed source, index, authority, LogicGuard generation, or invalidation token MUST force exact revalidation or visible failure; failed validation MUST NOT be cached. Observation-only events SHALL NOT invalidate entry eligibility. Before any lifecycle event that can change entry eligibility is committed, the writer MUST durably invalidate the active authority; a validated rebuild is the only operation permitted to reactivate it. Full manifest and lifecycle replay SHALL remain mandatory for rebuild, Sleep, migration, and aggregate audit rather than foreground query latency.

#### Scenario: Observation intake does not stale entry authority
- **WHEN** another AI records a new observation without changing any card lifecycle state
- **THEN** the current index generation MUST remain queryable through the compact authority path without a full manifest scan or lifecycle replay

#### Scenario: Entry transition invalidates before mutation
- **WHEN** a trusted or candidate entry is transitioned to a different lifecycle state
- **THEN** a durable fail-closed marker MUST exist before the lifecycle event is appended, and routine retrieval MUST remain unavailable until a full validated rebuild activates a new generation

#### Scenario: Active source changes outside the lifecycle writer
- **WHEN** an indexed source file is deleted, moved outside its declared scope, changes identity, or changes content
- **THEN** the compact query check MUST reject that generation even if no lifecycle invalidation marker was emitted

#### Scenario: Repeated queries use one exact immutable validation
- **WHEN** repeated foreground queries observe the same active-index, authority, LogicGuard generation, invalidation, and indexed-source identities
- **THEN** the process MAY reuse the prior successful exact validation without reparsing the same immutable LogicGuard meshes
- **AND** any identity or source-content drift MUST bypass that result and run exact validation again without a fallback reader

### Requirement: Indexed retrieval meets the P95 latency budget
The active-index query path SHALL complete with P95 latency below 1.0 second on the declared representative real-corpus benchmark and reference environment. The measurement MUST include route selection, active-status filtering, lexical scoring, confidence and trust reranking, related-card eligibility checks, and result serialization; it MUST exclude index construction but report index age and generation. The benchmark MUST run enough queries to calculate P95, publish raw timing evidence and the corpus digest, and distinguish cold-start, warm-query, rebuild, skipped, and failed measurements. A missing, stale, skipped, or environment-incomparable result MUST NOT be reported as passing.

#### Scenario: Current index satisfies P95 performance
- **WHEN** the versioned benchmark runs the required query set against the representative corpus on the reference environment
- **THEN** the measured query P95 MUST be below 1.0 second and the receipt MUST identify the corpus, query set, index generation, and raw timings

#### Scenario: An alternate scan path is introduced
- **WHEN** runtime code can return results by scanning card or lifecycle files after current index validation fails
- **THEN** the contract and performance gates MUST fail even if that scan is status-safe or meets the latency budget
### Requirement: Active-index rebuild and reactivation require explicit publisher authority
Every active-index rebuild SHALL require an explicit non-default publisher identity. Normal runtime MUST accept only the canonical Sleep lifecycle publisher; the versioned maintenance migration MAY publish only inside its rollbackable upgrade boundary. Retrieval, Dream, organization workflows, tests acting as ordinary consumers, manual helpers, and unknown callers MUST NOT rebuild, reactivate, or clear the durable invalidation marker.

#### Scenario: Canonical Sleep rebuilds a stale index
- **WHEN** the canonical Sleep lifecycle publisher supplies its exact authority and the complete candidate index passes prepublication, source, lifecycle, LogicGuard, activation-token, and superseding-publication checks
- **THEN** the system MUST activate that generation, write its authority receipt, and remove the captured invalidation marker

#### Scenario: Versioned migration rebuilds during upgrade
- **WHEN** the versioned maintenance migration owns the rollbackable upgrade and supplies its exact publisher authority
- **THEN** the system MAY rebuild and activate the current index only as part of the validated migration transaction

#### Scenario: An unauthorized caller requests rebuild
- **WHEN** a caller omits publisher authority or supplies an identity outside the exact allowlist
- **THEN** the rebuild MUST fail before writing the index, activation authority, or invalidation marker state

#### Scenario: Authority changes while rebuild scans
- **WHEN** the captured invalidation token, current LogicGuard authority, lifecycle authority, or active publication changes before activation
- **THEN** activation MUST fail visibly, the current marker MUST remain authoritative, and no alternate reader or publisher MAY complete the request
