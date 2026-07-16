---
name: flowguard-model-mesh
description: Use when a FlowGuard project has three or more local models, an oversized model, stale child evidence, parent/child partitioning, target split derivation, child reattachment, affected siblings, or whole-flow mesh closure risk.
---

# FlowGuard Model Mesh

## Purpose
Govern parent/child model ownership, evidence freshness, reattachment, and closure without expanding every child state graph into the parent.

## Entrypoint Scope
Route id: `model_mesh_maintenance`; role: `public_owner`; native owner: `model_mesh_maintenance`. This standalone FlowGuard satellite skill owns model hierarchy, not test or code splits.

## Local Material Routing
Read `references/model_mesh_protocol.md` for inventory, target split derivation, partition rules, Child Reattachment Gate, mesh closure, and evidence tiers/freshness.

## Entrypoint Acceptance Map
Accept a parent and bounded children; derive/verify partitions and current receipts; block overlap, stale/unconsumed child evidence, missing closure/liveness, or incomplete leaf boundaries; hand test/alignment/closure gaps to typed owners.

## Use When
- Use for 3+ models, oversized/incomplete model groups, changed child boundaries, stale child evidence, coverage receipts, affected siblings, or parent whole-flow claims.

## Do Not Use When
- Do not split tests or code, trust child-local green as parent proof, or use for ordinary single-model work; return that work to `model-first-function-flow`.

## Required Workflow
1. Inventory parent/children, risk boundaries, target split derivation, ownership partitions, evidence tiers, and freshness.
2. Review child disjointness, current reattachment, affected siblings, coverage receipts, leaf boundaries, and closure/liveness.
3. Preserve scoped/stale gaps and project cases/receipts to Model-Test Alignment, TestMesh, and closure owners.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Parent confidence requires complete partition ownership, legal overlap, current child evidence/receipts, and current parent consumption.
- Background progress is liveness only; missing closure feedback/bounds or template harvest closure blocks broad mesh confidence.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus a mesh diagram, reattachment, siblings, and receipt status.
- In the mesh diagram, edges mean delegates, reattaches, consumes output, or blocks the parent claim boundary.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard checks the native mesh contract and cannot reattach children or manufacture receipts.
