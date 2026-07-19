## 1. Freeze ownership, fields, structure, and validation boundaries

- [x] 1.1 Run predictive-KB recall and a full existing-model/BCL preflight; record exact lifecycle/retrieval owners, LogicGuard as dependency rather than scheduler, and a known-bad proof that parallel search/Sleep owners are rejected.
- [x] 1.2 Add the executable `khaos_brain_logicguard_authority_cutover` FlowGuard child model with finite FunctionBlocks, current owner handoffs, closure/progress rules, and known-bad variants for duplicate authority, projection-first publication, Dream mutation, flat fallback, cross-scope leakage, stale revision substitution, and partial migration.
- [x] 1.3 Create the FieldLifecycleMesh inventory for all new binding/projection/mesh/simulation fields and every retired, migrated, derived, compatibility-like, prompt, receipt, index, and UI field; close each old-field disposition.
- [x] 1.4 Create the ModelMesh parent/child partition and reattachment artifact covering lifecycle, governance, authority cutover, canonical/display interface, desktop projection, and LogicGuard runtime, including affected siblings and whole-flow closure.
- [x] 1.5 Create the code-structure recommendation mapping every FunctionBlock, state write, field reader/writer, side effect, facade, adapter, and leaf boundary to one module owner.
- [x] 1.6 Freeze the Model-Test Alignment obligations/code contracts/known-bad targets and the TestMesh child-suite inventory, receipt root, dependencies, timeouts, freshness selectors, and exactly one final aggregate execution owner.

## 2. Add current LogicGuard authority adapters

- [x] 2.1 Add a dependency preflight that verifies the imported public ResearchGuard package and exact `researchguard.logic` member version, public API symbols, package origin, schema versions, and required P0/P1 tool fingerprints; fail visibly without a standalone LogicGuard package or substitute framework.
- [x] 2.2 Implement scoped public/private/candidate model-store and mesh-store roots, exact identity parsing, stable card-to-model ids, store recovery, writer boundaries, and cross-scope rejection in `local_kb.logicguard_models`.
- [x] 2.3 Implement deterministic predictive ArgumentBlock construction for new observations/candidates and conservative legacy input, including typed context, method/action, root claim, available warrant/evidence/provenance, assumptions, rebuttals, qualifiers, limitations, and explicit role gaps.
- [x] 2.4 Implement exact model validation and CAS/idempotent commit helpers with immutable receipt projection and tests for first commit, update, conflict, idempotent replay, corruption, missing revision, head substitution, and recovery.
- [x] 2.5 Implement exact mesh registry/membership/grounded-edge construction, validation, CAS commit, bounded materialization/evaluation/simulation adapters, and tests for ungrounded relationships, stale child pins, duplicate paths, and scope violations.
- [x] 2.6 Add `tests/test_khaos_logicguard_models.py` covering public APIs, ArgumentBlock role mapping, provenance, scoped stores, model/mesh transactions, and known-bad authority paths.

## 3. Make YAML a verified projection

- [x] 3.1 Implement the current projection schema and deterministic projector in `local_kb.model_projection` with exact model/node/block/revision/mesh bindings and `projection_digest`.
- [x] 3.2 Map canonical nodes back to localized/human `if`, `action`, `predict`, and `use`; derive any display neighbor list only from the exact mesh and mark it non-authoritative.
- [x] 3.3 Implement fail-closed projection validation, exact binding reads, scope/privacy checks, atomic staged projection publication, and current active-index row generation.
- [x] 3.4 Remove normal-runtime semantic writes/reads of standalone card fields and `related_cards`; retain only projector/UI readers and the bounded versioned migration reader.
- [x] 3.5 Extend active-index schemas, digests, authority pointers, invalidation, full/fast validation, and receipts to bind projection/model/mesh identities and reject stale or unbound records.
- [x] 3.6 Add `tests/test_khaos_model_projection.py` for deterministic parity, tampering, missing model/revision/node/block, stale mesh, retired-field residuals, atomic publication failure, and public/private redaction.

## 4. Make retrieval and UI model-native

