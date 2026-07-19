# Repository expectations

## Bootstrap

- If the user asks to install, enable, deploy, bootstrap, or set up this predictive KB system on any machine, your default first action is to run `python scripts/install_codex_kb.py --json` from the repository root.
- Immediately after installation, run `python scripts/install_codex_kb.py --check --json` and confirm the install is healthy before doing anything else.
- Treat the installer as idempotent. If the system may already be installed, rerun the installer anyway rather than asking the user to verify it manually.
- If this repository was moved to a new path or re-cloned, rerun the installer from the new clone so the Codex-side manifest points at the current KB root.
- The installed global preflight skill must enable implicit invocation, remind Codex to add phase-change KB checkpoints during long mixed tasks, and remind Codex to record KB postflight observations after meaningful work, including skill/plugin and subagent/delegation usage lessons when they materially affect task outcomes. Treat missing behavior as an installation defect and fix it.
- The installer must also refresh the repository-managed `kb-sleep-maintenance`, `kb-dream-pass`, `kb-organization-contribute`, `kb-organization-maintenance`, and `khaos-brain-update` skills under `$CODEX_HOME/skills`; these skills are explicit maintenance, organization, or update entry points and should not enable broad implicit invocation. `khaos-brain-update` is manual-only and has no automation binding.
- The installer must refresh only `KB Sleep`, `KB Dream`, organization contribution, and organization maintenance automations under `$CODEX_HOME/automations`. It must permanently retire the exact legacy `kb-architect-pass` Skill, `kb-architect` automation, and `khaos-brain-system-update` automation on fresh installs and upgrades, without touching similarly named user assets.
- Every install or upgrade must run the versioned Chaos Brain maintenance migration, settle old lifecycle debt, archive retention-required cold evidence, prune only receipt-covered derivations, rescan for late reintroduced and Windows extended-length managed files, settle observations admitted by concurrent AI work through bounded post-commit receipts, rebuild the active index, preserve every surviving automation's user pause state, and remain rollbackable until current aggregate validation passes.
- Chaos Brain has zero normal-runtime compatibility and zero normal-runtime fallback. Exact retired formats may be read only by their versioned upgrade owner, which must rewrite or replace them directly, remove their old authority, prove zero residuals, and otherwise roll back while all four retained automations remain paused. An incompatible residual is an unfinished upgrade-AI work item: derive one evidence-bound direct-to-current disposition and retry inside the rollbackable upgrade instead of adding a product reader. Missing current authority must fail visibly; never add a dual reader/writer, alias, alternate launcher/model, or silent downgrade.
- The installer must also write or refresh a repository-managed global defaults block under `$CODEX_HOME/AGENTS.md` so other machines inherit the strongest available session-wide KB preflight and postflight rules, not only the implicit skill layer.
- The install check must expose a structured machine-install checklist that explicitly verifies the global skill files, implicit invocation, phase-change KB checkpoint wording, postflight reminder wording, mistake-first highest-priority postflight wording, skill/plugin and subagent/delegation signal wording, managed global AGENTS block, repo-managed maintenance/organization/update skills, all repo-managed automations, and the final `strong_session_defaults` readiness signal.

## Start here

- Read `PROJECT_SPEC.md` before making architectural changes.
- Treat `PROJECT_SPEC.md` as the authoritative v0.1 design brief.
- Keep `AGENTS.md` short; put detailed design rationale in `PROJECT_SPEC.md`.

## Purpose

This repository stores a local predictive knowledge library that Codex can consult before solving tasks.

## GitHub publish default

- When the user asks to update or sync GitHub for this repository, default to a **release audit** first, not to an automatic version bump.
- Inspect `VERSION`, visible README versioning, git tags, GitHub Release state, and the commit currently targeted by the latest tag together before publishing.
- Only create a new version when there is a **release-worthy public delta** since the last tagged commit. Do not mint a new version for history-only KB changes, private-card churn, release-note wording edits, or other same-commit repair work.
- If an existing tag or Release already points at the intended source commit, repair or reuse that release state instead of creating another version number for the same commit.
- Create the release commit first, then create the tag, then verify the tag target, then push branch and tag, then create or update the GitHub Release. Do not create the commit and tag in parallel.
- Do not move an existing tag unless the user explicitly asks for it.
- Keep detailed release rules in `docs/release_policy.md`.

