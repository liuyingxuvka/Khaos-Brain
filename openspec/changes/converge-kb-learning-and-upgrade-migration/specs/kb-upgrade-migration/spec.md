## ADDED Requirements

### Requirement: Direct-to-current cross-machine upgrade migration
Chaos Brain SHALL persist `software_version`, `maintenance_standard_version`, and `history_schema_version` in machine-readable installation state. On the current computer and any other computer upgraded from an older installation, the upgrader SHALL run the one current direct migrator over the discovered old managed surface, write only the canonical target form, remove every old runtime authority, and prove zero residual. Copying current files without this migration receipt MUST NOT satisfy upgrade completion, and normal software MUST NOT contain intermediate-version readers.

#### Scenario: Old computer upgrades across multiple versions
- **WHEN** a computer reports versions older than the Architect-retirement and history-debt standards
- **THEN** the upgrader MUST inventory every affected old software, maintenance, and history surface, apply the current dependency-ordered direct migration plan, and require one receipt for each canonicalization step before installing the target state

#### Scenario: Current computer runs the upgrader again
- **WHEN** all three installed versions already match the target and managed fingerprints are unchanged
- **THEN** the upgrader MUST perform an idempotent verification-only run, MUST create no duplicate component or migration effect, and MUST emit a no-delta upgrade receipt

### Requirement: Normal runtime has no compatibility or fallback authority
After upgrade commit, every Chaos Brain entrypoint SHALL recognize exactly one current managed schema, command grammar, installed Skill authority, active-index authority, organization layout, automation model policy, and update-state workflow. Old shapes MAY be inspected only inside the bounded direct migrator. Daily modules MUST NOT dual-read, dual-write, convert on demand, alias old fields or arguments, repair exact obsolete states, or return success through an alternate path after the current authority fails. Missing current authority MUST produce a visible non-success and MUST keep affected automations paused when installation or maintenance integrity is involved.

An incompatible residual discovered by the upgrade SHALL remain an open upgrade-AI obligation rather than a product compatibility requirement. The upgrade AI MUST use captured evidence to add or select one bounded direct-to-current migration decision, retry inside the rollbackable transaction, and prove zero residual before completion. If the evidence is insufficient for a safe decision, the transaction MUST remain paused and incomplete; it MUST NOT activate automations or close by adding a runtime reader, converter, alias, alternate authority, or fallback.

#### Scenario: Old organization layout exists during upgrade
- **WHEN** the upgrader discovers schema-v1 `kb/trusted` or `kb/candidates` organization roots
- **THEN** it MUST move their content into the sole schema-v1 `kb/main`, create `kb/imports`, rewrite the manifest, remove the old roots and keys, and prove the current validator has no old-layout reader

#### Scenario: An obsolete organization root reaches any normal consumer
- **WHEN** ordinary multi-source reading, contribution deduplication, organization-card adoption, or the installed GitHub repository checker sees `kb/trusted`, `kb/candidates`, a missing `kb/main`, or an inexact current manifest
- **THEN** that consumer MUST report visible non-success and MUST NOT ignore the residual, read it, reinterpret it as `kb/main`, or validate an alternate layout; only the direct upgrade migrator may settle the old material

#### Scenario: Current active index is absent during a query
- **WHEN** routine retrieval cannot validate the current active index or committed maintenance standard
- **THEN** it MUST return a visible unavailable error and MUST NOT scan cards, lifecycle history, or an older index for results

#### Scenario: Current provider facts are unavailable during automation install
- **WHEN** no explicit override, current provider cache, or current Codex configuration can establish the model or reasoning policy
- **THEN** installation MUST block and MUST NOT insert a fixed model slug or effort as a backup

#### Scenario: Removed launcher grammar is invoked
- **WHEN** an installed launcher is called without an explicit subcommand or with a removed argument alias
- **THEN** it MUST reject the call and MUST NOT reinterpret it as a current search request

