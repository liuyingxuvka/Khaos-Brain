## ADDED Requirements

### Requirement: Active-index rebuild and reactivation require explicit publisher authority
Every active-index rebuild SHALL require an explicit non-default publisher identity. Normal runtime MUST accept only the canonical Sleep lifecycle publisher; the versioned maintenance migration MAY publish only inside its rollbackable upgrade boundary. Retrieval, Dream, organization workflows, tests acting as ordinary consumers, manual helpers, and unknown callers MUST NOT rebuild, reactivate, or clear the durable invalidation marker.

#### Scenario: Canonical Sleep rebuilds a stale index
- **WHEN** the canonical Sleep lifecycle publisher supplies its exact authority and the complete candidate index passes prepublication, source, lifecycle, LogicGuard, activation-token, and superseding-publication checks
- **THEN** the system MUST activate that generation, write its authority receipt, and remove the captured invalidation marker

#### Scenario: Versioned migration rebuilds during upgrade
- **WHEN** the versioned maintenance migration owns the rollbackable upgrade and supplies its exact publisher authority
- **THEN** the system MAY rebuild and activate the current index only as part of the validated migration transaction

#### Scenario: An unauthorized caller requests rebuild
- **WHEN** a caller omits publisher authority or supplies an identity outside the exact allowlist
- **THEN** the rebuild MUST fail before writing the index, activation authority, or invalidation marker state

#### Scenario: Authority changes while rebuild scans
- **WHEN** the captured invalidation token, current LogicGuard authority, lifecycle authority, or active publication changes before activation
- **THEN** activation MUST fail visibly, the current marker MUST remain authoritative, and no alternate reader or publisher MAY complete the request
