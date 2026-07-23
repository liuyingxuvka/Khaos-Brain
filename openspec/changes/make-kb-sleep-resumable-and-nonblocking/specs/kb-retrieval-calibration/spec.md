## MODIFIED Requirements

### Requirement: Foreground retrieval uses a compact fail-closed authority snapshot
Routine retrieval SHALL read one compact current-generation pointer that binds an immutable active-index path and digest, activation receipt, current LogicGuard generation, lifecycle checkpoint, source watermark, and exact-entry deny projection digest. It SHALL validate only that bound authority, the immutable index, and the exact records that can be returned. It MUST NOT rescan every inactive card, replay the complete lifecycle event log, or treat mutable source YAML as the serving authority on each query. Within one process it MAY reuse only a successful exact validation whose key binds the repository root and every pointer-bound digest. A changed pointer, immutable index, activation authority, LogicGuard generation, or deny projection MUST force exact revalidation or visible failure; failed validation MUST NOT be cached. Observation-only, no-effect, and additive-pending work SHALL NOT block the current generation. Exact entry removal or replacement SHALL be enforced by the pointer-bound subtractive deny projection. Only evidence-bound corruption of the exact current generation or its authority MAY globally fail closed. Full manifest and lifecycle replay SHALL remain mandatory for rebuild, Sleep, migration, and aggregate audit rather than foreground query latency.

#### Scenario: Observation intake or additive candidate work occurs
- **WHEN** another AI records an observation or Sleep stages a candidate that is absent from the current index
- **THEN** the current immutable generation remains queryable without a full manifest scan or lifecycle replay

#### Scenario: One indexed entry loses eligibility
- **WHEN** a trusted or candidate entry currently present in the active index is revoked or replaced
- **THEN** its exact record identity is denied before the transition commits while unrelated records in the same generation remain queryable

#### Scenario: Current index authority is corrupt
- **WHEN** the bound immutable index, pointer, activation receipt, or exact current-generation digest fails validation
- **THEN** routine retrieval rejects the exact current generation and no stale-source or alternate-reader fallback may return results

#### Scenario: Mutable source changes while the generation remains current
- **WHEN** a source YAML changes after the current immutable generation was activated without an exact-entry revoke or proven current-generation corruption
- **THEN** foreground retrieval continues from its immutable generation and Sleep or migration accounts for the change before a later activation

### Requirement: Active-index rebuild and reactivation require explicit publisher authority
Every active-index rebuild SHALL require an explicit non-default publisher identity. Normal runtime MUST accept only the canonical Sleep lifecycle publisher; the versioned maintenance migration MAY publish only inside its rollbackable upgrade boundary. A publisher SHALL build a new immutable index and complete authority projection away from the current pointer, validate the entire candidate generation, and atomically replace the single current-generation pointer last. Retrieval, Dream, organization workflows, tests acting as ordinary consumers, manual helpers, and unknown callers MUST NOT rebuild, reactivate, mutate the pointer, or retire current-corruption authority.

#### Scenario: Canonical Sleep activates a complete staged generation
- **WHEN** the canonical Sleep lifecycle publisher supplies its exact authority and the complete candidate generation passes prepublication, source, lifecycle, LogicGuard, deny-projection, activation-token, and superseding-publication checks
- **THEN** the system MUST write immutable generation artifacts first and atomically replace the current-generation pointer last

#### Scenario: Versioned migration rebuilds during upgrade
- **WHEN** the versioned maintenance migration owns the rollbackable upgrade and supplies its exact publisher authority
- **THEN** the system MAY rebuild and activate the current index only as part of the validated direct-migration transaction

#### Scenario: An unauthorized caller requests rebuild
- **WHEN** a caller omits publisher authority or supplies an identity outside the exact allowlist
- **THEN** the rebuild MUST fail before writing immutable generation artifacts, activation authority, pointer, deny projection, or corruption state

#### Scenario: Authority changes while rebuild scans
- **WHEN** the captured current pointer, lifecycle authority, LogicGuard authority, deny projection, or active publication changes before activation
- **THEN** activation MUST fail visibly, the prior current pointer remains authoritative, and no alternate reader or publisher MAY complete the request
