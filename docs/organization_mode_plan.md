# Organization Mode Plan

This document records the planned post-v0.1 direction for adding optional
organization sharing to Khaos Brain.

`PROJECT_SPEC.md` remains authoritative for v0.1. Organization mode should be
added as an optional overlay on the same core software, not as a separate
product fork.

## Product Shape

Use one Khaos Brain codebase.

- Default mode: personal local KB only.
- Optional organization mode: personal local KB plus one or more configured
  organization sources.
- Organization sources are content repositories, not separate software
  editions.

The first organization source should be a GitHub repository that is mirrored to
the local machine for fast read-only retrieval.

## Source Model

Each local installation may have multiple knowledge sources:

```yaml
sources:
  - id: local
    type: local
    path: C:/Users/example/Documents/Knowledge
    writable: true

  - id: org-main
    type: git
    repo: https://github.com/example-org/org-kb.git
    local_path: C:/Users/example/.khaos/org/org-main
    writable: false
    contribution_mode: pull_request
```

Retrieval should prefer local knowledge but can merge organization results into
the same result list with clear source labels:

1. `local/private`
2. `local/public`
3. `org/<org-id>/trusted`
4. `org/<org-id>/candidate`
5. `org/<org-id>/skill`

Current user instructions always override any retrieved local or organization
card.

When no organization source is configured, the product should look and behave
like the current personal KB. After an organization GitHub source is configured,
the UI should expose a clear source split such as `Local` and `Organization` in
the browsing/filter area. Every card result and detail view should show at
least:

- source kind: local or organization;
- source scope: private, public, trusted, candidate, or Skill;
- contributor or maintainer identity when known.

Older personal cards that do not have source metadata should be interpreted as
local cards.

## Organization Repository Layout

An initial GitHub-backed organization KB can use a file layout such as:

```text
org-kb/
  kb/
    trusted/
    candidates/
    imports/
  skills/
    registry.yaml
    candidates/
  docs/
    sharing-policy.md
    privacy-policy.md
    maintainer-policy.md
```

The organization repository is the canonical shared source. Each machine keeps a
local mirror for search and browsing.

## Identity Model

Do not rely only on a raw machine code or hardware fingerprint.

Use a layered identity model:

- `github_login`: the verified GitHub account used to access the organization
  repository. This is the primary organization contributor identity.
- `display_name`: a user-editable human name for local UI display.
- `local_installation_id`: a generated UUID for this Khaos Brain installation.
  This distinguishes two computers used by the same person without exposing raw
  hardware identifiers.
- `machine_label`: a user-editable local label such as `office-laptop` or
  `home-desktop`.
- `organization_id`: the organization namespace, such as `acme`.

Example:

```yaml
local_identity:
  organization_id: acme
  github_login: alice
  display_name: Alice Zhang
  local_installation_id: 7f2444f5-8f02-4c58-91cc-9fda7ab3b391
  machine_label: office-laptop
```

Reasoning:

- GitHub login is better for unique organizational authorship because it is
  already tied to repository access.
- Installation ID is better than raw machine code because it is stable enough
  for provenance but avoids unnecessary hardware fingerprinting.
- Display name and machine label are local presentation fields by default. A
  user changing them should not rewrite other users' views or change canonical
  organization authorship.
- Machine label is useful for the local user to distinguish machines and can be
  changed by the user.
- One person using two machines should appear as the same GitHub contributor
  with two local installation IDs or machine labels.

Organization submissions should use `github_login` as the canonical author. A
submission may include `local_installation_id` for provenance when the user
allows it. Editable display names and machine labels should be treated as
optional display metadata, not as stable organization identity.

GitHub identity discovery should be best-effort rather than assumed. The UI
itself should not depend on Codex knowing a GitHub account. A local backend can
try, in order:

1. the configured organization source account;
2. `gh auth status` / `gh api user` when GitHub CLI is installed and logged in;
3. the authenticated `git` credential used to fetch the organization repo when
   it is available;
4. a manually entered or confirmed GitHub login.

The UI should show the detected account and ask for confirmation when identity
is ambiguous. For a personal-only user with no organization GitHub source,
GitHub identity remains optional.

## Permission Model

Permissions should be operation-based.

### Normal User

A normal organization user may:

- configure an organization GitHub KB source;
- sync and search organization cards locally;
- browse the organization Skill registry;
- manually install an approved organization Skill;
- allow sleep maintenance to generate sanitized organization candidates from
  eligible local model cards and observations;
- submit or auto-submit policy-approved organization candidates through a branch
  or pull request;
- submit Skill candidates when they are supported by card evidence and declared
  as card dependencies;
- open a GitHub pull request or contribution branch for those candidates.

A normal organization user should not:

- directly edit organization trusted cards;
- automatically upload private local cards, personal preferences, or
  user-specific cards;
