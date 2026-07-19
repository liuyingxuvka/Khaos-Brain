# Converge KB learning and upgrade migration

## Why

The maintenance system needs one current architecture after several generations
of migration, assurance, and skill-maintenance work. The earlier design made
SkillGuard part of installed skill execution and attempted to reuse validation
receipts across skills. That crossed the distribution boundary: SkillGuard is
an author-side school and examiner, not a consumer runtime.

## What Changes

- Keep Sleep, Dream, organization contribution, organization maintenance, and
  manual update as five independent maintenance units.
- Give every unit its own domain promise, FlowGuard model, native entrypoint,
  immutable runtime receipt, positive-depth test, and shallow-rejection test.
- Treat any semantic or test-node overlap between maintained units as a
  boundary defect; do not share or reuse proof across units.
- Keep author-only SkillGuard contracts in the maintainer source tree and
  exclude them completely from consumer installations and ordinary projects.
- Make the manual updater close its exact restore, final health, CURRENT, and
  cleanup route with its own native receipt.
- Make installation currentness a shallow read-only audit that never launches
  migrations, model regressions, retrieval evaluation, or another validation
  owner.
- Give every expensive consumer-assurance check an exact input-component
  identity so unchanged owners reuse one immutable success receipt and only
  affected owners execute. Late data admission invalidates only the owners
  whose declared data inputs changed; it never causes an unconditional second
  aggregate campaign.
- Run repository validation once per pull request or exact `main` source
  revision. A release tag only verifies the successful exact-`main` receipt
  and never owns another test execution.
- Keep official OpenSpec external and unmanaged by SkillGuard.
- Preserve transactional installation, exact user pause state, rollback,
  LogicGuard authority, FlowGuard behavior checks, retrieval quality, direct
  migration, and current-only runtime requirements.

## Impact

- Affected code: maintenance runners, consumer projection, installer,
  affected-owner assurance, readiness aggregation, model-test alignment,
  manual update, CI trigger ownership, and retirement checks.
- Affected artifacts: five author-side contracts, FlowGuard models, OpenSpec
  specifications, tests, installed skills, and local installation receipts.
- Out of scope: guaranteeing compatibility with arbitrary third-party skills
  on another computer or modifying official OpenSpec skills.