#### Scenario: A selected desktop runtime is unavailable
- **WHEN** the current desktop launcher or exact managed shortcut explicitly selects `source` or `release` and that selected entry is unavailable
- **THEN** it MUST report non-success and MUST NOT probe alternate executable locations, switch between source and release, or reinterpret the removed `--prefer-python` argument

#### Scenario: Retired desktop settings fields exist
- **WHEN** upgrade finds an exact pre-schema settings document or retired `maintainer_*` fields
- **THEN** the upgrader MUST snapshot and rewrite them into the complete current schema, remove every old key, and emit a residual-zero receipt; daily settings readers and UI writers MUST reject or omit those old keys

#### Scenario: Exact old and current desktop settings conflict
- **WHEN** an old `maintainer_*` value disagrees with its exact current `organization_maintenance_*` replacement
- **THEN** deterministic migration MUST block without mutation until the upgrade AI explicitly selects one value present in the captured inputs and records the reason, old value, current value, selected value, and before/after hashes; normal runtime MUST NOT make or reuse that decision

#### Scenario: Retired Skill guidance field aliases exist
- **WHEN** an active card uses `skill_fallback`, `fallback`, `without_skill`, or `fallback_guidance` as a Skill dependency guidance field
- **THEN** the upgrader MUST move the one unambiguous value into `unavailable_skill_guidance`, remove every alias, and block on conflicting values; daily contribution code MUST read only the current field

#### Scenario: Obsolete update failure remains from a prior install
- **WHEN** upgrade finds the exact former SkillGuard-installation-identity failure state and the current installation identity is proven
- **THEN** the migration phase MUST settle it once with a receipt before activation, and the scheduled runtime wrapper MUST contain no repair branch for that former state

#### Scenario: Pre-schema update state remains from an older installation
- **WHEN** upgrade finds the exact schema-less managed update-state document
- **THEN** the upgrade migration MUST rewrite it once into the complete current schema before aggregate assurance can invoke the current-only update owner, emit a residual-zero receipt, and restore the exact prior bytes if any later installation gate rolls back; the daily update reader MUST report any pre-schema, incomplete, unknown-field, or unknown-schema document as a visible non-success and MUST NOT normalize it into a successful current state

#### Scenario: Upgrade discovers an unhandled incompatible residual
- **WHEN** the bounded migrator inventories an old managed shape that has no safe current disposition yet
- **THEN** the upgrade MUST remain incomplete and paused while the upgrade AI derives an evidence-bound direct-to-current disposition and retries; normal software MUST NOT gain a compatibility or fallback branch to make the residual appear acceptable

### Requirement: Complete retirement of KB Architect
The target Chaos Brain version SHALL have no active KB Architect lane, Skill, automation, prompt route, queue owner, handoff target, update-gate name, health-rollup owner, release dependency, or completion dependency. Responsibilities formerly owned by Architect MUST be reassigned to explicit surviving owners before upgrade completion, and historical Architect material SHALL be inert cold history rather than an executable or retrievable maintenance surface.

#### Scenario: Former update gate is evaluated after retirement
- **WHEN** an available update has been prepared and the desktop is closed on the target version
- **THEN** the recovery-oriented update owner MUST evaluate and execute the update without invoking `architect_update_check`, an Architect Skill, or an Architect automation

#### Scenario: Readiness is evaluated after retirement
- **WHEN** Sleep, Dream, install, organization, migration, and assurance evidence are available
- **THEN** the readiness owner MUST aggregate those current receipts without requiring an Architect report, Architect queue, or Architect-named state

#### Scenario: Historical Architect evidence remains on disk
- **WHEN** the upgrade encounters Architect run reports, proposal queues, handoff records, or maintenance rollups that must be retained
- **THEN** it MUST route them through the history-debt cold archive, MUST preserve their audit provenance, and MUST prevent them from driving current maintenance or retrieval

