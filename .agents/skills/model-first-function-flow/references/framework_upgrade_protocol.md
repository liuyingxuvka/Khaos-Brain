# Framework Upgrade Protocol

Use this protocol only for FlowGuard/LiveFlowGuard framework upgrades,
benchmark/corpus claims, broad capability claims, or live failure triage that
affects the framework itself.

Ordinary project work should not run FlowGuard's internal evidence suites by
default.

## Coverage-First Repair

Before choosing a repair, build or inspect a full finding ledger across:

- invariant/model checks;
- model-quality audit;
- scenario or live-audit evidence;
- progress checks;
- contracts;
- conformance;
- skipped/not-run sections;
- adoption evidence.

Classify each actionable finding as:

- real-system repair;
- check-flow repair;
- model extension;
- explicit out-of-scope boundary.

Do not patch only the first visible failure with a point rule unless the ledger
shows that is the right repair.

## Model Hardening Gate

For complex optimizations, repeated bug repairs, stateful refactors, broad
workflow changes, or model-miss-sensitive work, write:

- a concrete change inventory;
- a risk catalog;
- a risk-to-model coverage matrix.

The matrix maps each important planned change to possible bugs, modeled state
or events, invariants or oracles, representative known-bad hazards, check
evidence, and residual blindspots. A happy-path pass is not enough:
representative bad variants must fail, or the risk must be marked out of scope
with the production-facing check or human review that covers it.

## Internal Evidence Boundaries

Use `docs/framework_upgrade_checks.md` for benchmark/corpus expectations and
framework-only gates. Preserve expected-vs-observed status categories and do
not convert `needs_human_review` or known limitations into ordinary passes.

For large model groups, prefer ledger-based sharding and background execution
with the long-check artifact contract. Pending work is incomplete, not OK.
