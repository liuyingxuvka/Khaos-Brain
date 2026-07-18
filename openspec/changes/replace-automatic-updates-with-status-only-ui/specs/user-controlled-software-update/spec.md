## ADDED Requirements

### Requirement: Read-only upstream update status
The desktop application SHALL asynchronously compare the local checkout with its exact configured Git upstream on launch and SHALL render a read-only status without blocking the UI thread.

#### Scenario: Fast-forward update is available
- **WHEN** the configured upstream contains commits not present locally and the local checkout contains no unique commits
- **THEN** the UI shows that a newer upstream version is available, including the human-readable upstream branch and version
- **AND** the status surface exposes no prepare, cancel, install, or update action

#### Scenario: Local checkout is current
- **WHEN** the local and configured upstream revisions are identical
- **THEN** the UI shows that the configured branch is current

#### Scenario: Local checkout is ahead or diverged
- **WHEN** the local checkout contains unique commits or both local and upstream contain unique commits
- **THEN** the UI distinguishes local-ahead from diverged history
- **AND** it does not report a fast-forward update as available

#### Scenario: Upstream status cannot be checked
- **WHEN** no tracking upstream is configured, the fetch fails, or Git cannot compare the revisions
- **THEN** the UI shows that update status is unavailable
- **AND** it does not claim that the software is current

#### Scenario: Large card catalog is still loading
- **WHEN** the desktop starts with a card catalog whose initial projection takes material time to build
- **THEN** the window and read-only update status become visible before catalog construction completes
- **AND** card loading runs in the background while route navigation remains inert until the current payload is ready

### Requirement: No UI update authorization
The desktop update-status surface MUST NOT write execution authorization or transition software into a prepared or upgrading state.

#### Scenario: User interacts with the status surface
- **WHEN** the user clicks, hovers, resizes, or navigates while the update status is visible
- **THEN** no update request, prepared state, updater process, or automation is created

### Requirement: Explicit conversational manual update
The system SHALL retain one transactional software-update route that can execute only when AI invokes it for an explicit update request made by the user in the current conversation.

#### Scenario: User explicitly asks AI to update
- **WHEN** AI invokes the guarded manual updater with explicit current-request authorization, the configured upstream is a fast-forward update, the UI is closed, and all safety gates pass
- **THEN** the updater fast-forwards, migrates, installs, validates, restores the four surviving automations, and reports the final result

#### Scenario: Explicit request authorization is absent
- **WHEN** the manual updater or guarded launcher is invoked without explicit current-request authorization
- **THEN** it refuses before Git mutation, installer execution, or automation-state mutation

#### Scenario: Manual update cannot safely fast-forward
- **WHEN** the checkout is dirty, ahead, diverged, missing its configured upstream, or has the Khaos Brain UI open
- **THEN** the updater reports the blocker and performs no Git fast-forward

### Requirement: Automatic update scheduling is retired
Fresh install, upgrade, repair, and repeated install SHALL keep the exact managed automation ID `khaos-brain-system-update` absent while retaining the manually invoked `khaos-brain-update` skill.

#### Scenario: Fresh installation
- **WHEN** Khaos Brain is installed into a Codex home with no prior managed update task
- **THEN** the installer creates only the four retained background automations
- **AND** it installs the manual update skill without an automation binding

#### Scenario: Upgrade from an installation with the old task
- **WHEN** the installer finds the exact managed `khaos-brain-system-update` task
- **THEN** it removes that task transactionally and does not restore it

#### Scenario: Repeated installation or repair
- **WHEN** the installer or installation check runs again after retirement
- **THEN** the old task remains absent and absence is reported as healthy

#### Scenario: Current machine returns maintenance to normal operation
- **WHEN** the current aggregate, exact five-skill activation inventory, clean installed state, and four scheduled-skill classifications are valid and the user explicitly requires the retained maintenance tasks to run normally
- **THEN** one hash-bound operator transaction activates exactly Sleep, Dream, organization contribution, and organization maintenance with no user-pause bit
- **AND** the installed `khaos-brain-update` skill remains classified as manual-only and receives no automation binding
- **AND** the exact Architect and system-update tasks remain absent
- **AND** any partial activation or final health failure re-pauses all four retained tasks

#### Scenario: All five maintained skills appear in assurance
- **WHEN** readiness reports the four scheduled skills and the manual-only update skill
- **THEN** the five-member report is accepted as the complete maintained inventory
- **AND** only the four scheduled members are required in automation activation and readback

### Requirement: Former authorization state is directly migrated
The installer-owned upgrade path SHALL convert the exact former update-state schema directly to the current status-only schema and SHALL leave no normal-runtime legacy reader.

#### Scenario: Prepared state is migrated
- **WHEN** an exact former state has `status=prepared` and `user_requested=true`
- **THEN** migration writes a status-only available state without `user_requested`
- **AND** no update execution is authorized

#### Scenario: Unknown legacy state is encountered
- **WHEN** the old state has an unknown schema or undeclared field
- **THEN** migration fails closed without inventing a fallback or compatibility reader
