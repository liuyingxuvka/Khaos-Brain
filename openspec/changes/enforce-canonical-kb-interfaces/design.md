## Context

The repository already has the correct high-level split:

- top-level card fields and route segments are canonical English;
- localized human display is stored under `i18n.zh-CN`;
- `local_kb.i18n` and `local_kb.ui_data` already project canonical entries into localized UI view models;
- file storage uses UTF-8 and should keep real human text intact.

The weak boundary is the command-line and automation layer. Many scripts directly call `json.dumps(..., ensure_ascii=False)` and print the result. That is fine on UTF-8 consoles, but it can fail on Windows consoles configured as `ascii`, `cp1252`, or other non-UTF-8 encodings. The repair should not guess console encodings and should not add a per-command fallback. Instead, it should make CLI/automation output encoding-stable by construction.

## Goals / Non-Goals

**Goals:**

- Preserve Chinese desktop/UI display.
- Preserve UTF-8 storage for KB files and history files.
- Make default CLI/automation JSON output safe on non-UTF-8 Windows consoles.
- Keep machine payloads canonical unless a command is explicitly a UI display surface.
- Centralize CLI output behavior so future scripts do not repeat encoding decisions.
- Make installer checks detect drift in prompts/templates and CLI output rules.
- Add tests that prove both sides: CLI output is encoding-stable and UI display remains localized.

**Non-Goals:**

- Do not translate all user input into English.
- Do not remove existing `i18n.zh-CN` content.
- Do not change card schema by adding another localization field.
- Do not change file storage to ASCII.
- Do not add a runtime fallback such as retrying with a different console code page.
- Do not introduce embeddings, databases, external services, or broad retrieval redesign.

## Decisions

### Decision 1: Canonical machine output is a separate interface from localized UI display

Default CLI/automation JSON is treated as a machine interface. It must use canonical keys, canonical route values, and encoding-stable serialization. Localized Chinese display stays in UI view models and files.

Alternative considered: let every command choose its own JSON encoding or add a `chcp 65001` prerequisite. Rejected because it creates many hidden branches and makes Windows behavior depend on shell state.

### Decision 2: Use a single CLI output facade

Add a small module, `local_kb/cli_output.py`, with helpers for JSON and short human messages. JSON output uses `ensure_ascii=True` by default, so even if a payload contains Chinese text, the terminal receives ASCII characters and the parsed JSON still round-trips to the same Unicode values.

Alternative considered: replace every `json.dumps(... ensure_ascii=False)` with `ensure_ascii=True` directly. Rejected because it would repeat the rule across scripts and make future drift likely.

### Decision 3: Keep storage UTF-8 and localized UI unchanged

`local_kb.store` and YAML/JSONL persistence keep using UTF-8 and `allow_unicode` / `ensure_ascii=False` where they are writing files, not terminal output. The encoding-stability rule applies to console emission, not durable storage.

Alternative considered: ASCII-escape all stored files. Rejected because it makes the KB less human-auditable and solves the wrong surface.

### Decision 4: Installer health checks become the sync gate

The installer check must report an explicit canonical-interface readiness item. It should inspect both installed global assets and repository-managed prompt/template sources because this repository has two behavior surfaces: installed Codex integration and repo-local skill prompts.

Alternative considered: rely only on tests. Rejected because cross-machine setup depends on the installer copying the right prompt/template state.

### Decision 5: FlowGuard evidence stays attached to existing model boundaries

Use existing i18n, governance, and maintenance FlowGuard models where possible. Add a focused child model only if the existing model inventory lacks a clear owner for CLI machine output.

Alternative considered: create a new broad "encoding model" from scratch. Rejected because the current issue is an interface-boundary gap in an existing architecture, not a new product subsystem.

## Risks / Trade-offs

- [Risk] ASCII-safe JSON is less readable in a raw console when localized text appears as escape sequences. -> Mitigation: this only affects machine output; UI and files remain readable Unicode.
- [Risk] A script may keep a direct `print(json.dumps(... ensure_ascii=False))`. -> Mitigation: add grep-style tests and targeted subprocess tests under hostile encodings.
- [Risk] Installer checks could become too brittle if they require exact wording. -> Mitigation: use stable marker phrases for the canonical-interface contract rather than matching long paragraphs.
- [Risk] Running install sync updates files under the user's Codex home, not only the repo. -> Mitigation: this is intentional for this task and is verified by `scripts/install_codex_kb.py --check --json`.
- [Risk] Existing dirty files may contain user or automation changes. -> Mitigation: preserve them, avoid reverting, and stage only this task's final intended files.

## Migration Plan

1. Add OpenSpec capability spec and tasks.
2. Run FlowGuard preflight and map the implementation structure.
3. Update docs and prompts with stable canonical-interface markers.
4. Add `local_kb/cli_output.py`.
5. Convert CLI/automation JSON emitters to use the facade.
6. Add installer checklist coverage for canonical-interface readiness.
7. Add tests for encoding-stable JSON and preserved UI localization.
8. Run focused tests, FlowGuard model checks, installer sync, and install check.
9. Commit the scoped repository changes on a Codex branch.

Rollback is ordinary git rollback for repository files plus rerunning the installer from the desired commit to refresh installed Codex assets.

## Open Questions

None for implementation. The intended user-facing behavior is fixed: one normal path, no console-encoding fallback, English canonical machine/core interface, Chinese UI display projection.
