# Local Model Mesh Protocol

Use this reference when a project already has several FlowGuard models, or when
a model miss suggests that local models are individually deep but disconnected.

## Trigger

Create or update a local model mesh when any of these are true:

- the project has three or more local FlowGuard models;
- a single model is too large to review comfortably, such as an estimated or
  observed state count above the configured threshold, defaulting to `10_000`;
- a budgeted model group remains incomplete with pending states;
- `review_auto_mesh_splits(...)` reports a required model split for oversized,
  incomplete, broad, separable, or progress-only direct model evidence;
- a model contains several unrelated functional areas that could be child
  model boundaries;
- a change can affect more than one existing model boundary;
- a green model result is being reused for a changed workflow, changed source,
  changed prompt, changed route, or changed runtime evidence;
- a runtime/test/replay/manual validation failure appears after a FlowGuard
  pass and the old model did not make the bug class visible;
- live state, result files, adoption logs, or conformance evidence disagree.

When DevelopmentProcessFlow classifies a failed validation as
`model_too_thick`, `oversized model evidence`, or parent model evidence that
cannot be trusted as one direct child, this protocol owns the handoff. Treat the
thick model as compatibility or source evidence until a target child split is
derived and the parent consumes current child evidence ids. Do not let a later
green run of the original thick model by itself close the parent confidence
gap.

Do not merge every child model into one giant state graph. The mesh is a
model-of-models: it treats child models as contract-bearing evidence sources
with inputs, outputs, state ownership, evidence tier, freshness, and known
blindspots.

When a child model is repaired after a model miss, a child-local green result is
not parent confidence by itself. The parent mesh must reattach the child through
the input, output, state, side-effect, outgoing-contract, and evidence-id
handoff that the parent flow consumes.

For final confidence claims, provide the consumed child evidence ids and stale,
skipped, or release-only gaps to the Risk Evidence Ledger. ModelMesh proves the
parent/child relationship; the ledger proves whether that evidence supports a
specific user-facing risk row.

Keep the current bug instance separate from bug-class responsibility.
Model-Miss Review owns classification of the observed instance and the
same-class generalized case. ModelMesh owns whether the repaired child boundary
still fits the parent and any affected siblings. A patched instance plus a
green child run is not mesh confidence until that class responsibility is
represented or explicitly out of scope and the parent/affected sibling handoffs
have been reviewed.

For hierarchical projects, treat each parent/child boundary as a partition map:
the parent is the total map, child models are region maps, and the mesh checks
whether those regions cover the parent space without unsafe overlap. A child can
become a parent when it grows large enough to split again, so mesh review can
apply at several levels.

Layered boundary proof is the parent-confidence bridge across ModelMesh,
Model-Test Alignment, and TestMesh. A parent model is not fully green merely
because each child has some evidence. The proof chain must show four tables:
parent coverage, child disjointness, child reattachment through current
evidence ids, and leaf boundary matrices. If a child is a leaf and owns a real
finite code boundary, the leaf must be small enough to prove every declared
`Input x State -> Set(Output x State)` cell, or it must split again or remain
scoped/blocked.

If the child leaf emits runtime path evidence, the child record should list
current runtime path evidence ids and the parent reattachment should list the
ids it consumed. Parent confidence is stale when it only consumes the child
model evidence id but not the current runtime path evidence for the real-code
node path.

Before a parent/child model layout supports mesh confidence, derive the target
child model structure from a FlowGuard source model or model-of-models. The
target split derivation should name the source model, target child model ids,
covered parent partition items, state ownership fields, side-effect ownership
fields, and the rationale for the split. A supplied partition map is review
input, not authority by itself.

## Inventory

Before trusting existing models, write a compact inventory with grouped fields:

| Group | What to capture |
| --- | --- |
| `model` | Stable model id plus model, runner, and result paths. |
| `risk_boundary` | Bug class or workflow protected by the model. |
| `interface` | Inputs accepted, outputs emitted, incoming contracts, outgoing contracts, and dependencies. |
| `ownership` | State, side effects, and parent partition coverage owned by the child. |
| `evidence` | Current evidence id, evidence tier, freshness rule, and stale or skipped gaps. |
| `split_signal` | Oversized state count, incomplete budgeted run, unrelated responsibilities, broad parent evidence, or progress-only evidence. |
| `deep_handoff` | Target split derivation, reattachment contracts, and closure model only when the decision needs parent/child confidence. |

