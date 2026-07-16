## Context

Chaos Brain has a working file-based predictive KB, but its maintenance throughput is inverted: 4,230 observations have produced hundreds of candidates while more than half of observations have no current card or maintenance disposition, formal trusted knowledge has barely grown, Dream repeats weak/no-delta experiments, and active retrieval still admits lifecycle states that should be terminal. Maintenance artifacts and local workspaces exceed twenty gigabytes and hundreds of thousands of files because each pass copies broad historical state.

The repository is already modeled by several FlowGuard files. Full existing-model preflight `kb-convergence-upgrade-20260711` found the current owners in `.flowguard`, `docs`, and `openspec` and returned `full_existing_model_preflight_can_continue`. This design therefore extends the existing Khaos Brain function/governance/maintenance boundaries and adds narrow child models for the new lifecycle and migration obligations; it does not create a competing maintenance controller.

The worktree is concurrently modified by other agents. Existing dirty files are preserved, changes are integrated against their latest content, and no rollback, checkout, broad formatter, or repo-wide generated rewrite may discard peer work.

## Goals / Non-Goals

**Goals:**

- Turn every observation and candidate into a timely, explicit, machine-consumable lifecycle decision.
- Make Sleep incremental and backlog reducing, and make Dream stop on unchanged evidence.
- Calibrate retrieval with current lifecycle state and real task outcomes.
- Migrate old history and maintenance debt into a small active surface plus bounded cold evidence.
- Retire Architect everywhere, including already-installed machines upgraded later.
- Make installation and migration staged, resumable, idempotent, downgrade-safe, and rollbackable.
- Make FlowGuard, SkillGuard, tests, install checks, and OpenSpec verification current hard gates.
- Leave exactly one current runtime authority for retrieval, organization layout, desktop settings, card Skill-guidance fields, automation model policy, installed Skill contracts, update state, command grammar, and each explicitly selected UI launch mode; old forms may be read only by the versioned upgrader and never by daily operation.
- Leave all five surviving automations paused through the final composed SkillGuard gate, then preserve or restore their exact prior runtime and user-pause state from a hash-bound plan. On this current machine, the user's latest explicit operator instruction is the stronger final-state override: keep all five survivors `PAUSED` with `user_paused=true`, read back the whole group after every installer or final gate, and treat any attempted activation as an unfinished or failed closeout. The portable installer still preserves each machine's own prior pause choice unless an explicit local operator override exists.

**Non-Goals:**

- Do not add a vector database, external database, daemon, or network dependency to local retrieval.
- Do not preserve Architect as a hidden alias, compatibility lane, or renamed recurring self-refactor agent.
- Do not preserve any old managed format through dual-read, dual-write, compatibility aliases, alternate success paths, fixed model defaults, implicit CLI grammar, or runtime repair branches.
- Do not promote observations merely to increase trusted-card counts.
- Do not require a human to review every record; uncertain evidence is parked with a machine-readable reopen condition.
- Do not delete canonical user knowledge, current cards, or raw observation evidence merely to meet a storage target.
- Do not modify organization repositories or unrelated user automations during local migration.

## Decisions

### 1. Use one lifecycle state machine for observations and candidates

The canonical maintenance state is `new -> classified -> represented | candidate | dream_pending | history_only | rejected | parked`, with candidate continuation `candidate -> trusted | merged | superseded | rejected | parked`. Every terminal or parked decision records evidence ids, reason, owner, decided time, and an optional reopen condition.

This is preferred over inferring status from scattered history events because inference has produced unresolved and contradictory active surfaces. Existing append-only events remain evidence, while a compact derived disposition ledger becomes the active decision surface and can be rebuilt deterministically.

### 2. Separate decision latency from promotion latency

New observations MUST receive a disposition by the next successful Sleep pass, but trusted promotion remains evidence dependent. User corrections, verified test outcomes, repeated cross-task evidence, and successful Dream results receive stronger grades than AI self-reported hits. A parked item is closed for backlog accounting and reopens only when its evidence fingerprint or named condition changes.

