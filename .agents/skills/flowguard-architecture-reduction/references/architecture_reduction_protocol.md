# Architecture Reduction Protocol

Use Architecture Reduction when an existing implementation has grown through
repeated branches, handlers, adapters, modules, state phases, UI surfaces, or
validation paths and the desired outcome is smaller code with the same declared
observable behavior.

Architecture Reduction is a model-to-code bridge. It does not refactor code,
parse the whole program, or replace StructureMesh. Agents collect existing
model ownership, code-boundary mapping, observable behavior, candidate
reductions, and proof evidence, then pass that evidence into
`review_architecture_reduction(...)`.

When Existing Model Preflight or Model Similarity supplies a same-intent or
duplicate-boundary handoff, declare the expected candidate ids independently
from the materialized candidates. Every alias, adapter, wrapper, helper,
fallback, facade, and duplicate handler needs a candidate or typed keep/scoped
disposition. Materialize each in-scope similarity relation and code-obligation
id on concrete candidates, target nodes, and target actions; plan-level opaque
ids are not contraction proof. Inventory/source revision changes stale the
review.

## Trigger

Create or update an Architecture Reduction review when any of these are true:

- a staged development task has accumulated multiple adapters, phases, or
  fallback branches around the same behavior;
- an existing-model preflight finds overlapping model or implementation
  ownership and the user wants a simpler architecture;
- a refactor is shrink-oriented, not just a parent/child split;
- ModelMesh finds sibling boundaries that express the same code
  responsibility;
- Model-Test Alignment finds duplicate test evidence caused by duplicate
  implementation paths;
- UI Flow Structure finds repeated UI states, controls, displays, or journeys
  and the implementation should become smaller.

Skip the route for greenfield module planning, model-only cleanup, trivial
edits, and formatting-only work.

## Observable Contract

Before considering code contraction, declare the behavior that must not change:

- source FlowGuard model id;
- source code boundary id;
- public entrypoints;
- observable outputs;
- observable state;
- observable side effects;
- validation boundaries;
- rationale.

This contract is the boundary for "same behavior." Internal proof fields may be
removed or merged only when the declared public behavior is preserved or the
report explicitly downgrades the proof to property-only.

## Model-To-Code Mapping

Map model elements to implementation nodes before recommending contraction:

- FunctionBlock -> function, class, handler, command, component, or module;
- state field -> dataclass field, storage key, UI state, config, or record;
- side effect -> file write, API call, database write, subprocess, UI effect;
- public entrypoint -> CLI, API, export, UI route, command, or plugin surface.

If this mapping is absent, the review should block rather than producing a
code-level recommendation from model-only simplification.

## Candidate Types

Use `ArchitectureReductionCandidate` rows for candidate contractions:

- `merge_handlers`: two or more handlers can become one owner;
- `merge_modules`: modules can share one target module;
- `collapse_adapter`: an adapter only forwards or normalizes without owning
  behavior;
- `remove_branch`: a branch is dead, subsumed, or behavior-equivalent to
  another branch;
- `remove_state_field`: a state field is not part of the observable contract
  and does not affect required properties;
- `merge_state_phase`: two phases are behavior-equivalent at the observable
  boundary;
- `remove_duplicate_validation`: repeated validation paths prove the same
  obligation;
- `keep_public_facade`: internals can shrink but compatibility facade stays;
- `manual_review`: the candidate is intentionally deferred.

## Compatibility Surfaces

When a candidate exists because of an old, alternate, or compatibility-like
surface, add `CompatibilitySurfaceClassification` rows before deciding whether
the candidate is ready. Classify old command aliases, event names, input
shapes, migration branches, old/replaced fields, field aliases, public facades,
pass-through compatibility adapters, retired validation artifacts, and negative
legacy tests.

Use these classifications:

- `current_contract`: still active behavior; remove/collapse is blocked;
- `boundary_adapter`: edge stays but should translate into the current owner
  contract; public surfaces require StructureMesh;
- `negative_legacy_test`: evidence that retired input is rejected; do not
  delete unless replacement rejection evidence is cited;
