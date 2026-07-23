# Changelog

## v0.7.0 - 2026-07-22

- Replace restart-on-timeout Sleep work with one versioned frozen batch, immutable per-item results, durable checkpoints, and exact resume of pending items only.
- Size each new batch at twice the newly eligible work within tested minimum and maximum bounds, and report previous, new, opening, target, completed, blocked, closing, net-reduction, and two-cycle convergence state.
- Preserve the previous validated knowledge generation during planning, progress saves, timeouts, and failed publication; stage model material first and switch the immutable active-index pointer only once after lifecycle review succeeds.
- Replace the retired global stale marker with impact-scoped safety: additive work keeps retrieval available, exact revokes use generation-bound subtractive denies, and only proved corruption of the exact current generation closes the whole index.
- Allow malformed items to settle only with a named owner and executable reopen condition while publishing completed siblings as `completed_with_blocks`; keep Dream and organization descendants explicitly `not_run` for unfinished or blocked Sleep outcomes.
- Direct-migrate retired index authority through maintenance-standard v6, refresh the Sleep prompt, receipts, localization, installer contracts, OpenSpec, and FlowGuard evidence, and supervise the affected Sleep skill with SkillGuard 0.4.1.

## v0.6.9 - 2026-07-22

- Refresh five author-side SkillGuard maintenance units to the bounded evidence lifecycle without changing their 25 target-declared checks.
- Rebuild deterministic maintenance contracts and add FlowGuard/OpenSpec lifecycle evidence.
- Preserve KB business-maintenance execution boundaries; no Sleep, Dream, Architect, organization, or update wrapper was run for this release.

## v0.6.8 - 2026-07-20

- Replaced per-candidate lifecycle publication during Sleep with deterministic bounded atomic batches. Candidate creation, parking, reopening, promotion, downgrade, and calibration now preserve exact order and stable idempotency while using at most one lifecycle replay before and after each batch.
- Made interrupted Sleep recovery convergent: a later canonical Sleep owner reuses already-durable candidate and lifecycle identities, appends only missing events, keeps residual work visible, and never falls back to per-event publication or counts partial work twice.
- Required every active-index rebuild to carry an explicit authorized publisher identity. Normal runtime accepts only canonical Sleep, versioned migration owns upgrade-time publication, and unauthorized callers fail before any index, authority, or invalidation-marker write.
- Added OpenSpec requirements, FlowGuard model-miss closure, same-class known-bad cases, and regression coverage for production-scale replay, partial-timeout retry, marker-token races, unauthorized publishers, and fail-closed retrieval, Dream, and organization lanes.
- Recovered the local runtime through one canonical Sleep run, verified active-index generation 149 and downstream lanes, synchronized installer-managed skills and automations, and restored all four scheduled automations to their intended active state.
- Corrected README dependency versions and release delivery language. This is a source-only release; no prebuilt Windows executable is attached.

## v0.6.7 - 2026-07-19

- Pinned the sole public reasoning dependency to ResearchGuard v0.1.2 commit `1e731fd85c229a11f8e14e639705ad30ac080768`; Khaos Brain continues to import only `researchguard.logic`, with no standalone LogicGuard package, repository, alias, compatibility reader, or fallback dependency.
- Pinned development and release validation to FlowGuard v0.58.5 commit `97d2b0e6660fb2298decc9d4f86b4a16a3f8b7fd` and SkillGuard v0.3.5 commit `b20feaf0718cb9a37f9a2d0e3aaeb8e7601cadce`, including the corrected consumer-suite version authority and cross-platform canonical text identity.
- Preserved affected-only verification as the normal rule: reuse exact terminal-success receipts for unchanged owners, execute only failed or invalidated owner chains, and reserve one complete campaign for a frozen release snapshot.
- Clarified that Sleep, Dream, and organization maintenance are scheduled, while software update remains an explicit current-conversation AI action; no scheduled system-update surface was restored.
- Aligned active-task postflight timeout ownership: the existing 120-second sole-writer lock now fits inside a 150-second terminal budget, callers allow at least 180 seconds, and an interrupted launcher preserves the same event id until zero descendants and exact-episode inspection; no second writer, automatic retry, fallback, or compatibility path exists.

## v0.6.6 - 2026-07-19