## Partition And Overlap Review

## Target Split Derivation

For each parent model boundary, record a target split derivation before green
mesh confidence:

- source FlowGuard model or model-of-models id;
- target child model ids;
- parent coverage items represented by the target split;
- state and side-effect owner fields that shaped the split;
- rationale for why these child model regions are the right target structure.

Missing, source-less, target-less, prose-only, or coverage-incomplete target
derivations are blockers. The mesh still should not expand every child state
graph; it derives the target child layout, then consumes each child model as a
contract-bearing evidence source.

When a mesh represents a parent/child hierarchy, add a compact partition map.
The map should classify parent-space items by function, state, input, output,
side effect, invariant, or failure mode. Each item must be one of:

- `child`: exactly one child owns the item;
- `parent`: the parent owns the item;
- `read_only`: a child reads the item but does not own it;
- `shared_kernel`: a deliberate shared kernel owns the item.
- `bridge`: a deliberate handoff boundary consumes one child output and exposes
  a parent-known token without taking over the child's internals.
- `out_of_scope`: the item is outside the present claim and must include a
  rationale.

Coverage gaps block confidence: every parent-space item needs an owner or an
explicit out-of-scope note. Unsafe overlap also blocks confidence: sibling child
models must not both own the same state write, side effect, or core functional
area. Shared reads are fine; shared ownership needs an explicit shared kernel.

Use `review_layered_boundary_proof(...)` when the claim joins these tables into
one parent proof. ModelMesh still owns target split derivation and child
reattachment shape; layered proof checks whether the combined evidence chain is
closed enough for the parent claim.

Child boundary changes propagate upward. If a child changes its risk boundary,
accepted inputs, emitted outputs, state ownership, side-effect ownership, or
outgoing guarantees, the parent partition map, target split derivation, and
reattachment contract are stale until reviewed. If the child is also a parent,
the same stale-boundary rule applies to every ancestor that consumes its
evidence id.

Review affected siblings when a child boundary changes. A sibling is affected
when it owns, reads, depends on, or shares the same parent partition item, state
write, side effect, invariant, failure mode, or outgoing contract. Unaffected
siblings do not need ceremony, but the mesh should make the no-overlap reason
visible instead of silently assuming all siblings remain current.

## Child Reattachment Gate

Use this gate whenever a local child model is changed to repair a bug or model
miss and a parent model still needs to trust that child as part of a larger
workflow. The parent should record a compact reattachment contract for the child:

- child model id;
- current child evidence id consumed by the parent;
- input classes the child must still accept;
- output classes the child must still emit;
- state fields and side effects the parent expects the child to own;
- outgoing guarantees or contract ids the parent depends on;
- rationale linking the reattachment to the parent flow.

The parent mesh must block when the child is locally green but the parent did
not consume the updated evidence id, consumed an older child evidence id, or the
child's declared inputs, outputs, state ownership, side-effect ownership, or
outgoing guarantees drift from the parent expectation. This gate does not inline
the child state graph; it checks whether the child can still plug into the
parent's modeled handoff.

## Mesh Closure Model

Use a mesh closure model when a parent mesh claims whole-flow confidence across
the parent/child model network. This is a FlowGuard-style meta-model of the
model connections, not a child-graph expansion. It treats root entries, child
outputs, parent or sibling consumers, joins, normal/failure exits, and explicit
out-of-scope dispositions as finite tokens and obligations.

The closure model should record:

- parent root entry tokens;
- model-to-model closure transitions and the model that consumes each handoff;
- child output tokens that must be consumed;
- required join points and the outputs each join needs;
- normal exits, failure exits, terminal side-effect closures, and
  out-of-scope dispositions with rationale;
- loop-like retry, rejection, or wait handoffs, the repeat-input tokens and
  repeated output tokens,
  repair feedback tokens, and either progress tokens, blocker tokens, or a
  finite iteration bound.

