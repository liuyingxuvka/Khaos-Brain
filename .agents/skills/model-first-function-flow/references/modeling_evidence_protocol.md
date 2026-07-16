# Modeling Evidence And Closure Protocol

Use this protocol to classify the modeling mode, preserve current evidence semantics, and route post-check gaps without expanding the kernel.

## Lightest mode

- `read_only_audit`: inspect existing models/replays/adoption and stale fallbacks; do not create a model solely for read-only work.
- `model_first_change`: create/update a fit-for-risk model before production behavior changes.
- `model_maintenance`: upgrade stale model, replay, adoption, or old-schema artifacts before trusting them.
- `layered_boundary_proof`: join parent coverage, child disjointness, child reattachment, and finite leaf boundary rows through ModelMesh/MTA/TestMesh.

Other clear risks route to the direct public owner: existing preflight, Behavior Commitment Ledger/PPA, FieldLifecycleMesh, ContractExhaustionMesh, Architecture Reduction, Code Structure Recommendation, UI Flow Structure, Model Topology Hazard Review, Model-Test Alignment, ModelMesh, TestMesh, StructureMesh, DevelopmentProcessFlow, or Model-Miss Review.

## Evidence status

Keep these distinct:

- current pass from the owning native command and final proof artifact;
- failed, timeout, error, or blocker;
- skipped/not-run with reason;
- running/progress-only liveness;
- stale or reused without current ticket/proof;
- scoped/partial/`pass_with_gaps` confidence;
- known limitation or human-review policy gap.

Only the first can satisfy the matching current obligation. A summary, checkbox, configured boolean, generated contract, path-only log, or directory inventory does not manufacture pass evidence.

## Model miss and maturation

If runtime, tests, replay, logs, manual validation, or UI behavior fails after green, use `flowguard-model-miss-review`. Preserve prior claim/failure, identify the affected behavior plane, search that plane for the existing commitment/owner first, keep related planes typed and separate, classify/backpropagate the miss, generate a canonical same-class case, bind owner code/tests, close old paths/fields, and rerun affected parent/sibling/freshness/risk gates.

Use internal `model_maturation_loop` when miss/alignment/state-closure/mesh/code-boundary/freshness evidence shows the model is too coarse, stale, disconnected, or supports only a scoped claim. Upgrade or preserve the scoped boundary; a later green command alone does not close the maturation action.

## Maintenance and final claims

Convert non-pass findings into route-owned maintenance obligations. DevelopmentProcessFlow's post-change scan consumes changed artifacts, stale evidence, skipped routes, and open obligations, then reopens the canonical owner. Do not leave actionable gaps as prose TODOs.

Broad behavior claims require a current Behavior Commitment Ledger with one production plane and actor kind per row, exactly one primary model owner per commitment, typed cross-plane relations, PPA for path-sensitive rows, canonical cases/shards/receipts, model-code-test bindings, process freshness, and Risk Evidence Ledger/closure consumption as triggered.

Broad done/release/archive/publish/production confidence cannot consume missing, stale, skipped, not-run, progress-only, scoped, blocked, downgraded, or `pass_with_gaps` child evidence. Guard-family children return structured closure reports; the kernel preserves their safe claim and unsafe boundary.

## Adoption record

For real project use, record task/trigger/status, model files, commands/results, elapsed time, findings/counterexamples, skipped steps/reasons, friction, and next actions in `.flowguard/adoption_log.jsonl` and `docs/flowguard_adoption_log.md`. Logging supports review but never replaces executable checks.

## Output

Return route decision, evidence, failures, blockers, skipped checks, residual risk, claim boundary, typed next actions, model/counterexample snapshot, and current validation scope. Diagrams explain the active semantics; they are not validation evidence and must not flatten other Guard-family edge meanings.
## Specification-provider evidence boundary

OpenSpec, Spec Kit, and comparable tools keep their native requirements, task
completion, verification, and archive authority. Route their cross-step
freshness and receipt coordination to DevelopmentProcessFlow as one bounded
`SpecWorkPackage`. FlowGuard may reconcile tasks with obligations/checks,
short-circuit dependent checks, and reverify immutable receipts, but it must
not create a second task engine or expose these development-process fields as
product UI content.
