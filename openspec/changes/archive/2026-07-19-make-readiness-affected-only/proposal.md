## Why

The final Khaos Brain readiness evaluator currently binds every owner to one
repository-wide source digest and reuses only the full-regression receipt.
Consequently, a one-file fix causes unrelated, already-successful owners to
rerun, wasting time and violating the existing affected-only assurance
contract.

## What Changes

- Give every readiness owner an explicit, closed set of source and external
  input components.
- Generalize immutable terminal-success receipt reuse from full regression to
  every owner.
- Reject missing, failed, timed-out, tampered, stale, or out-of-root evidence.
- Block on an unmapped or ambiguous watched input instead of selecting a
  run-all or compatibility route.
- Preserve full-regression JUnit inventory validation while using the same
  owner-scoped reuse contract.
- Keep exactly one complete foreground readiness campaign for a frozen release
  snapshot; later changes execute only affected owners.

## Capabilities

### New Capabilities

- `kb-readiness-affected-validation`: Define closed owner-input mapping,
  immutable receipt reuse, proof validation, and affected-only execution for
  the final readiness evaluator.

### Modified Capabilities

None.

## Impact

The change affects `scripts/check_chaos_brain_readiness.py`, its focused tests,
the Khaos Brain convergence FlowGuard model, and the runtime-assurance
specification. It does not add a fallback, compatibility reader, alternate
authority, scheduled validation owner, or consumer dependency.
