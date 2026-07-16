## ADDED Requirements

### Requirement: Every assurance obligation has one primary owner
The system SHALL maintain a versioned assurance-owner registry in which every runtime, migration, installation, Skill, model, test, parity, and completion obligation has exactly one primary owner and one authoritative receipt type. FlowGuard MUST own behavioral state, transition, invariant, liveness, loop, and replay obligations. SkillGuard MUST own Skill route, integration-boundary, contract, checker, and closure obligations. The migration runner MUST own migration-state receipts. The installer MUST own transactional installation, complete managed-tree manifests, source/staged/installed parity verdicts, anti-downgrade decisions, and managed-automation receipts. The final readiness evaluator MUST own only aggregation of the primary-owner receipts. CI SHALL invoke these owners and MUST NOT reimplement a competing pass path.

Model-test alignment SHALL reference only logical validation-owner ids declared by that registry; raw receipt producer names are implementation details and MUST NOT be used as alignment lookup keys. A missing or unknown logical owner MUST become explicit non-passing evidence and a failed aggregate gate, never an uncaught exception or an implicit alternate owner.

#### Scenario: Alignment names a raw or unknown validation owner
- **WHEN** an alignment obligation uses a leaf receipt producer name directly or names an owner absent from the logical registry
- **THEN** the aggregate MUST return a structured failed alignment with no evidence for that obligation, keep all automations paused, and MUST NOT crash or select a fallback receipt

#### Scenario: The ownership registry is complete
- **WHEN** runtime assurance resolves every requirement in the upgrade verification contract
- **THEN** each requirement maps to exactly one primary owner, one native checker entrypoint, and one authoritative receipt schema

#### Scenario: Two checkers claim primary ownership
- **WHEN** the registry assigns the same obligation to more than one primary owner or leaves it unowned
- **THEN** assurance fails before evidence aggregation and reports the ownership conflict or gap

### Requirement: FlowGuard evidence comes from a current executable run
FlowGuard SHALL execute the current model against the current runtime projection and the declared positive, negative, replay, progress, and stuck-loop cases. Its receipt MUST include the model digest, projection digest, FlowGuard package and schema versions, executed check IDs, counterexamples, skipped checks, blockers, and final status. A stored report whose digests do not match the current model and projection MUST NOT count as current evidence.

#### Scenario: Current FlowGuard checks pass
- **WHEN** the current model and current runtime projection execute every required check without a counterexample or skipped hard gate
- **THEN** FlowGuard emits a passing receipt bound to those exact digests and check IDs

#### Scenario: A model changes after a prior pass
- **WHEN** the FlowGuard model, projection binding, package version, or required check set differs from a stored passing receipt
- **THEN** assurance marks the receipt stale and requires a new executable run

#### Scenario: A required check is skipped
- **WHEN** a FlowGuard run omits a required replay, liveness, progress, invariant, or stuck-loop check
- **THEN** its receipt records the skip and cannot satisfy the final completion gate

### Requirement: SkillGuard closure uses current live checker receipts
SkillGuard SHALL run the native route, phase-order, evidence, quality, integration-boundary, and closure checks for both the repository source Skill and the staged or active installed Skill. Its receipt MUST bind the SKILL document, contract source, compiled contract, check manifest, checker scripts, required references, and executed outputs by digest. The repository source is the only compilation owner. Source-vs-installed execution authority MUST be derived only from the exact canonical source root or exact active Codex `skills/<skill-id>` root; surface labels are display-only, and a missing, unknown, or ambiguously resolved root MUST block before execution. An installed Skill is an immutable deployment projection: installed supervision MUST verify the current SkillGuard installation receipt, consume that installed tree's exact current compiled contract and check manifest, materialize one short content-addressed repository-local control projection containing only the exact installed current bytes, and execute the stable supervisor against the canonical repository target with its run state under that target. It MUST import the stable checker from a separate short repository-local content-addressed projection of the frozen current SkillGuard behavior files and current global-router sibling, exclude `.sg-runtime`, interpreter caches, and compiled bytecode, disable bytecode writes for the projection executor and its child Python processes, and require its official runtime fingerprint to equal the verified installed runtime fingerprint. It MUST NOT make correctness depend on a deeply nested Windows run path, pass an outside-repository installed root into a repository-owned executor, recompile the installed tree as another repository, substitute source bytes for installed bytes, accept label-derived execution authority, mutate the content-addressed behavior projection during import, or accept a behavior projection whose identity differs from installed currentness. A static `current_check_report` or closure assertion MUST NOT override a failing or stale live checker.

