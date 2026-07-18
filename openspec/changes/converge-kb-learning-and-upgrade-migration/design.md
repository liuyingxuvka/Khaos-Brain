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
