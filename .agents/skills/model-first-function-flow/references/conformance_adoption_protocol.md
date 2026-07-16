# Conformance And Adoption Protocol

Use this protocol when FlowGuard evidence must support production confidence,
install readiness, local sync, shadow workspace sync, or release preparation.

## Conformance Replay Trigger

Conformance replay should be the default next check when any of these are true:

- the invariant depends on a state field with multiple production write points;
- production code has database writes or durable side effects;
- runtime, cleanup, repair, or finalizer paths can update the same state;
- the result will be reported as production confidence rather than model-level
  confidence;
- adapter projection is required to compare real state with abstract state.

If replay is skipped in one of these cases, record why and report model-level
confidence only. A skipped replay is not a pass.

## Install And Sync Evidence

Before reporting a FlowGuard Skill or release as ready, verify the relevant
runtime copies:

- source checkout import;
- editable/local install metadata;
- installed Codex Skill files;
- shadow workspace source sets when a local workspace mirrors FlowGuard;
- Git version and GitHub version only when the user has authorized publication.

For shadow workspaces, sync whole source sets instead of cherry-picking only a
few files. At minimum verify imports and focused tests from the shadow root.

## Adoption Evidence

For real project usage, record:

- trigger reason;
- modeled workflow or risk;
- model files;
- commands run and pass/fail status;
- findings and counterexamples;
- skipped or deferred steps with reasons;
- friction points;
- next actions.

Preferred local records:

- `.flowguard/adoption_log.jsonl`;
- `docs/flowguard_adoption_log.md`.

The CLI helpers `adoption-start` and `adoption-finish` can create structured
entries, but logging does not replace executable validation.

## Release Sync

When GitHub publication is authorized, version metadata, changelog, README,
tag, pushed branch, and GitHub release should agree. If the user asks to pause
GitHub publication, stop before tag, push, and release creation while keeping
local validation and sync evidence complete.
