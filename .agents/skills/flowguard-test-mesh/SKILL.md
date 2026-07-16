---
name: flowguard-test-mesh
description: Use when tests, checks, transition cells, payload cases, or evidence are large, slow, layered, stale, skipped, backgrounded, release-only, or require parent/child ownership and freshness proof.
---

# FlowGuard Test Mesh

## Purpose
Govern parent/child test hierarchy, validation partitions, results, and freshness.

## Entrypoint Scope
This is a standalone FlowGuard satellite skill; `test_mesh_maintenance` owns evidence structure, not semantics, process optimization, or test execution.

## Local Material Routing
Read `references/test_mesh_protocol.md` for split, ownership, diagnostic accounting, reuse, matrices, and release scope.

## Entrypoint Acceptance Map
Review a model-derived parent/child validation mesh; block stale, skipped, incomplete, or unowned evidence; hand semantics and lifecycle/risk to typed owners.

## Use When
- Use for large/slow/background child test scripts, stale/reused evidence, release gates, artifact-payload matrices, or diagnostic boundaries.

## Do Not Use When
- Do not split code/models, choose DPF process shape, group root causes, decide semantics, or execute tests; return small tests to `model-first-function-flow`.

## Required Workflow
1. Define the parent gate and derive child suites/scripts from a FlowGuard validation-structure model.
2. Declare an independent inventory revision and every required surface, obligation, member, cell, case, and shard; map each id to one owner.
3. Attach status, freshness, artifacts, reuse tickets, skips/timeouts, terminal identity, fingerprint, covered ids, and versions. Diagnostics add `diagnostic_boundary`, planned/executed/failed/not-run counts, not-run reason, campaign id, and stable Finding Ledger ids. Provider checks preserve session/consumer and receipt identity.
4. Review routine/release scope and return child evidence plus typed handoffs.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Use the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- PID/log/running/progress proves liveness only; reuse requires current `TestResultReuseTicket` and `ProofArtifactRef`.
- One receipt may fan out but cannot be copied or counted as several executions.
- Require `planned = executed + not_run`, `failed <= executed`, no not-run under `declared_complete`, visible reasons elsewhere, and stable finding ids for failures.
- Locally green subsets cannot prove an independently declared complete inventory.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, a validation mesh diagram, and child freshness.

## SkillGuard Maintenance
- Edit contract source and regenerate; SkillGuard cannot turn liveness into pass.