`review_mesh_closure_model(...)` blocks green closure when a root entry is
missing, a consumed token is unknown, a child output has no consumer, a required
output is unreachable from the root entries, a join cannot complete, an
out-of-scope disposition lacks rationale, a terminal is reached with pending
required outputs, or a loop-like handoff lacks repair feedback, a structured
no-delta disposition, or a bound/progress rule.

When `HierarchyPartitionMap.closure_model` is present,
`review_hierarchical_mesh(...)` must consume the closure report before returning
`mesh_green_can_continue`. If a parent partition declares child outputs,
reattachment contracts, or runtime path evidence, the closure model is required
for broad parent green confidence. Without it, the mesh may still support
partition, target-split, evidence, or scoped reattachment facts, but it should
not be described as proving a closed parent/child flow.

Suggested evidence tiers:

- `candidate_only`: model exists but has not produced trustworthy current
  evidence.
- `abstract_green`: abstract formal model/invariant checks passed.
- `hazard_green`: known-bad hazard variants fail for the intended reasons.
- `live_current_green`: current runtime state or current artifact projection was
  checked against the model boundary.
- `conformance_green`: production or artifact replay conforms to model traces
  or projected states.
- `mesh_green`: the model mesh confirms no cross-model contradiction, stale
  dependency, missing hazard, or hidden skipped check blocks the decision.

Never use `abstract_green` alone as permission to continue a live workflow when
live evidence or conformance is required.

Background long-running checks are not pass evidence while they are still
running. Progress output is liveness only. A mesh may consume a long-check
result only after the final output, error, combined log, exit, and metadata
artifacts exist and the freshness rule says they still match this decision.

## Mesh Model Shape

Keep the mesh finite and inspectable. A useful mesh state usually contains:

- registered child models and their declared risk boundaries;
- evidence tier and freshness for each child model;
- live/current run or artifact facts that the decision depends on;
- cross-model dependencies and contract obligations;
- child reattachment contracts and consumed child evidence ids when a repaired
  child supports parent confidence;
- mesh closure root entries, child output obligations, consumers, joins, and
  terminal dispositions when whole-flow parent confidence is claimed;
- skipped, not-run, or parse-error sections;
- current decision: continue, block, add evidence, update child model, or split.
- parent partition coverage, sibling overlap, state ownership, and side-effect
  ownership for hierarchical boundaries;
- large-model split decisions for oversized new or legacy models.

Useful function blocks:

```text
InventoryModels x State -> Set(ModelInventory x State)
IngestChildEvidence x State -> Set(EvidenceTier x State)
ProjectLiveFacts x State -> Set(ProjectedLiveState x State)
CheckCrossModelContracts x State -> Set(ContradictionReport x State)
CheckChildReattachment x State -> Set(ReattachmentReport x State)
CheckPartitionCoverage x State -> Set(CoverageReport x State)
CheckSiblingOverlap x State -> Set(OverlapReport x State)
ReviewMeshClosure x State -> Set(ClosureReport x State)
ReviewLargeModelSplit x State -> Set(SplitDecision x State)
DecideMeshAuthority x State -> Set(ContinueOrBlock x State)
```

## Required Hazards

At minimum, the mesh must make these broken variants fail:

1. Abstract model pass is treated as live permission.
2. Skipped live audit, skipped replay, parse error, or not-run section is hidden
   inside a green result.
3. Stale or foreign result files are reused after source, prompt, route, input,
   or runtime facts changed.
4. A model that is not registered in the inventory is used as authority.
5. Two child models make incompatible claims about the same state, artifact,
   owner, or handoff.
6. A live blocker, open defect, or unresolved model-miss obligation is hidden
   by a safe-to-continue decision.
7. Conformance is required but missing, skipped, or only claimed by prose.
8. A post-runtime model miss is fixed in code without adding a same-class
   model scenario, invariant, replay adapter, or out-of-scope boundary.
9. The mesh reads sealed/private packet, report, or result bodies instead of
   metadata and explicit evidence pointers.
10. Local installed skill/source copies are stale but accepted as current.
11. The mesh expands every child state graph and becomes too large to inspect.
12. The project has three or more FlowGuard models but no mesh decision is
   created before a broad continue/release/completion claim.
