## ADDED Requirements

### Requirement: Mistake evidence has highest postflight priority
The predictive KB postflight instructions SHALL direct Codex to treat its own mistakes, weak paths, missed instructions, failed validations, tool or skill misuse, user corrections, and revised actions as the highest-priority observation evidence.

#### Scenario: Mistake and success evidence both exist
- **WHEN** a task produces both a reusable successful pattern and a Codex mistake or correction episode
- **THEN** the postflight instructions identify the mistake or correction episode as the highest-priority observation evidence while still allowing the successful pattern to be recorded when useful

#### Scenario: Contrastive correction fields are available
- **WHEN** a task includes an earlier weaker action and a later corrected action
- **THEN** the postflight instructions tell Codex to preserve both sides using contrastive fields whenever possible

### Requirement: Success observations remain allowed
The predictive KB postflight instructions MUST NOT suppress successful reusable observations merely because the outcome was successful.

#### Scenario: Successful pattern is reusable
- **WHEN** a task produces a successful reusable pattern without a mistake or correction episode
- **THEN** the postflight instructions still allow Codex to record that pattern as a meaningful KB observation

### Requirement: Install check verifies mistake-priority wording
The installer health check SHALL report whether the global predictive KB skill prompt and managed global AGENTS defaults contain mistake-priority wording.

#### Scenario: Current install contains mistake-priority wording
- **WHEN** `scripts/install_codex_kb.py --check --json` runs after installation
- **THEN** the checklist includes passing mistake-priority items and the strongest session defaults remain ready

#### Scenario: Mistake-priority wording is missing
- **WHEN** the installed global prompt or managed AGENTS defaults omit the mistake-priority markers
- **THEN** the install check marks the corresponding mistake-priority checklist item as not OK and strong session defaults are not ready