- Replaced unconditional consumer-install assurance with five exact validation owners. Each owner binds its declared source, data, toolchain, environment, and installed-projection components; unchanged terminal-success receipts are reused and only affected owners execute.
- Applied the same closed affected-only contract to all 17 final-readiness owners. Every owner now reuses only an exact immutable success receipt and proof artifact; failed, timed-out, stale, tampered, missing, duplicate-owned, unmapped, or ambiguous evidence blocks without a run-all route. Full regression retains its exclusive JUnit-validated lane.
- Removed the unconditional second migration and retrieval campaign after assurance. The single planner now compares declared inputs before and after execution and replans only owners whose inputs changed, with no run-all fallback.
- Made `install_codex_kb.py --check --json` a bounded read-only currentness audit. It launches zero migration, model, retrieval, pytest, resume, or assurance subprocesses while still failing visibly on stale installation, automation, migration, attempt, or assurance authority.
- Restricted GitHub push validation to `main` and release tags so pull-request branches no longer run the same suite once for `push` and again for `pull_request`. Tags remain receipt-only and require the exact successful `main` revision before publication.
- Kept Khaos Brain's sole reasoning dependency on public ResearchGuard and `researchguard.logic`; no standalone LogicGuard import, compatibility reader, alias, or alternate dependency route was introduced.

## v0.6.5 - 2026-07-18

- Retired the exact `Khaos Brain System Update` scheduled task. Fresh installs, upgrades, repairs, and repeated installs keep it absent while preserving the four scheduled Sleep, Dream, and organization automations.
- Replaced the desktop update action with a read-only status for the exact configured Git upstream. The UI no longer writes authorization, enters a prepared state, or launches an updater.
- Made software update an explicit current-conversation AI action with strict fast-forward topology, UI-closed, clean-tree, transactional install, rollback, migration, SkillGuard, and four-automation restoration gates. `no-update` is the only successful no-op; authorization, UI, topology, and operational blockers remain unfinished.
- Removed persisted `user_requested` and `prepared` authority from normal runtime through a direct schema-v1-to-v2 upgrade migration with no compatibility reader or fallback path.
- Made SkillGuard conditional branches target-owned, so the update contract contains only `no-update` and `explicit-manual-update`; manual execution carries no scheduler identity, authorization emits no premature target terminal, and finalization consumes the exact staged depth receipt.
- Repaired shared knowledge retrieval for the original `model-004` example by restoring exact current LogicGuard manifest/index authorization and confirming zero missing or drifted projections across the full local corpus.
- Replaced the oversized installed-state payload with a lightweight current manifest, removing the startup/help latency caused by serializing hundreds of megabytes of installation detail.
- Replaced upgrade-attempt directory scanning with one bounded, hash-bound `HEAD.json` to current-projection authority. Ordinary install/currentness checks now read zero historical attempt files and fail visibly when that sole current binding is missing or invalid.
- Repaired current-machine activation so the complete maintained inventory is modeled as five skills: four scheduled skills plus the manual-only `khaos-brain-update`. Activation touches only the four automation IDs and no longer mistakes the manual skill for missing scheduled evidence.
- Made the desktop window and read-only version status visible before the 3,429-card catalog finishes loading; initial catalog construction now runs in the background with navigation held inert until the current payload is ready.
- Made active-task KB postflight one bounded append-and-receipt path: a caller-stable event ID is fsynced exactly once under the current writer lock, success requires one matching terminal receipt, and an interrupted event without that receipt is `timeout_unknown`. Lifecycle admission, candidate decisions, LogicGuard publication, and index rebuild remain Sleep-owned; the foreground route performs no synchronous lifecycle replay and has no alternate or fallback path.
- Bound the committed lightweight install state to the final upgrade attempt by exact `attempt_id` and `receipt_hash`. The independent installation check now replays that binding after the installer exits, so an in-memory green check cannot hide a missing or stale durable attempt identity.
- Streamed full lifecycle replay over the canonical JSONL ledger while preserving the exact event digest, avoiding a second in-memory copy of large event histories. Current-machine activation now restores all four automations to `PAUSED` after any apply, install-check, or receipt-validation exception, including memory exhaustion, so an unreceipted `ACTIVE` state can never close successfully. Its receipt binds a deterministic installation-authority projection while keeping full migration diagnostics as a separate required pass, so volatile diagnostics cannot invalidate an otherwise identical current installation.
- Direct-migrated the runtime dependency from the retired standalone LogicGuard package to the public ResearchGuard v0.1.1 exact source identity. Khaos Brain imports only `researchguard.logic`; CI needs no private repository, SSH deploy key, alias, compatibility import, or alternate dependency route.
- Added a rollbackable maintenance-standard-v5 authority cutover that inventories and hashes every retired `logicguard.model-store.v1` / `logicguard.model-mesh.v1` artifact, rebuilds all current projections into `researchguard.logic.model-store.v1` / `researchguard.logic.model-mesh.v1`, records before/after counts and digests, and requires zero retired-schema residuals. A failure at any model/mesh, projection, index, or pointer boundary restores the exact pre-cutover authority.
- Removed the repository-local 17-member FlowGuard shadow Skill suite through its exact ownership manifest (135 unchanged owned files, zero conflicts), retired the compatibility verifier and suite-control paths, and preserved every Khaos-owned project Skill. Khaos remains an ordinary FlowGuard-adopted project that uses one pinned external package and the current global Codex Skill surface.
- Development and CI model assurance now pin the same public FlowGuard v0.58.4 commit used by the final local readiness owner.
- Kept the Khaos-owned retrieval evaluation fixture on its sole integer `schema_version: 1` contract and made the evaluator reject strings, floats, booleans, or other compatibility coercions. FlowGuard project adoption may update FlowGuard-owned records but cannot rewrite this target-owned artifact.
- Direct-migrated the FlowGuard behavior ledger to the exact v0.58.4 canonical envelope by removing retired per-path migration markers; the ledger has one current parser and no compatibility fields or alternate authority.

