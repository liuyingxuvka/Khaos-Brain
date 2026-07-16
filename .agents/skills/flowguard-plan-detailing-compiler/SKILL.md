---
name: flowguard-plan-detailing-compiler
description: Use only when explicitly requested or delegated by flowguard-development-process-flow's plan_detailing mode to compile a rough non-trivial plan into structured artifacts, steps, receipts, validations, failure/rework branches, and claim boundaries.
---

# FlowGuard Plan Detailing Compiler

## Purpose
Turn rough plans into checkable `PlanDetail` rows; detail is not implementation proof.

## Entrypoint Scope
Delegated FlowGuard mode skill; route `plan_detailing_compiler`, role `delegated_mode`, native owner `development_process_flow`. Generic work enters `flowguard-development-process-flow` first.

## Local Material Routing
Read `references/plan_detailing_compiler_protocol.md` for rows, findings, projection order, and confidence.

## Entrypoint Acceptance Map
Accept an explicit/delegated rough plan; compile scope, artifacts, state, steps, step receipts, validation, failures/rework, UI/payload gates, and claims; return typed projections.

## Use When
- Use for delegated `plan_detailing` with underspecified scope, steps, artifacts, UI/payload surfaces, validation, or rework.

## Do Not Use When
- Do not act as a generic planner, execute work, or replace downstream evidence; return unclear routing to `model-first-function-flow`.

## Required Workflow
1. Capture goal, assumptions, sources, risks, state/side effects, artifacts, UI actions, and payload/work-package surfaces; keep provider/task/obligation/check ids distinct.
2. Keep AI steps in `agent_operation`; add typed targets, order, receipts, validations, failure/rework/continue gates, freshness, and questions. If DPF optimization is active, keep only top-level `process_optimization_reasons` and one current `required_process_optimization_evidence_ids` reference—never copies on each step/validation. Run `review_plan_detail()`.
3. Project passing/scoped rows to DevelopmentProcessFlow, AgentWorkflow, UI, Model-Test Alignment, and TestMesh owners.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Use the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Prose, checkboxes, or progress cannot satisfy structured detail or terminal evidence.
- Full claims need resolved questions, final evidence, real-surface payload cases, human-operability gates, and template harvest closure.
- AgentWorkflow owns AI order; DPF owns lifecycle freshness; provider and product owners retain authority.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, `PlanDetail` rows, gaps, and projections.

## SkillGuard Maintenance
- Edit contract source and regenerate; SkillGuard cannot execute or create receipts.
