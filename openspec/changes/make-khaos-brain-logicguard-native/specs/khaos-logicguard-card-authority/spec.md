## ADDED Requirements

### Requirement: Every current card is an exact LogicGuard model projection
The system SHALL treat a card as current knowledge only when it binds to one exact canonical LogicGuard model revision, ArgumentBlock, and root claim node, and the card's projection digest matches a deterministic projection of that exact authority.

#### Scenario: Valid exact binding
- **WHEN** a card names a current projection schema, model id, revision id, block id, root node id, scope, and projection digest that match the scoped model store
- **THEN** the system may admit the card to lifecycle-eligible indexing and SHALL return the exact binding in retrieval receipts

#### Scenario: Missing or mismatched authority
- **WHEN** the model, exact revision, block, root node, scope, or recomputed projection digest is missing or mismatched
- **THEN** the system SHALL visibly reject the card from the active index and SHALL NOT substitute a model head, YAML semantics, alias, or fallback reader

### Requirement: Predictive experience is represented as an ArgumentBlock
Each canonical predictive unit MUST contain one root ArgumentBlock whose root claim represents the predicted outcome and whose declared members represent the available context/premise, action/method, warrant, evidence/provenance, assumption, rebuttal, qualifier, and limitation roles. Missing roles MUST remain explicit diagnostics or gaps and MUST NOT be fabricated.

#### Scenario: Rich supported experience
- **WHEN** an observation provides context, an action, a result, a licensing reason, and independent evidence
- **THEN** the model SHALL represent those meanings with typed nodes and edges inside the ArgumentBlock and SHALL preserve typed provenance on evidentiary nodes

#### Scenario: Sparse legacy experience
- **WHEN** a legacy card has only `if`, `action`, `predict`, and `use` text with no grounded evidence or warrant
- **THEN** migration SHALL create only licensed context/method/claim content, record missing support roles as gaps, and SHALL NOT relabel AI-authored text as independent evidence

### Requirement: Projection fields have no independent semantic authority
The human-readable `if`, `action`, `predict`, `use`, and derived neighbor fields SHALL be generated from the bound model revision. Normal runtime MUST NOT accept edits to those fields as a canonical knowledge change or use `related_cards` as an independent relationship source.

#### Scenario: Projection text is edited without a model revision
- **WHEN** YAML display text changes while the bound model revision and projection digest remain unchanged
- **THEN** projection validation SHALL fail and retrieval SHALL exclude the card until Sleep commits a canonical model revision and regenerates the projection

#### Scenario: Legacy related card list survives in input
- **WHEN** a normal-runtime card contains `related_cards` values that are absent from its exact mesh neighborhood
- **THEN** the system SHALL ignore them as authority, report a projection mismatch or retired-field residual, and SHALL NOT create graph edges from them

### Requirement: Knowledge publication is model first and atomic
Every knowledge-changing operation SHALL commit and validate canonical model and affected mesh revisions before it publishes card projections and the active index. A partial or conflicting operation MUST leave the prior complete generation authoritative.

#### Scenario: Successful model-first publication
- **WHEN** Sleep commits the expected model and mesh revisions and all projections validate
- **THEN** the system SHALL publish those projections and one active-index generation whose receipt binds every exact revision and digest

#### Scenario: Compare-and-swap conflict
- **WHEN** a model or mesh head differs from the expected revision during commit
- **THEN** the system SHALL publish no new projection or index generation, preserve the concurrent authority, and return a retryable conflict with no silent overwrite

### Requirement: Canonical authority is partitioned by privacy scope
Public, private, and candidate model/mesh authority SHALL use separate scoped stores. A scoped mesh MUST NOT contain a model, node, edge, provenance value, path, or digest from another scope, and public projections MUST be free of private material.

#### Scenario: Public graph requests a private node
- **WHEN** a public mesh proposal or public projection references a private model or node
- **THEN** validation SHALL block the commit and SHALL identify the cross-scope reference without serializing private content into public evidence

#### Scenario: Authorized local multi-scope search
- **WHEN** a local caller is authorized to search public and private scopes
- **THEN** the retrieval facade SHALL query each scoped authority separately and merge display results without persisting a mixed-scope canonical mesh