#### Scenario: Source and installed SkillGuard checks are current
- **WHEN** every required checker executes against source and installed trees whose digests match the receipt
- **THEN** SkillGuard emits one current closure receipt containing each check result and its exact input digest

#### Scenario: Installed Skill is outside the canonical repository
- **WHEN** the installer supervises a current Skill under the exact active Codex `skills` directory
- **THEN** supervision MUST replay the current SkillGuard installation identity, copy only the exact current installed control bytes into a short content-addressed repository-local projection, import the checker from a short behavior-only SkillGuard/global-router projection with no runtime state or caches, prove that projection's official fingerprint equals installed currentness, consume the installed current contract pair, and keep run state under the declared target; it MUST NOT execute the outside-repository root directly, compile that deployment as a second source repository, fall back to the repository copy, or accept an unverified or path-dependent runtime

#### Scenario: Frozen SkillGuard snapshot contains runtime state or is projected below a deep run root
- **WHEN** the validation snapshot contains `.sg-runtime` or interpreter caches, omits the current global-router sibling, differs from the verified installed runtime fingerprint, or would exceed the Windows path limit when nested below a scheduled run
- **THEN** supervision MUST exclude non-behavior files, materialize the complete behavior/router set at the short repository-local projection root, compare its official identity to installed currentness, and fail closed on any remaining mismatch rather than using a mutable live runtime or fallback

#### Scenario: Reusing a frozen SkillGuard projection after runtime import
- **WHEN** one scheduled supervision imports the content-addressed SkillGuard runtime and a later run reuses the same projection hash
- **THEN** both the parent executor and child Python processes MUST suppress bytecode writes, the projection file inventory and bytes MUST remain identical, and the later exact-inventory verification MUST succeed without rebuilding or reinstalling SkillGuard

#### Scenario: Scheduled display label does not identify execution authority
- **WHEN** a concrete scheduled run supplies an installed Skill root but its display label is `scheduled-guarded-*`, or a source run supplies an installed-looking label
- **THEN** the exact managed root MUST select the runner, the label MUST remain diagnostic only, and an unknown or ambiguous root MUST block rather than selecting either runner

#### Scenario: A live integration-boundary check fails
- **WHEN** the live checker reports a missing duplicate-path block, route conflict, stale reference, or another contract failure
- **THEN** SkillGuard closure is failed even if an older static report says `pass` or `closed_with_evidence`

#### Scenario: A Skill changes after closure
- **WHEN** any governed Skill, contract, manifest, checker, or required reference changes after the latest closure receipt
- **THEN** the receipt becomes stale and the final gate requires the SkillGuard checks to run again

### Requirement: Background automation completion is current declared-check supervised
Each retained background automation—Sleep, Dream, organization contribution, organization maintenance, and system update—SHALL run through one guarded scheduled entrypoint that invokes its native owner exactly once and writes an immutable native-output artifact for that concrete run id, command identity, payload hash, and receipt hash. Before the native owner starts, the current installed SkillGuard runtime MUST create one persistent official supervision session, verify the live installation once, freeze the exact behavior projection, target-control projection, sealed installation context, and scheduled-production identity, and bind the trigger, execution id, current installation receipt id/hash, portable installation receipt-root reference, and installed runtime fingerprint. The same retained authority MUST construct any target-native terminal and final closure after native execution without reloading live global SkillGuard currentness. Caller-authored identity fields are not authority; changing a supervised target Skill MUST NOT by itself reinstall global SkillGuard, and a newer live global or target identity is eligible only for the next scheduled execution.