### Requirement: Automatic Architect removal on legacy upgrades
An upgrade from any pre-retirement installation SHALL automatically remove the repository-managed KB Architect automation, installed `kb-architect-pass` Skill tree, registered lane and lock state, installer manifest entries, routing entries, queue and handoff bindings, and active update or completion dependencies. Discovery SHALL recognize exact managed identifiers and known managed fingerprints even when a legacy manifest is incomplete. Removal MUST be idempotent and MUST NOT delete a user-owned component merely because it has a similar name.

#### Scenario: Legacy machine has the managed Architect components
- **WHEN** the upgrader finds the managed KB Architect automation and `kb-architect-pass` Skill on an older computer
- **THEN** it MUST remove both automatically, MUST remove their registered active bindings, and MUST verify their absence before the upgrade can succeed

#### Scenario: Legacy manifest is missing an Architect entry
- **WHEN** an exact known managed Architect artifact is present but the old installation manifest does not list it
- **THEN** the upgrader MUST identify it by its managed identifier or verified fingerprint, MUST remove it, and MUST record the discovery method in the migration receipt

#### Scenario: User component has a similar Architect name
- **WHEN** an automation or Skill has a similar name but does not match a Chaos Brain-managed identifier, ownership record, or known fingerprint
- **THEN** the upgrader MUST leave it unchanged and MUST list it as outside the managed removal boundary

### Requirement: Architect retirement checks only the active Codex registry
Architect absence and SkillGuard routing checks SHALL resolve exactly the active current registry projected by the current `$CODEX_HOME/AGENTS.md`. If that projection is missing, unreadable, stale, or Architect-containing, retirement verification MUST fail; no alternate registry may supply authority. A registry in an unrelated repository or old installation is inert external history and MUST NOT block a clean active installation or be modified by this upgrade.

#### Scenario: An unrelated stale registry still contains Architect
- **WHEN** the current Codex registry is readable and contains no Architect route but an unrelated historical registry still names `kb-architect-pass`
- **THEN** retirement verification MUST pass, MUST identify the active registry in its receipt, and MUST leave the unrelated registry unchanged

#### Scenario: The active registry still contains Architect
- **WHEN** the registry projected by the current Codex home contains `kb-architect-pass` or cannot be read
- **THEN** retirement verification MUST fail before automation restoration and MUST report that exact active path

### Requirement: Fresh installations omit Architect
A fresh Chaos Brain installation SHALL initialize the current software, maintenance-standard, and history-schema versions without creating any Architect Skill, automation, lane, prompt, queue, update gate, or manifest entry. Installation verification MUST fail if any retired Architect surface is introduced by the installer, packaged assets, global router, or automation template.

#### Scenario: Install on a computer with no prior Chaos Brain state
- **WHEN** the current version is installed on a computer with no legacy installation
- **THEN** the installer MUST provision only current surviving components, MUST initialize current version state, and MUST verify that no Architect surface exists

#### Scenario: Packaged asset still references Architect
- **WHEN** a fresh-install staging tree contains an Architect Skill, automation, route, prompt, or required dependency
- **THEN** installation validation MUST fail before commit and MUST NOT publish the staged tree

### Requirement: Final SkillGuard router refresh is durable and currently fresh
Every real install or upgrade SHALL durably journal the router-refresh result before aggregate assurance and SHALL refresh again after the last transaction that can replace any managed Skill tree. The final success boundary MUST bind the final refresh receipt, active SkillGuard and global-router surface fingerprints, registry hash, managed AGENTS projection, installation transaction id, and current official `check-global-registry` plus `check-global-prompt` results. A prompt that still matches an older registry, a refresh result held only in process memory, or a registry generated before a later Skill-tree replacement MUST NOT satisfy completion. A failed attempt MUST preserve its checkpoint receipt separately without overwriting the last-known-good install manifest.

