## Context

The readiness evaluator has two distinct responsibilities: prove that one
campaign observed a stable repository snapshot, and decide whether each
validation owner needs to execute. It currently uses the same repository-wide
digest for both responsibilities. Only `full_regression` has a receipt reader;
the remaining owners execute unconditionally.

The repository already requires affected-only validation, one explicit
execution owner, immutable receipts, bounded evidence, foreground final
validation, and no fallback or compatibility routes.

## Goals / Non-Goals

**Goals:**

- Separate campaign stability from owner currentness.
- Bind every owner to exact declared input components.
- Reuse exact immutable terminal-success receipts for every owner.
- Keep JUnit coverage validation as an additional full-regression proof.
- Block unmapped or ambiguous inputs.
- Preserve one exclusive full-regression lane and the resource-sensitive
  LogicGuard lane.

**Non-Goals:**

- Reusing failed or timed-out evidence.
- Inferring dependencies from a previous receipt.
- Adding a legacy receipt reader, alias authority, run-all fallback, scheduled
  task, or unattended retry.
- Sharing one semantic owner's receipt with a different owner.

## Decisions

### Closed component inventory

Every watched repository file receives one semantic component classification.
Components declare their consuming owners. Documentation and release metadata
are explicitly campaign-only and consume no validation owner. A file with no
classification or more than one classification blocks planning.

This is preferred over a best-effort import scan because dynamic imports,
subprocess commands, templates, and external Codex state are not fully
discoverable from Python syntax. The explicit map is reviewable and fails
closed when a new path is introduced.

### Owner-scoped identities

An owner identity binds:

- semantic command and executable content identity;
- exact component digest;
- verifier implementation digest;
- environment and toolchain content identities;
- repository working directory.

The repository-wide snapshot remains only a before/after campaign-stability
gate. It no longer invalidates every owner.

### General receipt consumption

One general receipt reader validates canonical receipt bytes, hash, proof
artifact location and hash, owner name, exact identity, terminal success,
timeout state, command semantics, environment, and working directory.
`full_regression` additionally reparses its JUnit file and requires a nonempty
matching inventory. A failure at any check makes only that owner executable.

The current release performs one direct identity cutover. Old global-digest
receipts are not interpreted through a compatibility bridge. The first frozen
campaign under the new identity executes any owner lacking a current receipt;
subsequent campaigns reuse unaffected owners.

### Execution ordering

The full-regression owner is decided first and retains an exclusive lane. Only
owners without reusable receipts enter the ordinary parallel pool. The
LogicGuard runtime benchmark remains exclusive and starts after ordinary
owners finish. Reused owners never launch a subprocess.

## Risks / Trade-offs

- **A component map can become stale** → New or multiply classified watched
  files block with explicit diagnostics; tests cover the closed inventory.
- **A broad component invalidates more than necessary** → Components are split
  by actual owner responsibility and can be narrowed through reviewed changes,
  never by fallback inference.
- **External installed state may drift** → Owners that inspect Codex state bind
  a deterministic external-state snapshot as an owner component.
- **A receipt projection could become unbounded** → Full stdout remains an
  immutable proof artifact; the current receipt embeds structured JSON only
  below a fixed size limit and otherwise preserves its hash, tail, proof
  reference, and provenance ticket.

## Migration Plan

1. Introduce the closed component planner and tests.
2. Replace full-regression-only reuse with the general receipt reader.
3. Run focused tests and FlowGuard conformance checks.
4. Run one foreground final readiness campaign under the new identities.
5. Archive this OpenSpec change, then reissue a zero-execution current
   projection for the archive-only source change.
6. Publish only after the exact main revision is green.

Rollback means reverting the unreleased source revision. No runtime
compatibility path is retained.