## v0.6.4 - 2026-07-16

- Made `main` the sole final full-validation owner. Tag CI now proves the tag SHA equals `origin/main` and consumes the exact successful `main` Actions receipt for that SHA instead of rerunning the stateful installer/system-update owner in a detached tag environment.

- Made clean Linux CI self-contained by freezing the public SkillGuard v0.3.1 validation-toolchain commit and OpenSpec 1.6.0 instead of depending on user-level global installations.
- Declared an isolated CI-only automation model and reasoning effort so clean installation can validate rendered schedules without weakening the real-machine requirement for explicit current model authority.
- Made pre-restore assurance failures report each failed execution owner's terminal status, exit code, cleanup state, and bounded output tails instead of returning only opaque check names.
- Made full-regression JUnit receipt parsing platform-neutral by accepting only unique, unambiguous module aliases, so Linux and Windows executions resolve to the same canonical declared test nodes without weakening exact coverage.
- Replaced the machine-folder-derived SkillGuard project id with the single public `Khaos-Brain` id and audit exact managed bytes through a canonical temporary validation projection, so arbitrary clone paths do not create a second project authority or require a global SkillGuard reinstall.
- Froze `skillguard` and `skillguard-global-router` together from the same declared public validation bundle for scheduled supervision, removing the former hidden dependency on `$CODEX_HOME/skills/skillguard-global-router` without adding a fallback authority.
- Made the frozen SkillGuard pair pass through its official transactional installer inside the rollbackable Khaos upgrade attempt, capture a current official installation receipt, and use only that isolated `.codex` for scheduled-production replay; Khaos installation no longer requires or rewrites a global SkillGuard installation.
- Bound every scheduled-production replay to the exact Python launch path used when that isolated receipt was captured, while separately requiring it to resolve to the same interpreter binary; Linux aliases can no longer create a false command-fingerprint mismatch and a genuinely different interpreter still fails closed.
- Bound retrieval-quality cases to the current public active corpus and exact ModelMesh topology: stale expected card ids now fail visibly, grounded relations require traversal cases, and a single-node mesh records relation traversal as topology-not-applicable while retaining the 90% Top-3 and no-card safety gates.
- Reordered CI so the canonical rollbackable Khaos Brain installation publishes the current local LogicGuard authority before tests that intentionally require installed state.
- Repaired the fresh-clone authority path so an intact current public card projection is admitted only by the versioned migration owner, stripped of prior local bindings and derived relations, and rebuilt into a stable exact local model/mesh generation; tampered projections and partial authority still fail closed.
- Added the explicit upgrade-AI disposition route for an old machine that pulls a valid newly numbered public projection: software first emits an immutable work item and changes nothing, an AI may record only the evidence-bound direct-current projection-to-model decision, and the retry rebuilds that card while reusing every other exact local model in one new generation. Stale evidence, automatic rebinding, compatibility readers, and fallbacks remain blocked.
- Kept old-machine upgrades fail-closed: a pulled projection that disagrees with an existing local authority now opens an evidence-bound upgrade-AI work item and performs no automatic rebind, compatibility read, YAML fallback, alternate-model selection, or silent downgrade.
- Closed the real 3,427-card LogicGuard runtime model miss: distinct cards in one exact generation and authority scope now reuse a single immutable mesh view, publication clears every old-generation read cache, and catalog latency is measured separately from memory instrumentation without relaxing either budget. The observed runtime moved from a 3.146-second exact-context P95 failure to 0.053 seconds, with same-class and large-generation evidence bound back to the existing retrieval commitment.
- Made launcher-resolution and LogicGuard-origin assertions platform-neutral while preserving the exact executable-identity and package-origin checks.
- Kept product runtime behavior and dependencies unchanged; this patch repairs the public validation environment exposed by the v0.6.1 GitHub Actions run.