- automatically install organization Skills;
- overwrite another user's Skill package;
- promote candidates to trusted organization knowledge.

### Maintainer

Organization maintainers may:

- review imported card candidates;
- rewrite, split, merge, reject, or promote candidates;
- mark cards deprecated or superseded;
- approve organization Skill registry entries;
- assign organization Skill names and versions;
- maintain privacy and sharing policy docs;
- merge approved pull requests.

Maintainer authority should come from GitHub permissions, not from a local UI
toggle alone.

Recommended GitHub controls:

- protected default branch;
- pull request reviews for trusted-card changes;
- `CODEOWNERS` or an equivalent maintainer team;
- restricted write access for registry and trusted-card paths;
- branch or fork based contribution for normal users.

The local app may expose an "advanced maintainer tools" mode, but that mode
should mean "this installation is allowed to run organization-maintenance
automation locally," not "this installation can bypass organization permissions."
Write actions against the organization repository should still depend on the
authenticated GitHub account and repository rules.

## Advanced Maintenance Mode

Advanced mode is a local automation setting.

Its primary purpose is coordination: avoid every machine trying to maintain,
rewrite, or consolidate the organization repository at the same time.

When enabled on a machine, advanced mode may run scheduled organization
maintenance tasks such as:

- scanning organization candidates;
- proposing card merges, splits, rejections, or promotions;
- preparing pull requests;
- refreshing Skill registry proposals;
- checking organization repository health.

Advanced mode should not directly mutate protected organization content unless
the GitHub account has the required permission and the repository policy allows
that path. The safer default is for advanced maintenance to create a branch,
proposal, or pull request.

Future implementation should include a coordination mechanism so that only one
advanced maintenance job acts on the same organization repository state at a
time. A simple first version could use GitHub branches, pull requests, and a
visible maintenance run file rather than a separate server.

## Organization Candidate Pipeline

Local observations and private cards stay local by default.

The desired long-term behavior is automatic candidate generation, not a purely
manual upload picker. Sleep maintenance should scan local evidence and generate
organization-ready candidates when the evidence is reusable across the
organization.

Automatic candidate generation must filter aggressively:

- prefer predictive `model` and reusable `heuristic` cards;
- exclude personal preferences by default;
- exclude user-specific, credential-specific, customer-specific, or private
  details;
- require enough provenance to explain why the candidate exists;
- preserve the original local card while generating a sanitized organization
  candidate;
- compare against existing organization cards before proposing a duplicate.

The pipeline should be:

1. Local work creates cards, observations, and Skill-use evidence.
2. Sleep maintenance identifies reusable non-preference models.
3. Sleep maintenance generates sanitized organization candidates.
4. Sleep maintenance links required or recommended Skills when the card depends
   on a local Skill.
5. The app places candidates in a local organization outbox.
6. Depending on local policy, the app either shows a review queue or prepares a
   branch / pull request automatically.
7. Organization maintainers review and merge.
8. Organization maintenance consolidates candidates into trusted cards, updates
   older cards, merges duplicates, rejects weak candidates, or marks cards as
   superseded.

No organization contribution should silently upload local private knowledge.
If automatic PR creation is enabled later, it should still target candidate or
import paths, not trusted organization card paths.

## Skill Sharing

Skills should be shared through an organization Skill registry, not mixed
directly into card storage.

Skill sharing should be card-led. A Skill is strongest as an organization
candidate when one or more cards already explain when the Skill is useful, what
problem it solves, what outcome it predicts, and what fallback exists when the
Skill is missing.

Cards may reference organization or local Skills:

```yaml
required_skills:
  - org.github-release@>=1.2.0
fallback:
  guidance: Use the generic GitHub release workflow if the Skill is not installed.
```

Skill registry entries should include:

```yaml
id: org.github-release
version: 1.2.0
owner: platform-team
submitted_by: alice
status: approved
source_repo: https://github.com/example-org/org-skills
```

The first implementation should browse the registry and support manual
installation. Automatic Skill installation should wait for a later security
design.

Local Skill submission should normally follow card dependency evidence:

1. a local card or observation records successful use of a Skill;
2. maintenance detects that the card depends on that Skill;
3. maintenance checks whether the Skill is already in the organization registry;
4. if missing, maintenance proposes a Skill candidate alongside the card
   candidate;
5. maintainers review the card and Skill together.

If a local Skill is frequently used but has no supporting card, maintenance
should create or request a Skill-use observation first. The local KB workflow
should continue strengthening the rule that meaningful Skill use, especially
new Skill use, is written back as KB evidence.

## UI Information Architecture

Organization mode should change the UI, but it should not create two separate
applications.

Use one product shell with two major knowledge spaces:

- `My KB`: local personal knowledge, local candidates, local private/public
  cards, local observations, and locally installed Skills.