Each target SHALL declare one exact current check inventory covering intake, native execution, terminal validation, target-owned positive and intentionally shallow fixtures, and any route-conditional terminal/finalization check. SkillGuard SHALL execute and reconcile only that declared inventory. The target Skill retains all domain obligations, applicability decisions, fixture meaning, native terminal construction, finalization behavior, and failure judgment. SkillGuard MUST NOT create a second domain route, a parallel executor, an alternate checker inventory, or a compatibility authority.

A terminal success MUST consume the exact current declared-check receipt and all required target-owned artifacts in the sole `enforced` closure. That closure MUST cover exactly the target obligation set, carry only `passed` or proof-bound `not_applicable` results, and MUST NOT rerun checks already executed by the staged request. Capability regressions and AST-resolved JUnit evidence prove that an installed version can perform the route; they remain separate from the immutable receipt proving that one scheduled execution actually ran.

Target-owned positive and shallow fixture checks SHALL exercise the same native receipt evaluator. The positive fixture MUST satisfy every applicable target obligation. The shallow fixture MUST omit or fail a named important target obligation and be rejected for that target-specific gap. A generic fixture, caller-authored pass flag, missing declared check, repeated check, stale installed identity, or proposal-only artifact is an explicit non-pass state.

System update has one non-terminal authorization stage and one terminal closure profile. For a prepared update, the first supervisor request SHALL run and reconcile the exact declared checks, emit a current non-terminal declared-check authorization receipt with `overall_complete=false`, and emit no closure. While every survivor remains PAUSED, the runner SHALL bind preserved status, `user_paused`, source hashes, exact target `automation.toml` hashes, the native receipt, that non-terminal authorization receipt, and the deferred install check into one immutable staged-restoration artifact. A fresh composed `authorize+finalize` request SHALL validate both native artifacts and obtain the sole `enforced` closure before the native executor may apply exact hashes, read back every state/hash, run the normal install check, mark CURRENT, and emit the activation receipt. The three legal no-op branches—`no-update`, `waiting-for-user`, and `ui-running`—skip restoration but still require their target-owned terminal receipt and the same sole `enforced` closure.

#### Scenario: A retained automation completes its native route
- **WHEN** the native owner reaches a receipt-backed completed or legal gated no-op terminal and every declared check and required artifact is current
- **THEN** the sole `enforced` closure consumes that exact declared-check receipt, and only then may the scheduled entrypoint return success

#### Scenario: Live SkillGuard changes while a long native run is executing
- **WHEN** a scheduled Sleep, Dream, organization, or update run has frozen a current official supervision session and the live global SkillGuard or installed target tree changes before native execution finishes
- **THEN** the current run MUST finish supervision with the exact start-frozen installation context, behavior projection, target-control projection, and six-field identity; it MUST NOT reload or reinstall global SkillGuard, mix identities, or accept the newer bytes for the current run, and the newer identity MAY be considered only when the next run freezes its own session

#### Scenario: Native receipt is created after the supervision session is frozen
- **WHEN** a scheduled native owner finishes and creates the current receipt, run identity, or update-finalization evidence after the persistent SkillGuard session has already frozen its static authority
- **THEN** the wrapper MUST project only the exact declared seven-key dynamic evidence set into that retained session, clear every missing declared key inherited by the worker, reject or filter every undeclared key, and close against the current receipt without reloading or reinstalling global SkillGuard

#### Scenario: Dynamic evidence is missing, stale, or undeclared
- **WHEN** the current native receipt is not projected, an absent declared key retains an older run's value, or an undeclared environment key is offered as supervision evidence
- **THEN** scheduled completion MUST fail closed; it MUST NOT accept stale evidence, broaden the environment boundary, rediscover live SkillGuard, reinstall a target-neutral guard, or fall back to repository source

#### Scenario: Aggregate assurance executes real scheduled production
- **WHEN** the aggregate has completed its repository-wide regression owner and ordinary read-oriented child checks
- **THEN** the child that executes real Sleep, Dream, organization, and update production routes MUST run on one exclusive resource lane, MUST NOT overlap performance-sensitive siblings, and MUST retain timeout and cleanup evidence independently from those siblings

