## Why

Khaos Brain currently couples a desktop update prompt, persisted user authorization, and a scheduled updater that the installer recreates. This gives the software authority to prepare or execute an update without the user explicitly asking AI in the current conversation, which is no longer the desired product behavior.

## What Changes

- **BREAKING** Remove the `khaos-brain-system-update` scheduled automation and make fresh installs, upgrades, repair checks, and repeated installs keep it absent.
- Replace the desktop update action and prepared/waiting flow with a read-only status that compares the local checkout with its configured GitHub upstream branch.
- Show a clear current, update-available, or unavailable-to-check state without exposing an update or preparation action.
- Remove persisted `user_requested` and `prepared` authorization from the current update-state contract; directly settle known old state during upgrade and reject unknown legacy shapes.
- Keep the transactional updater and `khaos-brain-update` skill only for a user-explicit request made to AI in the current conversation.
- Update FlowGuard, the target-owned update contract, installer, tests, documentation, and release materials so no scheduled or UI-triggered execution path remains.

## Capabilities

### New Capabilities

- `user-controlled-software-update`: Defines read-only upstream version visibility, explicit conversational authorization for manual updates, retirement of automatic scheduling, and migration of the former prepared-update state.

### Modified Capabilities

- None. This repository currently has no baseline OpenSpec capability specifications for software update behavior.

## Impact

The change affects the desktop update surface, update-state schema and migration, manual updater entrypoint, managed automation installation and health checks, the `khaos-brain-update` skill and its source-only author contract, FlowGuard commitments/models, Windows installer tests, public documentation, version metadata, and the GitHub release package.