- `Organization KB`: configured organization sources, organization trusted and
  candidate cards, organization Skill registry, contribution status, and
  maintenance status.

The UI should also keep a unified search entry point. The default search can
search local knowledge first and organization knowledge second, then display the
merged result list with strong source labels.

Suggested navigation:

```text
Search
My KB
Organization KB
Skills
Contributions
Settings
Maintenance
```

The important distinction is:

- `Search` answers "what should Codex use right now?"
- `My KB` answers "what does this installation know locally?"
- `Organization KB` answers "what shared organization knowledge is available?"
- `Skills` answers "what capabilities are installed or available?"
- `Contributions` answers "what can I submit or what have I submitted?"
- `Maintenance` answers "what automated upkeep is running or proposed?"

When organization mode is not configured, organization-specific navigation
items should be hidden or shown as disabled setup entry points. The personal
local flow should stay simple.

Search and card detail UI must show:

- whether the card is from `Local` or `Organization`;
- source scope such as `local/private`, `local/public`, `org/trusted`, or
  `org/candidate`;
- canonical contributor identity from GitHub when the card came from an
  organization source;
- local display name or machine label only when it is local display metadata;
- trust level and review status;
- required Skill status, such as installed, available, missing, or fallback;
- whether the card is local editable, organization read-only, or contribution
  eligible.

The default browsing screen should not show every layer at once. Prefer a clear
mode switch between route browsing and card detail, with filters for source,
trust level, contributor, and required Skill status.

## UI Surfaces

Organization support should add these UI surfaces:

1. Organization settings
   - GitHub repository URL input.
   - Connection check.
   - Local mirror path.
   - Authenticated GitHub account.
   - Current permission level.

2. Search results
   - Source badge.
   - Contributor.
   - Trust level.
   - Required Skill status.
   - Local/private versus organization/shared distinction.

3. Contribution center
   - Select local cards, observations, and Skills.
   - Show sanitized preview before upload.
   - Show contributor metadata.
   - Create branch or pull request.

4. Organization Skill registry
   - Browse approved and candidate Skills.
   - Show owner, version, status, and install state.
   - Install approved Skills manually.

5. Maintainer tools
   - Review candidate cards and Skill proposals.
   - Promote, reject, split, merge, or deprecate.
   - Require GitHub maintainer permission for remote write actions.

## Implementation Phases

Do not implement all of organization mode at once.

1. Add organization source configuration and local read-only sync.
2. Add multi-source retrieval and source badges.
3. Add automatic organization candidate generation for eligible local model
   cards and observations.
4. Add read-only Skill registry browsing.
5. Add card-led Skill candidate generation and manual Skill installation from
   approved registry entries.
6. Add GitHub pull request contribution for generated card and Skill
   candidates.
7. Add maintainer review UI and GitHub-permission-gated write actions.

## Execution Roadmap

The practical path from personal KB to organization KB should be incremental.
Each milestone should preserve the current personal-only behavior when no
organization source is configured.

### Phase 0: Baseline and Compatibility

Goal: make the current personal KB behavior an explicit baseline.

- Keep existing local card loading, retrieval, UI browsing, and feedback capture
  working unchanged.
- Document the current card fields and decide which new organization fields are
  optional.
- Treat older cards without organization metadata as `local` cards.
- Add tests or checks that prove a personal-only installation still works after
  later organization changes.

Done when: the app can still run as a purely personal KB with no organization
configuration file.

### Phase 1: Source and Provenance Metadata

Goal: add the minimum card attributes needed to distinguish local and
organization knowledge.

Recommended new metadata:

```yaml
source:
  scope: local
  source_id: local
  visibility: private
  organization_id: null
  contributor:
    github_login: null
    display_name: null
    local_installation_id: null
    machine_label: null
```

For organization cards, `organization_id` and `contributor.github_login` become
the important canonical fields. Local display name and machine label remain UI
presentation metadata.

Done when: cards can be loaded and displayed with source labels such as
`local/private`, `local/public`, `org/acme/trusted`, and
`org/acme/candidate`.

### Phase 2: Organization Source Configuration

Goal: let a user connect one organization GitHub repository without changing the
personal KB storage.

Add a local organization source config containing:

- GitHub repository URL.
- Organization ID.
- Local mirror path.
- Authenticated GitHub login, detected when possible and confirmable in UI.
- Local installation ID and optional machine label.
- Contribution mode, initially `pull_request`.

The config should be local-machine state. It should not be committed into a
public repository with user secrets or machine-specific paths.

Done when: the app can validate a GitHub repo URL, fetch through local GitHub
credentials when available, show the configured or detected account, and
remember the local mirror location.

### Phase 3: Read-Only Organization Sync

Goal: make shared organization cards available locally without allowing local
machines to mutate trusted shared data.

