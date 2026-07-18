---
name: kb-dream-pass
description: Run one repository-managed automatic bounded KB Dream evidence pass. Use only for explicit Dream maintenance or the scheduled KB Dream automation, not Sleep consolidation, ordinary retrieval, or trusted-card maintenance.
---

# KB Dream Pass

Dream is a bounded immutable model-verification producer. It pins an exact LogicGuard generation, pressures its declared support and boundaries through simulations, and sends material model-gap deltas to Sleep; it does not own durable knowledge decisions or canonical model writes.

## Authority and entrypoint

Work from the repository root. Read `PROJECT_SPEC.md`, `docs/maintenance_agent_worldview.md`, `docs/dream_runbook.md`, and `.agents/skills/local-kb-retrieve/DREAM_PROMPT.md`. Current user instructions override repository defaults.

Run:

`python .agents/skills/local-kb-retrieve/scripts/kb_dream.py --json`

The native Dream runner owns simulations, experiments, terminal validation, and its immutable run receipt. Do not create a second experiment, maintenance, or model-write path.

## Required behavior

1. Acquire the shared `kb-dream` lane and run only when the maintenance lock is clear.
2. Pin the exact canonical generation, model revision, root node/ArgumentBlock, and ModelMesh revision before selection. Never substitute a floating head or readable-card projection when an exact binding is missing.
3. Build each evidence fingerprint from the pinned LogicGuard identities, canonical route, hypothesis, source identifiers and content digests, and prior applicable outcome. Run id, time, AI model name, thread id, and prompt wording must not make unchanged evidence appear new.
4. Load prior closure outcomes before broad work. If the fingerprint is already closed and no decision-relevant evidence changed, return or reuse `no_delta_closed` without another experiment, history entry, candidate, observation, or handoff.
5. Select only a small route-deduplicated set that clears the value and executability gates. A no-op is a valid convergent result.
6. For each selected model, plan one bounded suite covering evidence-removal, assumption-removal, rebuttal-strengthening or counterexample, boundary-pressure, cross-edge-removal, and neighbor-pin-replacement. Execute every applicable path separately. Each simulation is an overlay over the pinned immutable model, not a proposed canonical revision.
7. Record design, validation plan, safety tier, rollback plan, success/failure/inconclusive criteria, tested node and edge ids, expected invariant, and bounded sandbox path before execution.
8. Write only Dream-owned bounded runtime receipts and experiment evidence under the Dream run root.
9. For a material result, emit one typed idempotent Sleep handoff containing exact generation/model/mesh bindings, gap kind, affected node or edge ids, evidence fingerprint, result digest, provenance, and requested disposition.
10. Before closure, prove that the canonical generation pointer and pinned model/mesh revisions are unchanged.
11. Never directly write or modify models, meshes, readable card projections, candidates, confidence, lifecycle status, predictive observations, or central KB history.
12. Do not require a human to read files or select routine experiments. Keep external or irreversible actions outside Dream unless separately authorized in an active task.

## Closure report

Return the run id, pinned generation/model/mesh identities, evaluated fingerprints, tested perturbation paths, evidence deltas, model gaps, suppressed duplicate and no-delta counts, selected experiments, safety and rollback data, canonical-generation-unchanged proof, validation classifications, emitted handoff ids, input digest, blockers, and final state. Repeated unchanged runs must converge without growing knowledge history.

## Native completion boundary

For a scheduled run, intake, planning, or proposal-only output is incomplete. Run `python scripts/run_kb_automation.py --skill kb-dream-pass --json`. The target-owned wrapper invokes the native Dream owner once and accepts only its immutable terminal receipt for that exact run. A declared no-op counts only when the Dream gate receipt proves it terminal. Fixture or capability evidence cannot replace the concrete scheduled run.

If the native owner or any validation child times out, the run is incomplete until the target-owned launcher terminates the complete process tree, confirms zero remaining descendants, and records that cleanup.

Ordinary use is self-contained and does not read an author-maintenance contract, external receipt, router, or installed maintenance tool. Author-side checks may validate Dream before distribution but never participate in a scheduled Dream run.