#### Scenario: Aggregate assurance fails after router refresh
- **WHEN** the router refresh succeeds but aggregate assurance fails before the install manifest can be committed
- **THEN** the upgrader MUST retain a durable refresh checkpoint and failed-attempt receipt, MUST keep all five surviving automations PAUSED, MUST preserve the last-known-good install manifest, and MUST report assurance failure rather than falsely reporting that refresh never ran

#### Scenario: A Skill tree changes after refresh
- **WHEN** SkillGuard, the global router, or another scanned Skill tree changes after a passing refresh and before final installation closure
- **THEN** the prior registry receipt MUST become stale, the upgrader MUST refresh and run both official live freshness checks again, and bounded repeated drift MUST fail safely with all survivors PAUSED

#### Scenario: Prompt matches a stale registry
- **WHEN** the managed AGENTS block matches its saved registry but that registry no longer matches the active Skill trees
- **THEN** installation verification MUST fail the live-registry gate even though the prompt check alone passes

### Requirement: User pause state is preserved for surviving automations
Before changing managed automations, the upgrader SHALL capture both the exact runtime status and the independent `user_paused` value of each of the five surviving Chaos Brain automations and SHALL pause all five for the transaction. They MUST remain paused through migration, installation, the first update authorization check, construction of the exact restoration plan, and the final composed SkillGuard check. The restoration plan SHALL bind the five source hashes, five target hashes, prior states, target states, and plan hash without mutating the live automations. Only after that final check passes may the upgrader apply the exact plan and read back every status, `user_paused` value, and target hash. Any source drift, apply failure, or read-back mismatch MUST pause all five and fail the upgrade. The retired Architect automation MUST remain absent regardless of its prior state, and an unknown prior state MUST resolve to paused with a receipt blocker rather than guessed enablement.

#### Scenario: User paused Dream before upgrade
- **WHEN** Dream was user-paused and Sleep was enabled before the upgrade
- **THEN** a successful upgrade MUST leave Dream paused with its exact recorded `user_paused` value, MUST restore Sleep to enabled only after the final composed SkillGuard gate passes, and MUST record both before-and-after runtime states and hashes

#### Scenario: Architect was enabled before upgrade
- **WHEN** the legacy Architect automation was enabled before migration
- **THEN** the upgrader MUST remove it and MUST NOT recreate or restore it while restoring the surviving automation states

#### Scenario: Prior automation state cannot be established
- **WHEN** the upgrader cannot prove whether a surviving automation was enabled or user-paused before the transaction
- **THEN** it MUST leave that automation paused, MUST record the ambiguity, and MUST prevent a fully successful readiness claim until the state is resolved

#### Scenario: Final SkillGuard validation is still running
- **WHEN** migration and installation have passed but the final composed update route has not produced a current terminal closure
- **THEN** all five surviving automations MUST remain paused and the exact restoration plan MUST remain unapplied

#### Scenario: A staged automation changes after authorization
- **WHEN** any live source hash, planned target hash, runtime status, or `user_paused` value differs from the hash-bound restoration plan before activation
- **THEN** the upgrader MUST reject the plan, MUST keep all five automations paused, and MUST require a new current authorization rather than activating stale intent

#### Scenario: Restoration apply or read-back fails
- **WHEN** any of the five exact restoration writes fails or its status, `user_paused` value, or file hash cannot be read back exactly
- **THEN** the upgrader MUST pause all five, MUST enter the failed state, and MUST NOT mark the software update `CURRENT`

#### Scenario: Current-machine all-paused operator override
- **WHEN** this machine has a current immutable aggregate receipt, all five scheduled-production SkillGuard completions, and the user explicitly requires every retained automation to remain stopped
- **THEN** the final operator transaction MUST stage one exact five-member plan with `PAUSED` and `user_paused=true`, apply and read back the whole group, emit an immutable machine receipt, and block completion if any member is active, has a false pause bit, differs from the plan, or fails final install health