13. A single oversized model or automatic split diagnostic does not trigger
    large-model split review.
14. A DevelopmentProcessFlow `model_too_thick` handoff is treated as an
    ordinary implementation failure and the thick model remains direct parent
    evidence.
15. Parent partition items have no child, parent, or shared-kernel owner.
16. Two sibling child models both own the same state write, side effect, or
    core functional area without an explicit shared-kernel boundary.
17. Child boundary changes, reattachment gaps, oversized direct evidence, or
    duplicate edge-path signals are not fed to `review_model_maturation_loop(...)`
    before a broad parent confidence claim.
17. A legacy model is used as strong child evidence before compatibility
    classification and contract wrapping.
18. A repaired child model is green locally, but the parent did not consume its
    updated evidence id.
19. A parent consumes a stale child evidence id after the child model changed.
20. A repaired child changes accepted inputs or emitted outputs without a parent
    reattachment blocker.
21. A repaired child loses state or side-effect ownership that the parent flow
    still depends on.
22. A repaired child drops an outgoing guarantee or contract that the parent
    mesh consumes.
23. The current bug instance passes after a patch, but the bug class is neither
    represented in executable evidence nor explicitly marked out of scope.
24. A child boundary change is accepted without propagating stale-boundary
    review to the parent target split and reattachment contract.
25. An affected sibling model keeps stale ownership, read-only, shared-kernel,
    or outgoing-contract assumptions after a child boundary changes.
26. A background long-running check is accepted as pass evidence from progress
    output, an in-progress log, or a missing exit/result artifact.
27. A parent mesh claims whole-flow closure while a child output has no parent,
    sibling, terminal, or explicit out-of-scope consumer.
28. A parent mesh reaches a terminal disposition while required child outputs or
    join obligations remain pending.
29. A closure model marks a branch out of scope without rationale.
30. A loop-like parent/child handoff is accepted as closed without repair
    feedback, a blocker/progress token, a bound, ranking, or progress rule.
31. A closure model consumes an unknown or foreign output token that is not
    produced by a root entry, child output, transition, or join.
32. A repeated AI packet or rejected input is returned with the same packet or
    token shape and no repair instruction, so the next packet can be identical.

## Prompt Template

Use `references/templates/model_mesh_prompt_template.md` only when delegating
or scaffolding a fresh mesh. Ordinary route use should follow the checklists
above without loading the full prompt body.

## Completion Standard

The mesh is sufficient for the current decision only when:

- model inventory is complete enough for the decision boundary;
- each required child model has a freshness rule and evidence tier;
- known-bad hazards fail for the intended reasons;
- skipped or missing live/conformance checks remain visible;
- cross-model contradictions are either absent or converted into blockers;
- each parent partition item is covered or explicitly out of scope;
- the target child model layout is derived from a FlowGuard model and covers
  the parent partition items used by the decision;
- repaired child models reattach through current parent-consumed evidence ids
  and stable input, output, state, side-effect, and outgoing-contract handoffs;
- whole-flow parent confidence, when claimed, is backed by a green mesh closure
  model that consumes every required child output, completes joins, reaches a
  valid terminal disposition, and keeps out-of-scope, repair-feedback,
  blocker-token, and loop-progress gaps explicit;
- the current bug instance is not confused with bug-class closure; Model-Miss
  Review either represented the same-class responsibility or marked it out of
  scope before mesh confidence is claimed;
- child boundary changes have propagated to every parent that consumes the
  child evidence id;
- boundary-change, reattachment, oversized-model, and duplicate-edge-path
  findings have been resolved or scoped through `review_model_maturation_loop(...)`;
- affected siblings with overlapping ownership, read-only dependency,
  shared-kernel use, or outgoing-contract dependency have been reviewed or
  shown unaffected;
- background long-running checks are used only after final completion artifacts
  and exit status exist;
- sibling overlap is either read-only, shared-kernel-owned, or converted into a
  split/merge/refactor decision;
- oversized new or legacy models have a split-review decision;
- the final decision distinguishes model classification from permission to
  continue the real workflow.
