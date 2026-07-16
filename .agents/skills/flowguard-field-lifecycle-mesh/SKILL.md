---
name: flowguard-field-lifecycle-mesh
description: Use when a change adds, removes, renames, migrates, replaces, externalizes, preserves, or audits fields, schema keys, config flags, prompt fields, payload columns, persisted attributes, defaults, aliases, or fallbacks.
---

# FlowGuard Field Lifecycle Mesh

## Purpose
Account every discovered leaf field, project behavior-bearing fields upward, and close old-field disposition before broad confidence.

## Entrypoint Scope
Route id: `field_lifecycle_mesh`; role: `public_owner`; native owner: `field_lifecycle_mesh`. This standalone FlowGuard satellite skill owns field boundaries and projections, not downstream behavior proof.

## Local Material Routing
Read `references/field_lifecycle_mesh_protocol.md` for `FieldLifecyclePlan`, grouped leaf rows, projections, replacement policy, and handoffs.

## Entrypoint Acceptance Map
Accept a bounded field inventory; create leaf rows and behavior projections; block missing fields or unknown old-field disposition; hand canonical malformed cases, owners, obligations, and repair evidence to their routes.

## Use When
- Use for schema/payload/config/prompt/persisted/UI/runtime fields, migrations, aliases, defaults, fallbacks, or field-rooted model misses.

## Do Not Use When
- Do not put every field in the high-level model, treat inventory as behavior proof, or replace alignment/testing; return missing behavior models to `model-first-function-flow`.

## Required Workflow
1. Define the field boundary, parent groups, and every discovered `FieldLifecycleRow`.
2. Add `FieldProjection` rows only for behavior-bearing fields and route invalid/old cases to ContractExhaustionMesh.
3. Close replacement disposition and send owners, readers/writers, projections, cases, and gaps downstream.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Default replacement requires delete, block, migrate, delegate, repair, explicit preserve, or scoped reason; unknown disposition blocks full confidence.
- Behavior claims still require current obligations, owner code contracts, tests, freshness, and template harvest closure where the model deepens.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus leaf rows, projections, owners, and dispositions.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard validates field accounting and cannot fabricate behavior or compatibility evidence.
