## Why

The repository already defines five independent SkillGuard-maintained source
skills and exactly twenty-five target-owned checks. The current SkillGuard
author audit nevertheless blocks because the repository still carries the old
project-maintenance prompt/manifest shape, while every generated compiled
contract and check manifest is stale against the current compiler. Historical
owner evidence has also accumulated without a bounded, repository-local
lifecycle demonstration.

The target skills are not under-specified. This change must preserve their
existing promises, obligation sets, native routes, and checks rather than let
SkillGuard invent deeper domain requirements.

## What Changes

- Replace the old SkillGuard project-maintenance projection with the current
  private author-repository adoption for the same five single-member units.
- Regenerate only each unit's compiler-owned `compiled-contract.json` and
  `check-manifest.json` from its unchanged `contract-source.json`.
- Verify the exact 5-unit/25-check inventory, clean consumer projections,
  positive fixtures, and named shallow rejections through the repository's
  source-only author check.
- Model the maintenance sequence with FlowGuard so peer ownership, protected
  KB state, check-count preservation, business-wrapper exclusion, and evidence
  lifecycle boundaries are explicit.
- Demonstrate SkillGuard evidence lifecycle only in a fresh isolated author
  evidence root, using read-only audit and GC-plan commands. Do not apply or
  purge evidence in this change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `kb-runtime-assurance`: Make current author-repository adoption and bounded
  author-evidence lifecycle explicit while preserving target-owned depth and
  consumer independence.

## Impact

Affected surfaces are the repository `AGENTS.md`, the private author manifest,
the ten compiler-owned generated contract files, one OpenSpec change, one
FlowGuard development-process model, and adoption logs. The five `SKILL.md`
files, five `contract-source.json` files, KB business evidence, scheduled or
manual maintenance wrappers, installed consumer skills, Git publication, and
release identities are outside this change.