This prevents both indefinite backlog and unsafe mass promotion.

### 3. Make Sleep watermark-driven and Dream fingerprint-driven

Sleep stores its last committed event watermark and processes new events plus explicitly invalidated older items. The watermark advances only after disposition writes, index rebuild, validation, and receipt publication succeed. A bounded legacy-debt queue is consumed oldest/highest-risk first until drained.

Dream keys experiments by `route + mode + source entry ids + evidence fingerprint`. A passed, failed, weak, or inconclusive result closes that fingerprint. Only changed evidence, a new counterexample, or a changed Sleep disposition reopens it. Dream writes results only to history and the Sleep handoff ledger.

Fixed daily schedules remain acceptable because unchanged runs terminate as small no-ops.

### 4. Build a compact active index from lifecycle truth

Search reads a generated active index containing only eligible trusted and candidate entries. Rejected, merged, superseded, retired, and parked entries are excluded. Candidate weight is bounded by evidence grade; trusted status is not inferred solely from directory placement or a stale cache.

The index records source file fingerprints and is atomically replaced after validation. Routine search reads only a current validated generation. If the index or committed maintenance standard is absent, stale, or invalid, search returns an explicit unavailable error; only the maintenance, migration, or assurance owner may rebuild and reactivate it. There is no filtered-scan or unindexed-card success path.

Foreground retrieval reads a compact activation receipt and revalidates only records that could be returned. Observation-only history intake does not change entry authority. Every entry-lifecycle writer durably invalidates the active generation before mutation; only a full manifest/lifecycle audit and atomic rebuild may clear that marker. Full-corpus replay therefore remains a Sleep, migration, and assurance responsibility instead of being repeated on every query.

Local lifecycle authority and organization-source visibility are separate. An ineligible local candidate remains excluded. A read-only organization candidate may be visible only as explicitly untrusted input for adoption or automated validation and never enters the local active index merely because it was visible. Local adoption creates or resolves a local identity that must pass the normal local evidence gate.

Organization sources use one strict current manifest/layout: schema version 1 with exact `kb.main_path: kb/main` and `kb.imports_path: kb/imports` authority. `kb/trusted`, `kb/candidates`, the retired `trusted_path`/`candidates_path` fields, and their download/cleanup branches are migration inputs only. Connection or upgrade directly moves their content into current roots, rewrites the manifest, records a rollbackable receipt, and rejects normal use until the old roots and fields are absent. The central reader, outbox dedupe, adoption route, scheduled maintenance, and installed GitHub checker are all registered consumers of this same commitment; every one blocks an old-root residual rather than silently ignoring it or treating it as an alternate layout.

### 5. Treat outcome calibration as evidence, not self-report

Retrieval receipts bind query/task, returned entry ids, rank, decision use, later test/result/user-correction evidence, and a bounded outcome classification. Evaluation includes positive, negative, misleading, and no-card cases against the real active KB. Calibration may adjust confidence or reopen lifecycle review, but it may not silently rewrite trusted content.

### 6. Introduce a versioned maintenance standard and migration journal

Internal state carries `maintenance_standard_version` and `history_schema_version`. Upgrade uses the current direct migrator to inventory the detected old surface and write the canonical target state once; intermediate software readers and predecessor authorities are not loaded into normal operation. Each direct migration step has a stable id, input fingerprint, status, checkpoint, output fingerprint, rollback reference, and immutable receipt. Re-running a completed step with the same input is a no-op; changed inputs require a new receipt.

The migration state machine is:

`preflight -> snapshot -> classify -> canonicalize-runtime -> settle-logical-debt -> archive-cold-evidence -> prune-derived-data -> rebuild-index -> validate -> committed`.