- `archive_only`: historical evidence only; runtime authority blocks;
- `prune_candidate`: obsolete surface that can contract when proof status is
  ready;
- `evidence_needed`: insufficient evidence; linked candidates are not ready.

This classification is pre-reduction guidance. It does not replace
`LegacyPathDisposition` for post-repair closure when an old executable path
remains reachable.
It also does not replace FieldLifecycleMesh disposition when an old or
compatibility-like field remains reachable.

A retained same-intent facade preserves only an external entry boundary. It
must name the stable intent, active commitment, selected primary path, and owner
contract, with current evidence that it delegates to that path. Independent
business success, primary side effects, terminal mutation, or delegation to a
different same-intent path blocks keep-facade readiness.

## Proof Status

Every candidate must have one proof status:

- `safe_by_equivalence`: preserves declared observable behavior;
- `safe_by_public_facade`: internals can shrink while the public facade stays;
- `property_only_safe`: preserves selected invariants only, not full behavior;
- `needs_conformance_replay`: needs real-code replay before code contraction;
- `risky_keep`: looks duplicate but should stay visible;
- `blocked_by_missing_evidence`: do not contract yet.

Only `safe_by_equivalence` and `safe_by_public_facade` can become ready
contraction candidates. Property-only and replay-needed candidates are useful
diagnostics, not safe deletion proof.
Scoped, risky, or evidence-needed candidates that remain relevant should be
recorded as maintenance obligations with their owner route instead of prose
TODOs.

## Target Actions

Ready candidates produce target architecture actions:

- `merge`;
- `collapse`;
- `remove`;
- `keep_facade`;
- `manual_review`.

Public-entrypoint candidates must route through StructureMesh or equivalent
public parity evidence. Removing observable state or changing observable side
effects without full equivalence proof must block.

## Companion Route Handoff

Architecture Reduction is usually called by or hands off to another route:

- Existing Model Preflight supplies ownership and duplicate-boundary evidence.
- Code Structure Recommendation turns ready target actions into module
  ownership.
- StructureMesh governs the production refactor and public-entrypoint parity.
- DevelopmentProcessFlow governs edit order, evidence freshness, background
  regressions, and done/release claims.
- ModelMesh supplies sibling model overlap and parent/child boundary evidence.
- Model-Test Alignment supplies obligation and test duplication evidence.
- FieldLifecycleMesh supplies old-field ids, replacement field ids, and
  disposition evidence for field compatibility surfaces.
- UI Flow Structure supplies UI state/control/display duplication evidence.
- Layered boundary proof may expose duplicate child ownership; reduce the
  duplicated implementation or route the ownership conflict back to ModelMesh
  before adding more leaf tests.

## Required Hazards

Before trusting the route, make these known-bad variants fail:

- missing existing model grounding;
- missing observable contract;
- missing model-to-code mapping;
- unclassified candidates;
- unclassified compatibility surfaces around old paths or old fields;
- hidden proof status;
- risky candidates silently treated as deletions;
- current contracts treated as obsolete compatibility;
- negative legacy rejection tests deleted without replacement evidence;
- archive-only evidence retaining runtime authority;
- public entrypoint contraction without StructureMesh;
- missing target structure handoff;
- missing companion route triggers;
- direct production-code rewrite by the review route;
- hidden validation or parity gates.
- scoped or risky reduction candidates disappear instead of being preserved as
  maintenance obligations.
- illegal child overlap treated as a testing problem instead of a duplicate
  ownership or architecture-reduction candidate.
- expected same-intent candidate or similarity relation side omitted;
- similarity/code-obligation ids left only in plan metadata;
- retained facade able to succeed without the selected primary path.

## Reporting

For non-trivial reviews, show a compact user-facing diagram with current code
boundary, source model, observable contract, compatibility-surface
classification, reduction candidates, proof status, target structure, and
required next route. The diagram explains the review and does not replace
tests, conformance replay, LegacyPathDisposition, or StructureMesh evidence.
