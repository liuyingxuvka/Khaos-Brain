# FlowGuard Skill Kernel Protocol

The `model-first-function-flow` Skill is a kernel, not a monolith. The kernel
owns trigger selection, hard gates, route selection, and resource discovery.
Detailed procedures live in sub-protocol references or in route-specific
standalone satellite skills.

## Kernel Owns

- applicability decision: `use_flowguard`, `skip_with_reason`, or
  `needs_human_review`;
- flow lens: `behavior_flow`, `argument_flow`, or `decision_flow`;
- a soft oversize hint that suggests considering parent/child splits for large
  or hard-to-follow models, tests, scripts, modules, and commands;
- hard gates: real FlowGuard check-engine import, no fake mini-framework, executable evidence
  over prose, skipped is not pass, and adoption evidence for real use;
- route map to specialized protocols, public owner satellites, and delegated
  mode satellites;
- distinction between agent sub-protocols and package helper APIs.
- lightweight non-trivial lookup of the shared BCL/model inventory before
  route choice: same-plane hits guide the native owner, typed related-plane
  rows remain context, and ambiguous planes remain separated;
- the FlowGuard closure contract: complete FlowGuard use is not a mode, and a
  full done/release/publish/production-confidence claim requires current
  intake, model ownership, ContractExhaustionMesh case evidence when relevant,
  obligation-family parity when related obligations share a claim, analogous
  defect scan when a bug repair exposes a reusable failure shape, alignment,
  mesh/boundary proof when relevant, model maturation, freshness, ledger, and
  claim-chain support.
- the default model-code-test binding rule: broad model/test confidence needs
  model obligation ids, owner code contract ids, and current external-contract
  test evidence to name the same behavior. Model+test-only rows are scoped or
  blocked, not green.

## Public Owner Satellite Skills

These route-specific Codex skills are public owner routes. They can be invoked
directly when the user's request clearly matches their trigger:

| Satellite skill | Route |
| --- | --- |
| `flowguard-model-test-alignment` | `model_test_alignment` |
| `flowguard-contract-exhaustion-mesh` | `contract_exhaustion_mesh` |
| `flowguard-development-process-flow` | `development_process_flow` |
| `flowguard-model-miss-review` | `model_miss_review` |
| `flowguard-architecture-reduction` | `architecture_reduction` |
| `flowguard-code-structure-recommendation` | `code_structure_recommendation` |
| `flowguard-ui-flow-structure` | `ui_flow_structure` |
| `flowguard-model-topology-hazard-review` | `model_topology_hazard_review` |
| `flowguard-model-mesh` | `model_mesh_maintenance` |
| `flowguard-test-mesh` | `test_mesh_maintenance` |
| `flowguard-structure-mesh` | `structure_mesh_maintenance` |

If a task is ambiguous, cross-route, or starts from a general FlowGuard
applicability question, use the kernel first. Satellite skills must route back
to the kernel instead of taking ownership of unclear work.

Delegated mode skills are not public owner routes. DevelopmentProcessFlow may
delegate to `flowguard-plan-detailing-compiler` for `plan_detailing` rows or
to `flowguard-agent-workflow-rehearsal` for `agent_workflow` rows; explicit
user requests for those exact skills may still open them, but ordinary routing
keeps DevelopmentProcessFlow as the owner.

## Sub-Protocols Own