## v0.6.3 - 2026-07-16 (not released)

- The immutable candidate tag remains on its original commit, but no GitHub Release was created because materializing a branch name inside a tag job still duplicated the stateful full-validation owner. The receipt-consumer lifecycle repair is shipped as v0.6.4 without moving the old tag.

## v0.6.2 - 2026-07-16 (not released)

- The immutable candidate tag remains on its original commit, but no GitHub Release was created because tag CI correctly exposed that a detached tag checkout could not satisfy the system updater's fast-forward-only branch contract. The repair is shipped as v0.6.3 without moving the old tag.

## v0.6.1 - 2026-07-16

- Fixed clean-machine and GitHub Actions installation by pinning the public LogicGuard v0.18.0 source commit instead of requesting a package that is not published on PyPI.
- Raised the runtime minimum to LogicGuard 0.18.0, the first public release that provides the exact ModelStore and ModelMesh authority required by Khaos Brain 0.6.
- Split repository validation dependencies from product runtime dependencies, pinned the public FlowGuard v0.56.0 source commit, and declared pytest for reproducible model-assurance checks in GitHub Actions.
- Corrected GitHub Actions to run the pytest suite directly so pytest-style retirement and automation checks are executed instead of merely imported by unittest discovery.
- Documented the official GitHub dependency boundary and preserved the existing LogicGuard-native card, Sleep, Dream, migration, and retrieval behavior unchanged.

## v0.6.0 - 2026-07-16

- Made every admitted Khaos Brain card a deterministic projection of an exact LogicGuard model revision, root ArgumentBlock, generation, and grounded ModelMesh rather than an independent semantic authority.
- Made Sleep the sole normal-runtime publisher for canonical models, meshes, projections, and the active index; Dream now performs immutable pressure tests and emits typed model-gap handoffs without rewriting knowledge.
- Added evidence, warrant, assumption, rebuttal, counterexample, boundary, confidence, provenance, and explicit-gap modeling so retrieval can expose why a prediction is supported and what is still missing.
- Added direct-to-current, rollbackable upgrade migration with zero normal-runtime compatibility or fallback, precise retirement of the former Architect surfaces, residual-zero checks, and repair for authority-only generation/index drift.
- Added guarded current contracts for the five retained automations, FlowGuard 0.56 models and project records, model/retrieval/migration assurance, deterministic retrieval calibration, and stronger installer health checks.
- Kept live KB data and generated validation receipts local, sanitized public maintenance evidence, and documented the LogicGuard authority, ModelMesh linking, Sleep consolidation, Dream verification, and failure boundaries in the README and upgrade contract.

## v0.5.2 - 2026-06-27

- Added SkillGuard runtime-contract governance for the installed Khaos-Brain Codex skill materials.
- Synchronized installed skill copies with accepted source material and local git evidence.
- Recorded release-scope validation so route selection, evidence gates, quality floors, and closure boundaries remain visible before completion claims.

## v0.5.1 - 2026-06-15

- Added a canonical machine/core interface boundary so CLI tools, installers, launchers, automations, and global templates emit encoding-stable machine JSON while Chinese remains in UI display projections and `i18n.zh-CN`.
- Converted local KB scripts, top-level maintenance scripts, GitHub organization helpers, and installed launcher templates to the shared encoding-stable CLI output path.
- Added installer health checks, OpenSpec artifacts, FlowGuard coverage, and regression tests for the canonical machine interface and localized display boundary.
- Refreshed repository-managed skill prompts, automation checks, Windows desktop documentation, and zh-CN route display labels so another machine inherits the same interface split after install.
- Preserved the latest README positioning update and recorded recent local FlowGuard maintenance evidence before publishing.

## v0.5.0 - 2026-05-15

