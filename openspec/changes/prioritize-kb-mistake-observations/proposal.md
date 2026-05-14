## Why

Codex already records KB postflight observations, but the installed default prompts do not make the agent's own mistakes, weak paths, missed instructions, failed validations, and later corrections the highest-priority evidence. This makes the most reusable learning signal depend on implicit judgment instead of a checked install contract.

## What Changes

- Make mistake-first KB postflight explicit in the global predictive KB skill, global AGENTS defaults, and implicit OpenAI skill prompt.
- Preserve successful reusable observations as allowed KB signals; this change does not suppress useful success evidence.
- Add installer health checks and tests so future installs fail if the mistake-priority wording disappears.
- Keep the observation schema and consolidation rules unchanged because they already support contrastive evidence.

## Capabilities

### New Capabilities
- `kb-postflight-priority`: Defines the required priority order for KB postflight observation capture and install verification.

### Modified Capabilities

## Impact

- Affects predictive KB prompt templates under `templates/predictive-kb-preflight/`.
- Affects local installed Codex defaults after rerunning `scripts/install_codex_kb.py`.
- Affects installer check logic in `local_kb/install.py` and related tests.
- No API, dependency, schema, or trusted-card migration is required.