#### Scenario: Start-frozen supervision cannot be established
- **WHEN** the official installation context, behavior projection, target-control projection, or six-field identity cannot be verified before native execution
- **THEN** the guarded entrypoint MUST fail before invoking the native owner and MUST NOT substitute a live post-native recheck, caller-authored identity, fallback runtime, or global reinstall

#### Scenario: The shallow target fixture is not discriminating
- **WHEN** the shallow fixture passes, fails only for a generic environment error, or omits no named important target obligation
- **THEN** target-owned fixture validation fails and SkillGuard cannot close the scheduled route

#### Scenario: Only intake, planning, capability tests, or a native payload exists
- **WHEN** a run stops before exact declared-check reconciliation and target terminal evidence
- **THEN** no `enforced` closure is emitted and the scheduled run remains incomplete

#### Scenario: A prepared update has only its first authorization receipt
- **WHEN** the native update and declared-check authorization stage pass but no current staged-restoration artifact and composed `authorize+finalize` enforced closure exist
- **THEN** the update remains incomplete, every live survivor remains PAUSED, and the runner MUST NOT restore ACTIVE states or mark CURRENT

#### Scenario: The authorization stage emits a closure
- **WHEN** prepared-update authorization writes any closure profile or claims overall completion
- **THEN** the update contract fails because authorization is only a non-terminal declared-check receipt

#### Scenario: Staged restoration changes after enforced authorization
- **WHEN** any live automation source hash, target hash, status, or `user_paused` value differs from the exact staged plan
- **THEN** native apply fails before activation, all survivors remain or return PAUSED, and the update is marked FAILED with the mismatched automation id

#### Scenario: A legal update no-op lacks enforced closure
- **WHEN** `no-update`, `waiting-for-user`, or `ui-running` has only target-native or non-terminal authorization evidence
- **THEN** the scheduled update remains incomplete until its exact terminal receipt is consumed by the sole `enforced` closure

#### Scenario: An operational blocker is mislabeled as successful no-op
- **WHEN** the update owner reports `already-upgrading`, `failed-awaiting-user`, `concurrent-update`, or another operational blocker
- **THEN** no successful no-op receipt or closure is admitted and the run remains blocked or retryable

#### Scenario: Maintenance contention is mistaken for an inapplicable no-op
- **WHEN** Sleep or Dream encounters an active shared maintenance lane
- **THEN** the native owner MUST wait and recheck or return an explicit retryable non-success; contention MUST NOT satisfy functional obligations

#### Scenario: Fixture or capability evidence is presented as a scheduled run
- **WHEN** evidence lacks the exact scheduler execution, current installation receipt, or installed runtime fingerprint
- **THEN** scheduled-production binding fails even if the software version passed its regression suite

### Requirement: Managed source and installed trees have exact declared parity
The installer SHALL produce deterministic manifests and the authoritative parity verdict for every managed source tree, staged tree, and active installed tree. Each manifest MUST include every declared managed path, normalized content digest, control/schema version, and explicit generated-file rule. SkillGuard SHALL contribute its governed control-tree digests and current checker receipt as installer inputs rather than issuing a competing parity verdict. Missing files, undeclared extra managed files, changed content, partial Skill trees, or an unexplained generated difference MUST fail parity. Parity MUST be checked after staging, after commit, and after rollback recovery.

#### Scenario: A complete staged tree matches source
- **WHEN** a staged installation contains the same declared managed paths and normalized digests as the source manifest
- **THEN** the staging parity receipt passes and the transaction can proceed to activation

#### Scenario: The installed copy is stale or incomplete
- **WHEN** an active installed Skill, automation, contract, checker, prompt, or manifest differs from the intended source tree
- **THEN** parity fails with path-level differences and the upgrade cannot be declared complete

#### Scenario: A generated file is intentionally different
- **WHEN** a generated installed artifact differs under a versioned transformation rule declared by its primary owner
- **THEN** parity validates the transformation input, rule version, and resulting digest instead of silently excluding the file

