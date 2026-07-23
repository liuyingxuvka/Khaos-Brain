## 1. Freeze current authority and model ownership

- [x] 1.1 Re-audit peer-owned changes, installed/source identities, active-index marker, Sleep episode, automation state, and the stable FlowGuard commitment before editing
- [x] 1.2 Upgrade the repository FlowGuard record when the maintained global consumer projection is current, then record the existing-model, model-miss, DevelopmentProcessFlow, FieldLifecycleMesh, ModelMesh, TestMesh, and model-test alignment evidence
- [x] 1.3 Update `PROJECT_SPEC.md` and behavior commitments so bounded resumable batches, impact-scoped retrieval, immutable serving generations, and the retired generic marker have exactly one current owner

## 2. Implement resumable bounded Sleep batches

- [x] 2.1 Add the versioned batch plan, checkpoint, immutable per-item result, HEAD, counting, target-selection, and resume validation module
- [x] 2.2 Integrate frozen item selection and per-item durable reuse into native Sleep without changing item identities after freeze
- [x] 2.3 Add cooperative soft-stop handling and terminal `progress_saved` receipts that preserve the committed watermark and downstream not-run state
- [x] 2.4 Record previous/new/opening/target/completed/blocked/closing/net counts and two-cycle `backlog_growing` classification
- [x] 2.5 Ensure blocked items require evidence, one owner, and an executable reopen condition and remain distinct from completed work

## 3. Replace global stale-marker behavior with scoped retrieval safety

- [x] 3.1 Add exact retrieval-impact classification for `none`, `additive_pending`, `entry_revoke`, `entry_replace`, and `global_current_corruption`
- [x] 3.2 Add a generation-bound exact-entry subtractive deny projection and publish it before affected current-entry mutation
- [x] 3.3 Publish immutable active-index generation artifacts and atomically replace one complete current pointer last
- [x] 3.4 Change foreground retrieval to validate the pointer-bound immutable index and deny projection without using mutable root YAML as serving authority
- [x] 3.5 Remove all normal-runtime writers/readers of the retired generic invalidation marker and all ungoverned per-event or alternate publication paths

## 4. Complete canonical Sleep publication and downstream gating

- [x] 4.1 Stage candidate, lifecycle, LogicGuard, index, deny, ready-receipt, and watermark outputs under the frozen batch owner
- [x] 4.2 Activate a new generation and advance watermark only after every item is completed or validly blocked and all publication checks pass
- [x] 4.3 Preserve the prior validated generation on progress, validation failure, cancellation, or timeout unless exact current corruption is independently proven
- [x] 4.4 Gate Dream and organization descendants after open/progress/failed/backlog-growing Sleep and emit explicit per-stage `not_run` evidence
- [x] 4.5 Remove or reroute direct generation/index publication callers so Sleep remains the sole normal-runtime publisher and migration remains the sole upgrade publisher

## 5. Directly migrate legacy authority and install the target behavior

- [x] 5.1 Extend the versioned maintenance migration to inventory and directly classify the generic marker and incomplete Sleep episodes into current impact and batch authority
- [x] 5.2 Reuse verified settled historical item evidence, retain explicit blockers, create current immutable generation/pointer authority, and prove zero retired normal-runtime residuals
- [x] 5.3 Update canonical Sleep skill prompts, automation contracts, receipts, localized status projection, installer payloads, and upgrade validation for the new states and fields
- [x] 5.4 Update only the affected `kb-sleep-maintenance` SkillGuard obligation, implementation inventory, native checks, and consumer projection; preserve the other four peer-refreshed units

## 6. Verify behavior and model alignment

- [x] 6.1 Add unit/property tests for target selection, frozen boundaries, item idempotency, checkpoint corruption, resume, blocked reopen, and remainder comparison
- [x] 6.2 Add lifecycle/index tests proving false-to-false and additive work remain readable, exact revokes are locally denied, and exact current corruption globally fails closed
- [x] 6.3 Add crash/restart and soft/hard timeout tests proving settled work is not repeated, prior generation remains available, watermark does not advance, and descendants are not run
- [x] 6.4 Add migration, installer, installed-current, prompt/receipt schema, no-fallback/no-retired-authority, and source-to-installed parity tests
- [x] 6.5 Run affected FlowGuard models and alignment checks, target-native Sleep checks, OpenSpec strict validation, and bounded performance evidence to select the tested minimum batch size
- [x] 6.6 Freeze the integrated source/tool/owner inventory and run one final full regression in an isolation-safe background owner with a terminal result artifact
- [x] 6.7 Model and test the activation model miss: a current receipt-bound ACTIVE decision overrides the older upgrade snapshot during installation checking, while a missing or stale receipt still fails safely back to PAUSED

## 7. Maintain install activate and publish

- [x] 7.1 Wait for the maintained SkillGuard source identity to become stable, then run the latest author-side SkillGuard supervision for only `unit:kb-sleep-maintenance` and reconcile exact current receipts
- [x] 7.2 Run the canonical installer and independent install check, verify the four retained automations preserve pause state, and activate the target feature through its sole installed route
- [x] 7.3 Perform the release audit, update the public version and release notes for the behavior change, and verify local source, installed projection, automation, Git, tag, and GitHub identities separately
- [ ] 7.4 Commit only owned and deliberately integrated peer changes, push the branch and new immutable tag, create the GitHub Release, and verify its target
- [ ] 7.5 Run the explicit predictive-KB postflight check, record one structured observation for this repeated-timeout/process miss, and close every task with current evidence or a concrete blocker
