## ADDED Requirements

### Requirement: Maintained skills are independent consumer products
Each maintained skill SHALL own its domain promise, native entrypoint, runtime
receipt, positive depth test, intentionally shallow rejection test, and
terminal decision. A consumer installation MUST NOT contain `.skillguard`,
invoke SkillGuard, import SkillGuard, read a SkillGuard receipt, depend on a
SkillGuard router, or write SkillGuard state into an ordinary project.

#### Scenario: A maintained skill is installed on another computer
- **WHEN** the installer projects a maintained source skill into a Codex home
- **THEN** the installed tree contains only the skill's consumer files and the skill can complete its native route without SkillGuard

#### Scenario: An ordinary project uses a maintained skill
- **WHEN** the installed skill performs its domain work
- **THEN** neither the project root nor the skill runtime receives a `.skillguard` directory or other SkillGuard-owned state

### Requirement: SkillGuard is author-side maintenance supervision
The maintainer repository MAY keep one current SkillGuard contract source,
compiled contract, and check manifest inside each maintained skill's source
tree. SkillGuard SHALL use those files only to prove that the skill's own
declared promise is complete, deep, and independently testable before
distribution. This author-side proof MUST NOT become a consumer dependency or
installed authority.

#### Scenario: A maintainer changes one skill
- **WHEN** the skill's promise, prompt, implementation, model, or declared tests change
- **THEN** only that skill's author-side contract and its own affected evidence are invalidated and rechecked

#### Scenario: A third-party computer has overlapping skills
- **WHEN** an independently distributed skill overlaps with an unrelated third-party skill
- **THEN** the overlap is outside this repository's guarantee and no cross-skill receipt-sharing mechanism is introduced

### Requirement: Maintenance units and test evidence are disjoint
Every maintained skill SHALL be its own maintenance unit with exactly one
member. Two maintained skills MUST NOT claim the same semantic obligation or
the same test node. A discovered overlap SHALL be treated as a boundary defect
to resolve by changing ownership or splitting the test, never as permission to
share, consume, or project another skill's receipt.

#### Scenario: Two skills claim one test node
- **WHEN** the model-test alignment inventory finds the same node under two maintenance units
- **THEN** assurance fails with a cross-unit ownership conflict

#### Scenario: Tests happen to execute the same low-level helper
- **WHEN** two independent domain tests transitively exercise shared infrastructure
- **THEN** each skill still owns a distinct test node and result; neither test receipt satisfies the other skill

### Requirement: FlowGuard and target-native checks own consumer assurance
FlowGuard SHALL own behavior, state, transition, invariant, progress, loop, and
counterexample modeling. Each target skill SHALL own its native runtime checks.
The installer SHALL own clean consumer projection and transactional activation.
The final readiness evaluator SHALL aggregate these current owners without
rerunning one skill's test as another skill's proof.

#### Scenario: Final readiness is evaluated
- **WHEN** source and tool identities are frozen
- **THEN** one repository regression owner, the current FlowGuard suite, target-native checks, clean installation checks, and the separate author-contract audit all reach terminal results

#### Scenario: A launcher times out
- **WHEN** an execution owner is interrupted or times out
- **THEN** its evidence is non-reusable until the entire descendant process tree is confirmed stopped

### Requirement: Manual update closes in one native route
The explicit conversational update skill SHALL perform authorization, safe
fast-forward, migration, clean consumer installation, exact automation-state
restoration, final installed-health readback, CURRENT state, snapshot cleanup,
and its own immutable native receipt in one target-owned route. It MUST NOT
pause for an intermediate SkillGuard authorization or a second activation
receipt.

#### Scenario: Explicit update succeeds
- **WHEN** the user explicitly requested the update and every native gate passes
- **THEN** the skill restores the exact captured automation state, confirms installed health, marks CURRENT, removes its snapshot, and validates its own receipt

#### Scenario: A native gate fails
- **WHEN** update, migration, installation, restoration, or final readback fails
- **THEN** the route remains failed or recoverably paused and no external guard converts it to success

### Requirement: Official OpenSpec remains external
Official OpenSpec skills and commands SHALL remain externally maintained and
outside SkillGuard coverage. Repository OpenSpec artifacts MAY specify and
verify the product change, but the official OpenSpec installation MUST NOT
receive repository `.skillguard` authority or be repackaged as a maintained
SkillGuard target.

#### Scenario: OpenSpec validates this change
- **WHEN** strict OpenSpec validation runs
- **THEN** it reads repository proposal, design, specification, task, and verification artifacts through the official OpenSpec toolchain without SkillGuard enrollment
