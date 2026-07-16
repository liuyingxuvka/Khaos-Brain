---
name: flowguard-behavior-commitment-ledger
description: Use for external behavior registration, bidirectional source coverage, exactly one primary owner model, change-mode accounting, internal Primary Path Authority handoff, or broad done/release/archive/publish confidence.
---

# FlowGuard Behavior Commitment Ledger

## Purpose
Maintain one plane-partitioned `BehaviorCommitmentLedger` with source evidence, one owner, typed relations, and path authority.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns route/native owner `behavior_commitment_ledger` (`public_owner`) and the internal PPA handoff.

## Local Material Routing
Read `references/behavior_commitment_ledger_protocol.md` for fields, modes, lookup, PPA, and projections.

## Entrypoint Acceptance Map
Accept a bounded inventory/mode; register one owner per commitment; block coverage, relation, freshness, or PPA gaps; hand evidence downstream.

## Use When
- Use for the six ledger modes: bootstrap, add, change, remove/replace, gap backfill, or miss check.

## Do Not Use When
- Do not inventory helper internals or replace sibling evidence owners; return ordinary modeling to `model-first-function-flow`.

## Required Workflow
1. Define boundary/mode; query canonical JSON lightly, then do mode-required bidirectional discovery.
2. Set one `product_runtime`, `agent_operation`, or `development_process` plane plus `actor_kind`; kind is form, not plane.
3. Give each exact same-plane intent one stable id/active commitment; equivalent surfaces map to it, never a delegate row.
4. Set one owner, typed variants/relations with cross-plane rationale, lookup binding, lifecycle, and evidence.
5. Bind one current-green `primary_path_id`; run `review_behavior_commitment_ledger()` and project DCAR/TestMesh/risk evidence.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Use the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework or second success path.
- Duplicate exact promises, owner overlap, source/freshness/PPA/shard gaps, unknown or disallowed relations, and missing cross-plane rationale block broad confidence.
- Cross-plane language never merges owners. `unclassified`, legacy dependencies, and ambiguous plural paths are upgrade-only blockers.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, and commitment/source/owner/lookup/PPA status.

## SkillGuard Maintenance
- Edit contract source, regenerate; SkillGuard cannot manufacture native evidence.
