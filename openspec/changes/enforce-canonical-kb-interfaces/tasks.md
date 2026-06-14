## 1. FlowGuard And Contract Setup

- [x] 1.1 Verify the real FlowGuard package is importable before production edits.
- [x] 1.2 Inventory existing FlowGuard models and decide whether to extend an existing model or add a focused child model.
- [x] 1.3 Record the implementation structure mapping from model obligations to modules, prompts, tests, and install checks.

## 2. Documentation And Prompt Contract

- [x] 2.1 Update `PROJECT_SPEC.md` with the canonical machine/core interface and localized display projection contract.
- [x] 2.2 Update runbooks and UI/Windows docs so maintenance, desktop UI, and CLI boundaries agree.
- [x] 2.3 Update repository-managed local KB prompts and skills with stable canonical-interface markers.
- [x] 2.4 Update installed preflight templates and global default templates with the same boundary.

## 3. CLI Output Implementation

- [x] 3.1 Add a shared CLI output helper for encoding-stable machine JSON and short human text.
- [x] 3.2 Convert local KB skill scripts to use the shared JSON output helper.
- [x] 3.3 Convert top-level scripts and templates that emit machine JSON to use the shared output behavior.
- [x] 3.4 Preserve UTF-8 storage behavior and localized UI display behavior.

## 4. Installer And Regression Coverage

- [x] 4.1 Add installer health-check coverage for canonical-interface readiness across repository prompts and installed assets.
- [x] 4.2 Add CLI encoding regression tests for hostile Windows console encodings.
- [x] 4.3 Update existing i18n/launcher/install tests to assert the canonical/display boundary.

## 5. Validation, Install Sync, And Git Sync

- [x] 5.1 Run FlowGuard model checks and model-test alignment review for the changed obligations.
- [x] 5.2 Run focused pytest/unittest regression suites and fix failures.
- [x] 5.3 Run installer sync and install health check to update the local Codex installation.
- [x] 5.4 Run final git checks, stage only scoped files, and create a local git commit on the Codex branch.
- [x] 5.5 Perform KB postflight and record any reusable lesson exposed by the implementation.
