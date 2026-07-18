## 1. Model and Contract Ownership

- [x] 1.1 Update the main FlowGuard update workflow and conformance replay for read-only status plus explicit conversational manual execution, including current, available, ahead, diverged, unavailable, UI-open, missing-authorization, and no-update branches.
- [x] 1.2 Update the field-lifecycle mesh to directly retire `user_requested`, `prepared`, and `khaos-brain-system-update` while registering schema-v2 status fields and their exact owners.
- [x] 1.3 Register one primary behavior commitment each for read-only upstream visibility, explicit manual AI update authority, and exact scheduler absence; run the ledger check.

## 2. Status-Only Desktop Surface

- [x] 2.1 Replace update-state schema v1 with the status-only schema v2 and an upgrade-only direct migration that drops former authorization.
- [x] 2.2 Implement strict configured-upstream topology comparison for current, available, local-ahead, diverged, and unavailable states.
- [x] 2.3 Add one non-blocking launch-time status check, keep the status surface visible while the initial card catalog loads in the background, and remove update hitboxes, click handlers, prepared styles, and mutation imports.
- [x] 2.4 Add focused status, schema-migration, topology, background-refresh, initial-catalog-loading, and non-interactive UI tests.

## 3. Explicit Manual AI Update

- [x] 3.1 Replace the scheduled native update entrypoint with a manual entrypoint that refuses before mutation unless explicit current-request authorization is supplied.
- [x] 3.2 Update the CLI surface for the manual trigger while preserving UI-closed, clean-tree, fast-forward, snapshot, rollback, migration, clean install, exact restoration, final health, CURRENT, cleanup, and native-receipt gates.
- [x] 3.3 Rewrite the `khaos-brain-update` skill activation and report contract so only a user-explicit conversational request can invoke it.
- [x] 3.4 Add positive and negative native/guarded manual-update tests and remove former prepared/scheduled branch expectations.

## 4. Installer and Managed Skill Contracts

- [x] 4.1 Move `khaos-brain-system-update` to the exact retired automation set, reduce the survivor set to four, retain the manual skill without an automation binding, and make install health require task absence.
- [x] 4.2 Update migration-debt ownership, update-state migration, automation snapshots, installer reports, and repeated-install behavior for four survivors and no scheduler recreation.
- [x] 4.3 Convert the source-only update author contract from scheduled/UI-prepared authorization to the target-declared explicit manual route and regenerate current authority without shipping it.
- [x] 4.4 Add fresh-install, upgrade-removal, repeated-install, similarly-named-user-asset, managed-skill-retention, clean consumer projection, and author-contract tests.

## 5. Documentation and Release Metadata

- [x] 5.1 Update README, Windows UI/install documentation, upgrade documentation, automation descriptions, and current-runtime residual rules to describe status-only UI, four background tasks, and manual AI update.
- [x] 5.2 Update VERSION, CHANGELOG, and release-facing version references for the patch release selected by the release audit.
- [x] 5.3 Remove or replace every current production/documentation reference that could recreate or advertise the retired scheduled/UI-prepared update route, while preserving historical evidence as non-authoritative history.

## 6. Verification and Local Activation

- [x] 6.0 Define and test the exact activation inventory: five maintained
  skills, four scheduled automations, and manual-only `khaos-brain-update`.
- [ ] 6.1 Run the focused update/UI, installer, residual, author-contract, FlowGuard, field-lifecycle, commitment-ledger, conformance, and project-audit checks from the verification contract; fix every failure.
- [ ] 6.2 Run one final full regression on the frozen integrated source and record its terminal result under one execution owner.
- [ ] 6.3 Run the real transactional installer and independent install check, confirm the exact old task is absent, then apply the user's explicit current-machine all-active override and prove all four surviving tasks are `ACTIVE`; repeat the independent check for idempotence.
- [ ] 6.4 Launch the real Windows desktop UI, capture the status-only surface, click/hover it, and record visual/runtime evidence that no state or process mutation occurs.
- [ ] 6.5 Perform the predictive-KB postflight and record any reusable task/skill/delegation lesson exposed by this change.

## 7. GitHub Patch Release

- [ ] 7.1 Freeze the validated diff, run privacy and release-readiness checks, commit intentionally, push the candidate branch, and require successful branch CI.
- [ ] 7.2 Fast-forward the validated commit to `main`, require successful main CI for that exact SHA, create the new immutable patch tag, and require successful tag-receipt CI.
- [ ] 7.3 Build and verify the Windows executable and checksum from the final tag, publish the GitHub Release, and confirm latest release, tag target, version text, and both assets agree.
