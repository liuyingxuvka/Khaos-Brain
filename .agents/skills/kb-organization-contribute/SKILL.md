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

An organization card is an exchange projection, not local semantic authority.
Contribution derives it only from a current exact local LogicGuard binding and
must not export projection-only `related_cards` as relationship authority. A
receiving machine may adopt the content only through its local Sleep model
publisher, which creates a new scoped model revision and records organization
provenance; contribution never writes a local model or mesh.

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
4. Sync the validated organization mirror first so contribution compares against current organization `main` cards and `imports` before upload. Any retired layout must block this runtime and be handled by the versioned upgrader.
5. Run KB preflight against system/knowledge-library/organization before exporting any proposals.
6. Export only shareable model or heuristic projections whose exact local LogicGuard binding is current, public, privacy-safe, and useful at organization scope.
7. Do not export private cards, personal preferences, credentials, raw local paths, or raw machine identifiers.
8. Use content hashes for duplicate prevention across all exchanged hashes: downloaded, used, absorbed, exported, uploaded, current local cards, current organization `main` cards, and current organization imports.
9. Put eligible local cards into the organization outbox, then automatically prepare and push an organization import branch under kb/imports/<contributor>/ when proposals were created.
10. After branch materialization and immediately before push, revalidate the exact changed files, card counts, content hashes, privacy checkpoint, shareability, Skill author/version/hash metadata, and rollback/base-branch information. A preflight result from before materialization cannot authorize the push.
11. After a successful revalidation and push, open the organization PR when the repository is on GitHub; apply the `org-kb:auto-merge` label only when the exact changed files and current checks allow it. On validation, push, PR, or label failure, report the concrete terminal and restore the local mirror rather than claiming a partial contribution.
12. Leave movement into organization `main`, trust upgrades, merge approval, and final organization exchange decisions to organization maintenance and GitHub checks.
13. When a card depends on a local Skill, upload it as a card-bound Skill bundle with `bundle_id`, `content_hash`, `version_time`, `original_author`, `readonly_when_imported: true`, and `update_policy: original_author_only`.
14. If several local cards point at the same `bundle_id`, upload the local latest version for that bundle, not an older card-carried copy.
15. Include Skill dependencies only when card evidence explains when the Skill is useful, what outcome it predicts, and the current `unavailable_skill_guidance`; otherwise omit the Skill bundle while preserving the card itself without pretending the Skill is available.
16. Run KB postflight after a non-skipped contribution pass and record the result as structured history.

## Report

Report the settings gate result, sync result, preflight entry ids, created/skipped proposal counts, content-hash duplicate decisions, card-bound Skill bundle ids and version hashes, import branch status, push or PR URL, postflight record path, and any errors.

## Native completion boundary

For a scheduled run, intake, planning, or proposal-only output is incomplete. Run `python scripts/run_kb_automation.py --skill kb-organization-contribute --json`. The target-owned wrapper invokes the native contribution owner once and accepts only its immutable terminal receipt for that exact run. A settings-gated no-op counts only when the native gate receipt proves it terminal. Fixture or capability evidence cannot replace the concrete scheduled run.

Ordinary use is self-contained and does not read an author-maintenance contract, external receipt, router, or installed maintenance tool. Author-side checks may validate contribution behavior before distribution but never participate in a scheduled contribution run.