## How to use the library

- Run `python scripts/install_codex_kb.py` once per machine to install the global Codex preflight skill and launcher.
- When the task is machine setup for this system, do not wait for extra confirmation or extra explanation. Run the installer and check commands as the default bootstrap path.
- When a task may depend on user preference, recurring workflow, domain heuristics, or prior lessons, invoke `$local-kb-retrieve` first.
- For long mixed tasks, rerun retrieval at phase-change KB checkpoints before substantially different work begins, such as switching from analysis to code edits, packaging, privacy-sensitive handling, organization-KB work, automation changes, GitHub push/tag/release, or public publication. Do not rerun retrieval for repeated same-type subtasks.
- Infer a primary conceptual route before retrieval. Do not rely on flat keywords alone when a route is apparent.
- Treat KB entries as bounded context, not unquestionable truth.
- Prefer entries with `status: trusted`.
- If an entry conflicts with direct user instructions in the current conversation, follow the current user instruction.

## Update rules

- Do not write directly into `kb/public/` or `kb/private/` from an active task thread.
- In the current implementation, new lessons should normally land in `kb/candidates/` or structured history first. Treat trusted-scope rewrites and promotions as maintenance work, not as default inline edits.
- New lessons should first be proposed into `kb/candidates/`.
- Keep private data out of commits unless the user explicitly wants it versioned.
- Do not add embeddings, vector databases, MCP services, or subagent orchestration in v0.1 unless explicitly requested.

## Validation

- Before changing retrieval logic, run a quick manual search test.
- Keep the skill description narrow so it does not trigger on trivial tasks.
- Keep scoring logic explainable and easy to inspect.

<!-- BEGIN MANAGED SKILLGUARD PROJECT RULES -->
## SkillGuard project maintenance

This repository contains skills maintained with SkillGuard. For non-trivial skill maintenance, validation, installation, synchronization, or release work, use SkillGuard by default.

Canonical SkillGuard repository: https://github.com/liuyingxuvka/SkillGuard

