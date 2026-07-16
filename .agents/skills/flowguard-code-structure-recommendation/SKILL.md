---
name: flowguard-code-structure-recommendation
description: Use when a FlowGuard model should drive pre-code module and function boundaries, FunctionBlock ownership, field/state/side-effect owners, facade design, adapter boundaries, or validation structure before production edits.
---

# FlowGuard Code Structure Recommendation

## Purpose
Derive a target implementation structure from a named functional model without refactoring existing production code.

## Entrypoint Scope
Route id: `code_structure_recommendation`; role: `public_owner`; native owner: `code_structure_recommendation`. This standalone FlowGuard satellite skill owns recommendation-only architecture.

## Local Material Routing
Read `references/code_structure_recommendation_protocol.md` for model inputs, recommendation shape, field ownership, leaf boundaries, and StructureMesh handoff.

## Entrypoint Acceptance Map
Accept a source model and named responsibilities; produce FunctionBlock-to-module ownership, state/field/side-effect maps, facade plan, and validation boundaries; block source-less or duplicate ownership; hand existing-code refactors to StructureMesh.

## Use When
- Use before code when module split, function ownership, facade, adapter, field reader/writer, or validation boundary is unclear.

## Do Not Use When
- Do not perform existing-code refactors, invent behavior, or replace parity/alignment evidence; return missing models to `model-first-function-flow`.

## Required Workflow
1. Name the source model, FunctionBlocks, state, fields, side effects, and public entrypoints.
2. Recommend cohesive target modules, single owners, facades, adapters, and observable leaf boundaries.
3. Record rationale plus StructureMesh, Model-Test Alignment, or FieldLifecycleMesh handoffs.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Do not invent modules before responsibilities; require one owner per state/field write, explicit public facade, and validation boundaries.
- A too-large leaf must split or remain scoped; new/deepened models require template harvest closure.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus a code structure diagram and ownership map.
- When drawing the code structure diagram, edges mean owns, calls, adapts, exposes, or validates.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard checks recommendation inputs/outputs and cannot implement the proposed structure.
