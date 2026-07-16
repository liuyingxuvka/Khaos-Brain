# Model Topology Hazard Prompt Template

```text
Build a FlowGuard Model Topology Hazard Review.

Read the FlowGuard model topology before naming risks. Do not use a generic
checklist. For every hard candidate, identify the exact topology anchor that
caused the concern.

Use these groups:

- Usage intent: local/CLI/library/plugin/service/release/migration, final
  claim, history or compatibility possibility, compatibility policy, and goal.
- Topology digest: states, inputs, blocks, workflow edges, state writes,
  side-effect edges, terminal nodes, external boundaries, old/new paths,
  business path identities, parent/child compression, and landmark ids.
- Business path identity: stable path id, business intent, trigger,
  preconditions, expected terminal, state writes, side effects, equivalent
  paths, exclusive paths, superseded old paths, compatibility disposition,
  source labels, and evidence ids.
- Candidate hazards: hazard id, anchor ids, rationale from topology shape,
  future failure mode, affected state/edge/side effect/terminal/boundary,
  disposition, required owner route, handled/scoped status, and evidence ids.

Hard rule: unanchored AI concerns are observations only. They may be listed,
but they must not block confidence until bound to a concrete topology anchor.

Promote anchored hazards when the topology suggests hidden future-use risk:
repeatable side effects, shared writers, broad terminal states, duplicate or
conflicting business paths, unproven important paths, old/new or schema paths,
external confirmation boundaries, parent/child compression, or local-only
evidence used for release/full confidence.

Route unresolved hazards to model_maturation_loop, model_test_alignment,
risk_evidence_ledger, development_process_flow, architecture_reduction, or an
explicit scoped-out decision with reason.
```