`canonicalize-runtime` owns one-time repairs that must never remain in daily code: organization schema/layout replacement, `maintainer_*` desktop-settings rewrite, card Skill-guidance alias collapse into `unavailable_skill_guidance`, exact obsolete update-failure settlement, installed launcher and caller replacement, current-only runtime policy verification, and residual scans for old retrieval, settings, card, organization, or launcher readers. Successful validation proves that normal modules cannot import or execute these old paths.

An exact old/current value conflict is not normalized by deterministic runtime code. It blocks before mutation so the upgrade AI can select one value already present in the captured pair, record a concrete reason and before/after hashes, and then resume the same transaction. This bounded AI decision is migration evidence, not a persistent compatibility policy.

Failure transitions to `paused_failed` with the previous active surface intact. Interrupted work resumes from the last validated checkpoint.

Production replay exposed a scale miss in the first settlement implementation: replaying the entire lifecycle log before and after every individual observation is correct on small fixtures but loses practical progress on thousands of records. Logical settlement therefore compiles missing admission, disposition, and entry-snapshot events into one bounded idempotent batch. The authoritative JSONL log is atomically extended, then replayed once before and once after the batch; an interrupted older per-item attempt is reused through the same stable idempotency keys and candidate identities. The receipt records replay and event counts so scale convergence is executable evidence rather than an elapsed-time claim.

Live installation exposed a second temporal miss: a delayed process can reintroduce an old managed workspace after the prune scan starts but before a long archive-integrity check finishes. Maintenance standard v3 therefore scans the current managed surface at the end of validation and supports nested, versioned reconciliation passes. Each pass owns stable inventory, archive, prune, partial-resume, and receipt paths; a late delta reopens the gate, remains resumable with exact accounting, and cannot be hidden by an earlier committed receipt.

The same live cross-check exposed a Windows representation miss: ordinary `pathlib` existence checks can hide files at the legacy path-length boundary even while PowerShell still enumerates them. The migration keeps canonical relative paths in receipts but uses Win32 extended-length paths for enumeration, stat, hashing, archive reads, attribute repair, deletion, and empty-directory cleanup. This preserves readable machine records without allowing long paths to escape physical-debt accounting.

A later interrupted live install exposed a lock-ownership miss: the legacy lock was an empty directory, so the next run could neither prove a live owner nor recover a dead one. The migration lock is therefore recoverable state. New holders publish a versioned owner token, PID, and heartbeat. A live owner is never displaced; a recent ownerless legacy directory remains blocked. A dead recorded owner or sufficiently old ownerless legacy lock with no matching migration process is atomically renamed out of the live lock name, recorded in an append-only recovery receipt, and then reacquired. This closes the crash window without making manual lock deletion part of the upgrade contract.

Because other AI tasks remain active during long local maintenance, post-commit convergence also owns logical drift. A search or postflight observation admitted after the main settlement checkpoint reopens the gate, is settled through the same atomic lifecycle batch, rebuilds the active index, and receives its own logical-reconciliation receipt. The loop is bounded; continuously arriving debt leaves the upgrade paused rather than allowing an unstable finish claim.

### 7. Divide history into canonical evidence, compact cold evidence, and disposable derivations

- Canonical: current cards, `events.jsonl`, lifecycle/disposition ledgers, current migration/install receipts, and current indexes.
- Cold evidence: compact summaries and hashes for retired Architect runs, old maintenance decisions, and older successful experiments needed for provenance or reopen checks.
- Disposable derivations: broad proposals, duplicate full snapshots, completed sandboxes, caches, test output, and maintenance-lab workspaces that can be regenerated and are covered by a successful migration receipt.

Pruning occurs only after hashes, counts, ownership, and rollback boundaries are recorded. The migration reports before/after bytes and files, but correctness gates take precedence over a fixed reduction percentage.

### 8. Retire Architect through an explicit tombstone, not omission

