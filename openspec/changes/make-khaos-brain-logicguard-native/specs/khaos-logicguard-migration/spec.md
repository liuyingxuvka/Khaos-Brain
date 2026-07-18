## ADDED Requirements

### Requirement: Legacy card authority is consumed only by a versioned direct migration
The upgrade owner SHALL be the only code allowed to interpret managed pre-model YAML fields as semantic input. It SHALL migrate them directly to the current canonical LogicGuard model/mesh and projection schemas and SHALL leave no normal-runtime legacy reader, dual writer, alias, alternate launcher/model, or fallback path.

#### Scenario: Old machine upgrade
- **WHEN** the installer detects managed cards without current exact model bindings
- **THEN** it SHALL run the versioned migration before normal runtime, create canonical models/meshes, rewrite current projections, prove zero residuals, and only then allow retained automations to resume according to preserved pause intent

#### Scenario: Normal runtime receives an old card
- **WHEN** retrieval, Sleep, Dream, UI, or organization processing encounters a pre-model card after migration authority is current
- **THEN** the route SHALL fail visibly and SHALL NOT invoke migration logic or a compatibility reader

### Requirement: Migration is complete, deterministic, and conservative
For every managed card, migration SHALL record the source digest, scope, lifecycle state, deterministic model id, exact committed revision, block/root ids, explicit gaps, mesh disposition, projection digest, and final active-index disposition. It MUST NOT invent evidence or silently discard an eligible card.

#### Scenario: Sparse card lacks support
- **WHEN** a legacy eligible card contains predictive prose but no verifiable evidence or warrant
- **THEN** migration SHALL bind the prose to a conservative model, record missing roles, retain its lifecycle trust boundary, and SHALL NOT promote it from migration output alone

#### Scenario: Legacy relationship cannot be grounded
- **WHEN** `related_cards` proposes a relation without valid targets or admissible provenance
- **THEN** migration SHALL record a typed unresolved-relation disposition and SHALL NOT commit a canonical cross-model edge

### Requirement: Migration is atomic, resumable, idempotent, and rollbackable
Migration SHALL acquire the declared managed-writer boundary, preserve unrelated/concurrent files, checkpoint immutable source and toolchain identities, use idempotent model/mesh transaction keys, and either publish one complete current generation or restore the prior authority generation.

#### Scenario: Migration is interrupted after model commits
- **WHEN** canonical revisions exist but projections/index were not committed
- **THEN** resume SHALL reuse matching immutable revisions, continue from the journal without duplicate semantic revisions, and keep normal runtime blocked until a complete generation commits

#### Scenario: Concurrent managed card changes
- **WHEN** a source digest changes after planning or a writer appears inside the migration boundary
- **THEN** migration SHALL preserve the change, invalidate the affected plan, and either replan from captured evidence or roll back; it SHALL NOT overwrite the concurrent content

#### Scenario: Projection or privacy validation fails
- **WHEN** any migrated projection, exact binding, scope audit, zero-residual check, or active-index rebuild fails
- **THEN** migration SHALL restore the prior complete generation, record the blocker, and keep all four retained automations paused

### Requirement: Installer and install check enforce current model authority
Every fresh install and upgrade SHALL run the current model-authority migration before readiness checks. The install check SHALL expose structured signals for LogicGuard package identity, scoped store readiness, model-bound card coverage, projection parity, mesh/index validity, zero legacy authority residuals, skill/install parity, and final strong-session readiness.

#### Scenario: Fresh clone with bootstrap card projections
- **WHEN** the installer runs on a repository that has no local current model store
- **THEN** it SHALL create the current stores through the same migration owner, validate them, and SHALL NOT rely on YAML as normal runtime authority after installation

#### Scenario: LogicGuard package is missing or stale
- **WHEN** the current required LogicGuard public API or package identity cannot be verified
- **THEN** installation SHALL fail visibly before card migration or automation resume and SHALL NOT install a substitute mini framework

#### Scenario: LogicGuard package identity changes during a long upgrade
- **WHEN** the current LogicGuard package passes preflight and is then replaced, redirected, or edited after its immutable snapshot is committed
- **THEN** every migration and readiness child SHALL consume only the frozen package digest, final live mismatch SHALL keep all four automations paused, and no compatibility or fallback reader SHALL be introduced
