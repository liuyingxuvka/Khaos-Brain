---
name: flowguard-architecture-reduction
description: Use when an existing FlowGuard model and code map should drive behavior-preserving architecture contraction, including merging duplicate handlers or modules, collapsing adapters, removing dead branches, or preparing a StructureMesh refactor.
---

# FlowGuard Architecture Reduction

## Purpose
Classify model-backed contraction candidates without changing the declared observable contract or editing production code.

## Entrypoint Scope
Route id: `architecture_reduction`; role: `public_owner`; native owner: `architecture_reduction`. This standalone FlowGuard satellite skill owns reduction proof, not implementation.

## Local Material Routing
Read `references/architecture_reduction_protocol.md` for observable contracts, compatibility classifications, proof statuses, and target actions.

## Entrypoint Acceptance Map
Accept existing-model ownership plus code mapping; classify contraction candidates; block missing equivalence/facade evidence; hand ready public-entrypoint work to Code Structure Recommendation, StructureMesh, and DevelopmentProcessFlow.

## Use When
- Use for merge, collapse, remove, keep-facade, or manual-review decisions over duplicate handlers, modules, adapters, branches, fields, or validations.

## Do Not Use When
- Do not use for greenfield module planning, direct refactoring, or behavior change; return unclear models to `model-first-function-flow`.

## Required Workflow
1. Ground existing ownership and declare an `ObservableArchitectureContract`.
2. Consume the independently expected same-intent candidate inventory and materialized Similarity relations/code obligations; map FunctionBlocks, state, side effects, public entrypoints, and every candidate or typed keep/scoped disposition.
3. Record stable intent/commitment/selected-path binding, proof status, target action, compatibility disposition, risks, and required next route.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Only equivalence or current facade proof can make a contraction ready; risky, scoped, stale, and property-only candidates remain visible.
- An empty/smaller candidate list cannot pass after Preflight or Similarity found duplicates. Retained facades require current evidence that they delegate to the selected primary path and cannot succeed independently.
- Public entrypoints require StructureMesh parity, duplicate generators route to ContractExhaustionMesh, and new/deepened models require template harvest closure.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus contraction candidates and proof status.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard gates the native reduction review and cannot refactor code or invent equivalence.