Repository-managed retired ids include automation `kb-architect` and Skill `kb-architect-pass`. Fresh installs never create them. Upgrades inspect exact managed ids/markers, pause and wait for a running lane, remove installed copies, remove global route entries, and verify absence. Presence after migration is a failed install check.

Architect handoff fields are migrated to either Sleep evidence handoff or system-maintenance observation. `architect_update_check` becomes a system update gate owned by the update workflow. Architect queue/history becomes cold evidence and is excluded from active maintenance.

An explicit tombstone is preferred to simply removing the current spec because older installers and machines otherwise recreate the retired assets.

### 9. Stage whole Skill and automation trees transactionally

The repository is the portable authority. Installation first freezes the complete executable SkillGuard tree and complete imported FlowGuard and LogicGuard packages into receipt-bound validation snapshots, then checks the complete source Skill tree with that current compiler and the target-owned generator/depth contracts, copies it into a staging root, proves source/stage parity and native currentness, and atomically activates. Every long-assurance child consumes the same three snapshots; a temporary global SkillGuard replacement or concurrent edit to either editable model package cannot split one run across tool versions, while a genuinely changed final live identity invalidates currentness. A current installed tree is compared for semantic hard-authority loss. An absent or non-current exact managed tree is not parsed as a predecessor, converted, renewed, or used as fallback authority; it is preserved only as the rollback backup while the validated incoming whole tree replaces it. A versioned transaction receipt binds complete source, staged, installed, and post-operation manifests, all three current validation identities, the active-tree currentness disposition, and immutable replay evidence. The prior active copy remains a rollback backup until post-activation validation passes; abandoned staging and excess backups are cleaned only after that durable boundary.

The five retained automation Skills expose only the current contract source,
compiled contract, and exact check manifest. After current contract-depth,
positive, and intentionally shallow target-native evidence pass, the repository
removes the exact former work contract, underscore check manifest, flat run
records, and empty former runtime directories. Deterministic regeneration never
recreates a compatibility, conversion, renewal, retirement-receipt, alias, or
fallback surface, and the installer blocks any old-machine or late write that
reintroduces one.

An upgrade-attempt journal is deliberately separate from the last-known-good install manifest. It records every durable checkpoint—including the pre-assurance router refresh—even if aggregate assurance, final activation, or post-install verification fails later. The successful manifest is replaced only after the final transaction that can change a managed Skill tree, a second router refresh, and the official live registry and managed-prompt checks all agree with the current Skill surfaces. A failure after commit is therefore a recoverable `PAUSED` attempt, not an ignored exception or a false success based on an older prompt/registry pair.

Both runtime status and the independent `user_paused` value are preserved for every managed automation, not only organization automations. All five survivors remain migration-paused while the updater builds a no-mutation restoration plan containing exact source/target hashes and desired states. The final composed SkillGuard route authorizes that exact plan before it can be applied. Apply or read-back drift re-pauses all five and leaves the update failed. Retired automations are deleted regardless of prior active/paused status.

Aggregate readiness is a single outer boundary. Installer calls made by its own regression suite run as isolated fixtures, so they cannot acquire the outer migration lock, launch another aggregate suite, mutate live automation state, write the live Codex shell-tools directory, or persist the user's PATH. Fixture mode fails closed unless it receives an explicit non-default Codex home, a fixture-local shell-tools directory, and disabled PATH persistence. Model alignment may run focused installer tests in parallel with unrelated gates, but the full repository regression receives an exclusive validation lane afterward so identical fixtures never compete for shared Windows resources. This isolation is active only in the aggregate/test context; a normal product install still defaults to the complete migration and assurance gates.

Aggregate success is followed by a bounded data-dependent catch-up while all five tasks remain paused. Each attempt runs the production history migration, rebuilds the active index when needed, reruns the real retrieval evaluation, and checks migration currentness again. This avoids rerunning code/model/full regression evidence that did not depend on new observations, while preventing peer AI observations admitted during the long assurance window from slipping past the restoration boundary. Failure remains a durable recoverable paused attempt.