- [x] 4.1 Extend `local_kb.search.search_with_receipt` and rendering payloads to require current bound index rows, return exact qualified identities, and remove YAML scan and `related_cards` fallback success paths.
- [x] 4.2 Implement exact card/model/node lookup and deterministic bounded neighborhood materialization with hard hop/node/edge budgets, frontier/exclusion diagnostics, and lifecycle/scope filtering before ranking.
- [x] 4.3 Add explainable model-native ranking signals for exact match, role, distance, importance, support/opposition, membership, and scope while preserving existing confidence/status/route policy.
- [x] 4.4 Add a single graph-first desktop view model and detail surface for prediction summary, exact revision, local support/warrant/assumption/rebuttal/limitation nodes, memberships, and open gaps with localized labels and visible stale/unavailable states.
- [x] 4.5 Add `tests/test_khaos_model_native_retrieval.py` and extend desktop tests for exact lookup, bounded truncation, no-card, stale/missing authority, no fallback, ineligible neighbors, cross-scope isolation, graph/text consistency, and language projections.
- [x] 4.6 Add representative P50/P95/memory performance fixtures for active-index load, exact-card lookup, and bounded neighborhood materialization; freeze justified budgets in the readiness inventory.

## 5. Upgrade Sleep to consolidate canonical models

- [x] 5.1 Implement `local_kb.model_maintenance` actions that translate lifecycle-selected observation/candidate/outcome/Dream deltas into create/revise/merge/supersede/no-delta model generations without owning lifecycle decisions.
- [x] 5.2 Add LogicGuard diagnostics, gap ledger, importance, provenance, duplicate support, and stale-revision review so missing evidence/warrant/assumption/opposition/boundary receives an explicit Sleep disposition before strengthening.
- [x] 5.3 Implement higher-order scoped mesh grouping through the exact registry, preserved memberships, and admissible cross-model edges; treat legacy/AI-only relations as unresolved candidates rather than canonical edges.
- [x] 5.4 Extend the existing `run_incremental_sleep` transaction to commit models, meshes, projections, and index generation before advancing its watermark; restore the prior complete generation on any blocker.
- [x] 5.5 Preserve candidate lifecycle, merge/supersede targets, active eligibility, organization read-only boundaries, maintenance-lane locks, concurrent change handling, and idempotent no-delta behavior.
- [x] 5.6 Add `tests/test_khaos_sleep_model_maintenance.py` and extend Sleep convergence tests for gap dispositions, grounded/ungrounded linking, CAS conflict, partial failure rollback, concurrent inputs, watermark safety, idempotency, and parent-mesh closure.
- [x] 5.7 Keep the full lifecycle ledger as Sleep authority while making duplicate-key replay linear in event count; add a scaling regression and a FlowGuard known-bad variant for quadratic single-replay cost.

## 6. Upgrade Dream to validate and deepen the mesh

- [x] 6.1 Replace card/list opportunity authority with exact pinned mesh/model gaps while preserving the existing Dream selection, value, safety, lane, and no-delta boundaries.
- [x] 6.2 Implement bounded separate perturbation plans for missing support, evidence removal, assumption removal, rebuttal activation, edge removal, neighbor model-pin replacement, boundary stress, and important fragile claims using LogicGuard public simulation APIs.
- [x] 6.3 Extend Dream fingerprints and receipts with exact generation/mesh/model revisions, roots, perturbations, evidence, result deltas, and claim boundary.
- [x] 6.4 Enforce read-only canonical stores during Dream and restrict writes to sandbox evidence, simulation receipts, and typed idempotent Sleep handoffs; reject direct model/mesh/projection/index writes.
- [x] 6.5 Extend `tests/test_kb_dream.py` and `tests/test_khaos_logicguard_models.py` for useful counterexamples, all applicable perturbation branches, no-delta closure, changed-evidence reopening, duplicate handoff prevention, write boundary, privacy, budget, and interrupted experiment behavior.

## 7. Implement direct-to-current migration and installer adoption

