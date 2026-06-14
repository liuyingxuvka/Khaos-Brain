## Why

Khaos Brain already treats English top-level card fields and route segments as the canonical data model while using `i18n.zh-CN` for human-facing Chinese display. The missing contract is at the CLI and automation boundary: machine-facing commands can still print raw localized Unicode, which makes Windows consoles with non-UTF-8 encodings fail even though the underlying storage and UI model are sound.

This change makes the existing architecture explicit and enforceable: core data and machine interfaces stay canonical and encoding-stable, while desktop/UI display remains localized through the existing display projection layer.

## What Changes

- Add a formal canonical-interface contract for KB storage, CLI/automation output, UI display projection, maintenance prompts, installer checks, and tests.
- Keep top-level card fields, routes, status values, command payload keys, and default machine JSON as English canonical surfaces.
- Keep Chinese UI support through existing `i18n.zh-CN`, route segment labels, and `local_kb.ui_data` display projection.
- Add a single CLI output facade for JSON/text emission instead of per-script encoding workarounds.
- Update repository-managed prompts and templates so future agents maintain the same boundary.
- Update installer health checks so installed global skills/templates are considered healthy only when the canonical-interface markers are present.
- Add regression coverage for Windows-hostile console encodings such as `ascii`, `cp1252`, and `cp936`.
- Do not add a fallback path such as "try UTF-8, then try another console encoding"; the normal path must be encoding-stable by construction.

## Capabilities

### New Capabilities
- `kb-canonical-interface`: Defines how KB canonical data, localized display data, CLI/automation machine output, installer checks, and regression tests must stay separated.

### Modified Capabilities

None. There are currently no archived OpenSpec specs in `openspec/specs/`, so this change introduces the first explicit capability spec for this boundary.

## Impact

- Affected documentation: `PROJECT_SPEC.md`, maintenance/UI runbooks, and Windows desktop notes.
- Affected prompts/templates: local KB retrieval skill prompts and installed preflight templates.
- Affected code: KB CLI scripts, installer/check output, preflight launcher template, and any JSON-emitting KB automation entrypoints.
- Affected tests: i18n/display tests, launcher compatibility tests, installer tests, and new encoding-matrix tests for CLI output.
- Affected local install state: after implementation, `scripts/install_codex_kb.py --json` and `scripts/install_codex_kb.py --check --json` must be run so the machine-installed Codex integration receives the updated templates.