Automation model and reasoning policy resolution also has one authority. The installer may use an explicit environment override or current Codex provider/config metadata and selects the strongest declared model plus deepest supported effort. If those facts are unavailable or inconsistent it blocks installation; it never inserts a fixed model slug or reasoning effort as a backup.

The installed predictive-KB launcher accepts only the explicit subcommand grammar and canonical `--route-hint`. Calls without a subcommand or with the removed `--path-hint` spelling fail visibly. The desktop launcher likewise requires an explicit `source` or `release` runtime; `release` means the one canonical `dist/KhaosBrain.exe` path, and an unavailable selected runtime fails instead of probing other executable locations or switching to Python. Upgrade replaces callers, launchers, and templates together instead of retaining argument aliases or path-selection fallback.

### 10. Reuse and repartition existing FlowGuard ownership

- `khaos_brain_function_flow`: parent ownership for local lane mutual exclusion and system-update state.
- `khaos_brain_governance_flow`: parent ownership for candidate backlog, route governance, and health projection.
- `kb_sleep_generalization_flow`: existing evidence for Sleep semantic generalization.
- New lifecycle child: observation/candidate disposition, watermark commit, Dream fingerprint closure, and active-index eligibility.
- New migration child: upgrade checkpoints, history classes, Architect tombstone, pause/restore, failure recovery, and idempotency.
- FieldLifecycleMesh: every removed/renamed Architect field and every new lifecycle/migration field.
- ContractExhaustionMesh: fresh install, old active/paused Architect, missing manifest, interrupted migration, repeated migration, stale index, failed validation, and no-delta Dream combinations.
- Model-Test Alignment/TestMesh: obligation-to-code-to-test bindings and background regression hierarchy.
- DevelopmentProcessFlow: artifact/evidence freshness across OpenSpec, models, code, install, migration, and final claims.

This child split avoids adding more responsibilities to already-large governance models while preserving a single parent claim chain.

### 11. Validate in shadow roots before the real machine migration

Migration tests create old-version fixture homes and history trees for fresh, active, paused, partial, interrupted, missing-manifest, and repeated-upgrade cases. The same production migration code runs against fixtures. Long full regressions run once under one explicit foreground validation owner after source and tool identities are frozen, with durable logs and confirmed descendant-tree cleanup on interruption; focused non-overlapping checks may run independently, but no scheduled task, background resume, or retry loop may own the full gate.

The current machine is upgraded only after fixture migration, focused tests, FlowGuard, SkillGuard, install checks, and OpenSpec verification are green. Real migration remains reversible until its final receipt is committed.

### 12. Separate version capability from each scheduled run's completion

Pytest and static contract compilation prove that the installed version can perform the designed behavior; they do not prove that a particular background task ran. Every one of the five retained automations therefore has its own guarded scheduled entrypoint, target-specific route, unique obligations, exact declared checks, and immutable native artifact. The wrapper invokes the native owner exactly once and binds its receipt to the current installed SkillGuard execution identity. SkillGuard executes and reconciles only the declared check inventory; the target remains responsible for domain obligations, terminal construction, and positive/shallow fixture semantics. Only the sole current `enforced` closure over the exact declared-check receipt and required target artifacts lets the wrapper report terminal completion. An intentionally shallow receipt must fail for the named target obligation it omits, not merely because of a generic environment error.

The current SkillGuard profile is target-neutral declared-check supervision, not a second model of target work. Each task declares the exact intake, native, terminal, fixture, and conditional branch/finalization checks that SkillGuard may execute. The active provider/runtime must be enrolled and prove declared-check inventory, receipt reconciliation, installation binding/currentness, and single-flight execution capabilities. Missing or duplicated checks, stale installation identity, caller-authored pass flags, generic fixtures, and proposal-only artifacts remain explicit non-pass states.

