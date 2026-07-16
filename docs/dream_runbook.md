# Dream Exploration Runbook

This runbook defines the automatic `KB Dream` pass. `PROJECT_SPEC.md` is
authoritative. Dream is bounded immutable LogicGuard model verification, not
consolidation and not autonomous self-modification.

## Purpose and Ownership

- Sleep owns observations, lifecycle decisions, candidates, canonical models,
  scoped ModelMeshes, readable card projections, confidence, and the active index.
- Dream pins exact model authority, explores a small set of grounded hypotheses,
  and writes only simulation/experiment artifacts plus typed model-gap handoffs.
- System update is separate and does not consume Dream outputs.
- The retired Architect lane has no active handoff, queue, or completion role.

The installer provisions Dream at its repository-managed schedule with the
strongest available model and deepest supported reasoning policy. Dream and
Sleep use the shared local-maintenance lock and wait/recheck on overlap rather
than silently abandoning a scheduled pass.

## Eligible Inputs

- repeated retrieval misses or weak hits;
- an existing eligible candidate that needs one narrow validation;
- repeated route or taxonomy gaps;
- bounded proposal evidence that can be checked without product mutation;
- an important model missing evidence, warrant, assumption review, rebuttal,
  counterexample coverage, or a boundary condition;
- an explicit user hypothesis tied to a route, exact model node, or observable outcome.

Vague curiosity and broad mechanism redesign are not inputs.

## Fingerprint and Convergence Rule

Before selection, Dream pins the exact authority generation, model revision,
root node/ArgumentBlock, and ModelMesh revision, then computes a stable
fingerprint from those identities, route, experiment mode, source ids, source
lifecycle state, hypothesis, and decision-relevant evidence. The rule applies
to passed, failed, weak, and inconclusive results:

- unchanged fingerprint: close as `no_delta_closed`, with no experiment replay,
  knowledge write, or duplicate handoff;
- materially changed fingerprint: one new bounded experiment may run;
- knowledge-changing result: emit one typed, idempotent Sleep handoff;
- no knowledge delta: close in the Dream run artifact only.

## Run Loop

1. Acquire the shared maintenance lock and record lane state.
2. Retrieve prior Dream-process guidance.
3. Load exact LogicGuard models and grounded mesh neighborhoods. Missing exact
   authority blocks; a readable projection or floating head is not a fallback.
4. Gather grounded opportunities and attach hypothesis, validation, success,
   failure, stop, safety, and rollback contracts.
5. Compute fingerprints and remove every unchanged closed opportunity.
6. Select a bounded route-deduplicated batch; a no-op is valid.
7. Write plan, opportunity, experiment, and execution-plan artifacts before
   running the first experiment.
8. Execute sequentially inside the declared read-only or sandbox boundary.
   Plan evidence-removal, assumption-removal,
   rebuttal/counterexample-strengthening, boundary-pressure,
   cross-edge-removal, and neighbor-pin-replacement, then execute every
   applicable path separately.
9. Classify evidence and write the result artifact with exact affected node and edge ids.
10. Emit at most one typed Sleep model-gap handoff for each knowledge-changing result.
11. Prove the pinned generation, models, and meshes remain unchanged.
12. Validate artifact hashes, handoff idempotency, lock release, and final lane
    receipt.

## Allowed Experiment Types

- route-first retrieval comparison;
- retrieval A/B under the Dream sandbox;
- scenario replay with and without one tested candidate;
- exact-model evidence or assumption removal;
- rebuttal/counterexample strengthening, boundary pressure, cross-edge
  removal, and neighbor-pin replacement;
- read-only candidate or low-confidence-model validation;
- taxonomy-gap and proposal inspection;
- narrow local checks with explicit rollback and no production mutation.

## Disallowed Writes

Dream must not:

- append ordinary central-history observations;
- create, update, promote, reject, merge, or park candidates;
- commit models or meshes, rewrite trusted/private card projections, or change taxonomy;
- edit prompts, Skills, installers, automation specs, dependencies, or lockfiles;
- perform external-system mutation or broad workspace cleanup.

Such evidence may be represented only in a typed Sleep handoff or an ordinary
explicit development task outside Dream.

## Required Artifacts

Each run records canonical JSON under `kb/history/dream/<run-id>/`:

- `plan.json`, `preflight.json`, `opportunities.json`, `experiments.json`,
  `execution_plan.json`, and `report.json`;
- sandbox artifacts under `sandbox/` only;
- evidence fingerprints, result digests, source ids, evidence grades,
  validation status, exact generation/model/mesh bindings, affected node/edge
  ids, tested perturbations, allowed writes, rollback, and no-delta disposition;
- typed Sleep model-gap handoff ids and acknowledgement expectation when applicable;
- canonical-generation-unchanged proof.

These artifacts are experimental evidence. They do not enter active retrieval
and do not independently increase trusted confidence.

## Command

```powershell
python .agents/skills/local-kb-retrieve/scripts/kb_dream.py --json
```

A healthy repeated run over unchanged evidence reports zero selected
experiments and one or more `no_delta_closed` opportunities. A changed-evidence
run may select again, but still cannot write knowledge directly.
