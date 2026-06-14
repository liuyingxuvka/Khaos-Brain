## ADDED Requirements

### Requirement: Canonical Core Data
The system SHALL treat top-level card fields, route segments, status values, command payload keys, and search/routing paths as canonical English machine data.

#### Scenario: localized display does not rename routes
- **WHEN** a card has `domain_path`, `cross_index`, and `i18n.zh-CN` display data
- **THEN** storage, search, and default machine output preserve the canonical English route values

#### Scenario: user-facing display can localize canonical data
- **WHEN** the desktop UI requests Chinese display data
- **THEN** the UI view model may render `i18n.zh-CN` fields and route segment labels without changing the canonical stored fields

### Requirement: CLI Machine Output Is Encoding-Stable
Default CLI and automation JSON output SHALL be safe to print on non-UTF-8 Windows consoles without requiring console code page changes.

#### Scenario: JSON output under hostile console encoding
- **WHEN** a KB CLI command emits `--json` output while `PYTHONIOENCODING` is `ascii`, `cp1252`, or `cp936`
- **THEN** the command exits without `UnicodeEncodeError` and the output remains valid JSON

#### Scenario: parsed JSON preserves Unicode values
- **WHEN** ASCII-safe JSON contains escaped localized values
- **THEN** a JSON parser reconstructs the original Unicode values without data loss

### Requirement: CLI Output Uses A Single Facade
The system SHALL route machine JSON emission for KB command-line and automation entrypoints through a shared CLI output helper instead of duplicating per-script encoding behavior.

#### Scenario: new CLI script emits JSON
- **WHEN** a KB CLI or automation script needs to emit machine JSON
- **THEN** it uses the shared CLI output helper rather than direct `print(json.dumps(... ensure_ascii=False))`

#### Scenario: storage writes remain separate from console writes
- **WHEN** KB files or history events are written to disk
- **THEN** durable storage continues to use UTF-8 and may preserve readable Unicode text

### Requirement: Prompts Preserve The Interface Boundary
Repository-managed skills, prompts, and installed preflight templates SHALL state that canonical machine/core interfaces and localized UI display projections are separate surfaces.

#### Scenario: maintenance prompt handles Chinese display
- **WHEN** Sleep or i18n maintenance fills Chinese display fields
- **THEN** the prompt requires it to update `i18n.zh-CN` or route display labels without rewriting top-level English fields or canonical routes

#### Scenario: architect prompt reviews interface changes
- **WHEN** a proposal touches CLI output, installer templates, prompt behavior, or localization mechanisms
- **THEN** the Architect prompt requires review of the canonical/display boundary before applying mechanism changes

### Requirement: Installer Sync Verifies The Contract
The installer check SHALL expose a canonical-interface readiness checklist item covering repository prompts, installed preflight assets, and CLI output guidance.

#### Scenario: installer check after sync
- **WHEN** `scripts/install_codex_kb.py --json` has refreshed the local Codex installation
- **THEN** `scripts/install_codex_kb.py --check --json` reports the canonical-interface readiness item as passing

#### Scenario: missing canonical-interface marker
- **WHEN** an installed or repository-managed prompt/template loses the canonical-interface marker
- **THEN** the install check reports a failed checklist item or issue instead of claiming full health

### Requirement: Tests Align With The Model
Regression tests SHALL cover both sides of the boundary: encoding-stable machine output and preserved localized UI display.

#### Scenario: machine-output tests
- **WHEN** the focused CLI encoding regression tests run
- **THEN** they execute representative CLI and install-check entrypoints under hostile console encodings and verify valid JSON output

#### Scenario: UI localization tests
- **WHEN** i18n and desktop view-model tests run
- **THEN** they verify that Chinese display fields and route labels remain available through the UI projection layer
