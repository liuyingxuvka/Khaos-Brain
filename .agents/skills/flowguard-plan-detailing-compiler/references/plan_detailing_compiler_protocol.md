# Plan Detailing Compiler Protocol

Plan detailing answers one delegated simulator-mode question before ordinary
FlowGuard modeling starts: is the plan detailed enough to check?

Use it when a request is non-trivial but the plan is still a rough idea, a few
steps, or an AI-written outline and the user explicitly requested
PlanDetailing or DevelopmentProcessFlow selected the `plan_detailing` mode. The
route converts that rough plan into structured rows that downstream routes can
consume. It does not execute the plan and does not prove the implementation.

## Invocation Topology

Generic automatic routing for rough-plan discussion enters
`flowguard-development-process-flow` first as the development-process simulator
front door. That front door records the `plan_detailing` mode and either:

- keeps the gap visible as a scoped simulator finding; or
- delegates here for full `PlanDetail` row construction and
  `review_plan_detail(...)` evidence.

Direct invocation is still valid when the user names PlanDetailing, an existing
OpenSpec/FlowGuard artifact requires this exact route, or another FlowGuard
route delegates the `plan_detailing` mode. Do not describe this protocol as the
generic first entry for all rough plans.

## Required Rows

- `PlanDetailSource`: current source evidence for the plan.
- `PlanDetailSurface`: in-scope risks, scoped-out risks, and evidence/source
  mappings.
- `PlanDetailArtifact`: requirements, designs, models, code, tests, docs,
  adapters, reports, release assets, and other versioned things the plan reads
  or writes.
- `PlanDetailStateSurface`: durable state, facts, or side effects that must be
  visible to the model.
- `PlanDetailStep`: ordered work with prerequisites, receipts, evidence gates,
  validation flags, rework targets, `agent_operation` ownership, and separate
  target commitment/plane/typed-relation references.
- `PlanDetailValidation`: validation obligations with evidence kinds, artifact
  ids, evidence ids, and commands.
- UI/action validation rows when a plan has visible controls: reachable
  enabled control ids, expected click-through method, pure-UI classifications,
  work mode, source-baseline inventory and target mapping when applicable,
  human-operability, and manual/native-dialog boundaries.
- Artifact payload rows when a plan imports, exports, saves, loads, generates,
  or consumes files/work packages: real payload surface ids, payload contract
  ids, synthetic accepted and rejected case ids, expected
  outputs/errors/state writes, fixture location, expected execution proof refs,
  and downstream owner route.
- `PlanDetailEvidence`: expected or current evidence rows.
- `PlanDetailFailureBranch`: failure, retry, blocked, or rework branch.
- `PlanDetailHumanQuestion`: unresolved decisions that block or scope claims.
- `PlanDetailFreshnessRule`: upstream changes that stale artifacts or evidence.
- Optional DPF process optimization: store only top-level
  `process_optimization_reasons` and exactly one current
  `required_process_optimization_evidence_ids` reference when active. Do not
  duplicate candidate, diagnostic, repair, or freshness state on each step or
  validation; ordinary plans leave both fields empty.

## Findings To Expect

- `missing_goal`
- `missing_source_evidence`
- `missing_risk_surfaces`
- `missing_artifacts`
- `missing_state_or_side_effect_surfaces`
- `missing_steps`
- `missing_validations`
- `missing_ui_action_coverage`
- `missing_artifact_payload_pack`
- `missing_failure_branches`
- `rework_gate_missing`
- `continue_gate_missing_evidence`
- `side_effect_missing_evidence_gate`
- `human_question_unresolved`
- `full_claim_missing_final_evidence`
- `full_claim_has_detail_gaps`

## Projection Order

After `review_plan_detail()`:

1. Use `plan_detail_to_plan_intake()` to preserve source evidence and risk
   surfaces.
2. Use `plan_detail_to_step_contracts()` to create receipt gates.
3. Use `plan_detail_to_development_process()` to review artifact freshness and
   completion claims. Projection changes lifecycle action ownership to
   `development_process` while retaining target references.
4. Use `plan_detail_to_agent_workflow_plan()` when the work involves multiple
   installed skills or external actions. Projection keeps AI steps in
   `agent_operation` and preserves receipts/continue/rework gates.
5. Send UI controls to UI Flow Structure and real-surface payload case evidence
   to Model-Test Alignment or TestMesh before any broad implementation claim.

## Confidence Boundary

`pass` means the plan has enough structured detail to continue. `scoped` means
the plan may continue only with an explicit boundary. `needs_revision` means
the plan should be expanded before execution. `blocked` means a broad claim or
irreversible action is unsupported.

A product target never becomes an AI/process owner through projection. Missing
target commitment ids or typed cross-plane relations blocks plane-aware detail;
legacy/trivial plans remain opt-in so this does not become a universal action
gate.
## Specification-provider sources

A provider work package enters PlanDetail as a current source row with explicit
`spec_provider_id`, `work_package_id`, `change_id`, task ids, obligation ids,
check ids, and binding ids. Keep those identities distinct: a task is not an
obligation, a provider obligation is not a stable validation obligation, and a
check label is not a terminal receipt. Missing task binding ids or a missing
reverse obligation/check owner is a plan-detail blocker.

Projection sends lifecycle order/freshness to DevelopmentProcessFlow and check
children/consumer fan-out to TestMesh. It never makes the planning compiler the
provider authority and never transfers product-runtime ownership to a provider
task.
