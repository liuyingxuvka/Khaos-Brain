---
name: kb-organization-maintenance
description: Run the repository-managed Khaos Brain organization maintenance pass. Use only when a user or automation explicitly asks to inspect, review, or maintain a validated organization KB repository and this machine has opted into organization maintenance; this is the organization-level Sleep-like maintenance flow, not ordinary local KB Sleep.
---

# KB Organization Maintenance

Run one organization-level Sleep-like maintenance pass for this predictive KB repository.

The organization KB is a shared exchange layer, not a central truth layer. Treat
organization maintenance as Sleep for the shared exchange surface: it can
maintain `main` cards and imported card content when the evidence supports
the decision. Local machines still decide what to adopt and how strongly to rely
on organization cards after import.

The shared card remains an exchange projection. Organization maintenance owns
the organization repository's review state, not any machine's local LogicGuard
model or ModelMesh. Local use or adoption must enter the receiving machine
through its sole Sleep model publisher, and organization similarity or co-use
never creates a local canonical mesh edge automatically.

Use `kb/imports` as the sole incoming lane and `kb/main` as the sole organization
exchange surface. Retired `kb/trusted` or `kb/candidates` roots are upgrade-only
input and must make daily maintenance fail visibly. Local download/search reads
organization cards only from `kb/main`, never from `kb/imports` or an old root.

## Authority

Work from the repository root. Treat these files as authoritative before stateful organization maintenance:

- PROJECT_SPEC.md
- docs/maintenance_agent_worldview.md
- docs/organization_mode_plan.md
- .agents/skills/local-kb-retrieve/SKILL.md
- `organization-review` guidance, when available. This is a judgment aid, not an apply gate.

Current user instructions still override repository files.

## Execution Contract

1. Use scripts/kb_org_maintainer.py --automation as the entry point.
2. The entry point must first read .local/khaos_brain_desktop_settings.json.
3. If organization mode is not validated or this machine has not opted into organization maintenance, exit successfully with a no-op result.
4. Run KB preflight against system/knowledge-library/organization before inspecting organization candidates.
5. Validate the exact current organization manifest, `kb/imports` incoming lane, `kb/main` exchange surface, absence of retired roots/keys, Skill registry, and current Git state before proposing changes.
6. Read the shared maintenance-agent worldview and apply the exchange-layer Sleep model: organization `main` cards are maintainable content, not untouchable central truth.
7. Run the organization card-surface map checkpoint. Summarize `main` trusted/candidate/rejected/deprecated counts plus import counts; low-confidence main trusted cards; duplicate/similar cards; stale rejected/deprecated cards; Skill-linked cards; retired-layout residual count; and privacy/Skill risks before applying anything. A nonzero retired-layout residual is a blocker, not a readable surface.
8. Run the organization candidate intake checkpoint. Review new imports for reusable scenario, action, prediction, confidence, route, provenance, and public sharing value; reviewed imports can move into `main` as `candidate` or `trusted`.
9. Run the organization content-hash checkpoint. Use content hashes for duplicate analysis across `main`, imports, prior accepted uploads, and current proposals. Duplicate entry ids alone are not a maintenance blocker.
10. Run the mandatory organization similar-card merge checkpoint. Inspect overlapping organization cards by scenario, action, prediction, route, evidence, and content hash. Decide whether to merge, propose a merge, supersede, or keep/watch with a concrete reason. Uncertain similarity must remain a recorded watch decision, never an automatic merge.
11. Run the mandatory organization overloaded-card split checkpoint. Inspect broad, recurrent, or multi-branch organization cards and decide whether each is still a useful hub, should move toward a split proposal, or should remain keep/watch with a concrete reason. Ambiguous branch boundaries must not be force-split.
12. Run the organization card decision checkpoint. For each reviewed card bundle, including `main` cards, decide whether to keep, approve/promote, reject with reason, rewrite, adjust confidence, supersede, deprecate, merge, or split. Do not skip the decision checkpoint itself.
13. Apply the organization maintenance worldview to card candidates, `main` card changes, card-and-Skill bundles, Skill registry changes, privacy boundaries, and GitHub auto-merge readiness. Use `organization-review` as a review lens when available, but do not block direct Sleep-style maintenance because the local Skill is absent.
14. Run the organization Skill safety checkpoint. For every declared Skill dependency or Skill candidate, check card evidence, public usefulness, privacy boundaries, install risk, `bundle_id`, `sha256:` content hash, current `unavailable_skill_guidance`, read-only import behavior, and status.
15. Run the organization Skill bundle version checkpoint. Group Skill bundles by `bundle_id`; approve only original-author updates on the same bundle, treat non-author changes as forks with new `bundle_id`, and select the latest approved version by `version_time` for organization distribution.
16. Treat `candidate`, `approved`, and `rejected` as the first-pass Skill review states. Do not auto-install or recommend auto-install for candidate, rejected, unknown, unpinned, or non-hash-verified Skills.
17. Build an organization Sleep decision set over the cleanup proposal. Record every action as selected-for-apply or watch with a reason.
18. Apply only exact action ids that the organization Sleep decision set selected. Do not run broad cleanup just because tooling can apply it; `main` card changes are allowed when they pass the same Sleep-style evidence, usefulness, and rollback review. Missing `organization-review` guidance is not a blocker.
19. Run the post-apply organization check after selected actions are applied, and keep the audit path for rollback.
20. Commit and push applied maintenance changes to a maintenance branch, open the PR when the repository is on GitHub, apply `org-kb:auto-merge` only for reviewed main/imports changes with audit evidence, then restore the local mirror to the organization base branch so later sync or contribution work does not continue on an old maintenance branch.
21. Run the GitHub merge-readiness checkpoint. Confirm changed paths, low-risk import eligibility or reviewed-maintenance eligibility, required checks, rollback story, and whether the PR should be auto-merge eligible or remain review-only.
22. Do not skip the merge, split, card-decision, Skill-safety, Skill-bundle-version, decision-apply, post-apply, maintenance-branch, or GitHub-readiness checkpoints. It is acceptable to skip applying a change when evidence, safety, tooling, permissions, or scope is insufficient, but the inspection and recorded decision must still happen.
23. Run KB postflight after a non-skipped maintenance pass and record the result as structured history.

