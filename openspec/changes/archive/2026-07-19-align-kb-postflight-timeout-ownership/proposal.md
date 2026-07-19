## Why

The active-task KB postflight may legitimately wait up to 120 seconds for the sole lifecycle writer lock, while its terminal budget and common launcher timeout stop near 30 seconds. That mismatch can interrupt a healthy owner, produce `timeout_unknown`, and tempt a duplicate attempt even though the one-path write contract is functioning correctly.

## What Changes

- Align the postflight terminal budget with the existing writer-lock timeout and explicit completion headroom.
- Require callers to allow a larger outer launcher timeout than the complete internal terminal budget.
- Preserve one stable event id and one writer owner across timeout inspection; do not start a second writer, alternate route, fallback, or compatibility path.
- Extend the existing FlowGuard model and focused regression tests to reject budget ordering that cannot contain the lock wait.
- Install the clarified timeout ownership rules into the global predictive-KB skill.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `kb-history-debt-migration`: Strengthen the active-task postflight requirement so its lock, terminal, and launcher time budgets are ordered and a launcher interruption cannot authorize duplicate execution.

## Impact

Affected surfaces are the postflight feedback runtime, its existing FlowGuard terminal model, the predictive-KB skill templates and local author skill, focused lifecycle/CLI tests, installation currentness checks, and v0.6.7 release notes. Search, Sleep, Dream, retrieval, ResearchGuard integration, and lifecycle ownership remain unchanged.