- Clone or fetch the organization KB repo into the configured local mirror.
- Read `kb/trusted`, `kb/candidates`, and Skill registry metadata from that
  mirror.
- Show sync status, last fetched commit, and last sync time.
- Do not upload anything in this phase.

Done when: one machine can search and browse organization cards from a local
mirror, and disconnecting the org source returns the app to personal-only mode.

### Phase 4: Multi-Source Search and UI Labels

Goal: merge personal and organization knowledge in the user experience without
blurring ownership.

- Search local cards first, then organization cards.
- Add filters for source, trust level, contributor, and required Skill status.
- Show source badges on every result and in card detail.
- Make organization cards read-only by default.
- Keep the current simple browsing surface, but add clear entry points for
  `My KB`, `Organization KB`, `Skills`, and `Contributions`.

Done when: the user can see which result came from local private memory, local
public memory, organization trusted knowledge, or organization candidates.

### Phase 5: Automatic Candidate Outbox

Goal: let sleep maintenance automatically prepare organization candidates from
eligible local knowledge.

- Add an organization outbox for generated card and Skill candidates.
- Let sleep maintenance scan local cards, observations, and Skill-use evidence.
- Generate sanitized organization candidates only from reusable models or
  heuristics, not personal preferences.
- Compare candidates against existing organization cards and propose updates,
  merges, supersessions, or rejections when appropriate.
- Keep generated candidates reviewable in UI even when later auto-PR is enabled.
- Write contributions to a branch, fork, or candidate import path.
- Prepare or open a GitHub pull request according to local policy.

Done when: sleep maintenance can produce a local organization candidate outbox
from eligible cards without exposing unrelated private cards.

### Phase 6: Card-Led Organization Skill Registry

Goal: share reusable capabilities separately from predictive cards, but use card
evidence to decide which Skills are worth proposing.

- Add read-only browsing for `skills/registry.yaml`.
- Show Skill owner, version, approval status, source repository, and local
  install state.
- Let cards reference required or recommended organization Skills.
- Detect local Skill dependencies from cards and observations.
- Generate Skill candidates when a generated organization card depends on a
  Skill missing from the registry.
- Require supporting card evidence for normal Skill submission.
- Support manual installation of approved Skills after the registry browsing
  path is reliable.
- Defer automatic Skill installation until there is a stronger security design.

Done when: a generated organization card can carry its Skill dependency, and a
missing dependency can become a linked Skill candidate for maintainer review.

### Phase 7: Maintainer Review and Advanced Maintenance

Goal: support organization cleanup without making every local machine a direct
writer to shared truth.

- Add maintainer UI for reviewing card and Skill candidates.
- Gate trusted-card writes through GitHub permissions and protected-branch
  rules.
- Let advanced maintenance mode run scheduled scans and prepare review PRs.
- Let advanced maintenance detect duplicate cards, stale cards, superseded
  cards, and local evidence that should update an existing organization card
  rather than create a new one.
- Coordinate maintenance through visible branches, pull requests, and run files
  before considering any separate server.

Done when: maintainers can promote, reject, merge, split, or deprecate
organization candidates through a review flow that respects GitHub repository
permissions.

### Phase 8: Rollout and Hardening

Goal: validate the organization model with real multi-machine use before adding
more automation.

- Test with one private organization repo and two or three machines.
- Verify that source labels remain clear in UI and retrieval output.
- Verify that private local cards and personal preferences never upload as raw
  cards; only sanitized, policy-eligible organization candidates may leave the
  local machine.
- Verify that GitHub identity is stable across two machines used by the same
  person.
- Add policy docs for sharing, privacy, and maintainer expectations.
- Only after this, consider richer org features such as centralized policy,
  audit dashboards, or SSO.

Done when: the organization mode works as an optional, reviewable overlay on
the personal KB instead of becoming a separate product.

## First MVP

The first useful organization MVP should include only:

- organization GitHub repo configuration;
- local read-only mirror sync;
- source/provenance metadata;
- multi-source search with source badges;
- organization browsing in the UI.

Call this the read-only foundation MVP.

The first automatic contribution MVP should come after that foundation and
include:

- sleep-generated organization candidate outbox;
- reusable-model filtering that excludes preferences by default;
- duplicate/update detection against organization cards;
- card-led Skill dependency detection;
- branch or pull request preparation to candidate/import paths.

Skill installation, maintainer write tools, and direct trusted-card maintenance
should come after the automatic candidate path is reliable.

## Non-Goals For The First Organization Pass

- No central server.
- No SQL database requirement.
- No vector database.
- No direct multi-user writes to trusted cards.
- No automatic private-card upload.
- No automatic Skill installation.
- No separate enterprise edition unless later requirements demand SSO,
  centralized policy enforcement, or audit dashboards.