- Added explicit Sleep evidence-scope classification for `project-local`, `skill-specific`, `single-project-generalizable`, `cross-project-general`, and `insufficient-evidence` outcomes before candidate scaffolds or semantic card-surface changes.
- Updated new candidate previews and existing-card review actions so project names stay in provenance by default, same-project repetition is treated as chronology evidence, and old project-shaped reusable cards can be recommended for generalization.
- Preserved Skill/plugin/connector/tool-specific lessons as valid bounded rules when future invocation depends on that capability, instead of forcing every lesson into a capability-independent rule.
- Required semantic review apply decisions to include a `scope_assessment` object and carried the accepted scope into apply reports and maintenance-decision metadata.
- Added an OpenSpec change package, FlowGuard model, focused regression coverage, and Sleep maintenance prompt/runbook/spec documentation for the new generalization flow.

## v0.4.8 - 2026-05-14

- Prioritized Codex mistakes, weak paths, missed instructions, failed validations, tool/skill misuse, user corrections, and later correction episodes as the highest-value KB postflight observation evidence.
- Updated the installed predictive-KB prompt, managed global `AGENTS.md` defaults, installer health checklist, and regression coverage so other machines inherit and verify the same mistake-first postflight priority.
- Added an OpenSpec change package and executable FlowGuard model for the KB postflight priority path, including preservation of successful reusable patterns as lower-priority but still valid observations.
- Clarified organization-maintenance desktop status so local maintenance participation is displayed separately from GitHub merge authority and stale permission messages do not make valid maintenance participation look disabled.

## v0.4.7 - 2026-05-07

- Added a governance FlowGuard model for mature KB maintenance risks: candidate backlog closure, Dream-to-Sleep handoff review, Architect execution outlets, route drift, install drift, and manual organization pauses.
- Updated Sleep proposal output so it scans the full action surface while exposing a bounded immediate review batch with selected/deferred counts instead of hiding excess observations.
- Allowed strong/moderate Dream scenario-replay handoffs to be reviewed by Sleep, closing the previous handoff blind spot.
- Normalized known route aliases and dotted route families before governance review, retrieval hints, and maintenance history routing.
- Included the current AI-authored zh-CN route segment display labels used by the desktop card browser.
- Preserved user-paused organization automations during install refresh and health checks, while still flagging unexpected automation drift.
- Reconciled stale running lane statuses without live locks into explicit stale status and added regression coverage for organization lane completion.

## v0.4.6 - 2026-04-30

- Made KB Sleep's Chinese display cleanup a single final AI-authored completion checkpoint that covers both card fields and route/path display labels.
- Added an AI-maintained zh-CN route label display layer so canonical routes stay stable while missing path labels can be completed by the i18n apply path.
- Added Architect's system-readable maintenance rollup with Sleep, Dream, Architect, FlowGuard, organization, content-boundary, and install-sync status in one place.
- Added content-boundary reporting and release-gate visibility for formal cards, candidate review files, local adoption caches, history reports, private cards, and machine-local state.
- Refreshed repository-managed Sleep/Architect prompts, runbooks, installer automation checks, FlowGuard adoption records, and regression coverage for the new maintenance flow.

## v0.4.5 - 2026-04-29

- Refreshed the desktop card visual system with a broader premium palette, diagonal card/header gradients, larger title rings, and bold card titles.
- Brought the same title-ring treatment into the card detail header and tightened the detail metadata pill so source information stays on one line.
- Updated the README desktop preview screenshots from a public-safe fixture that demonstrates local and organization cards without exposing live local KB data.
- Added a flowguard model for the sandbox-to-production visual merge boundary, covering visual readiness, sandbox cleanup, route/data preservation, and rejected broken variants.

## v0.4.4 - 2026-04-28

- Fixed software update coordination so a failed update cannot be retried automatically by Architect until the user prepares the update again.
- Kept failed updates clickable in the desktop update badge so the user can deliberately re-prepare the same target, while new remote targets return to the available-update state.
- Hardened Dream, Architect, organization contribution, and organization maintenance runners so unexpected exceptions write failed lane status and release maintenance locks immediately.
- Added model-first function-flow artifacts and conformance replay coverage for update retry gates, maintenance lock cleanup, and organization exchange boundaries.

## v0.4.3 - 2026-04-27

- Fixed installer health checks on non-Windows CI runners so Windows-only Codex shell shims are not required when the installer did not create them.
- Added regression coverage for non-Windows partial shell-tool installs while preserving the stricter Windows local-machine check.

## v0.4.2 - 2026-04-27