### Requirement: Transactional Skill and integration installation
The upgrader SHALL stage complete repository-managed Skill trees, automation definitions, global defaults, manifests, and integration metadata outside the live installation, SHALL validate the staged set, and SHALL commit it atomically while retaining a rollback reference to the prior live set. Before long validation, it SHALL copy the complete executable current SkillGuard tree plus the complete imported current FlowGuard and LogicGuard packages into three immutable manifest-bound snapshots, SHALL route every compiler, router, depth, model, and child-test consumer through those snapshots, and SHALL recheck all three final live identities. The transaction receipt SHALL use a versioned schema with complete source, staged, installed, and post-operation manifests plus an immutable replay record. Validation MUST prove current-compiler and target-owned contract currentness plus source-to-install parity for every declared file, MUST reject any incomplete or unvalidated incoming hard authority, and MUST clean abandoned staging and bounded obsolete backups only after a safe receipt boundary. A current active tree SHALL still receive semantic hard-authority comparison. That comparison MUST project checks onto covered obligations, evidence classes, and mandatory owners: a renamed, merged, split, or reorganized check set MAY replace the active set only when the incoming semantic hard authority is a superset, while any lost obligation, evidence class, or mandatory owner remains a downgrade. A conditional scheduled-production depth wrapper MAY be removed only when its declared independent hard dependency remains semantically unchanged, remains required by the same conditional obligation, and every active closure profile still requires that obligation. Check-identifier, native-route, and depth-dimension subset preservation MUST NOT be used as proxies for capability preservation. An absent or non-current exact managed tree SHALL be preserved only as rollback material and replaced as a whole; the upgrader MUST NOT interpret it through predecessor hashes, compatibility conversion, renewal, retirement proof, alias, or fallback execution.

#### Scenario: Global SkillGuard is replaced during long assurance
- **WHEN** the live global SkillGuard directory is temporarily unavailable or replaced after the validation snapshot is frozen
- **THEN** every check in the active upgrade MUST continue against the exact frozen snapshot, MUST NOT mix tool identities, and MUST keep all five automations paused if the final live identity differs from the frozen receipt

#### Scenario: Editable FlowGuard changes during long assurance
- **WHEN** the imported live FlowGuard package changes after its validation snapshot is frozen
- **THEN** every model and child check in the active upgrade MUST continue against the exact frozen package, MUST NOT mix package identities, and MUST keep all five automations paused if the final live identity differs from the frozen receipt

#### Scenario: Editable LogicGuard changes during long assurance
- **WHEN** the imported live LogicGuard package or its editable-install target changes after its validation snapshot is frozen
- **THEN** every migration, model, mesh, projection, retrieval, Dream, and child check in the active upgrade MUST continue against the exact frozen package, MUST NOT mix package identities, and MUST keep all five automations paused if the final live identity differs from the frozen receipt

#### Scenario: Staged Skill tree passes validation
- **WHEN** every staged managed file matches its authoritative source fingerprint, all required files are present, and SkillGuard depth is not reduced
- **THEN** the upgrader MUST atomically publish the complete staged set and MUST retain the previous live-set reference until post-commit verification succeeds

#### Scenario: Partial Skill copy is staged
- **WHEN** a staged Skill is missing a referenced file, nested contract, check manifest entry, or required asset
- **THEN** the upgrader MUST reject the entire staged transaction and MUST leave the prior live installation unchanged and paused

#### Scenario: Staged SkillGuard contract is weaker
- **WHEN** the staged contract or check manifest would remove an installed hard gate, reduce the declared contract depth, or replace current runtime evidence requirements with a shallower legacy contract
- **THEN** the upgrader MUST fail validation, MUST preserve the stronger contract, and MUST record the prevented downgrade

#### Scenario: Native checks are reorganized without semantic loss
- **WHEN** a current staged contract renames, merges, splits, or removes native check identifiers while its validated native-check projection still covers every active obligation with every active evidence class
- **THEN** the upgrader MUST accept the semantic comparison, MUST record the new whole-tree authority, and MUST NOT falsely block the upgrade merely because an old check identifier is absent

