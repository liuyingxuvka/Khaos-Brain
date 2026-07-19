## MODIFIED Requirements

### Requirement: Active-task postflight has one bounded history-intake path
An active-task postflight SHALL durably append exactly one caller-identified
observation and SHALL emit one matching terminal receipt without synchronously
admitting the observation, replaying lifecycle history, creating a candidate,
publishing LogicGuard authority, or rebuilding the active index. Sleep SHALL be
the sole normal-runtime owner of those later stages. The terminal receipt SHALL
bind the event fingerprint, uniqueness result, lifecycle/current-authority/index
identities before and after the append, writer-lock release, measured duration,
and terminal budget. The complete writer-lock wait MUST fit inside the terminal
budget, and the caller's launcher timeout MUST exceed that terminal budget with
explicit startup, result-transport, and process-cleanup headroom.

#### Scenario: Postflight records an observation on a large KB
- **WHEN** the lifecycle ledger is large but an active task records one new observation
- **THEN** the command MUST complete through the bounded history-intake path without reading or replaying that lifecycle ledger, MUST leave lifecycle/current-authority/index identities unchanged, and MUST return terminal `success` only after the history event and matching receipt are durable

#### Scenario: Postflight waits behind the current writer
- **WHEN** the sole current writer owns the lifecycle lock for less than the declared writer-lock timeout
- **THEN** the postflight caller MUST continue waiting through a terminal budget that contains that lock timeout and MUST NOT interrupt or duplicate the valid owner

#### Scenario: Postflight is retried with the same event id
- **WHEN** a caller repeats a postflight request with the same event id and identical event fingerprint after terminal success
- **THEN** the system MUST reuse the existing success receipt, MUST keep exactly one history event, and MUST NOT admit, create, publish, or index anything synchronously

#### Scenario: The outer launcher stops before terminal JSON
- **WHEN** the launcher is interrupted or reaches its own timeout before receiving terminal JSON
- **THEN** the caller MUST preserve the original event id, MUST confirm whether the original descendant process tree is still live, and MUST inspect the same episode after confirmed exit without starting another writer, alternate route, fallback, or compatibility path

#### Scenario: A process stopped after the event append but before terminal receipt
- **WHEN** inspection finds exactly one matching history event but no valid matching terminal receipt
- **THEN** the result MUST be `timeout_unknown`, MUST NOT be inferred as success or failure, and a retry MUST NOT append a duplicate event; the current Sleep or versioned upgrade owner SHALL settle the episode through the sole current lifecycle path
