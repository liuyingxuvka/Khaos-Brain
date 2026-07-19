# kb-upgrade-migration Specification

## Purpose
TBD - created by archiving change converge-kb-learning-and-upgrade-migration. Update Purpose after archive.
## Requirements
### Requirement: Complete retirement of KB Architect
Fresh installs and upgrades SHALL omit the exact managed Architect skill,
automation, prompt, lane, queue, and runtime entrypoints. Retirement checking
SHALL inspect current source, installed paths, active prompts, and managed
automation definitions without depending on a SkillGuard registry.

#### Scenario: A similarly named user asset exists
- **WHEN** an unrelated user file contains the word architect
- **THEN** retirement leaves it unchanged and checks only the exact managed surfaces

### Requirement: Consumer skill installation is clean and transactional
The installer SHALL stage each maintained skill from its clean consumer
projection, prove exact staged and active manifests, activate transactionally,
and retain rollback material until post-activation health passes. Author-side
`.skillguard` files, contracts, receipts, router projections, fixtures, and
source-only notes MUST NOT enter the installed skill.

#### Scenario: Author-control material reaches staging
- **WHEN** a staged skill contains `.skillguard` or a SkillGuard runtime token
- **THEN** activation fails before the live skill tree is changed

#### Scenario: Installation succeeds
- **WHEN** every clean projection and target-owned health check passes
- **THEN** the active installed manifest equals the consumer projection and no ordinary project is modified

### Requirement: Automation state is preserved exactly
Before changing managed automations, the installer SHALL capture runtime status
and independent `user_paused` state for the four surviving automations and
pause them. After every target-owned update and installation gate passes, it
SHALL apply and read back the exact restoration plan. Architect and automatic
system update remain absent.

#### Scenario: One restoration readback differs
- **WHEN** status, user pause metadata, or target file hash differs
- **THEN** all survivors remain or return paused and the upgrade fails visibly

### Requirement: Validation toolchains are product-native
Long assurance SHALL freeze the current FlowGuard package and the complete
public ResearchGuard package that owns the exact `researchguard.logic` member.
It MUST NOT install or consult the retired standalone LogicGuard package, and
it MUST NOT require, freeze, install, or recheck SkillGuard as a consumer
validation toolchain. The author contract audit resolves its compiler only on
the maintainer computer and remains outside the installed product.

#### Scenario: Installed SkillGuard is absent
- **WHEN** consumer readiness runs with current FlowGuard, ResearchGuard logic, clean installed skills, and target-native tests
- **THEN** absence of SkillGuard does not block consumer readiness

### Requirement: Upgrade completion uses current independent evidence
Completion SHALL require current passing migration, Architect absence,
transactional clean installation, active-index integrity, FlowGuard behavior,
LogicGuard runtime, retrieval, target-native tests, and full-regression
evidence. Author contract maintenance is reported separately. Stale, skipped,
failed, timed-out, running, progress-only, or cleanup-unconfirmed evidence
MUST NOT satisfy completion.

#### Scenario: One skill's test is offered as another skill's evidence
- **WHEN** the alignment or aggregate attempts cross-unit receipt reuse
- **THEN** completion blocks with an ownership conflict

### Requirement: Manual update completes directly
An applicable explicit manual update SHALL bind one run id from authorization
through exact restoration, final installed health, CURRENT state, snapshot
cleanup, lock release, and immutable native receipt. No intermediate
SkillGuard closure or separate activation receipt is required or permitted.

#### Scenario: Direct manual update passes
- **WHEN** every native gate and final receipt validation passes
- **THEN** the update reports `current-and-restored`

#### Scenario: No update is available
- **WHEN** the target-owned topology check proves the declared no-update condition
- **THEN** the route may close as its own non-mutating no-op without external authorization

### Requirement: Upgrade receipts are encoding-stable and bounded
Every fresh install, upgrade, rollback, and no-delta run SHALL emit a bounded
machine receipt recording source and installed identities, migration and
transaction checkpoints, preserved automation state, clean projection
manifests, final target-native checks, and terminal status.

The current upgrade-attempt authority SHALL consist of one bounded HEAD
document and the one bounded current projection named by that HEAD. Ordinary
installation currentness and health checks MUST NOT enumerate attempt
directories, load immutable event payloads, or inspect prior attempt
projections. A missing, malformed, oversized, stale, or escaping HEAD/current
binding SHALL fail visibly; it MUST NOT select an attempt by scanning history
or fall back to the committed install manifest.

After the final upgrade-attempt checkpoint is published, the lightweight
committed install state SHALL bind that exact attempt by both `attempt_id` and
`receipt_hash`. An independent post-command installation check SHALL compare
those fields with the sole current HEAD/current authority. The installer MUST
NOT report durable completion from an earlier in-memory projection that omits
or predates the final attempt receipt.

#### Scenario: Only version metadata changed
- **WHEN** no current transaction and validation receipt exists
- **THEN** the upgrade MUST NOT be reported complete

#### Scenario: Attempt history is very large
- **WHEN** immutable attempt events and retired attempt projections occupy many gigabytes
- **THEN** the ordinary currentness check reads only the bounded HEAD and its exact current projection
- **AND** its declared read budget and history-scan count remain bounded independently of history size

#### Scenario: Current attempt authority is absent or oversized
- **WHEN** the HEAD or the exact current projection is missing, malformed, oversized, hash-mismatched, or outside the attempt root
- **THEN** currentness fails immediately with the current-authority defect
- **AND** no prior attempt, install-manifest copy, directory scan, compatibility reader, or fallback authority is consulted

#### Scenario: Installer internal check passes but committed binding is missing
- **WHEN** the installer publishes its final attempt checkpoint but the
  lightweight install state omits or mismatches that attempt's `receipt_hash`
- **THEN** the independent installation check fails with an exact
  current-attempt binding defect
- **AND** the four scheduled automations remain paused until one current
  installer transaction persists and verifies the matching binding