#### Scenario: Native-check reorganization loses semantic coverage
- **WHEN** a native check reorganization leaves any previously covered obligation or evidence class without incoming native coverage
- **THEN** the upgrader MUST classify the change as a downgrade, MUST preserve the prior tree, and MUST keep all surviving automations paused

#### Scenario: Conditional depth wrapper moves to its independent owner
- **WHEN** a conditional depth wrapper is removed to break an evidence cycle, its declared independent hard dependency remains semantically unchanged, the conditional obligation still requires that dependency, and every active closure profile still requires the obligation
- **THEN** the upgrader MUST record an exact replayable ownership-reorganization proof and MAY accept the current-to-current replacement without treating the removed wrapper, route, or dimension membership as lost capability

#### Scenario: A non-current managed Skill is upgraded
- **WHEN** an exact managed Skill path contains absent, partial, or former authority while the incoming whole tree has current compiler, generator, depth-calibration, manifest, and parity evidence
- **THEN** the upgrader MUST preserve the old tree only as rollback material, replace it as a whole, and record the non-current disposition without reading it as execution or migration authority

#### Scenario: An older receipt is replayed after schema upgrade
- **WHEN** an interrupted or committed pre-current installation receipt is encountered during a later upgrade
- **THEN** the upgrader MUST recover or preserve it as inert historical evidence without converting its authority payload, then issue a new current transaction receipt without losing source, staged, installed, post-operation, rollback, or incoming-currentness evidence

### Requirement: Failure preserves a safe paused state
The upgrade state machine SHALL enter `maintenance-migrating` before mutation and SHALL not enter a successful current state until Architect removal, history migration, installation commit, index rebuild, and all required validations pass. Any failure, timeout, interruption, stale evidence, or unresolved concurrent write SHALL leave all covered maintenance automations paused and SHALL either roll back to the verified pre-upgrade artifacts or preserve a resumable failed checkpoint. A failed or rolled-back attempt MUST NOT automatically resume maintenance.

The maintenance migration lock SHALL publish a versioned owner identity and current heartbeat while held. A live recorded owner or a recent ownerless legacy lock MUST NOT be displaced. A recorded dead owner, or an old ownerless legacy lock for which no matching migration process exists, MAY be atomically quarantined and recovered only with a durable reason-bound recovery receipt. Lock recovery MUST be idempotent and MUST NOT recreate or remove a lock owned by another process.

#### Scenario: Architect removal fails
- **WHEN** any managed Architect surface cannot be removed or its absence cannot be verified
- **THEN** the upgrade MUST enter or remain failed, MUST keep surviving maintenance automations paused, and MUST NOT claim the target maintenance standard

#### Scenario: An interrupted old migration left an ownerless lock
- **WHEN** the legacy lock is older than the declared grace boundary and no matching migration process is running
- **THEN** the upgrader MUST quarantine it atomically, write a recovery receipt, acquire a new owner/heartbeat lock, and resume from the durable checkpoint

#### Scenario: A migration lock may still be live
- **WHEN** its recorded owner is alive or an ownerless legacy lock is still recent
- **THEN** the upgrader MUST fail closed without stealing or deleting the lock and MUST keep all five automations paused

#### Scenario: History migration fails after install staging
- **WHEN** staged integration artifacts are valid but the required history-debt migration fails or remains incomplete
- **THEN** the upgrader MUST NOT commit success, MUST retain or restore the verified live artifacts according to the transaction checkpoint, and MUST keep maintenance paused for a resumable retry

#### Scenario: Upgrade is interrupted and restarted
- **WHEN** an interrupted upgrade has a valid persisted checkpoint and unchanged covered fingerprints
- **THEN** the next run MUST resume from that checkpoint, MUST avoid repeating committed effects, and MUST keep automations paused until the complete target state is verified

