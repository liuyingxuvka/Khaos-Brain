---
name: kb-organization-contribute
description: Run the repository-managed Khaos Brain organization contribution pass. Use only when a user or automation explicitly asks to export local shareable KB cards into a validated organization repository; no-op in personal mode or unvalidated organization settings.
---

# KB Organization Contribute

Run one organization contribution pass for this predictive KB repository.

The organization KB is a shared exchange layer. Export only reusable material
that other local KBs may choose to adopt later; organization acceptance does not
override each machine's local Sleep or final adoption judgment.

Contribution writes only to the incoming lane under kb/imports/<contributor>/.
It must never write directly to kb/main; organization maintenance is
responsible for reviewing imports and moving accepted material into the main
exchange surface. Local download/search reads organization cards from kb/main,
not from kb/imports.

## Authority

Work from the repository root. Treat these files as authoritative before stateful contribution work:

- PROJECT_SPEC.md
- docs/organization_mode_plan.md
- .agents/skills/local-kb-retrieve/SKILL.md

Current user instructions still override repository files.

## Execution Contract

1. Use scripts/kb_org_outbox.py --automation as the entry point.
2. The entry point must first read .local/khaos_brain_desktop_settings.json.
3. If organization mode is not connected to a validated organization repository, exit successfully with a no-op result.
4. Sync the validated organization mirror first so contribution compares against current organization main cards, legacy compatibility cards, and imports before upload.
5. Run KB preflight against system/knowledge-library/organization before exporting any proposals.
6. Export only shareable model or heuristic cards with public scope and useful organization-level guidance.
7. Do not export private cards, personal preferences, credentials, raw local paths, or raw machine identifiers.
8. Use content hashes for duplicate prevention across all exchanged hashes: downloaded, used, absorbed, exported, uploaded, current local cards, current organization `main` cards, legacy compatibility cards, and current organization imports.
9. Put eligible local cards into the organization outbox, then automatically prepare and push an organization import branch under kb/imports/<contributor>/ when proposals were created.
10. After a successful push, open the organization PR when the repository is on GitHub; apply the `org-kb:auto-merge` label only when the changed files are eligible for the GitHub checks.
11. Leave movement into organization `main`, trust upgrades, merge approval, and final organization exchange decisions to organization maintenance and GitHub checks.
12. When a card depends on a local Skill, upload it as a card-bound Skill bundle with `bundle_id`, `content_hash`, `version_time`, `original_author`, `readonly_when_imported: true`, and `update_policy: original_author_only`.
13. If several local cards point at the same `bundle_id`, upload the local latest version for that bundle, not an older card-carried copy.
14. Include Skill dependencies only when card evidence explains when the Skill is useful, what outcome it predicts, and what fallback exists.
15. Run KB postflight after a non-skipped contribution pass and record the result as structured history.

## Report

Report the settings gate result, sync result, preflight entry ids, created/skipped proposal counts, content-hash duplicate decisions, card-bound Skill bundle ids and version hashes, import branch status, push or PR URL, postflight record path, and any errors.

<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose
Bind each kb run to the declared integration mode, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers kb-organization-contribute plus explicitly routed local materials; no unrelated repos, private files, external services, publication, or release claims unless requested and routed.
## Local Material Routing
Use workspace, skill directory, user files, or configured project paths; keep private machine paths local and public instructions portable.
## Entrypoint Acceptance Map
Use SkillGuard as the runtime contract executor attached to the native route/check owner: Predictive KB launcher, local KB records, and KB maintenance workflow. It enforces contract gates through that native owner before progress or closure; duplicate SkillGuard-owned execution paths are invalid. Declared gates/routes: recall or maintenance, evidence update, validation, closure.
## Use When
Use when the request matches kb-organization-contribute and needs this governed workflow, materials, checks, or handoff behavior.
## Do Not Use When
Do not use outside the domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the target-owned native route/check surface, run the SkillGuard contract gates around the native workflow, collect evidence, run checks, fix failures, then report.
## Hard Gates
Do not skip phases, do not replace required evidence with prose, do not treat stale reports as current, do not weaken validation to pass, and do not claim completion when blockers remain.
## Output Requirements
Report evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary; distinguish checked, unchecked, blocked, and uncertain.
## SkillGuard Maintenance
Keep `.skillguard` contracts, checks, evidence, and ledger current; rerun SkillGuard after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