| Sub-protocol | Owns |
| --- | --- |
| `core_modeling` | Risk Intent, state write inventory, function blocks, invariants, formal CheckPlan, known-bad proof, and the internal finite runner |
| `development_process_simulator` | internal request helper consumed by `development_process_flow` for rough-plan, multi-skill, execution-freshness, install/sync, release/archive/publish, and final claim modes |
| `plan_detailing_compiler` | delegated `plan_detailing` mode rows, receipts, validation, rework, human questions, and projection to downstream routes |
| `architecture_reduction` | behavior-preserving code contraction candidates, observable architecture contracts, and target StructureMesh handoff |
| `ui_flow_structure` | UI interaction model, app-level journey coverage, implemented/runnable UI click-through evidence alignment, reachable visible-control branches, state/control/event/display transitions, parent/child UI topology, menu levels, overlays, stable placements, UI text hierarchy blueprint, and intentional redundancy |
| `model_topology_hazard_review` | topology digest, usage intent, anchored future-use hazards, required owner routes, and scoped or blocked confidence before broad claims |
| `model_test_alignment` | direct comparison of model obligations, transition coverage obligations, owner code contracts, code-boundary observations, artifact payload cases, obligation-family parity, and ordinary test evidence |
| `contract_exhaustion_mesh` | canonical bad-case generation from declared finite boundaries, same-class family seeds, payload contracts, transition cells, parent/child closure hazards, no-delta loops, broad coverage universes, and observed-problem backfeed |
| `model_maturation_loop` | converts post-code, post-miss, alignment, mesh, boundary, and freshness signals into model-upgrade or scoped-claim decisions |
| `risk_evidence_ledger` | final risk-to-model-to-code-to-family/UI/payload-gates-to-evidence confidence boundary for done/release/publish/full-confidence claims |
| `model_mesh_maintenance` | parent/child model hierarchy, child reattachment, whole-flow mesh closure, and oversized-model governance |
| `test_mesh_maintenance` | parent/child test hierarchy plus validation evidence |
| `structure_mesh_maintenance` | parent/child script/module structure split evidence |
| `agent_workflow_rehearsal` | delegated `agent_workflow` mode inventory, selected/skipped skills, side effects, continue/rework gates, and final claim scope |
| `development_process_flow` | public process owner plus internal simulator and `execution_freshness` mode for staged development, artifact overwrite, post-change scan signals, evidence freshness, and minimum revalidation |
| `model_miss_review` | non-trivial bug repair, model miss classification, root-cause backpropagation, current bug instance handling, same-class bug responsibility, and analogous defect scan closure |
| `conformance_adoption` | replay, install sync, shadow workspace sync, release sync, adoption evidence |
| `long_check_observability` | background log artifacts, liveness-only progress, and completion proof |
| `framework_upgrade` | FlowGuard self-upgrades and broad capability claims |

## Helper APIs Are Not Sub-Skills

These are check-engine helpers:

- `RiskIntent`, `RiskProfile`, `FlowGuardCheckPlan`,
  `MinimumModelContract`, `KnownBadProof`, `TemplateReuseReview`,
  `TemplateHarvestReview`, and `review_known_bad_proofs`;
- property factories and packs;
- `review_model_test_alignment()` and `review_code_boundary_conformance()`;
- `TransitionCoverageMatrix`, `transition_coverage_to_model_obligations()`,
  `transition_coverage_to_code_contracts()`, and
  `transition_coverage_to_required_leaf_cell_ids()`;
- `model_mesh_closure_to_transition_coverage()` and
  `MODEL_MESH_CLOSURE_RETRY_TEST_KINDS`;
- `ContractDimension`, `ContractMutationCase`, `ContractExhaustionPlan`,
  `review_contract_exhaustion()`, and contract-exhaustion feeder/consumer
  projection helpers;
- `review_obligation_family_parity()` and `review_analogous_defect_scan()`;
- `review_model_maturation_loop()` for post-evidence model upgrade decisions;
- `review_risk_evidence_ledger()` and risk evidence ledger rows;
- `review_hierarchical_mesh()`, `review_mesh_closure_model()`,
  `review_test_mesh()`, `review_structure_mesh()`;
- `review_development_process_flow()` and `derive_revalidation_plan()`;
- `PlanDetail`, `review_plan_detail()`, and plan-detail projection helpers;
- `review_architecture_reduction()`, compatibility-surface classification, and
  architecture reduction candidate rows;
- `UIDisplayElement`, `UIJourneyCoverage`, `UIImplementationValidation`,
  `UITextHierarchyBlueprint`,
  `review_ui_interaction_model()`, `review_ui_journey_coverage()`,
  `review_ui_implementation_validation()`,
  `review_ui_structure_derivation()`, and `review_ui_text_hierarchy()`;
- public starter templates.

They can support a route, but they are not independently triggerable agent
sub-skills.

