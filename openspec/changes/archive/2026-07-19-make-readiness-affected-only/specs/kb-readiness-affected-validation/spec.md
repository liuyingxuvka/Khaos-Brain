## ADDED Requirements

### Requirement: Final readiness executes only affected owners
The final readiness evaluator SHALL classify every watched source or external
input into exactly one declared component and SHALL bind each validation owner
to the exact components it consumes. A changed component MUST invalidate only
its consuming owners. A campaign-only component MAY consume no validation
owner. An unclassified or multiply classified input MUST block planning
without running any owner.

#### Scenario: One owner input changes
- **WHEN** a component consumed only by one owner changes after a successful campaign
- **THEN** that owner executes once and every other current owner is reused
- **AND** no run-all, fallback, or compatibility route is selected

#### Scenario: New input is unclassified
- **WHEN** a watched file or external input has no unique component classification
- **THEN** readiness stops with an explicit planning error before launching validation

#### Scenario: Only campaign metadata changes
- **WHEN** a documentation or release-metadata component changes and consumes no validation owner
- **THEN** the campaign snapshot changes but every owner with exact current inputs is reused

### Requirement: Every owner consumes only exact immutable success evidence
Every validation owner SHALL produce one immutable receipt bound to its
semantic command, executable content identity, owner component digest,
verifier identity, toolchain and environment identity, and working directory.
Readiness MAY reuse that receipt only when its canonical bytes, stored hash,
proof artifact, terminal result, and all bound inputs still match. Failed,
timed-out, cleanup-unconfirmed, missing, stale, tampered, or out-of-root
evidence MUST NOT be reused.

#### Scenario: Exact owner receipt remains current
- **WHEN** a preceding owner receipt and proof artifact still match every current bound input
- **THEN** readiness emits a bounded current projection bound to the exact source receipt and launches no subprocess for that owner

#### Scenario: Owner output is oversized
- **WHEN** an owner's structured stdout exceeds the current-projection size limit
- **THEN** readiness keeps the complete stdout as a hash-bound proof artifact
- **AND** the receipt contains only a bounded summary, proof reference, and provenance binding

#### Scenario: Prior owner failed
- **WHEN** the preceding receipt records a failure or timeout
- **THEN** readiness executes that owner again and does not mark the preceding evidence current

#### Scenario: Proof artifact changed
- **WHEN** the receipt or its referenced proof artifact is missing, modified, or outside the evidence root
- **THEN** readiness executes that owner again or reports its new terminal failure

### Requirement: Full regression retains stronger proof validation
The repository full-regression owner SHALL use the same affected-only receipt
contract as every other owner and SHALL additionally bind a parseable, nonempty
JUnit inventory. It SHALL retain its exclusive foreground execution lane.

#### Scenario: JUnit proof remains exact
- **WHEN** the full-regression receipt is otherwise current and its JUnit proof reparses to the exact stored nonempty inventory
- **THEN** full regression is reused without execution

#### Scenario: JUnit proof is tampered
- **WHEN** the JUnit bytes or parsed inventory do not match the stored receipt
- **THEN** only the full-regression owner is invalidated by that proof failure

### Requirement: Release closure uses one frozen complete campaign
After implementation and planning artifacts are frozen, release closure SHALL
run one explicit foreground readiness campaign. That campaign SHALL wait for
all required owners to reach terminal success, SHALL confirm the repository
source snapshot stayed stable, and SHALL reject any timeout whose descendant
process cleanup is unconfirmed.

#### Scenario: Frozen campaign succeeds
- **WHEN** every executed or reused owner is current and successful and the pre/post source snapshot matches
- **THEN** readiness emits one complete current manifest suitable for exact-revision release gating

#### Scenario: Source changes during campaign
- **WHEN** the post-campaign repository snapshot differs from the frozen starting snapshot
- **THEN** the campaign is non-current and only owners consuming changed components are eligible for the next execution plan