### Requirement: Installation accepts only current complete SkillGuard authority
The installer MUST bind every staged managed Skill to a current-compiler validation receipt, the target-owned generator/depth contracts, a complete current authority trio, and exact source/stage manifests before activation. The target-owned generator, current SkillGuard compiler, and each managed Skill source tree MUST retain the same content identity from immediately before through immediately after the validation that issues the receipt. It SHALL reject missing or concurrently replaced checkers, weakened incoming hard gates, incompatible or partial schemas, caller-authored validation, source drift during checking, and any tree whose validation inputs do not match the staged bytes. A current active tree SHALL still receive semantic hard-authority comparison. An absent or non-current exact managed tree SHALL be preserved only as rollback material and replaced as a whole; it MUST NOT be interpreted through predecessor hashes, compatibility conversion, renewal, retirement proof, alias, or fallback execution. A rejected incoming tree MUST leave the active installation and preserved automation pause state unchanged.

#### Scenario: An unvalidated or weaker incoming tree is offered
- **WHEN** the staged source lacks current compiler/generator/depth evidence, has missing required checks, weaker closure obligations, or validation inputs that differ from the staged bytes
- **THEN** the installer aborts before activation, records the currentness failure, and preserves the active tree

#### Scenario: A validation owner changes during receipt production
- **WHEN** the generator, current SkillGuard compiler, or managed Skill source tree has a different content identity after a validation than it had immediately before that validation
- **THEN** no validation receipt is issued, activation does not start, and every surviving automation remains paused for a later frozen-identity retry

#### Scenario: A current active tree would lose hard authority
- **WHEN** the active exact managed tree is current and the incoming tree removes a required checker, hard obligation, or closure binding
- **THEN** the semantic comparison blocks activation and preserves the current active tree

#### Scenario: A non-current exact managed tree is upgraded
- **WHEN** the active tree is absent, partial, or non-current and the incoming whole tree has current compiler, target generator/depth, manifest, and parity evidence
- **THEN** the installer records the non-current disposition, preserves the old bytes only as rollback material, and may replace the tree while all five automations remain paused

#### Scenario: Incoming currentness or receipt replay is partial or tampered
- **WHEN** a member/obligation/floor/stratum/capability/scope/protocol/input binding is missing or altered, the staged digest differs from validation, or replay does not reproduce the stored currentness disposition
- **THEN** the installer MUST block before activation, preserve the old tree, retain a retryable journal, and keep all five automations paused

### Requirement: Assurance freshness is bound to exact migration, installation, model, and test inputs
Every assurance receipt SHALL carry the source revision or source-tree digest, data snapshot or watermark, migration version and checkpoint, installation transaction ID, installed manifest digest, resolved model and reasoning policy, test-suite digest, test-data digest where applicable, execution time, and primary-owner version relevant to that receipt. Evidence is current only when these bindings match the final state under evaluation and the evidence was produced after the last mutation of that state. `skipped`, `not_run`, `unknown`, or a receipt from a different binding MUST NOT be treated as passed.

#### Scenario: Final files change after tests pass
- **WHEN** source, migration code, installed managed files, FlowGuard models, SkillGuard controls, model policy resolution, or required tests change after a passing receipt
- **THEN** every dependent receipt becomes stale and the affected owner checks must run again

#### Scenario: A cached receipt has identical content bindings
- **WHEN** a cached receipt matches every required immutable digest, version, policy resolution, and input watermark for the final state
- **THEN** assurance can reuse it as current evidence and records the content-addressed reuse in the aggregate receipt

#### Scenario: Only an unrelated aggregate sibling changes
- **WHEN** the repository-wide regression owner retains the exact source, verifier, command semantics, environment, canonical receipt bytes, proof hash, and parsed JUnit inventory while an unrelated aggregate sibling check is added or removed
- **THEN** the aggregate reuses the immutable owner receipt, records the source and consumer inventory revisions, and MUST NOT launch the repository-wide regression again

#### Scenario: A reusable regression proof is touched
- **WHEN** any owner input, canonical receipt byte, proof byte, or parsed JUnit field differs from the stored current receipt
- **THEN** reuse is rejected and the repository-wide regression owner executes once on its exclusive lane before any capability consumer starts

