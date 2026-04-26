# Changelog

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
