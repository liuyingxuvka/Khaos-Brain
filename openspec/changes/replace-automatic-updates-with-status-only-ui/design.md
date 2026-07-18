## Context

The former update design had three coupled parts: a desktop badge that wrote `user_requested`, a scheduled `khaos-brain-system-update` job that converted persisted state into execution authority, and a transactional updater whose completion depended on an external guard. The desktop application itself did not check GitHub; without the scheduled job its badge became stale. The old comparison also treated any unequal revisions as an available update, including local-ahead and diverged histories.

The user wants visibility without delegated execution authority. The UI must remain useful when the network or Git tracking configuration is unavailable, and the safe transactional update machinery must remain available when the user explicitly asks AI to update in the current conversation.

## Goals / Non-Goals

**Goals:**

- Give the desktop UI a read-only, non-blocking view of the configured Git upstream branch.
- Distinguish current, fast-forward update available, local ahead, diverged, and unavailable-to-check states.
- Remove every UI, persisted-state, scheduler, installer, and repair path that can prepare or automatically execute an update.
- Preserve one explicit conversational AI route through the transactional installer and existing rollback/validation safety controls.
- Directly migrate the exact former update-state schema during an upgrade and keep normal runtime free of a legacy reader.

**Non-Goals:**

- The UI will not install, prepare, cancel, queue, or request an update.
- The UI will not expose commit hashes or internal model or native receipts.
- The change will not weaken fast-forward-only Git, dirty-worktree, rollback, migration, or validation gates.
- The change will not add a replacement scheduler, background retry service, or compatibility alias.

## Decisions

### 1. Make update visibility a read-only projection

On desktop startup, one daemon worker performs a remote check and writes the current status cache. Rendering only reads the cache; it never performs network or Git work. Completion is posted back to the Tk event loop for a repaint. The badge has no hitbox, hand cursor, click handler, or mutation callback.

This preserves a responsive UI and avoids repeated fetches during resize, hover, and navigation redraws. A launch-time check was chosen over periodic polling because it satisfies visibility without adding an unattended recurring process.

### 2. Compare the exact configured upstream by topology

The checker requires `@{u}` to resolve and fetches only that upstream's remote. It does not guess `origin/<current-branch>` or `origin/main`. `git rev-list --left-right --count HEAD...@{u}` classifies the checkout as:

- `current`: neither side has unique commits;
- `available`: local is strictly behind and can fast-forward;
- `local_ahead`: local has commits and upstream has none;
- `diverged`: both sides have unique commits;
- `unavailable`: tracking, fetch, or revision comparison failed.

Only `available` means a newer upstream revision is available. The UI shows the human-readable branch and version but not raw revision hashes.

### 3. Replace persisted authorization with status schema v2

Schema v2 removes `user_requested` and the `prepared` status, adds `upstream_ref`, `ahead_count`, and `behind_count`, and makes an unchecked fresh state `unavailable` rather than falsely `current`. `upgrading` and `failed` remain execution-safety states for the explicit manual updater.

The installer-owned upgrade migration accepts only the exact former schema, maps `prepared` to `available`, drops the retired authorization field, and writes v2 atomically. Unknown schemas or fields fail closed. Normal load paths accept only v2.

### 4. Retire the scheduler while retaining the manual skill

`khaos-brain-system-update` becomes an exact retired managed automation ID. It is removed from the surviving automation specification and installation state snapshots, and install/repair health requires it to be absent. The `khaos-brain-update` skill remains installed as a manually invoked skill with no automation ID.

The native updater is renamed to a manual-update entrypoint. The native owner requires an explicit user-request flag for the invocation; no authorization bit is written to disk. The manual route checks the remote, requires a fast-forward target and a closed Khaos Brain UI, then performs dirty-tree, pause, snapshot, migration, clean transactional install, exact restoration, final health, CURRENT, cleanup, rollback, and immutable native-receipt gates in one target-owned route.

The portable installer continues to preserve the exact prior state of the four
surviving maintenance tasks. A separate current-machine operator transaction may
override that preserved state only after aggregate and scheduled-production
evidence is current. For this rollout the user's explicit override is all four
survivors `ACTIVE`, while both retired tasks stay absent; any partial activation
or final health failure re-pauses the group.

### 5. Keep verification ownership explicit

FlowGuard owns the UI/status/manual-execution behavior model and the four-survivor automation invariant. The field-lifecycle model owns deletion and migration of `user_requested`, `prepared`, and the scheduler identity. The behavior commitment ledger registers exactly one primary owner for read-only status, manual conversational authorization, and scheduler absence. The manual updater owns its native checks and receipt; SkillGuard may audit the source contract on the maintainer computer but is absent from execution and installation.

## Risks / Trade-offs

- **Remote check can be slow or offline** → run it outside the UI thread, expose `unavailable` with a concise message, and preserve the last checked timestamp without claiming currentness.
- **A local-ahead checkout may have the same VERSION as upstream** → classify from commit topology, not version text alone.
- **Removing the scheduled job could accidentally remove the manual updater** → keep the skill installed, add explicit positive manual-route tests, and separate skill inventory from automation inventory.
- **Old prepared state could retain authority** → migration drops `user_requested`, maps `prepared` to read-only `available`, and tests that no execution follows from the migrated file.
- **A similarly named user asset could be deleted** → retire only the exact installer-managed automation ID under the managed Codex automation root.
- **Renaming the native entrypoint can leave stale references** → use direct replacement with zero compatibility alias and repository-wide residual checks.

## Migration Plan

1. Freeze and validate the new OpenSpec, FlowGuard, field-lifecycle, and commitment-ledger contracts.
2. Add schema-v2 status projection and upgrade-only v1 migration.
3. Change the desktop UI to a launch-time background check and remove all interactive update surfaces.
4. Retire the exact scheduled task in installer specifications and health checks; reduce surviving automation snapshots from five to four.
5. Convert the update skill and guarded/native runner to explicit conversational manual execution.
6. Regenerate the source-only author contract, update tests and documentation, and run affected then full verification.
7. Run the real installer so the local scheduled task is removed, verify repeated install/check idempotence, and visually verify the UI.
8. Publish a new patch release from the validated source and assets.

Rollback is a normal source rollback plus the transactional install backup. Rollback does not recreate the retired scheduled job automatically; restoring automatic scheduling would require a separate explicit product change.

## Open Questions

None. The desired execution authority and UI behavior are explicit.