Target receipt validation is deliberately target-owned. `performed` evidence must project exact existing source fields. `not_applicable` evidence additionally binds an evaluated false applicability gate, exact run id, reason, terminal status, canonical gate-facts hash, proof id, and proven non-mutation; a forged proof, missing branch field, or generic shared pass is rejected. Each target supplies a positive native fixture and a shallow fixture with one real important obligation missing or failed. SkillGuard supervises those declared commands but does not reinterpret their domain result.

Scheduled completion accepts only evidence produced by the installed SkillGuard runtime and bound to a concrete scheduler execution, current installation receipt id/hash, portable `active_skill_root` receipt-root reference, and installed runtime fingerprint. Before the native owner starts, the guarded entrypoint opens one persistent official supervision session, verifies the live installation once, and freezes the exact SkillGuard behavior projection, target-control projection, sealed installation context, and six-field execution identity. The same session is retained through native execution and used for terminal construction and closure; it never reloads the live global SkillGuard after native completion. A newer live SkillGuard or target contract is therefore eligible only for the next scheduled execution, while a missing or invalid start snapshot blocks before native side effects. This boundary does not reinstall global SkillGuard when a supervised target Skill changes. Fixture and release-capability evidence stay separate from scheduled completion and cannot be relabeled as a real run.

Static authority and per-run evidence deliberately use different channels. SkillGuard code, contracts, target control, and installation identity are immutable start-frozen inputs. The native receipt path/hash, run id, scheduled identity, fixture gate, and update-finalization receipt are dynamic evidence that can exist only after native work. The wrapper projects only that exact seven-key set into the retained frozen process, clears every missing declared key so stale inherited evidence cannot survive, and never forwards an undeclared environment key. A missing current receipt therefore blocks honestly instead of causing a global reinstall, live runtime reload, or source fallback.

Shared maintenance-lock evidence is part of the native contract, not an external scheduling assumption. Sleep and Dream bind acquisition, run ownership, wait/recheck behavior, and release to their receipts; lock contention is retryable and cannot masquerade as a full no-op. System update has exactly three legal no-op branches: `no-update`, `waiting-for-user`, and `ui-running`; operational blockers remain incomplete. A legal no-op needs its target-owned terminal receipt and the sole `enforced` closure.

The native Sleep, Dream, organization, and update implementations remain the sole domain owners. For prepared update, the first request produces a non-terminal declared-check authorization receipt and no closure. The updater then stages the exact restoration artifact while paused. A fresh composed request executes the exact declared checks once, builds the target terminal receipt, and obtains the sole `enforced` closure without rerunning checks during close. That closure authorizes activation but does not claim activation already happened; the native updater applies the bound plan, reads back all five files, runs the normal install check, writes an immutable activation receipt, and only then marks the update `CURRENT`.

Source compilation and installed execution have different ownership. The one
canonical repository owns contract generation and compilation. An installed
Skill is a content-addressed deployment projection under the active Codex home,
so installed supervision replays the current SkillGuard installation receipt,
copies only that tree's five current managed control files into a short
content-addressed repository-local execution projection, and passes the exact
installed `compiled-contract.json` and `check-manifest.json` into the stable
supervisor. The stable checker is imported from a separate short,
content-addressed repository-local projection of the frozen current SkillGuard
behavior bytes plus the current global-router sibling. That behavior projection
excludes `.sg-runtime`, interpreter caches, and compiled bytecode, and its
official runtime fingerprint must exactly equal the verified installed runtime
fingerprint. The projection executor disables Python bytecode writes in both
its own process and supervised child processes, so importing the frozen runtime
cannot add `__pycache__` files and make the next exact-inventory reuse fail.
Run state belongs to the declared target, not either installed or
projection directory; projection correctness cannot depend on a deeply nested
Windows run path. It never executes an outside-repository root through the
repository executor, recompiles the installed tree as a second repository,
substitutes repository source for installed control bytes, or accepts a runtime
projection whose behavior identity differs from the installed currentness
receipt.

