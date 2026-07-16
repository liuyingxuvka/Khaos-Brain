## ADDED Requirements

### Requirement: Executable FlowGuard model owns the authority-cutover behavior
The repository SHALL contain a current executable FlowGuard child model for the LogicGuard authority cutover, with every FunctionBlock represented as `Input x State -> Set(Output x State)`, exact existing-owner handoffs, and known-bad variants that reject duplicate search/Sleep authority and partial or fallback publication.

#### Scenario: Correct child model is checked
- **WHEN** the model runs with current package and artifact identities
- **THEN** model checks, scenario/conformance obligations, progress/closure checks, and declared known-bad calibrations SHALL produce current terminal receipts

#### Scenario: Parallel controller or partial generation is modeled
- **WHEN** a variant adds a second retrieval/Sleep owner, publishes projection before model authority, lets Dream mutate authority, or retains YAML fallback
- **THEN** the model SHALL reject the variant for the declared invariant or ownership reason

### Requirement: Model, code contracts, fields, and tests are bidirectionally aligned
Every required authority, maintenance, retrieval, UI, privacy, and migration obligation SHALL bind exactly one primary external code owner, behavior-bearing field projections, current source-audit evidence where applicable, and current tests for happy, failure, negative, replay, conflict, and rollback paths.

#### Scenario: Required obligation lacks a code/test binding
- **WHEN** the alignment inventory finds an orphan model obligation, duplicate owner, missing field disposition, stale test, internal-only assertion, or missing known-bad target
- **THEN** completion SHALL be blocked or explicitly scoped and the gap SHALL be routed to its native owner

### Requirement: Validation uses one frozen final execution owner
The final assurance campaign SHALL freeze source, test, model, prompt, skill, package, environment, and inventory identities; run every required child suite under exactly one parent execution owner; and publish immutable terminal child and parent receipts. Consumer checks MUST verify or project those receipts and MUST NOT rerun the same owner command.

#### Scenario: LogicGuard editable-install target drifts after freeze
- **WHEN** the live LogicGuard import target changes after the final campaign freezes its complete package tree
- **THEN** every child SHALL continue from the exact frozen digest, the campaign SHALL reject any import outside that snapshot, and the later normal-runtime install check SHALL fail visibly if the live target is no longer current

#### Scenario: Focused development validation precedes final assurance
- **WHEN** an affected module changes before the frozen snapshot
- **THEN** the agent MAY run the minimum affected focused suite, but those provisional runs SHALL NOT be presented as the final aggregate receipt

#### Scenario: Final launcher times out or is interrupted
- **WHEN** the final owner does not produce a terminal receipt
- **THEN** the result SHALL be non-reusable, every descendant process SHALL be confirmed terminated before another owner starts, and completion SHALL remain blocked

### Requirement: Resource-sensitive validation owners run on exclusive lanes
The aggregate SHALL run repository-wide regression first, ordinary read-oriented children in the bounded parallel pool, LogicGuard performance validation next on an exclusive lane, and real installed scheduled production last on a separate exclusive lane.

#### Scenario: LogicGuard performance validation competes with sibling checks
- **WHEN** representative LogicGuard runtime budgets would be measured while another aggregate child is consuming the same machine resources
- **THEN** the aggregate SHALL defer the performance owner until the ordinary parallel pool is terminal

#### Scenario: Real scheduled production begins
- **WHEN** installed Sleep, Dream, organization, or update execution is selected for aggregate evidence
- **THEN** it SHALL begin only after LogicGuard performance validation and every ordinary child are terminal, with no sibling aggregate owner active

### Requirement: Skills, prompts, UI, installer, and documentation state the same architecture
Managed Sleep, Dream, retrieval, update, organization, and preflight Skills/prompts; SkillGuard current contracts; PROJECT_SPEC; README; UI text; installer manifests; and runbooks SHALL consistently state that LogicGuard models are canonical, YAML is projection, Sleep writes, Dream validates/hands off, retrieval is model-native, and legacy authority is upgrade-only.

#### Scenario: Installed skill tree differs from source authority
- **WHEN** normalized source and installed managed Skills, contracts, or prompt projections differ for a behavior-bearing component
- **THEN** readiness SHALL block until the current SkillGuard-supervised installation projection is refreshed and validated

### Requirement: Performance, privacy, migration, and package evidence are release gates
Broad completion SHALL require current LogicGuard package/API identity, representative scale/performance evidence, public/private isolation tests, direct migration matrix coverage, rollback/resume/concurrency evidence, UI model-view evidence, and zero legacy authority readers/residuals.

#### Scenario: Lifecycle replay count is bounded but one replay is quadratic
- **WHEN** a representative current lifecycle ledger shows duplicate-key work growing faster than event count even though Sleep uses only the declared replay count
- **THEN** performance readiness and the FlowGuard scale obligation SHALL fail until replay membership is indexed and current real-corpus evidence is terminal

#### Scenario: A required release-only child is missing or stale
- **WHEN** the final parent inventory includes a failed, stale, skipped, timed-out, running, progress-only, or absent required child receipt
- **THEN** the aggregate SHALL remain blocked and SHALL expose the child status without converting it to a pass