#### Scenario: Aggregate readiness is launched as a direct file
- **WHEN** the installer launches `scripts/check_chaos_brain_readiness.py` by file path rather than importing it as a package module
- **THEN** the aggregate MUST resolve the repository-owned model-test alignment module through the explicit repository root, MUST reject an unrelated or missing `scripts` namespace, and MUST remain paused before restore if that owner cannot be loaded

#### Scenario: Required evidence is not run
- **WHEN** any required migration, installation, model, parity, or test result is `skipped`, `not_run`, `unknown`, or missing
- **THEN** the final readiness state is incomplete or blocked and cannot be reported as passed

### Requirement: Former SkillGuard runtime authority has no surviving route
Each retained automation Skill SHALL expose only its current contract source,
compiled contract, and exact check manifest after current target-native positive
and intentionally shallow calibration pass. The repository, generator,
installation, and old-machine upgrade MUST remove the exact former work contract,
underscore check manifest, flat run records, and empty former runtime directories.
They MUST NOT preserve compatibility, conversion, renewal, retirement-receipt,
alias, or fallback authority, and MUST block if any such residual is reintroduced.

#### Scenario: All target-native currentness evidence is current
- **WHEN** one retained automation Skill has current contract-depth, positive `EXECUTION_DEPTH_PASS`, intentionally shallow `SHALLOW_BLOCKED`, exact native identity, and a clean former-runtime inventory
- **THEN** only the current authority trio remains and no separate retirement or migration lifecycle is created

#### Scenario: A former runtime file reappears
- **WHEN** a former work contract, underscore check manifest, or flat run record reappears
- **THEN** source audit, installation, and aggregate readiness fail with a residual-authority blocker and never use it as fallback evidence

#### Scenario: The current contract is regenerated
- **WHEN** an automation contract is regenerated after a legitimate implementation change
- **THEN** regeneration updates only the current authority trio and does not recreate former files, compatibility metadata, renewal state, or a retirement receipt chain

### Requirement: Model obligations and tests remain bidirectionally aligned
Every FlowGuard obligation and SkillGuard hard gate SHALL map to at least one current executable test or conformance case, and every upgrade-critical test SHALL map back to its primary model or contract obligation. The alignment manifest MUST include positive behavior, canonical bad cases, retry and interruption behavior, rollback behavior, and historical regression replays. A changed obligation or test MUST invalidate the prior alignment receipt.

#### Scenario: A new invariant is added to FlowGuard
- **WHEN** a runtime invariant is added or materially changed
- **THEN** the alignment gate requires a mapped positive case and at least one mapped violating or replay case before the model can contribute passing completion evidence

#### Scenario: A regression test has no declared owner obligation
- **WHEN** an upgrade-critical test cannot be traced to a FlowGuard, SkillGuard, migration, installer, retrieval, or lifecycle obligation
- **THEN** alignment fails and reports the orphan test instead of treating its isolated pass as assurance coverage

### Requirement: CI exercises the supported upgrade and failure matrix
CI SHALL execute the native primary-owner checks against the final source revision for fresh installation, supported legacy upgrade, repeated idempotent upgrade, interrupted migration resume, interrupted installation rollback, preserved pause state, managed-tree parity, anti-downgrade rejection, retrieval filtering, Sleep/Dream convergence, and final readiness aggregation. CI MUST preserve machine-readable receipts as artifacts and MUST fail the required check when any hard scenario fails or lacks current evidence.

#### Scenario: A supported upgrade path passes in CI
- **WHEN** a supported prior installation is upgraded through migration, staged installation, parity validation, and final readiness checks
- **THEN** CI publishes the linked native receipts and marks the upgrade matrix cell passed for the exact source revision

#### Scenario: An interruption path leaves partial state
- **WHEN** an interruption test detects an advanced watermark, partial active tree, lost pause state, duplicate mutation, or non-resumable migration checkpoint
- **THEN** CI fails and the change cannot use passing results from unrelated matrix cells as substitute evidence

#### Scenario: CI receives stale cached artifacts
- **WHEN** cached receipts do not match the final source, installed manifest, migration, model, or test bindings
- **THEN** CI reruns the owning checks or fails without accepting the stale artifacts

