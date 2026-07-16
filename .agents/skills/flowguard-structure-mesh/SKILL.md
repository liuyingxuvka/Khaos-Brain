---
name: flowguard-structure-mesh
description: Use when an existing large script, module, package, command, public API, facade, config surface, or plugin entrypoint split needs model-derived ownership, dependency, compatibility, parity, and release gates.
---

# FlowGuard Structure Mesh

## Purpose
Govern an existing-code parent/child structural split while preserving public entrypoints, facades, configuration, side effects, and observable parity.

## Entrypoint Scope
Route id: `structure_mesh_maintenance`; role: `public_owner`; native owner: `structure_mesh_maintenance`. This standalone FlowGuard satellite skill owns refactor structure evidence, not behavior invention or code edits.

## Local Material Routing
Read `references/structure_mesh_protocol.md` for target derivation, partition items, module/public-entrypoint evidence, routine/release scopes, and layered handoff.

## Entrypoint Acceptance Map
Accept a named source model and existing parent surface; derive child ownership; block missing facade, duplicate owner, cycle/config drift, or stale parity; hand validation/freshness/risk evidence to typed owners.

## Use When
- Use for splitting large code surfaces, moving public imports/CLI/API/data/plugin entrypoints, dividing state/config/side effects, or checking dependency cycles and parity.

## Do Not Use When
- Do not derive behavior requirements from scratch, recommend greenfield modules, refactor code directly, or claim parity from internal/formatting checks; return unclear models to `model-first-function-flow`.

## Required Workflow
1. Derive target modules from a named FlowGuard model with FunctionBlock/state/side-effect/facade/validation maps.
2. Partition functions, state, config, side effects, contracts, dependencies, public entrypoints, and facades to single owners.
3. Attach current routine/release parity evidence and export gaps/obligations downstream.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Missing model-derived target structure, public facade, owner, compatibility, or current parity blocks the matching scope.
- Dependency/config drift and release-only gaps remain visible; new/deepened models require template harvest closure.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus a structure mesh diagram and parity status.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard checks native mesh evidence and cannot perform the refactor or invent parity.