Managed skills:
- `.agents/skills/kb-dream-pass` — native owner=`kb-dream-pass`, route evidence=`.agents/skills/kb-dream-pass/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/kb-organization-contribute` — native owner=`kb-organization-contribute`, route evidence=`.agents/skills/kb-organization-contribute/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/kb-organization-maintenance` — native owner=`kb-organization-maintenance`, route evidence=`.agents/skills/kb-organization-maintenance/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/kb-sleep-maintenance` — native owner=`kb-sleep-maintenance`, route evidence=`.agents/skills/kb-sleep-maintenance/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/khaos-brain-update` — native owner=`khaos-brain-update`, route evidence=`.agents/skills/khaos-brain-update/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.

Required maintenance handoff:

1. Read the target skill's `SKILL.md` and its native route/check contracts before editing.
2. Use SkillGuard to inventory, run every target-declared check, reconcile exact receipts, and close non-trivial skill changes.
3. Preserve the target's sole current native route and exact declared checks; SkillGuard never supplies a target-domain route.
4. Never let SkillGuard replace target-owned domain judgment, simulation, search, modeling, actions, or checks.
5. Do not claim complete use from contract presence alone; require a current declared-check execution receipt.
6. If SkillGuard is unavailable or this block/manifest is missing, stale, duplicated, or invalid, report the maintenance result as blocked instead of silently bypassing it.

Validation execution ownership:

- policy_id: `skillguard.validation_execution_ownership.current`
- Creating, updating, directly rewriting a non-current target, compiling its consumer projection, or releasing a maintained skill requires author-side SkillGuard maintenance supervision; no migration or compatibility route exists.
- Covered skill maintenance uses direct current replacement. Do not add a compatibility reader, fallback, migration or upgrade command, converter, alias, renewal path, dual manifest, or parallel authority. An ordinary software historical reader is allowed only when an explicit requirement names the old document/data/interface and FlowGuard records its bounded owner and claim boundary.
- Ordinary use of an already-installed skill for its domain work does not start SkillGuard maintenance or validation.
- SkillGuard supervises one source Skill at a time: its exact promises, target-owned checks, positive fixture, named shallow gap, affected-only revalidation, and clean consumer projection. The target Skill retains its domain actions, judgment, native-check authority, and runtime closure.
- Before multi-skill maintenance starts, freeze one task-level boundary plan in the existing verification contract or TestMesh: list each target as a separate single-member unit with its own exact checks, obligations, evidence domain, dependencies, and execution owner. Missing, duplicate, cyclic, or semantically overlapping ownership blocks execution.
- A receipt belongs only to the unit that produced it. Another Skill neither consumes nor projects that receipt as its own proof. If two units appear to need the same test or evidence, repair the ownership boundary instead of introducing receipt sharing.
- Compile the complete maintained inventory into exact content components before validation. A change invalidates only owners and projections that explicitly consume its changed component; an unmapped or ambiguous file blocks instead of falling back to run-all.
- Treat maintained test, code, contract, configuration, toolchain, and policy changes as freshness inputs only through those exact component edges. Reports, receipts, progress logs, checkboxes, and other runtime outputs are evidence outputs and must not refresh source authority or trigger their own validation.
- Installation consumes only the clean target-owned consumer projection. Source-only contracts, `.skillguard`, tests, fixtures, models, notes, author receipts, SkillGuard commands/imports, and router material never enter an installed Skill. Installed currentness is target-native and never calls SkillGuard.
- Treat `--resume` as an execution command that may run missing owners; it is never a read-only receipt audit, and a receipt consumer must not invoke it.
- A repository-level full regression may run once under one explicit aggregate owner after source and tool identities are frozen. Its result is repository evidence only; it does not replace or get shared as any target Skill's native proof.
- After any launcher timeout, cancellation, or interruption, confirm the entire descendant process tree count is zero before accepting evidence or starting another owner; `cleanup-unconfirmed` results are invalid and non-reusable.
- Never use a Windows Scheduled Task, background resume, or unattended retry script to run full validation or resume a mutable worktree.

Portable audit command: `python <installed-skillguard>/scripts/skillguard.py project-audit --root .`

This managed block is a routing and maintenance contract. It is not runtime, test, release, or future-behavior proof.
<!-- END MANAGED SKILLGUARD PROJECT RULES -->


<!-- BEGIN FLOWGUARD PROJECT RULES -->

<!-- flowguard-rule:project.scope -->

## FlowGuard Project Rules

This project uses FlowGuard for non-trivial maintenance, feature work, bug
fixes, refactors, tests, release work, project upgrades, and evidence-sensitive
process changes.

<!-- flowguard-rule:project.repository -->

FlowGuard repository:
https://github.com/liuyingxuvka/FlowGuard

<!-- flowguard-rule:skill_suite.agent_surface -->

FlowGuard agent skill suite:
- Primary agent surface: the current clean consumer projection under
  `$CODEX_HOME/skills/`
- Default entry skill: `$CODEX_HOME/skills/flowguard/SKILL.md`
- Complete AI-agent setup means the agent can read `AGENTS.md` and all
  FlowGuard sibling `SKILL.md` files under `$CODEX_HOME/skills/`.
- An ordinary target project does not copy the FlowGuard suite into its local
  `.agents/skills/` tree and does not own the canonical suite map.
- Project audit and upgrade verify the package-owned clean-consumer authority
  directly against that global projection and its ownership manifest.
- The Python `flowguard` module/CLI is executable check support, not the
  AI-agent skill installation surface.

<!-- flowguard-rule:project.record_locations -->

Project FlowGuard record:
- Manifest: `.flowguard/project.toml`
- Machine log: `.flowguard/adoption_log.jsonl`
- Human log: `docs/flowguard_adoption_log.md`

<!-- flowguard-rule:project.rendered_versions -->

Current adoption record:
- FlowGuard check-engine version: `0.58.4`
- FlowGuard schema version: `1.0`

<!-- flowguard-rule:project.preflight_version_gate -->

Before non-trivial work:
1. Verify the real FlowGuard check engine:
   `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`
2. Check the installed check-engine version:
   `python -c "import importlib.metadata as m; print(m.version('flowguard'))"`
3. Audit the project record:
   `python -m flowguard project-audit --root .`
4. Compare the installed version with `.flowguard/project.toml`.
5. If the installed version is newer, run:
   `python -m flowguard project-upgrade --root .`
   This updates the project record and scans existing FlowGuard artifacts,
   model evidence, tests, docs, and guidance for deterministic upgrades into
   the current FlowGuard shape. Use `--records-only` only when intentionally
   scoping out artifact/model/test upgrade scanning.
   Then rerun affected models/tests before broad confidence and record the result.
6. If the installed version is older than the project record, stop and connect
   a current FlowGuard check engine before claiming FlowGuard confidence.

<!-- flowguard-rule:runtime.latest_schema_first -->

FlowGuard runtime guidance is latest-schema-first: old artifacts may be
detected and upgraded at project/tool boundaries, but normal route logic should
not keep long-lived old branches for obsolete fields, aliases, or wrappers.

<!-- flowguard-rule:lifecycle.default_replacement -->

Default replacement means dispose the old path, old field, alias, wrapper, or
alternate success path. Delete, block, migrate, delegate, repair, replace, or
scope it out with a concrete reason; do not leave it as a second successful
route.

<!-- flowguard-rule:behavior.commitment_ledger -->

Broad behavior work should use or update BehaviorCommitmentLedger before
claiming full coverage: register external behavior promises, map source
surfaces to commitments, assign exactly one primary owner model per
commitment, classify plane and actor kind, record typed relations/evidence,
and hand `path_sensitive=true`
commitments to Primary Path Authority. Do not treat every helper function,
file, field, or model as a behavior commitment.

<!-- flowguard-rule:behavior.plane_partitioning -->

Keep product runtime behavior, AI-agent operations, and development lifecycle
behavior in one BehaviorCommitmentLedger structure but classify every
production commitment as exactly one of `product_runtime`, `agent_operation`,
or `development_process`. `commitment_kind` describes form, not plane.
Before non-trivial work, use the lightweight existing-model/commitment lookup
to select one same-plane primary context; keep other planes separated or
connected only by typed, reasoned relations. A related product commitment is
target context for an AI/process step, not an instruction that the step owns.
Model Miss backfeed searches the affected plane first and creates a gap row
only when no matching promise exists. This is recall guidance, not a universal
requirement to execute a model for every trivial action.

<!-- flowguard-rule:behavior.commitment_ledger_modes -->

Before changing or claiming behavior coverage, classify the behavior-ledger
mode: `bootstrap_ledger`, `add_behavior`, `change_behavior`,
`remove_or_replace_behavior`, `coverage_gap_backfill`, or `model_miss_check`.
Only bootstrap and gap backfill require broad historical source discovery.
Ordinary add/change/remove work updates affected commitments, owner models,
DCAR cases, and TestMesh evidence. Model-miss checks first map the failure to
an existing same-plane commitment and owner model; keep typed related-plane
context separate, and create/backfill a commitment only when the observed
external behavior was not registered in that plane.

<!-- flowguard-rule:lifecycle.field_mesh -->

Field-bearing work should use or update FieldLifecycleMesh: high-level behavior
models include behavior-bearing fields, while child/leaf field rows account all
discovered fields and record owner, readers, writers, projection, lifecycle,
and old-field disposition.

<!-- flowguard-rule:evidence.ui_and_payload -->

UI runnable claims and file/work-package claims need current UI click-through
or artifact-payload evidence gates before broad done/release confidence.

<!-- flowguard-rule:behavior.primary_path_authority -->

Path-sensitive behavior commitments need Primary Path Authority evidence before
broad confidence: one primary runtime authority per business intent, visible
primary failure, no automatic alternate success, ContractExhaustionMesh
coverage, TestMesh shards, and Risk Evidence Ledger gates.

<!-- flowguard-rule:behavior.exact_intent_reuse -->

Treat one exact external user purpose as one stable `business_intent_id`, one
active Behavior Commitment, and one singular `primary_path_id`. UI, API, CLI,
aliases, adapters, wrappers, helpers, and compatibility surfaces for that same
purpose delegate to the selected commitment and path; they do not become
independent successful implementations.

<!-- flowguard-rule:ui.product_language -->

Use the existing UI Flow Structure route to review one product-wide design
language across declared surfaces: typography hierarchy, components,
navigation, interaction, feedback, recovery, and transition semantics. Equal
semantic roles reuse the same rule or token; any exception is bounded,
presentation-only, and cannot change the business intent, commitment, path,
visibility class, or user-visible result.

<!-- flowguard-rule:ui.content_admission -->

Classify UI content exactly once as `user_visible`, `user_on_demand`, or
`internal`. Ordinary UI renders only admitted user content; on-demand content
needs an explicit reveal and return path, while internal identities, audit
fields, evidence metadata, diagnostics, and routing state stay internal by
default.

<!-- flowguard-rule:process.development_process_flow -->

Non-trivial rough-plan discussion, multi-skill/tool workflow setup, staged
execution, install/sync, release/archive/publish, post-change owner scans, and
final process claims enter `flowguard-development-process-flow` first as the
development-process simulator. Record `plan_detailing`, internal
`strategy_selection`, `agent_workflow`, and `execution_freshness` modes in that
order; delegate to PlanDetailing or
AgentWorkflowRehearsal only when explicit or simulator-selected.
DevelopmentProcessFlow owns lifecycle order/freshness; AgentWorkflowRehearsal
owns AI-operation planning. Both may reference product commitments and their
evidence without copying product behavior into their own steps. Internal
`strategy_selection` stays inactive unless `explicit_request`,
`multiple_equivalent_routes`, `material_rework_risk`, or
`diagnostic_boundary_choice` applies. When active, first prove
outcome/obligation-evidence/safety/protected-side-effect/dependency-authority/
execution-owner equivalence, then choose `targeted`, `declared_complete`, or
`budgeted` diagnosis plus `sequential` or isolation-proven `safe_parallel`
execution. Hard blockers stop invalid descendants and material evidence stales
the decision. TestMesh owns diagnostic accounting; relation-backed repair
groups use ordinary primary-owner evidence and affected revalidation.
Estimated comparison may support a preference, never a global optimum.

<!-- flowguard-rule:process.spec_context_read_only -->

When official OpenSpec is in scope, FlowGuard may read only the current
proposal, design, specifications, tasks, and task status as external planning
context. FlowGuard must not write OpenSpec files, execute provider checks,
create provider sessions/caches/receipts, claim provider execution ownership,
or place provider-internal fields in product UI. OpenSpec retains validation
and archive authority.

<!-- flowguard-rule:process.post_change_scan -->

After non-trivial FlowGuard-managed work, let DevelopmentProcessFlow consume
post-change scan signals for changed artifacts, skipped routes, stale evidence,
open obligations, or split/reduction pressure. The scan output routes each gap
to the owning specialist, such as Model-Test Alignment, Architecture
Reduction, StructureMesh, ModelMesh, TestMesh, or AgentWorkflowRehearsal.

<!-- flowguard-rule:claim.no_fake_adoption -->

Do not create a fake local FlowGuard replacement. Do not claim full FlowGuard
completion from an AGENTS/manifest/log update alone; executable model checks,
tests, replay, and closure evidence still need to be current for the claim.

<!-- END FLOWGUARD PROJECT RULES -->
