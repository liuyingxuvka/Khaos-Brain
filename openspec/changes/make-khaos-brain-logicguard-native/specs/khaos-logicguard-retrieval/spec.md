## ADDED Requirements

### Requirement: Foreground retrieval uses only a current model-bound active index
Routine retrieval SHALL load a compact current active-index authority whose every record contains a validated exact card/model/node/mesh binding. It MUST fail visibly when the index or bound authority is unavailable, stale, malformed, or scope-incompatible and MUST NOT scan YAML or use `related_cards` as a fallback.

#### Scenario: Current indexed query
- **WHEN** a query matches one or more current eligible model-bound records
- **THEN** retrieval SHALL rank projections and return exact model/node/revision/mesh identifiers plus a bounded current neighborhood receipt

#### Scenario: Missing current model authority
- **WHEN** the index exists but a bound exact model or mesh revision cannot be loaded or verified
- **THEN** retrieval SHALL return a visible unavailable/failure result, exclude the affected record, and SHALL NOT reinterpret YAML as authority

### Requirement: Exact card or node lookup expands through the model
An exact card id, model id, or qualified node id lookup SHALL identify the bound root and materialize a deterministic bounded neighborhood containing relevant support, warrant, assumption, rebuttal, qualifier, limitation, membership, and cross-model relations from the exact mesh revision.

#### Scenario: Exact card id is requested
- **WHEN** the caller requests an indexed card id
- **THEN** retrieval SHALL return the card projection and its exact root-centered model neighborhood within declared hop/node/edge budgets

#### Scenario: Neighborhood exceeds the budget
- **WHEN** the reachable exact graph is larger than the configured budget
- **THEN** retrieval SHALL return a deterministic truncated neighborhood with excluded/frontier diagnostics and SHALL NOT silently traverse an unbounded graph

### Requirement: Retrieval ranking remains explainable and lifecycle-safe
Ranking SHALL combine the existing route/status/confidence policy with model-native signals such as exact node match, role, distance, support/opposition state, importance, and scope, while rejected, merged, superseded, retired, parked, malformed, or stale-bound records have zero exposure.

#### Scenario: Related node is surfaced
- **WHEN** a non-root node is included because it supports, contradicts, qualifies, or shares a higher-order model with the exact result
- **THEN** the receipt SHALL name the relation, distance, exact qualified node, and score contribution

#### Scenario: Ineligible related model exists
- **WHEN** a mesh neighbor belongs to an ineligible lifecycle entry or unauthorized scope
- **THEN** it SHALL be excluded before ranking and SHALL contribute neither text nor score to the returned result

### Requirement: Desktop detail is a graph-first projection of one current authority
The desktop UI SHALL show the selected card together with one recommended bounded model graph and on-demand details for revision, support, warrant, assumptions, rebuttals, limitations, memberships, and open gaps. UI text SHALL be localized display projection; machine ids and receipts remain canonical.

#### Scenario: User opens a model-bound card
- **WHEN** the selected card and exact mesh revision validate
- **THEN** the UI SHALL render its familiar prediction summary and the same exact bounded graph returned by the retrieval view model

#### Scenario: Binding becomes stale while viewing
- **WHEN** the selected projection or mesh binding is no longer current
- **THEN** the UI SHALL show a visible stale/unavailable state and SHALL NOT retain a misleading graph from a different revision

### Requirement: Model-native retrieval meets bounded performance budgets
The system SHALL define and verify budgets for active-index load, exact binding verification, exact-card lookup, and bounded neighborhood materialization on representative current-card and scale fixtures.

#### Scenario: Representative local knowledge base
- **WHEN** the performance suite runs on the declared representative fixture and environment
- **THEN** P95 retrieval and neighborhood materialization SHALL remain within the frozen budget and memory cap recorded by the verification contract

#### Scenario: Multiple exact nodes are read from one generation
- **WHEN** a process reads different model-bound cards from the same authority generation and privacy scope
- **THEN** it MAY reuse one pinned read-only model/mesh store session keyed by the exact authority pointer digest, and a changed digest SHALL open a new session before another context is returned