- [x] 7.1 Add a versioned model-authority migration phase to `local_kb.maintenance_migration` with complete managed-card inventory, source/toolchain fingerprints, deterministic per-card plans, explicit unresolved relationships/gaps, and scoped model/mesh targets.
- [x] 7.2 Stage full prior YAML/index/model/mesh/lifecycle/automation state, acquire all declared writer/lane boundaries, preserve user pause intent, and checkpoint resumable/idempotent model/mesh transaction receipts.
- [x] 7.3 Migrate every eligible and ineligible card conservatively, rewrite exact current projections, rebuild scoped meshes and active index, and reconcile observations admitted during the transaction through bounded post-commit receipts.
- [x] 7.4 Add zero-residual audits proving normal runtime has no legacy semantic reader/writer, unbound eligible card, projection mismatch, stale revision, retired relation authority, alternate store/model, compatibility alias, or fallback success path.
- [x] 7.5 Implement rollback/resume/interruption/concurrent-change handling that restores one complete prior generation or completes the current one and keeps all four retained automations paused on failure.
- [x] 7.6 Integrate the migration and structured model-authority checklist into `scripts/install_codex_kb.py` install/upgrade/check paths, including fresh clone bootstrap and moved-repository behavior.
- [x] 7.7 Add migration matrix tests for fresh, already-current, mixed legacy/current input, sparse cards, bad relations, private cards, malformed input, missing ResearchGuard logic, interruption at each publication boundary, resume, repeat, concurrency, rollback, Windows paths, and zero residuals.
- [x] 7.8 Direct-migrate complete retired `logicguard.model-store.v1` / `logicguard.model-mesh.v1` authority into current ResearchGuard logic schemas with frozen full-tree inventories, before/after counts and hashes, zero old-schema residuals, exact card/scope coverage, and failure-injection rollback at every publication boundary.

## 8. Align Skills, prompts, author contracts, consumer projections, UI copy, and documentation

- [x] 8.1 Update repo-managed `local-kb-retrieve`, `kb-sleep-maintenance`, `kb-dream-pass`, `khaos-brain-update`, organization contribution/maintenance, and global preflight prompt surfaces to state the model-native contract and exact ownership/handoff rules.
- [x] 8.2 Use author-side SkillGuard maintenance supervision to compile each single-skill source inventory into current `.skillguard/contract-source.json`, `.skillguard/compiled-contract.json`, and `.skillguard/check-manifest.json`; validate unique target-owned depth without creating a consumer dependency.
- [ ] 8.3 Refresh clean installed Skill and automation projections transactionally, exclude author-control material, verify consumer-projection parity, and preserve user pause state.
- [x] 8.4 Rewrite PROJECT_SPEC as the authoritative LogicGuard-native design, update README architecture/use/upgrade sections, AGENTS managed guidance, migration/recovery runbooks, UI help/status text, and release notes without retaining YAML-as-authority language.
- [x] 8.5 Add static and behavior tests that fail on stale architecture wording, missing ResearchGuard logic dependency declarations, Dream write authority, flat retrieval fallback, legacy schema guidance, author-control leakage, cross-unit test overlap, or installed-projection drift.
- [x] 8.6 Remove the repository-local FlowGuard shadow Skill suite only through its exact ownership manifest, retire the compatibility verifier and suite-control paths, preserve all Khaos-owned project Skills, and enforce the ordinary-project boundary in current-runtime readiness.

## 9. Run layered verification and close the change

- [x] 9.1 Run affected focused child suites after each repair batch; preserve failed/skipped/not-run/timeout evidence and rerun only obligations invalidated by changed components.
- [ ] 9.2 Run the current FlowGuard child model, all calibrated known-bad variants, field lifecycle review, parent ModelMesh reattachment/closure, Model-Test Alignment, UI flow validation, and TestMesh inventory checks; consume current evidence ids in the parent process review.
- [x] 9.3 Run strict OpenSpec validation and verify every required obligation maps bidirectionally to one code owner, current test evidence, and the frozen child-suite inventory.
- [ ] 9.4 Freeze source, tests, models, prompts, Skills, package/toolchain, environment, and inventory identities; confirm no active writer/child process exists; execute `python scripts/check_khaos_logicguard_native_readiness.py --json` exactly once as the final full owner.
- [ ] 9.5 Verify the terminal parent receipt consumes current terminal child receipts for the complete ResearchGuard package / exact logic-member API, model/projection, Sleep/Dream, retrieval/UI, migration/privacy, scale/performance, clean installer projection, zero residuals, and existing Chaos Brain regressions; keep the author contract audit separate.
- [ ] 9.6 Run `python scripts/install_codex_kb.py --json` and `python scripts/install_codex_kb.py --check --json` on the stable integration snapshot; prove FlowGuard and ResearchGuard logic are each frozen to one exact digest for long-assurance children, confirm clean installed skills and all four retained automations' intended pause state, and rerun only the explicitly invalidated installation projection if packaging changed.
- [ ] 9.7 Perform the explicit KB postflight, record mistake-first reusable lessons or route/card weaknesses as structured observations, update FlowGuard adoption evidence, and report any deliberately scoped release gaps without marking the OpenSpec change complete.
