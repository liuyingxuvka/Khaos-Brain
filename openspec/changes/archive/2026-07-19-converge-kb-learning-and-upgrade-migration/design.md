# Design

## Boundary

The maintainer computer has two layers:

1. Author maintenance: SkillGuard checks one source skill at a time, proving
   that its declared promise is complete, deep, and independently testable.
2. Consumer product: the installed skill runs only its own prompt, entrypoint,
   model, tests, and native receipt.

The installation compiler creates a clean consumer projection. It excludes
`.skillguard`, author contracts, author receipts, router dependencies, test
fixtures, and source-only notes. The active installed tree is compared against
that projection, not against the full maintainer source tree.

## Independent maintenance units

The five units are:

- `kb-sleep-maintenance`
- `kb-dream-pass`
- `kb-organization-contribute`
- `kb-organization-maintenance`
- `khaos-brain-update`

Each unit has one member and unique obligations and test nodes. Shared
infrastructure may be called by several units, but infrastructure tests do not
become shared completion evidence. If two units claim the same semantic duty
or test node, alignment blocks until ownership is clarified or the test is
split.

## Assurance ownership

- FlowGuard owns observable behavior, state, transitions, invariants, progress,
  loops, and counterexamples.
- LogicGuard owns the reasoning-model product dependency and its native
  authority checks.
- Each maintenance unit owns its domain result and immutable native receipt.
- The installer owns transactional clean projection, exact manifests, pause
  preservation, activation, rollback, and currentness.
- SkillGuard owns only source-side contract compilation and depth audit.
- The final readiness evaluator aggregates current owners without turning one
  unit's receipt into another unit's proof.

## Update route

The manual update is one native transaction:

`explicit request -> topology/safety gate -> snapshot -> pause -> fast-forward -> migration -> clean install -> deferred health -> exact restore -> final health -> CURRENT -> snapshot cleanup -> native receipt`

Any failure remains failed or recoverably paused. There is no intermediate
SkillGuard authorization, no composed finalization request, and no separate
activation receipt.

## External boundaries

Official OpenSpec remains an external toolchain and is not enrolled as a
SkillGuard-maintained skill. Third-party skill overlap on another computer is
outside this repository's guarantee.

## Validation

During development, run only affected target checks. After source and tool
identities are stable, run one foreground full regression and one final
FlowGuard/readiness campaign. A timeout or interruption invalidates that
owner's evidence until all descendant processes are confirmed stopped.

### Installation and assurance execution ownership

The product has one validation graph, not an ordered list of fallback
commands. Every expensive owner declares:

- its stable owner id and exact command semantics;
- the exact source, data, toolchain, environment, and installed-projection
  components it consumes;
- one immutable terminal-success receipt keyed by those inputs.

Toolchain identity is content-bound and location-independent: a frozen
validation copy and the live package have the same identity when their
portable manifests match. Owner receipts retain a bounded decision summary
plus the exact raw-output hash and byte count; they do not embed complete
model traces into the currentness authority. The planner source is bound by
the top-level currentness authority but is not a native owner input, so a
planner-only change reissues that authority with zero owner executions.

The assurance planner compares current input identities with the preceding
receipts. Exact matches are consumed read-only. A changed component
invalidates only owners with an explicit edge to that component. An unmapped
or multiply owned component blocks planning rather than selecting a run-all
route.

The normal `install_codex_kb.py --check --json` path is a bounded read-only
currentness projection. It checks source-to-installed consumer bytes,
automation specifications and activation state, the sole current migration
authority, the sole current upgrade-attempt authority, and the immutable
assurance receipts. It does not run migration, FlowGuard, LogicGuard,
retrieval evaluation, pytest, or any subprocess validation owner.

During an actual upgrade, automations remain paused while affected assurance
owners run. The planner snapshots their declared inputs before execution and
checks them again afterward. If a writer admitted data during the campaign,
only the owner inputs whose identities changed are replanned. Unchanged owner
receipts remain reusable. Restoration is permitted only when a stable plan has
no missing, stale, failed, ambiguous, or cleanup-unconfirmed owner.

Before any safety pause, the installer persists the exact four-automation
runtime status and pause intent in the current upgrade attempt. A failed retry
must consume that attempt-bound snapshot; it cannot reinterpret the
installer-created `PAUSED` TOMLs as a new user choice. Outside recovery, the
Codex-owned TOML status is the user-visible intent. An old recoverable attempt
without the snapshot blocks until AI supplies one explicit direct-repair
snapshot.

### CI and release ownership

Pull-request validation and exact-main validation are distinct events, but a
revision executes the repository suite only once in its applicable lane.
Ordinary feature-branch pushes do not duplicate a pull-request run. After the
exact main revision succeeds, a tag workflow verifies that the tag and
`origin/main` both resolve to that revision and that its main validation
receipt is successful. The tag workflow does not execute the repository suite
again.