## Report

Report the settings gate result, participation status, preflight entry ids, organization manifest status, current-layout policy, retired-layout residual count, card-surface map, `main` status counts and import counts, main-card maintenance decisions, content-hash duplicate decisions, organization merge checkpoint decisions, organization split checkpoint decisions, card approval/rejection/rewrite/deprecation decisions, Sleep decision counts, selected action ids, apply result, post-apply check result, maintenance branch, PR, push, and auto-merge-label result, Skill dependency decisions, Skill bundle version decisions, GitHub merge-readiness result, organization-review guidance availability, recommendations, postflight record path, and any errors.

## SkillGuard completion boundary

For a scheduled run, intake, planning, or proposal-only output is incomplete. Run `python scripts/run_kb_guarded_automation.py --skill kb-organization-maintenance --json`; do not call the child entrypoint directly. The guarded runner invokes the native organization-maintenance owner once, writes an immutable run receipt, and requires the sole current enforced SkillGuard closure receipt for that exact run. A settings-gated no-op counts only when the native gate receipt proves its terminal. Positive and shallow fixtures remain target-owned checks; SkillGuard supervises their exact receipts without interpreting their domain meaning. Fixture or capability evidence cannot replace the concrete scheduled run. The installed SkillGuard builder—not caller-authored fields—binds the trigger, execution id, current installation receipt id/hash plus portable receipt-root reference, and installed runtime fingerprint. SkillGuard does not create a parallel organization-maintenance executor.

The current authority is `.skillguard/contract-source.json` plus its declared FlowGuard model. `.skillguard/compiled-contract.json` and `.skillguard/check-manifest.json` are generated projections. No former work contract, underscore manifest, flat run record, compatibility, conversion, renewal, retirement-receipt, alias, or fallback closure route may exist.

<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose
Bind each kb run to the declared integration mode, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers kb-organization-maintenance plus explicitly routed local materials; no unrelated repos, private files, external services, publication, or release claims unless requested and routed.
## Local Material Routing
Use workspace, skill directory, user files, or configured project paths; keep private machine paths local and public instructions portable.
## Entrypoint Acceptance Map
Use SkillGuard as the runtime contract executor attached to the native route/check owner: Predictive KB launcher, local KB records, and KB maintenance workflow. It enforces contract gates through that native owner before progress or closure; duplicate SkillGuard-owned execution paths are invalid. Declared gates/routes: recall or maintenance, evidence update, validation, closure.
## Use When
Use when the request matches kb-organization-maintenance and needs this governed workflow, materials, checks, or handoff behavior.
## Do Not Use When
Do not use outside the domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the target-owned native route/check surface, run the SkillGuard contract gates around the native workflow, collect evidence, run checks, fix failures, then report.
## Hard Gates
Do not skip phases, do not replace required evidence with prose, do not treat stale reports as current, do not weaken validation to pass, and do not claim completion when blockers remain.
## Output Requirements
Report evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary; distinguish checked, unchecked, blocked, and uncertain.
If the native owner or any validation child times out, the run is incomplete until the guarded launcher terminates the complete owned process tree, confirms zero remaining descendants, and records that cleanup under the ordered native-to-scheduled-to-aggregate timeout budget.

## SkillGuard Maintenance
Keep `.skillguard` contract sources and native bindings current. Reuse a current receipt when its execution identity and precise inputs still match; after an entrypoint, route, evidence, or closure change, run only the affected SkillGuard checks. Run full or release validation only for a stable integration snapshot or an explicit release.
<!-- END SKILLGUARD CONTRACT LAYER -->