The supervision caller also separates identity from presentation. The exact
canonical source root selects source supervision; the exact active Codex
`skills/<skill-id>` root selects installed supervision. A scheduled-run label,
calibration label, or installed-looking display name never selects the runner.
Any root that is missing, outside those two managed locations, or resolves
ambiguously blocks before a packet runs. This prevents both the observed
installed-as-source failure and the inverse source-as-installed substitution
without adding an alias, compatibility rule, or fallback.

The first current-only consumer also fixes migration ordering. Exact obsolete
update state is canonicalized after the paused install transaction but before
aggregate assurance invokes the update owner; a later failure restores the
captured pre-migration bytes. Organization cleanup action identity hashes the
complete canonical decision payload, including related merge/split targets, and
closure reconciles unique action ids with exact proposal and disposition counts.

### 13. Scope Architect retirement to the active Codex routing projection

The live `$CODEX_HOME/AGENTS.md` projection determines the active SkillGuard registry. Retirement checks use only that registry, or the canonical registry under the same Codex home when the projection is absent. Historical registries in unrelated repositories are neither executable routes nor upgrade-owned data. This prevents a clean old-machine migration from being falsely blocked by stale external state while still failing closed when the active registry is unreadable or still exposes Architect.

### 14. Make interrupted Sleep recovery and validation timeout cleanup scale-safe

Sleep treats the durable lifecycle ledger and the history watermark as two independently committed facts. If interruption occurs after dispositions are durable but before the watermark receipt is written, the next run reads the current lifecycle projection once, advances across already-terminal history without readmitting or redisposing it, and spends its bounded work budget only on actionable observations. Genuinely new admission/disposition events are committed through one atomic lifecycle batch with one replay before and one replay after. This converts crash recovery from repeated full-ledger work per historical row to one bounded scan plus one bounded transaction.

Candidate calibration follows the same scale rule. One Sleep cycle builds a shared outcome-and-lifecycle evidence index, then reuses it for every candidate. Reopening and promotion semantics stay entry-specific, but full evidence authorities are never reloaded once per candidate.

When a parked entry's aggregated evidence digest changes without satisfying its reopen condition, Sleep records one `entry-calibration-snapshot` with the new digest. This is an evidence-review watermark, not an eligibility transition: it is committed in one lifecycle batch, does not invalidate the active index, and makes the next unchanged cycle a receipt-backed skip. Likewise, an initial `no_delta` model result is already the final model identity; Sleep validates or directly rebuilds the current active index without executing the complete model-publication path a second time.

Dream handoff acknowledgement is a post-publication action. Pending handoffs first compile their missing observation admissions and dispositions into the same bounded lifecycle batch as ordinary Sleep input, with one replay before and one after the batch rather than a full replay per handoff. Sleep may durably admit and classify the handoff observation while staging its candidate projection, but it writes the acknowledgement only after the complete candidate/model generation publication succeeds. If the owner dies before a completed Sleep receipt exists, the recovered lane identity scopes rollback to that exact run's premature acknowledgements and makes those handoffs pending again; stable candidate identity keeps the retry idempotent.

The two-replay bound also has a computational bound: each replay keeps the durable ordered `idempotency_keys` projection for inspection but uses a separate in-memory set for duplicate membership, so replay work grows linearly with lifecycle event count. A bounded number of quadratic replays is still a failed scale design and must be rejected by the executable model and performance regression.

Maintenance locks use both heartbeat age and recorded process liveness. A live owner is never displaced; a fresh lock with a confirmed dead PID is recovered immediately and reported in the next owner receipt, instead of blocking for the full age threshold.

Every long validation launcher owns the complete process tree it starts. On timeout it captures descendants, terminates the tree, waits for the root to be reaped, and records a zero-descendant cleanup receipt. Timeout layers are strictly ordered: native work expires before its scheduled-production consumer, scheduled production before aggregate SkillGuard assurance, and aggregate assurance before the installer. A timeout without confirmed cleanup is non-reusable evidence and blocks any new validation owner.

