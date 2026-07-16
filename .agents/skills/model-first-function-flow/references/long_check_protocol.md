# Long Check Observability Protocol

Use this protocol for long-running FlowGuard checks, model regressions, test
suites, simulations, or release validations that should run in the background.

## Artifact Contract

Default to a project-local log root at `tmp/flowguard_background/` unless the
repository defines a stricter convention. Use a stable command base name and
write:

- `<name>.out.txt` for stdout;
- `<name>.err.txt` for stderr and progress;
- `<name>.combined.txt` for a human-readable merged stream;
- `<name>.exit.txt` for the final exit code;
- `<name>.meta.json` for command, start/end time, status, and proof-reuse
  metadata.

## Completion Evidence

Before reporting a long check as complete, inspect the actual artifacts and
report:

- log root;
- stdout/stderr/combined paths;
- exit code;
- latest update time;
- completion status;
- whether the result was newly executed or reused from a valid proof.

A path-only report, an in-progress log, or a missing exit artifact is not
completion evidence.

Do not treat a background long-running check as pass evidence just because it
has started, is still writing progress, or has a recent timestamp. Until the
final artifacts above exist and match the current risk boundary, other routes
may cite the run only as in-progress liveness.

## Progress Is Not Pass/Fail

Formal `run_model_first_checks(...)` runs inherit bounded finite-runner progress
on `stderr`. Treat progress as liveness/observability only. It does not change
pass/fail semantics.

Distinguish inherited formal-runner progress from project-specific or legacy custom
runners. A custom runner that bypasses the formal path may only emit a final
report until it implements its own progress signal. Do not describe final report
sections as live progress; final summaries become completion evidence only
after the exit and log artifacts exist.

## Proof Reuse

If the exact same abstract model, scenarios, oracle, invariants, risk boundary,
and task revision already passed and none of those inputs changed, it is
acceptable to reuse that result instead of rerunning only for ceremony. Mention
reuse briefly and keep stale evidence visible.
For tests, reuse only a completed result with final exit/status/result artifacts
plus a current `TestResultReuseTicket` and `ProofArtifactRef`. Progress output
is liveness only, not reusable pass evidence.