- Fixed GitHub Actions coverage so retrieval, taxonomy, and desktop UI tests use deterministic fixture KB data instead of depending on ignored local candidate cards.
- Kept release validation reproducible on clean checkouts while preserving the public repository boundary that excludes live `kb/candidates` and `kb/history` data.

## v0.4.1 - 2026-04-27

- Added public repository hygiene files, including the MIT license, contribution guide, and a GitHub Actions workflow that runs tests plus installer and desktop checks.
- Tightened Sleep, Dream, and Architect reporting so maintenance runs expose clearer status, selected work, sandbox-style validation, and final application results.
- Expanded Dream experiment handling with bounded scenario-replay validation and richer execution records.
- Refined organization contribution and maintenance checks for the `imports` / `main` organization-KB layout and direct maintenance audit summaries.
- Clarified README positioning so the project describes its automatic local maintenance rhythm without overstating autonomy.

## v0.4.0 - 2026-04-27

- Added a shared maintenance-agent worldview so Sleep, Dream, Architect, and organization maintenance receive clearer role boundaries, evidence standards, sandbox expectations, and human-review criteria.
- Expanded local Sleep/Dream/Architect behavior with stronger prompt framing, real sandbox experiment handling, Architect sandbox-ready execution packets, rollback-oriented maintenance traces, and broader validation coverage.
- Added core maintenance lane locks so local Sleep, Dream, and Architect wait on one another, while organization contribution and organization maintenance share a separate organization-maintenance lock.
- Upgraded organization contribution and maintenance into a fuller exchange loop: contribution syncs first, avoids re-uploading already exchanged hashes, prepares import branches, and organization maintenance directly applies exact selected Sleep-style cleanup actions with audit records.
- Updated global predictive-KB preflight defaults so long mixed tasks add phase-change KB checkpoints before substantially different work such as edits, packaging, automation, organization-KB work, GitHub publishing, or public release work.
- Refreshed installer checks, repository-managed Skills, organization GitHub workflow checks, and tests so new machines inherit the same maintenance, organization, and preflight behavior after bootstrap.

## v0.3.0 - 2026-04-26

- Added the repository-managed `khaos-brain-update` Skill and installer/check coverage so software updates can be applied through the same Codex Skill distribution path as maintenance and organization skills.
- Added `.local/khaos_brain_update_state.json` software-update coordination, with desktop UI version/update capsules, prepared-update toggling, and launch blocking while an update is in progress.
- Added an Architect update gate that checks remote version state and only invokes `$khaos-brain-update` after the user has prepared the update and the desktop UI is closed.
- Clarified Sleep vs Architect ownership for Skill-use maintenance signals: Sleep keeps card/candidate work, while Skill prompt/workflow changes surface as proposal-only Architect signals.
- Expanded Chinese route labels and tightened desktop UI tests so live KB growth no longer creates false failures in navigation-count checks.

## v0.2.2 - 2026-04-25

- Replaced Sleep/Dream/Architect post-completion cooldown windows with explicit core maintenance lane status checks.
- Restored the default local cadence to Sleep 12:00, Dream 13:00, and Architect 14:00 while preventing overlap when another core lane is still running.
- Removed Dream and Architect cooldown CLI knobs from runner prompts, automation specs, docs, and tests so other machines inherit the same behavior after bootstrap.
- Refreshed installer validation for repository-managed maintenance skills and automations.

## v0.2.1 - 2026-04-24

- Refined the desktop card browser UI with lighter card shadows, subtler gradient surfaces, tighter spacing, and denser card layout.
- Updated the README desktop preview screenshots to show the refreshed overview and detail views.
- Added the organization mode planning document for the future GitHub-backed shared KB direction.
- Clarified Skill and plugin-use evidence capture rules in the project spec and local KB retrieval skill.
- Added Chinese route labels for the new release, desktop UI, branding, icon, and Skill-sharing planning routes.

## v0.2.0 - 2026-04-24

- Renamed and presented the project as `Khaos Brain` with refreshed public README positioning, icon artwork, and English UI screenshots.
- Added the local desktop card viewer as a human-facing way to browse the predictive memory library.
- Added Windows desktop packaging support for `KhaosBrain.exe`, including the icon source, shortcut helper, and UI-opening skill.
- Expanded Sleep/Dream/Architect maintenance behavior, semantic review handling, installer checks, and tests for stronger cross-machine defaults.
- Kept build outputs and live KB data out of source control; the Windows executable is published as a GitHub Release asset instead of committed to the repository.
