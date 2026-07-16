# ModelMesh Prompt Template

Use this prompt shape when asking an agent or officer to build the mesh:

```text
Build or update a FlowGuard model mesh for this project before production work.

Context:
- Project root: <path>
- Planned change or decision: <summary>
- Existing model count: <N>
- Large-model signals: <estimated/observed state counts, incomplete budgeted
  groups, or unrelated functional areas>
- Known model files/runners/results: <paths or "scan first">
- Current live/runtime artifacts to project: <paths or "none">
- Protected harms: <what must not slip through>

Tasks:
1. Inventory every local FlowGuard model, runner, result file, adoption log, and
   conformance/replay artifact relevant to this decision.
2. Classify each model's evidence tier:
   candidate_only, abstract_green, hazard_green, live_current_green,
   conformance_green, or mesh_green.
3. Define freshness rules for each result and mark stale, skipped, not-run, or
   parse-error evidence explicitly.
4. Create or update a model-of-models. Treat child models as evidence contracts;
   do not inline all child internals unless a contradiction requires a narrower
   adapter.
5. For each parent boundary, create a partition map that assigns parent-space
   functions, state, side effects, invariants, and failure modes to a child,
   the parent, read-only use, or an explicit shared kernel.
6. Record the target split derivation from the FlowGuard source model to the
   proposed child model layout. Include source model, targets, coverage, state
   owners, side-effect owners, and rationale.
7. For each repaired child model, record the parent reattachment contract:
   expected inputs, expected outputs, expected state and side-effect ownership,
   expected outgoing guarantees, and the consumed child evidence id.
8. When whole-flow parent confidence is claimed, or when child outputs,
   reattachment contracts, or runtime path evidence are present, create a mesh
   closure model that records root entries, child outputs, consumers, joins,
   terminals, out-of-scope branches, repeat-input tokens, repair feedback, and
   loop progress or blocker rules.
9. Separate the current bug instance from the bug class: confirm Model-Miss
   Review represented the same-class responsibility or marked it out of scope.
10. When a child boundary changed, propagate that change to the parent
   partition/split/reattachment review and review affected siblings.
11. Treat background progress as liveness only; require final long-check
   artifacts before using the result as evidence.
12. Encode the required hazards from `model_mesh_protocol.md` as broken variants.
13. Run the formal check plan plus progress/stuck review, hazard review, and conformance or
   live projection when applicable.
14. Return a decision: `mesh_green_can_continue`, `add_evidence`,
   `update_child_model`, `split_model_boundary`, `coverage_gap_blocked`,
   `overlap_too_high_refactor_needed`, `ownership_conflict`,
    `target_split_derivation_required`, `large_model_split_review_required`,
    `child_reattachment_required`, `blocked_by_stale_evidence`,
    `unconsumed_child_output`, `missing_join_point`, `terminal_leak`,
    `loop_progress_required`, `loop_repair_feedback_required`,
    `loop_no_delta_disposition_required`, `mesh_closure_required`,
    `blocked_by_cross_model_contradiction`, or `model_coverage_insufficient`.
15. Report what the mesh proves, what it does not prove, and which checks were
   skipped. Skipped is not pass.
```