## Risks / Trade-offs

- **[Risk] Mass automatic classification could hide useful one-off evidence.** -> Park uncertain items in cold history with explicit reopen conditions; exclude them from active backlog without deleting source events.
- **[Risk] Pruning large maintenance trees can destroy rollback material.** -> Classify canonical/cold/derived surfaces, hash before removal, retain current canonical state, and test restore before physical pruning.
- **[Risk] Old machines have incomplete or malformed manifests.** -> Detect exact legacy managed ids and content markers independently of the manifest; model missing-manifest upgrades explicitly.
- **[Risk] Installing from the repository can downgrade deeper installed SkillGuard contracts, while a topology-based comparison can falsely reject a safe check or owner reorganization.** -> Validate repository authority first, compare obligation/evidence/mandatory-owner coverage rather than check-id, native-route, or depth-dimension subsets; require an exact proof before moving a conditional depth wrapper to its unchanged independent hard owner; block real authority loss; then stage the whole tree and atomically activate with rollback.
- **[Risk] Concurrent agents can invalidate evidence or overwrite files.** -> Avoid dirty peer-owned paths until integrated, fingerprint artifacts, rerun affected checks after peer writes, and never reset or checkout their changes.
- **[Risk] Full history cleanup may take a long time or run out of disk.** -> Stream inventories, avoid duplicating the whole history, checkpoint each phase, estimate disk before writes, and resume without restarting completed work.
- **[Risk] Windows read-only files or an interrupted prune can stop cleanup after earlier deletions.** -> Clear only the read-only attribute after ownership, fingerprint, and retention checks; preserve ACL failures as blockers; merge durable partial prune rows into the resumed final accounting.
- **[Risk] Daily Dream still consumes model time on no-op days.** -> Make the first fingerprint/index check deterministic and small; no-op before sandbox or broad prompt expansion.
- **[Risk] A small trusted layer may remain after cleanup.** -> Judge success by evidence-backed coverage and task utility, not promotion quota.

## Migration Plan

1. Snapshot current automation status and pause all managed KB automations after active lanes finish.
2. Freeze baseline counts, bytes, active cards, event watermark, candidate debt, Guard state, and install/source fingerprints.
3. Add and pass lifecycle/migration FlowGuard models and finite known-bad cases.
4. Implement lifecycle/disposition state, active index, incremental Sleep, and Dream fingerprint closure behind migration-version gates.
5. Implement Architect tombstones, neutral system-update gate, transactional installer, and full source/install parity.
6. Implement history-debt inventory, logical settlement, cold archival, derived-data pruning, receipts, resume, and rollback.
7. Run fixture migrations and focused tests; repair all failures.
8. Run background full tests, FlowGuard mesh, per-target SkillGuard capability checks, install checks, and OpenSpec verification.
9. Execute the production migration on the current machine while all five surviving automations remain paused.
10. Build the exact hash-bound restoration plan and pass the final composed update SkillGuard route while the plan remains unapplied.
11. Apply and read back the authorized five-task plan, run the normal install check, write the activation receipt, and mark the update current only after all evidence passes.
12. Verify active debt, retrieval, storage, installed artifacts, scheduled-run receipts, and live automation state.
13. Archive the OpenSpec change only after tasks and current verification pass.

Rollback restores the pre-migration active indexes, lifecycle ledgers, installed Skill trees, automation specs/status, and canonical files. Derived artifacts are not pruned until the restore boundary has passed its check.

## Open Questions

- Exact physical retention counts and byte budgets will be calibrated from the migration inventory, then frozen in the verification contract before production pruning.
- Old Architect summaries may be stored as one compressed cold package or compact per-run receipts; choose the smaller representation that still preserves provenance hashes and required reopen evidence.
