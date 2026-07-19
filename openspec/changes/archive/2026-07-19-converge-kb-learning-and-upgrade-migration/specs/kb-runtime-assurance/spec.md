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

Every expensive assurance owner SHALL declare an exact input-component
identity and SHALL produce one immutable terminal-success receipt. An
unchanged owner SHALL consume its exact receipt without execution. A changed
component SHALL invalidate only owners that explicitly consume that component.
An unmapped or ambiguous component MUST block instead of falling back to a
run-all plan.

Toolchain component identity SHALL be derived from portable content rather
than its absolute frozen or live installation path. Each owner receipt SHALL
retain a bounded decision summary plus the exact raw-output hash and byte
count; the currentness authority MUST NOT embed the owner's complete model
trace. Planner source SHALL be part of the top-level currentness identity but
SHALL NOT be an input of every native validation owner. A planner-only change
MUST reissue currentness with zero native owner executions.

The installation currentness command SHALL be read-only and SHALL NOT launch a
migration, model regression, retrieval evaluation, pytest process, assurance
owner, resume command, or other validation subprocess. It SHALL compare
current source-to-installed consumer bytes, automation specifications and
states, the sole current migration and upgrade-attempt authorities, and exact
assurance receipt identities.

If declared owner inputs change while an upgrade assurance campaign is
running, the installer SHALL replan after the campaign and execute only owners
whose inputs changed. It MUST NOT unconditionally repeat migration, retrieval,
or the complete assurance campaign merely because time elapsed.

Current-machine activation SHALL bind one exact maintained-skill inventory
schema. That schema SHALL list all five maintained consumer skills, classify
exactly four as scheduled, and classify only `khaos-brain-update` as
manual-only. Scheduled activation and live readback SHALL operate only on the
four scheduled automation IDs. The manual-only skill MUST remain installed but
MUST NOT be treated as missing scheduled-production evidence or receive an
automation binding.

Activation SHALL replay large lifecycle ledgers in a streaming form that
preserves the exact canonical event digest without materializing the complete
event array. After any automation has been changed to `ACTIVE`, every
exception, including memory exhaustion during the installation check or
receipt self-validation, SHALL restore all four managed automations to
`PAUSED`. An `ACTIVE` state without one current validated activation receipt
MUST NOT be accepted as completion.

Before changing any automation to a safety `PAUSED` state, the installer SHALL
bind all four original statuses and pause intents into the current upgrade
attempt. A failed retry SHALL reuse that exact snapshot rather than treat the
installer-created TOML state as user intent. Outside a recoverable attempt,
the Codex-owned TOML status remains the user-visible intent. An old
recoverable attempt without the snapshot MUST block until an explicit direct
repair snapshot is supplied.

The activation receipt SHALL bind one deterministic installation-currentness
projection. The full history-migration validation MUST pass and remain visible
as runtime evidence, but volatile validation diagnostics MUST NOT participate
in receipt identity. Migration status and its committed receipt identity SHALL
remain inside the deterministic projection, so excluding diagnostics cannot
turn a changed migration authority into a current installation.

#### Scenario: Final readiness is evaluated
- **WHEN** source and tool identities are frozen
- **THEN** one repository regression owner, the current FlowGuard suite, target-native checks, clean installation checks, and the separate author-contract audit all reach terminal results

#### Scenario: A launcher times out
- **WHEN** an execution owner is interrupted or times out
- **THEN** its evidence is non-reusable until the entire descendant process tree is confirmed stopped

#### Scenario: Installation currentness is checked
- **WHEN** an operator runs `install_codex_kb.py --check --json`
- **THEN** the command reads bounded current authorities and exact installed projections
- **AND** it launches zero validation subprocesses and writes no migration, model, retrieval, assurance, or activation state

#### Scenario: One owner input changes
- **WHEN** a component mapped only to retrieval quality changes after a prior successful campaign
- **THEN** the retrieval-quality owner executes once and every unchanged owner receipt is reused
- **AND** no run-all or fallback route is selected

#### Scenario: A frozen toolchain copy matches the live package
- **WHEN** the two package roots differ but their portable content manifests are identical
- **THEN** the owner receipt remains current without execution
- **AND** the bounded currentness authority does not copy the complete native model output

#### Scenario: Only the assurance planner changes
- **WHEN** native owner commands and all declared owner inputs are unchanged
- **THEN** the top-level currentness authority is reissued with zero native owner executions

#### Scenario: Data changes during assurance
- **WHEN** a concurrent writer changes a declared data input while owners are executing
- **THEN** the stable post-campaign plan invalidates only owners that consume that data input
- **AND** restoration remains blocked until those owners pass against the stable identity

#### Scenario: A release tag is pushed
- **WHEN** the tag resolves to the exact successful `main` revision
- **THEN** the tag lane verifies the existing successful main receipt without running the repository suite again
- **AND** a tag without that exact receipt is rejected

#### Scenario: Readiness contains all five maintained skills
- **WHEN** current author and consumer assurance report the four scheduled skills plus `khaos-brain-update`
- **THEN** activation validates the complete five-skill inventory
- **AND** it activates and reads back only the four scheduled automations

#### Scenario: A failed upgrade left an enabled automation safely paused
- **WHEN** the live automation is `PAUSED` and the failed attempt snapshot binds its original state as `ACTIVE` with `user_paused=false`
- **THEN** a successful retry restores it to the declared `ACTIVE` policy
- **AND** no runtime pause is promoted into a user preference

#### Scenario: A user paused an automation outside an upgrade
- **WHEN** no recoverable attempt owns a safety pause and the Codex TOML is `PAUSED`
- **THEN** a later installation preserves that user-visible paused state

#### Scenario: An inventory uses an old or ambiguous shape
- **WHEN** the activation receipt omits the manual-only classification, overlaps the scheduled and manual sets, or does not exhaust the five maintained skills
- **THEN** activation fails without interpreting an older receipt or inferring a fallback classification

#### Scenario: Activation assurance exhausts memory
- **WHEN** a large lifecycle ledger cannot complete the installation check or receipt self-validation
- **THEN** the activation route reports non-success and restores all four scheduled automations to `PAUSED`
- **AND** no unreceipted `ACTIVE` state is accepted or recovered through a second runtime path

#### Scenario: Two healthy installation checks emit different diagnostics
- **WHEN** consecutive checks have the same installed authority, both pass, and only history-validation diagnostics differ
- **THEN** they produce the same installation-currentness identity
- **AND** a changed migration receipt, installed skill projection, automation specification, or upgrade-attempt authority still changes that identity

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
