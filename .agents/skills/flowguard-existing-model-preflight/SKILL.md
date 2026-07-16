---
name: flowguard-existing-model-preflight
description: Use before non-trivial discussion, proposal, feature, bug, refactor, UI, test, prompt, skill, workflow, or process work in an existing modeled system to identify current ownership and duplicate-boundary risk.
---

# FlowGuard Existing Model Preflight

## Purpose
Ground new work in current existing model boundaries before another route changes them.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns `existing_model_preflight` (`public_owner`); it is a companion preflight, not the change owner.

## Local Material Routing
Read `references/existing_model_preflight_protocol.md` for lookup, light/full search, ownership, reuse, and proof.

## Entrypoint Acceptance Map
Accept boundary/root; query/search; choose reuse, extend, child, new, or none; block duplicate-boundary risk and select a downstream route.

## Use When
- Use before non-trivial proposals/implementation where commitments, fields, similar models, or mesh evidence may own the change.

## Do Not Use When
- Do not implement, split, or replace native validation; skip trivial/no-context work and return unclear scope to `model-first-function-flow`.

## Required Workflow
1. Query canonical commitments from task plus exact id/path/tool/workflow/error clues before path discovery; select one grounded primary plane or preserve ambiguity.
2. Search current models/specs/docs/surfaces/records; add exact owner models from primary hits and classify old evidence. Only after plane-first lookup, attach any specification-provider context as `development_process` target context with stable provider/work-package/change ids.
3. Extract block/state/field/effect/entrypoint/commitment/intent/path/mesh ownership.
4. Independently inventory every declared same-intent surface, not only caller candidates.
5. Record lookup/fingerprint, primary/related hits, reuse, unknown/scoped surfaces, duplicate/stale risks, and typed handoff.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; SkillGuard only supervises FlowGuard-declared checks.
- Use the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework. Full mode precedes proposal/implementation.
- Missing/stale search or ownership, duplicate owners, unresolved mesh proof, or omitted same-intent surfaces block full preflight; equivalent current semantics default to reuse.
- Shared words cannot promote a wrong-plane hit. Missing/stale lookup falls back explicitly; ambiguity blocks full-confidence selection.
- A provider task cannot become a product-runtime owner. Provider context before canonical lookup, missing provider identities, the wrong primary plane, or `provider_owns_product_behavior=true` blocks full preflight.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, hits, ownership, plane lookup, reuse, and duplicate risks.

## SkillGuard Maintenance
- Edit contract source, regenerate; SkillGuard cannot approve downstream work.