### Requirement: Aggregate assurance cannot recursively re-enter upgrade gates
The aggregate readiness evaluator SHALL be the sole outer owner of the real migration and installation gate sequence. Installer invocations exercised inside its regression suite MUST run as isolated fixtures that cannot acquire the real maintenance-migration lock, start another aggregate readiness run, alter live automation state, write the live Codex shell-tools directory, persist the user's PATH, or increment the real upgrade depth. The full repository regression MUST run in an exclusive validation lane after parallel non-overlapping gates finish; it MUST NOT overlap a model-alignment gate that runs the same installer fixtures. Direct product installation outside an aggregate child MUST retain the full migration and assurance gates by default.

#### Scenario: Full regression exercises the installer CLI
- **WHEN** the aggregate readiness suite runs an installer CLI grammar or encoding test
- **THEN** that child invocation MUST use isolated fixture semantics and MUST NOT recursively launch migration or another full regression

#### Scenario: Product installation starts normally
- **WHEN** a user or supported upgrade invokes the installer outside an aggregate-assurance child
- **THEN** the installer MUST run the versioned history migration and current aggregate assurance gates before restoring surviving automations

#### Scenario: Child context attempts real migration
- **WHEN** an aggregate child or isolated fixture attempts to enter the real migration state machine
- **THEN** the model and runtime MUST block the transition and preserve the outer upgrade's lock and pause state

#### Scenario: Fixture omits shell-tool isolation
- **WHEN** an aggregate child disables migration but does not declare a non-default Codex home, an explicit fixture-local shell-tools directory, and disabled user-PATH persistence
- **THEN** installation MUST fail before any global shell tool or user environment is written

#### Scenario: Full regression overlaps focused installer tests
- **WHEN** model-to-test alignment includes installer fixtures that also belong to the full regression
- **THEN** aggregate readiness MUST finish the parallel non-overlapping gates first and then run the full regression alone

### Requirement: Final readiness is a hard aggregate completion gate
The final readiness evaluator SHALL report the upgrade complete only when every verification-contract obligation has exactly one primary owner and a current passing receipt, the migration is at its committed terminal version, installation is transactionally committed, source/install parity passes, anti-downgrade checks pass, model/test alignment passes, the required CI matrix passes, and no hard blocker or skipped check remains. Because aggregate assurance can run long enough for peer AI work to admit new observations, the installer MUST then run a bounded post-assurance convergence loop that settles late debt, rebuilds and validates the active index, reruns retrieval-quality thresholds, and rechecks migration currentness before any restoration transaction. Surviving automations MUST remain paused until this gate passes, and only automations allowed by preserved user pause state and the upgraded policy can resume. The evaluator MUST emit a machine-readable aggregate receipt containing the complete evidence graph and all input digests.

#### Scenario: Every current assurance obligation passes
- **WHEN** the final evaluator receives current passing receipts for every declared owner and confirms the final migration and installed state
- **THEN** it emits `ready`, records the evidence graph, and permits only eligible surviving automations to resume

#### Scenario: Peer AI admits an observation during aggregate assurance
- **WHEN** a new observation invalidates lifecycle or active-index currentness while the long aggregate gate is running
- **THEN** the installer MUST keep all five survivors paused, settle the late debt through a receipt-backed bounded retry, rebuild the index, rerun retrieval thresholds, and recheck migration before restoration

#### Scenario: Post-assurance data does not converge
- **WHEN** the bounded post-assurance loop cannot obtain current migration, active-index, and retrieval evidence together
- **THEN** installation MUST end at a recoverable paused checkpoint and MUST NOT execute the final restoration transaction

#### Scenario: One required receipt is stale or failed
- **WHEN** any owner receipt is missing, stale, failed, skipped, blocked, or bound to a different final state
- **THEN** the evaluator emits `not_ready`, names the exact unsatisfied obligations, and keeps surviving automations paused

#### Scenario: A partial success report claims completion
- **WHEN** local tests, a model-only pass, an installation-only pass, or a historical closure exists without the remaining required current receipts
- **THEN** the completion gate rejects the claim and distinguishes checked, unchecked, blocked, and stale evidence in its receipt