#### Scenario: Installation transaction committed before a later gate fails
- **WHEN** the managed installation transaction has committed but final router freshness, aggregate assurance, or post-install verification fails
- **THEN** the state machine MUST record a recoverable post-commit failure checkpoint, MUST not ignore the failure merely because commit occurred, MUST keep or return all five survivors to PAUSED, and MUST require a current retry before success

### Requirement: Upgrade mutation boundary protects concurrent work
The upgrader SHALL mutate only declared Chaos Brain-owned installation, automation, migration, and history surfaces. It SHALL compare precondition fingerprints immediately before each commit or deletion; a peer or user change after inventory MUST invalidate that action, preserve the changed path, and keep the upgrade paused for reconciliation rather than overwriting, reverting, formatting, or broadly cleaning unrelated workspace changes.

#### Scenario: Another agent changes a covered file during staging
- **WHEN** a live covered file no longer matches the fingerprint captured before staging
- **THEN** the upgrader MUST abort that commit, MUST preserve the newer file, and MUST record a concurrent-writer conflict for resumable reconciliation

#### Scenario: Unrelated repository changes are present
- **WHEN** the working tree contains changes outside the declared upgrade mutation set
- **THEN** the upgrader MUST leave those changes untouched and MUST evaluate upgrade readiness only against the declared managed surfaces

### Requirement: Current-evidence upgrade gates
Upgrade completion SHALL require current passing evidence for the applicable history migration, Architect absence, transactional installation, source-to-install parity, active-index integrity, FlowGuard ownership and transition checks, SkillGuard contracts, retrieval regressions, and model or integration regressions. Evidence that is stale, skipped, failed, timed out, still running in the background, progress-only, or passing with unresolved gaps MUST NOT satisfy the completion gate.

#### Scenario: Background regression is still running
- **WHEN** implementation work is complete but a required background model or regression run has not produced its final artifact and successful exit status
- **THEN** the upgrader MUST keep the upgrade incomplete and maintenance paused until current final evidence is available

#### Scenario: FlowGuard still requires Architect ownership
- **WHEN** a current FlowGuard model or conformance result still names Architect as an active update, rollup, lane, queue, handoff, or completion owner
- **THEN** the upgrade gate MUST fail and MUST require the model and implementation ownership to be reconciled before success

#### Scenario: All required gates pass on current artifacts
- **WHEN** every required evidence record covers the committed target fingerprints and has a final passing status with no hard gap
- **THEN** the system MUST first authorize the exact staged restoration plan through the final composed SkillGuard route, then apply and read back that exact plan, and restore only the surviving automations that were enabled before upgrade

### Requirement: Upgrade migration receipt and success boundary
Every fresh install, upgrade, resume, rollback, and idempotent no-delta run SHALL emit an encoding-stable machine receipt. The receipt SHALL record before-and-after versions and fingerprints, migration order and checkpoints, staged and committed artifact identities, Architect discoveries and removals, preserved automation status and `user_paused` values, the hash-bound restoration plan, authorization and finalization SkillGuard closures, exact activation read-back, the history-migration receipt, index identity, validation evidence, concurrent-write decisions, rollback or resume state, residual debt, and final status. A target-version file copy, version-number update, authorization-only closure, or unapplied restoration plan without this current receipt MUST NOT be reported as a completed Chaos Brain upgrade.

#### Scenario: Legacy upgrade completes successfully
- **WHEN** all migrations, removals, commits, validations, and state restorations pass for the committed target fingerprints
- **THEN** the system MUST emit a successful receipt proving Architect absence, cleared history hard debt, current active index, source-to-install parity, and the final state of every surviving automation

#### Scenario: Upgrade remains incomplete
- **WHEN** any required migration, removal, validation, pause-state restoration, or receipt reference is missing or non-passing
- **THEN** the system MUST emit an incomplete or failed receipt with the blocking checkpoint and residual obligations, MUST keep maintenance paused, and MUST NOT identify the target upgrade as complete