## Maintenance Rules

- Keep `SKILL.md` short enough to scan as a router.
- Do not describe closure as an optional or default mode. If the closure gates
  required by a claim are missing, stale, skipped, progress-only, or scoped,
  report partial/scoped FlowGuard evidence instead of complete FlowGuard use.
- Add detailed procedures to references, not the kernel.
- Keep satellite skills concise and self-contained enough for direct Codex use.
- Keep ModelMesh, TestMesh, and StructureMesh aligned as sibling
  parent/child partition routes for models, tests, and code structure.
- When a model miss repair changes a child model under a parent ModelMesh, keep
  Model-Miss Review responsible for the miss and ModelMesh responsible for the
  parent reattachment gate, upward child-boundary propagation, and affected
  sibling model review.
- When ModelMesh closure transitions include retry/rejection or repeated-input
  loops, project them through ContractExhaustionMesh, then Model-Test
  Alignment/TestMesh before broad evidence claims.
- Keep the current bug instance separate from bug-class responsibility:
  patching the observed instance is not closure until the miss is classified
  and the ContractExhaustionMesh case is represented or explicitly out of scope.
- Keep `product_runtime`, `agent_operation`, and `development_process` in one
  BCL structure without merging their owners. Do not turn product rows into AI
  instructions or force trivial actions through a model; escalate recall when
  a non-trivial match, Model Miss, recurring/high-risk operation, or broad claim
  makes route-native evidence relevant.
- Keep LongCheck evidence boundaries explicit: background progress is liveness,
  not pass evidence, until final output, error, combined log, exit, and
  metadata artifacts exist.
- Keep Model-Test Alignment independent from mesh routes; it compares plain
  obligation, transition coverage, code-contract, code-boundary observation,
  source-audit, closure-target, and evidence rows and does not split tests or
  code. Real-code claims with paths/symbols can require green source audit, and
  concrete counterexample or known-bad repairs need target-aware owner-code
  tests. When the transition cell set is large or slow, route evidence
  hierarchy to TestMesh while keeping the semantic obligations visible.
- Keep Risk Evidence Ledger as a final claim boundary. It consumes evidence ids
  from sibling routes, but it does not replace their checks or rerun tests.
- Keep Architecture Reduction as the model-to-code contraction route. It may
  recommend merge/collapse/remove/keep-facade candidates, but it must hand
  production refactors to StructureMesh and lifecycle evidence to
  DevelopmentProcessFlow.
- Keep DevelopmentProcessFlow as a sibling lifecycle route. It may reference
  evidence ids from ModelMesh, TestMesh, StructureMesh, Model-Test Alignment,
  LongCheck, or Conformance Adoption, but it must not supervise, inspect, or
  replace those sibling route internals.
- Keep UI Flow Structure as a UI interaction/topology route. It builds or
  reviews the UI-level interaction model and, for complete app claims,
  launch-to-terminal journey coverage before deriving menus, regions, overlays,
  stable placements, display ownership, intentional redundancy, parent/child UI
  topology, and the UI text hierarchy blueprint for headings, labels, action
  text, state/status messages, helper text, and error/recovery copy slots; it
  aligns feature contracts with browser/desktop/manual click-through evidence
  when implemented/runnable UI completion is claimed; it
  does not replace visual design, final copywriting, or code-structure routes.
- Keep artifact payload validation in Model-Test Alignment: file import/export,
  generated artifact, save/load, and AI work-package claims need synthetic
  accepted/rejected payload cases that exercise the real payload surface plus
  current external evidence refs or proof artifacts; large payload matrices can
  route freshness and child ownership through TestMesh.
- Keep Model Topology Hazard Review grounded in model shape. Unanchored AI
  concerns are observations only; anchored hazards must route to the owning
  sibling evidence path before broad confidence.
- Keep oversize guidance as a short consideration hint, not a threshold policy
  or forced split rule.
- Avoid duplicate ownership of the same rule across multiple references.
- Preserve standalone FlowGuard use; external planner handoffs remain optional.
- Before broad release, verify the installed kernel and satellite skills match
  the source skill directories.
