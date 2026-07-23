## ADDED Requirements

### Requirement: Upgrade installs one current resumable Sleep authority
The upgrade transaction SHALL install the current resumable Sleep batch engine, current impact-scoped retrieval authority, current immutable index generation layout, current pointer contract, and current canonical Sleep automation payload as one direct replacement. Before migration work starts, it SHALL persist the exact pre-pause `status` and `user_paused` intent for every retained automation in the current upgrade-attempt authority. It SHALL prove zero normal-runtime readers or writers of the retired generic invalidation marker, mutable-root serving authority, per-event publication fallback, or prior batch schema before restoring that recorded intent and unpausing eligible automations.

#### Scenario: Migration fails before its first content checkpoint
- **WHEN** the installer has safety-paused the retained automations and migration then fails immediately
- **THEN** the failed current upgrade attempt MUST still contain the exact pre-pause automation intent, a retry MUST reuse that snapshot instead of reading the safety pause as user intent, and all automations remain paused until a healthy retry restores the snapshot

#### Scenario: A retired runtime path remains
- **WHEN** source, installed projection, automation payload, or import scanning finds a normal-runtime reader or writer for a retired authority
- **THEN** upgrade completion blocks and the transaction MUST repair or directly replace the residual before retrying validation

#### Scenario: Installed Sleep is current
- **WHEN** installation finishes and the independent check runs
- **THEN** the source skill, clean installed consumer, automation payload, native runtime, batch schema, pointer schema, and target-native checks MUST bind the same released identities

### Requirement: Release evidence keeps source installed Git and GitHub identities separate
A public release SHALL separately record governed source identity, installed consumer identity, canonical automation identity, native runtime/version identity, Git commit, tag target, and GitHub Release target. Equality is required only where the release contract declares it. A passing source test or local install check MUST NOT be projected as GitHub publication evidence.

#### Scenario: The tag points to a different commit
- **WHEN** the intended release tag does not target the exact release commit
- **THEN** publication MUST stop before creating the GitHub Release and the existing tag MUST NOT be moved without explicit user authorization

#### Scenario: Release and installed projections agree
- **WHEN** the final release audit runs after local installation
- **THEN** it reports the exact source, installed, automation, version, commit, tag, and GitHub Release identities and only then claims the requested release complete
