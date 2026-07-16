---
name: flowguard-model-topology-hazard-review
description: Use when a locally green FlowGuard model needs topology-grounded future-use hazard review for broad claims, business paths, old/new disposition, side effects, terminals, loops, external boundaries, or parent/child compression.
---

# FlowGuard Model Topology Hazard Review

## Purpose
Infer actionable future-use hazards from the actual model topology and usage intent; keep unanchored AI concerns observation-only.

## Entrypoint Scope
Route id: `model_topology_hazard_review`; role: `public_owner`; native owner: `model_topology_hazard_review`. This standalone FlowGuard satellite skill owns topology-anchored risk routing, not generic brainstorming.

## Local Material Routing
Read `references/topology_hazard_protocol.md` for `TopologyDigest`, `UsageIntent`, business-path identity, anchors, dispositions, and completion rules.

## Entrypoint Acceptance Map
Accept a current topology digest, usage intent, and evidence boundary; promote only anchored hazards; block unresolved high-impact paths/loops/side effects; hand model, test, reduction, process, and risk work to typed owners.

## Use When
- Use before broad done/release/publish confidence when local green may hide duplicate/conflicting paths, broad terminals, repeatable side effects, compatibility paths, or closure/liveness hazards.

## Do Not Use When
- Do not use for generic risk lists, unmodeled systems, or as a replacement for maturation, alignment, Risk Evidence Ledger, or Architecture Reduction; return unclear topology to `model-first-function-flow`.

## Required Workflow
1. Record usage intent, claim scope, topology landmarks, business paths, current evidence, and stale/skipped gaps.
2. For each candidate, name the topology anchor, real-use failure, affected element, confidence effect, and disposition.
3. Resolve, scope with rationale, or issue typed owner-route handoffs and maintenance obligations.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Unanchored concerns cannot block confidence; anchored hazards need current evidence, owner route, or explicit scoped disposition.
- Important path conflicts, loop liveness, compatibility/history, and template harvest closure must remain visible before broad confidence.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus anchored candidates and confidence effects.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard validates hazard structure and cannot promote unanchored prose into proof.
