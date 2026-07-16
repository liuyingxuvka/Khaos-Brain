---
name: flowguard-agent-workflow-rehearsal
description: Use only when explicitly requested or delegated by flowguard-development-process-flow's agent_workflow mode to rehearse a multi-skill, tool, plugin, or external-action workflow from a fresh inventory; generic workflow planning enters flowguard-development-process-flow first.
---

# FlowGuard Agent Workflow Rehearsal

## Purpose
Rehearse capability selection, order, side effects, evidence gates, and rework before execution; never execute or supervise the selected tools.

## Entrypoint Scope
Delegated FlowGuard mode skill; route `agent_workflow_rehearsal`, role `delegated_mode`, native owner `development_process_flow`. Generic multi-skill work enters `flowguard-development-process-flow` first.

## Local Material Routing
Read `references/agent_workflow_rehearsal_protocol.md` for `SkillInventorySnapshot`, plan rows, finding codes, and completion decisions.

## Entrypoint Acceptance Map
Accept a fresh current-machine inventory and explicit/delegated scope; produce an `AgentWorkflowPlan`; block stale inventory, unsafe side effects, or unsupported full claims; return execution and final evidence to DevelopmentProcessFlow.

## Use When
- Use for delegated `agent_workflow` planning where selected/skipped skills, plugins, tools, external actions, or continue/rework gates change confidence.

## Do Not Use When
- Do not use as a generic router, execute the workflow, or replace route-native validation; return unclear routing to `model-first-function-flow`.

## Required Workflow
1. Capture a fresh `SkillInventorySnapshot` and mark required/candidate skills.
2. Keep rehearsed steps in `agent_operation`. When a step invokes or validates product/process behavior, reference its commitment id, target plane, and typed BCL relation; do not copy that behavior into the AI step.
3. Rehearse ordered steps, skipped consequences, prior evidence gates, side effects, compensating checks, receipts, and rework paths.
4. Return selected/skipped skills, candidate skills, continue/rework gates, validation gaps, and final claim scope.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Require explicit delegation/direct request, current inventory, accepted skip boundaries, and evidence before every irreversible side effect.
- Progress or missing real-surface artifact payload proof, UI/manual/install evidence cannot satisfy a full claim.
- Registered same-plane behavior should be recalled for non-trivial matching operations, but this route does not force every trivial action through a model or turn related product rows into AI instructions.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, selected/skipped skills, and side effects.

## SkillGuard Maintenance
- Edit contract source, regenerate; SkillGuard cannot create an executor.
