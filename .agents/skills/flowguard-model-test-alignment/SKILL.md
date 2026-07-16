---
name: flowguard-model-test-alignment
description: Use when model obligations, owner external CodeContracts, source audits, transition cells, boundary observations, payload cases, closure targets, or ordinary test evidence need direct current comparison.
---

# FlowGuard Model-Test Alignment

## Purpose
Compare model obligations, owner external `CodeContract`, and current tests for the same behavior and coverage.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns `model_test_alignment` (`public_owner`) rows and hands large evidence to TestMesh.

## Local Material Routing
Read `references/model_test_alignment_protocol.md` for contracts, audits, matrices, targets, and bindings.

## Entrypoint Acceptance Map
Accept obligations/contracts/evidence; compare bindings/freshness; block missing/stale/orphan rows and hand gaps to owners.

## Use When
- Use for model-code-test coverage, cells, field projections, code boundaries, targets, or payload evidence.

## Do Not Use When
- Do not split tests/code/models or use TestMesh as a parallel semantic owner; return undefined obligations to `model-first-function-flow`.

## Required Workflow
1. List obligations, stable plane/intent/commitment/path ids, fields, `ArtifactPayloadContract`, owner/delegating contracts, similarity, and evidence kinds.
2. Materialize similarity/exhaustion rows into obligations, owner contracts, targets, tests, or typed scoped dispositions; consume current source/runtime/family evidence.
3. Classify gaps and hand them to TestMesh, maturation, risk, or closure owners.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Use the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework. Full confidence requires each obligation to bind one owner contract and current same-plane test.
- One intent cannot align to two primary paths; facades delegate with current no-independent-success evidence.
- Opaque family/similarity ids and missing/stale/skipped/audit/payload/target evidence do not count; delegate large evidence explicitly.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, binding gaps, and a diagram whose edges mean covers, partially covers, or does not cover.

## SkillGuard Maintenance
- Edit contract source, regenerate; SkillGuard cannot manufacture proof.
