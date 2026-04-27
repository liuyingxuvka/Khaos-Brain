# Organization Mode Plan

This document records the optional organization-sharing design for Khaos Brain
and the current implementation checkpoints used for the first multi-machine
test.

`PROJECT_SPEC.md` remains authoritative for the core product. Organization mode
is implemented as an optional overlay on the same core software, not as a
separate product fork. Sections that still use "should" describe the target
behavior and review rules that the implementation is being checked against.

## Product Shape

Use one Khaos Brain codebase.

- Default mode: personal local KB only.
- Optional organization mode: personal local KB plus one or more configured
  organization sources.
- Organization sources are content repositories, not separate software
  editions.

The first organization source should be a GitHub repository that is mirrored to
the local machine for fast read-only retrieval.

## Organization Mode Gate

Organization mode should be enabled from Settings, not inferred from the mere
presence of GitHub on the machine.

The settings flow should be:

1. User chooses organization mode.
2. UI requires an organization GitHub repository URL.
3. App clones or fetches the repository into a local mirror.
4. App validates that the repository is a Khaos Brain organization KB source.
5. Only after validation succeeds does the app enter organization mode.

Until that validation succeeds, the product stays in personal mode:

- no organization navigation is opened;
- no organization card source is searched;
- no GitHub identity discovery is required;
- no maintainer or advanced maintenance controls are shown.

Validation should check for a minimal repository contract, such as:

- expected `kb/` layout;
- organization KB manifest, for example `khaos_org_kb.yaml`;
- supported schema version;
- organization id;
- readable `kb/main` paths, with `kb/imports` kept as the incoming lane;
- optional `skills/registry.yaml`.

If validation fails, the UI should show the failure reason and keep the local
personal KB as the active mode.

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

The organization repository should contain a small manifest so clients can
distinguish a valid organization KB from an arbitrary GitHub repository. An
initial manifest could be:

```yaml
kind: khaos-organization-kb
schema_version: 1
organization_id: acme
kb:
  main_path: kb/main
  imports_path: kb/imports
skills:
  registry_path: skills/registry.yaml
```

## Private Sandbox Repository

Organization-mode development should use a private GitHub sandbox repository to
exercise the real integration path.

The sandbox should be private, but privacy should be defense-in-depth rather
than the only safety boundary. Content seeded into the sandbox should still be
safe if accidentally exposed.

Recommended sandbox content:

- real shareable `public` model cards;
- real reusable engineering or Codex workflow heuristics;
- sanitized candidate cards generated from local evidence;
- demo organization Skill registry entries;
- policy docs for sharing, privacy, and maintenance.

Do not seed the sandbox with:

- private preference cards;
- user-specific interaction patterns;
- credentials, tokens, raw machine identifiers, or local absolute paths;
- customer, employer, or project secrets;
- raw local observations that have not been sanitized.

This makes the sandbox useful for real testing while preserving the intended
organization-sharing boundary: organization content should be reusable public
experience, not personal memory.

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

GitHub identity discovery should only run after a valid organization source has
been configured. It should be best-effort rather than assumed. The UI itself
should not depend on Codex knowing a GitHub account. A local backend can try, in
order:

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
- install approved organization Skills manually or allow policy-approved
  automatic installation;
- allow sleep maintenance to generate sanitized organization candidates from
  eligible local model cards and observations;
- opt in to local organization maintenance runs that inspect the shared
  organization repo and prepare maintenance branches or pull requests;
- submit or auto-submit policy-approved organization candidates through a branch
  or pull request;
- submit Skill candidates when they are supported by card evidence and declared
  as card dependencies;
- open a GitHub pull request or contribution branch for those candidates.

A normal organization user should not:

- directly edit organization trusted cards;
- automatically upload private local cards, personal preferences, or
  user-specific cards;
- automatically install candidate, rejected, unknown, or unpinned organization
  Skills;
- overwrite another user's Skill package;
- promote candidates to trusted organization knowledge.

### Maintainer

Organization maintainers may:

- review imported card candidates;
- rewrite, split, merge, reject, or promote candidates;
- mark cards deprecated or superseded;
- approve or reject card-and-Skill bundles through organization maintenance;
- assign organization Skill names and versions;
- maintain privacy and sharing policy docs;
- merge approved pull requests.

Separate local maintenance execution from remote authority. A local
"participate in organization maintenance" switch may run scheduled maintenance,
prepare reviewed branches, and open pull requests from any opted-in machine.
GitHub permissions and repository rules decide whether those branches can be
pushed, merged, or become official organization knowledge. The local switch
does not bypass protected branches, but it also should not prevent normal users
from producing maintenance proposals.

Recommended GitHub controls:

- protected default branch;
- pull request reviews for trusted-card changes;
- required GitHub Actions checks for organization-maintenance pull requests;
- repository auto-merge or merge queue for eligible maintenance pull requests;
- a constrained GitHub-side merge actor, such as `github-actions[bot]`, an
  organization bot account, or a GitHub App;
- `CODEOWNERS` or an equivalent maintainer team;
- restricted write access for registry and trusted-card paths;
- branch or fork based contribution for normal users.

The merge actor should live in GitHub cloud automation, not on one user's local
machine. Local machines prepare branches or pull requests. GitHub Actions checks
the pull request. If all required rules pass, GitHub auto-merge or a restricted
bot merges it. If checks fail, the pull request stays open for review.

Some private repositories may not support branch protection without a paid
GitHub plan. In that case, the fallback is still cloud-side automation: run the
organization KB check workflow on pull requests, then let a restricted
GitHub-side bot workflow merge only labeled PRs after the check workflow
completes successfully. This preserves the core boundary that no local machine
directly merges protected organization knowledge.

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

For product wording, advanced mode may appear as an administrator or maintainer
area inside organization mode. Architecturally it is still two checks:

1. organization mode is active because a valid organization KB repo was
   configured;
2. maintainer actions are allowed only to the extent the GitHub account and repo
   rules allow them.

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

## Hash-Based Organization Exchange

Organization mode should use content hashes for exchange deduplication, not a
complex shared version tree.

The organization repository is a stream of reusable cards. Each local
installation periodically mirrors that stream, searches it, and absorbs only the
cards that are actually useful locally. Local and organization maintenance then
use the same existing consolidation logic: similar cards are merged, overloaded
cards are split, weak cards are rejected, and durable cards are promoted.

The exchange unit is a normalized `card_exchange_hash`.

- The hash is based on the predictive card content.
- Local bookkeeping does not affect the hash: adoption metadata, organization
  proposal metadata, paths, timestamps, source labels, status, scope, confidence,
  ids, and display translations are ignored.
- If two cards have the same exchange hash, they are the same exchange payload
  even if their local ids, paths, display language, or review status differ.

### Download And Use

Organization cards can be mirrored locally as read-only source cards, but they
do not become local maintenance cards merely because they were visible in search
or browsing.

Rules:

1. When organization cards are loaded, skip any card whose exchange hash already
   exists in the local KB. This avoids downloading or displaying exact content
   duplicates such as a local trusted card and an organization trusted card with
   the same predictive content.
2. If an organization card is shown but never used, it stays an organization
   source card.
3. When Codex actually uses an organization card, mark that exchange hash as
   used locally.
4. If the same hash already exists locally, do not create another adopted file.
   Treat the existing local card as the local copy.
5. If the hash does not exist locally, create one local adopted candidate under
   `kb/candidates/adopted/<org-id>/`.
6. After use, the card participates in local maintenance as local knowledge. The
   organization provenance is retained for attribution, but split/merge/rewrite
   decisions are handled by the normal local maintenance loop.

If the organization later publishes a new card with the same id but different
content, it has a new exchange hash. The local installation may see it as a new
organization card. The local maintenance loop can then decide whether it is a
duplicate, improvement, split candidate, or unrelated card.

### Upload

Local-to-organization contribution uses the same hash rule.

Rules:

1. Before creating an organization outbox item, compute the local card's
   exchange hash.
2. Do not export two local cards with the same exchange hash in the same outbox.
3. Organization repository checks should report duplicate exchange hashes across
   trusted, candidate, and import paths.
4. Organization maintenance receives only new exchange payloads and then applies
   the normal organization maintenance loop: merge duplicates, split overloaded
   cards, reject weak cards, promote useful cards, and keep Skill bundles tied to
   card evidence.

This keeps the system simple: hashes prevent exact duplicate exchange, while AI
maintenance handles semantic similarity, merge, split, and quality review.

## Organization Card Adoption And Feedback Loop

Organization cards should not become globally mutable just because many local
installations use them. The organization repository remains the shared source,
while each local installation records its own evidence about whether an
organization card worked.

When search retrieves an organization card and Codex actually uses it, the local
installation should either reuse an existing same-hash local card or create one
local adopted candidate. This keeps the local KB as the active maintenance
surface and preserves a natural path for later improvement without requiring a
shared card-version tree.

The rule should be **use on hash**:

1. **Local used copy**
   - On first real use of an organization card, compute its exchange hash.
   - If that hash already exists locally, use the existing local card and do not
     create another duplicate.
   - If that hash does not exist locally, create one local adopted copy.
   - The local copy should keep organization provenance such as organization id,
     source repo, card id, source commit, source path, and source exchange hash.

2. **Usage evidence**
   - Record local usage against the local card or adopted copy.
   - Track local hit quality, task contexts, last used time, and use count.
   - The used copy participates in local-first retrieval on later tasks.

3. **Local maintenance**
   - Once used, the card is local maintenance material.
   - If it is similar to existing local knowledge, local sleep maintenance may
     merge it.
   - If it mixes several predictive relations, local sleep maintenance may split
     it.
   - No special organization-only merge tree is required.

4. **Upstream contribution**
   - Clean adopted copies are not proposed back.
   - Locally improved or newly consolidated cards can enter the organization
     outbox only if their exchange hash has not already been exported in that
     outbox.
   - The organization repository then applies its own maintenance loop to the
     incoming candidates.

This keeps the local KB as the place where actual use is learned and refined,
while the organization KB receives reviewed new payloads instead of uncontrolled
direct edits from every machine.

Example local adopted-candidate metadata:

```yaml
organization_adoption:
  organization_id: acme
  source_entry_id: org-release-checklist
  source_repo: https://github.com/acme/org-kb
  source_commit: abc1234
  source_path: kb/main/release-checklist.yaml
  source_exchange_hash: 6f4c...
  state: clean
  hit_count: 3
  adopted_at: 2026-04-24T08:00:00Z
  last_used_at: 2026-04-24
```

## Skill Sharing

Skills should be shared through organization maintenance, not as standalone
files that become trusted merely because someone uploaded them.

Skill sharing should be card-led. The review unit is a bundle:

- one or more candidate cards;
- required or recommended Skill candidates;
- dependency metadata linking cards to Skills;
- task evidence showing when the Skill helped, failed, replaced a fallback, or
  should be invoked earlier.

A Skill is strongest as an organization candidate when cards already explain
when it is useful, what problem it solves, what outcome it predicts, and what
fallback exists when the Skill is missing.

Cards may reference organization or local Skills. In the first implementation,
Skills travel as card-bound bundles rather than as free-floating organization
assets:

```yaml
skill_dependencies:
  - bundle_id: skill-bundle-20260424T213000Z-a8f3
    local_name: github-helper
    requirement: required
    content_hash: sha256:...
    version_time: 2026-04-24T21:30:00Z
fallback:
  guidance: Use the generic GitHub release workflow if the Skill is not installed.
```

The `bundle_id` is the Skill lineage. The `content_hash` is the exact version.
The latest approved version for a `bundle_id` is selected by `version_time`.
Imported organization Skill bundles are read-only locally. Only the original
author may update the same `bundle_id`; non-author changes must fork to a new
`bundle_id`.

Skill registry entries or bundle metadata should include:

```yaml
bundle_id: skill-bundle-20260424T213000Z-a8f3
local_name: github-helper
original_author: alice
status: approved
content_hash: sha256:...
version_time: 2026-04-24T21:30:00Z
readonly_when_imported: true
update_policy: original_author_only
```

Use three Skill review states:

- `candidate`: uploaded or generated, but not reviewed yet;
- `approved`: reviewed together with supporting cards and evidence, eligible
  for search and policy-approved automatic installation;
- `rejected`: reviewed and not recommended; kept only as an audit signal so the
  same weak Skill/card bundle does not recur silently.

Do not make `blocked` or `deprecated` first-pass states unless later operation
shows they are needed. Rejected bundles are enough for the initial review loop.

Approved Skill auto-installation is allowed when local policy permits it and
the bundle entry is pinned to a version time and content hash. Candidate or
rejected Skills must not be silently installed.

Local Skill submission should normally follow card dependency evidence:

1. a local card or observation records successful use of a Skill;
2. maintenance detects that the card depends on that Skill;
3. maintenance checks whether the Skill bundle already has a `bundle_id`;
4. if missing, maintenance proposes a new card-bound Skill bundle alongside the
   card candidate;
5. organization maintenance reviews the card, Skill, dependency link, and
   evidence together;
6. approved bundles enter the official organization KB; rejected bundles stay
   out of the official search/install path.

Local sleep maintenance should consolidate imported organization Skills by
`bundle_id`, keep only the latest approved local copy by `version_time`, and
preserve the source-card references explaining why the Skill exists. Uploading
any card that depends on a Skill should attach the local latest version for
that `bundle_id`, not an older copy carried by the card.

If a local Skill is frequently used but has no supporting card, maintenance
should create or request a Skill-use observation first. The local KB workflow
should continue strengthening the rule that meaningful Skill use, especially
new Skill use, is written back as KB evidence.

## Organization Sleep And Maintenance

Organization maintenance is the shared-library equivalent of local sleep/dream.
Its purpose is to turn many users' candidate uploads into a smaller, reviewed,
auditable organization knowledge base.

Inputs:

- imported candidate cards from local outboxes;
- imported Skill candidates;
- dependency metadata linking cards and Skills;
- local adoption feedback from organization cards;
- task evidence and Skill-use observations;
- current organization approved cards and approved Skill registry entries.

Organization maintenance should review bundles, not isolated files. A bundle can
contain a card, one or more Skills, and evidence. The maintenance run decides
whether the whole bundle should become organization knowledge, stay candidate,
or be rejected.

Core maintenance actions:

- deduplicate similar cards from different contributors;
- merge compatible cards and split overloaded cards;
- rewrite candidates into organization-neutral wording;
- reject weak, private, unsafe, or over-specific candidates;
- approve card-and-Skill bundles together when evidence supports them;
- pin approved Skill versions and content hashes;
- write rejected review records so similar weak submissions can be recognized;
- check that every approved Skill has supporting card evidence;
- check that every approved card dependency points to an approved Skill or a
  documented fallback;
- scan for private data, local paths, credentials, and unsafe Skill behavior.

Participation model:

- Any opted-in machine may run local organization maintenance and prepare a
  maintenance branch or pull request.
- GitHub permissions and protected branch rules decide whether the maintenance
  branch is accepted into the organization repo.
- The local "participate in organization maintenance" switch schedules work; it
  does not grant merge authority.

Machines that participate in organization maintenance may use a local
organization-review Skill as a judgment aid. That Skill teaches Codex how to
audit other Skills, card dependencies, evidence quality, privacy boundaries,
and install safety, but it is not an apply gate for ordinary organization
Sleep-style card maintenance. Routine organization maintenance should select
exact supported actions, apply them directly, and leave audit evidence.

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

When organization mode is not configured or the organization repo has not passed
validation, organization-specific navigation items should be hidden or shown only
as disabled setup entry points. The personal local flow should stay simple. The
full organization UI should open only after the organization source is validated.

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
   - Personal mode / organization mode selector.
   - GitHub repository URL input.
   - Repository validation check for the Khaos Brain organization KB manifest
     and layout.
   - Local mirror path.
   - Authenticated GitHub account after organization source validation.
   - Current permission level after account detection.

2. Search results
   - Source badge.
   - Contributor.
   - Trust level.
   - Required Skill status.
   - Local/private versus organization/shared distinction.
   - Exchange-hash status for organization cards when available, such as
     already local, new organization payload, or used locally.

3. Local exchange and contribution center
   - Show organization cards that were used locally.
   - Show whether a used organization hash reused an existing local card or
     created a local adopted candidate.
   - Show whether the local card is clean, diverged, feedback-ready, or already
     exported.
   - Show generated local outbox candidates from cards, observations, and
     Skills.
   - Show sanitized preview before upload.
   - Show contributor metadata.
   - Create branch or pull request.

4. Organization Skill registry
   - Browse candidate, approved, and rejected Skills.
   - Show owner, version, status, and install state.
   - Install approved Skills manually or automatically according to local
     policy.
   - Never silently install candidate or rejected Skills.

5. Organization maintenance tools
   - Review card-and-Skill bundles.
   - Promote, reject, split, merge, or supersede through reviewed proposals.
   - Require the local organization-review Skill for full automated review.
   - Let any opted-in machine prepare maintenance branches or PRs.
   - Require GitHub maintainer permission only for merge or protected remote
     write actions.

## Implementation Phases

Do not implement all of organization mode at once.

1. Add organization source configuration and local read-only sync.
2. Add multi-source retrieval and source badges.
3. Add hash-based organization exchange: mirror read-only organization cards,
   hide exact content duplicates already present locally, and create local
   adopted copies only when a used organization hash is not already local.
4. Add automatic organization candidate generation for eligible local model
   cards and observations.
5. Add read-only Skill registry browsing.
6. Add card-led Skill candidate generation and policy-approved installation
   from approved registry entries.
7. Add GitHub pull request contribution for generated card and Skill
   candidates.
8. Add organization-review Skill and local organization maintenance proposals.
9. Add GitHub cloud auto-check, auto-merge, and protected write rules.

## End-To-End Master Plan

This is the canonical order for turning the personal KB into an organization KB.
It ties the sandbox repository, first local machine, simulated second user,
Skill review, maintenance workflow, and UI rollout into one path. After every
stage, rerun the strongest practical personal-mode and organization-mode checks
before continuing.

1. **Freeze the personal baseline**
   - Verify current local search, UI browsing, feedback/history writes, sleep
     inputs, and existing tests.
   - Record that no organization source is configured and the product behaves
     exactly as a personal KB.
   - Checkpoint: personal mode can be used with no GitHub repo, no organization
     UI, and no source/provenance metadata required on old cards.

2. **Prepare the private GitHub sandbox**
   - Use one private repository as the organization KB sandbox.
   - Add `khaos_org_kb.yaml`, `kb/main`, `kb/imports`,
     `skills/registry.yaml`, `skills/candidates`, and policy docs.
     Keep `.gitkeep` files in initially empty `kb/imports` and
     `skills/candidates` directories so fresh clones validate.
   - Seed it with real shareable public/sanitized cards and demo Skill registry
     entries, never private preferences or raw local observations.
   - Checkpoint: a clean clone validates as a Khaos Brain organization KB.

3. **Add the organization mode gate**
   - Add Settings fields for personal/organization mode, GitHub repo URL, local
     mirror path, validation status, and organization id.
   - Organization UI opens only after the repo URL validates against the
     manifest and required layout.
   - Checkpoint: invalid or missing repo URL leaves the app in personal mode.

4. **Mirror the organization source locally**
   - Clone or fetch the sandbox into a local mirror under app-managed storage.
   - Store last sync commit, sync time, validation result, and read-only status.
   - Discover GitHub identity only after the organization source is valid.
   - Checkpoint: the same machine can switch personal -> organization ->
     personal without losing local KB behavior.

5. **Add source and provenance everywhere**
   - Treat old local cards as local by default.
   - Add source labels for local private/public/candidate and organization
     main-card status (`trusted` or `candidate`) plus Skill status.
   - Carry contributor, organization id, source repo, and source commit on
     organization cards.
   - Checkpoint: every search result and card detail can explain where the card
     came from.

6. **Implement multi-source retrieval and UI filtering**
   - Search local first, then organization cards.
   - Add source filters and badges for local, organization, trusted, candidate,
     contributor, and required Skill status.
   - Keep organization mirror cards read-only.
   - Checkpoint: disabling organization mode hides organization results and
     restores the personal-only UI.

7. **Implement hash-based local use**
   - When an organization card is actually used, compute its exchange hash.
   - If that hash already exists locally or was already absorbed/exported by
     this installation, reuse or suppress it instead of creating another file.
   - If the hash is new locally, create one adopted candidate and record source
     provenance plus `source_exchange_hash`.
   - Checkpoint: merely viewing a result does not copy it; real use either
     reuses an existing local same-hash card or creates one adopted candidate.

8. **Track local divergence and feedback readiness**
   - Mark adopted cards as `clean`, `diverged`, `feedback_ready`, or
     `locally_rejected`.
   - Clean adopted copies are not proposed back to the organization.
   - Diverged or feedback-ready copies can become organization update
     candidates.
   - Checkpoint: a hit-count-only copy stays local; a meaningfully edited copy
     can enter the outbox.

9. **Generate automatic organization candidates**
   - Extend sleep maintenance to produce a local organization outbox.
   - Include eligible local model/heuristic cards, sanitized observations,
     Skill-use evidence, and locally improved used organization cards.
   - Exclude personal preferences, user-specific memories, credentials, raw
     machine identifiers, local absolute paths, and sensitive provenance.
   - Skip cards whose exchange hash was already exported by this installation,
     already exists in the organization mirror, or duplicates another outbox
     item.
   - Checkpoint: the outbox is generated locally and writes nothing to GitHub.

10. **Contribute candidates through GitHub branches or PRs**
    - Convert outbox items into branch changes under `kb/imports` or
      `skills/candidates`.
    - Include provenance and a sanitization summary.
    - Never write directly to `kb/main` from contribution; organization
      maintenance moves reviewed imports into `main`.
    - Checkpoint: one generated candidate can be pushed or prepared for the
      sandbox as a reviewable GitHub change.

11. **Configure GitHub cloud auto-check and auto-merge**
    - Add GitHub Actions workflows for organization-maintenance pull requests.
    - Required checks should cover schema and manifest validity, path policy,
      private-data scans, local path and credential scans, duplicate/update
      risk, Skill registry states, approved Skill version/hash pinning, and
      card-and-Skill bundle evidence.
    - Enable repository auto-merge or merge queue for eligible maintenance pull
      requests.
    - Use a constrained GitHub-side merge actor, such as `github-actions[bot]`,
      an organization bot account, or a GitHub App.
    - Local machines should not directly push to protected branches.
    - Checkpoint: a low-risk maintenance PR with the right label and passing
      checks merges automatically; a failing PR stays open and does not update
      the organization KB.

12. **Simulate a second local user or second machine**
    - Create a second local install profile or workspace mirror with a different
      local installation id and machine label.
    - Point both profiles at the same private sandbox repo.
    - Verify both can sync, search, use organization cards, and create separate
      local adopted copies.
    - Checkpoint: two local profiles can share organization knowledge through
      GitHub while keeping their local KBs and local evidence separate.

13. **Test cross-user feedback flow**
    - Let profile A contribute a candidate.
    - Let profile B sync it, use it, adopt it locally, and optionally diverge it.
    - Verify clean adoption from profile B does not flow back, while a real
      refinement can become a feedback candidate.
    - Checkpoint: organization cards improve through reviewed feedback, not
      uncontrolled direct edits from every machine.

14. **Add card-led Skill registry workflow**
    - Read and display `skills/registry.yaml`.
    - Use only three Skill states: `candidate`, `approved`, and `rejected`.
    - Link Skill candidates to the cards and evidence that justify them.
    - Allow automatic install only for approved, version-pinned, hash-pinned
      Skills when local policy permits.
    - Checkpoint: candidate/rejected/unknown/unpinned Skills cannot be silently
      installed.

15. **Create and install the organization-review Skill**
    - Define how Codex reviews other Skills, card dependencies, evidence
      quality, privacy, unsafe behavior, and install safety.
    - Require this Skill before a machine runs full automated organization
      maintenance.
    - Checkpoint: machines without the organization-review Skill can submit
      candidates, but cannot run full review automation.

16. **Add organization sleep and maintenance**
    - Add a local "participate in organization maintenance" switch.
    - Review card-and-Skill bundles, not isolated files.
    - Let any opted-in machine prepare maintenance branches or PRs.
    - Let GitHub permissions and branch rules decide what becomes official.
    - Checkpoint: local maintenance can propose merges, splits, approvals, and
      rejections without bypassing GitHub protected branches.

17. **Wire the final organization UI**
    - Settings: personal/organization mode, repo validation, sync status,
      identity, local maintenance participation.
    - Search: source badges, owner/contributor, trust state, Skill status,
      adoption state.
    - Contributions: outbox, sanitized preview, branch/PR status.
    - Skills: candidate/approved/rejected, install state, dependency evidence.
    - Maintenance: bundle review, proposed changes, run history.
    - Checkpoint: a user can understand whether an item is local or
      organization, who contributed it, whether it is trusted, and what action
      is safe.

18. **Harden with multi-machine regression tests**
    - Re-run personal mode with no organization settings.
    - Re-run one-machine organization sync and search.
    - Re-run two-profile adoption and contribution.
    - Re-run Skill registry and approved-Skill install policy checks.
    - Re-run organization maintenance proposal checks.
    - Checkpoint: organization mode is an optional overlay on the personal KB,
      not a forked product and not a direct-write shared database.

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
credentials when available, verify that the repo is a Khaos Brain organization
KB source, show the configured or detected account only after validation, and
remember the local mirror location. If validation fails, the app remains in
personal mode.

### Phase 3: Read-Only Organization Sync

Goal: make shared organization cards available locally without allowing local
machines to mutate trusted shared data.

- Clone or fetch the organization KB repo into the configured local mirror.
- Read active `trusted` and `candidate` cards from `kb/main`, plus Skill registry metadata from that
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

### Phase 5: Organization Card Usage Feedback

Goal: preserve local learning from organization cards without letting every
machine directly edit organization truth.

- Compute a normalized exchange hash when an organization card is actually used.
- Reuse an existing same-hash local card when one exists; otherwise create one
  local adopted candidate.
- Store organization provenance on the adopted candidate when one is created,
  including organization id, card id, source repo, source commit, source path,
  and source exchange hash.
- Record local observations against the reused local card or adopted candidate.
- Let normal local maintenance narrow, update, split, merge, supersede, or
  connect the used card to a Skill after it becomes local maintenance material.
- Keep the organization card read-only in the local mirror.

Done when: using an organization card either reuses an existing same-hash local
card or creates one adopted candidate that participates in local-first
retrieval and can later produce organization feedback.

### Phase 6: Automatic Candidate Outbox

Goal: let sleep maintenance automatically prepare organization candidates from
eligible local knowledge.

- Add an organization outbox for generated card and Skill candidates.
- Let sleep maintenance scan local cards, observations, and Skill-use evidence.
- Include evidence from used organization cards after they have entered local
  maintenance.
- Generate sanitized organization candidates only from reusable models or
  heuristics, not personal preferences.
- Compare candidates against existing organization cards and propose updates,
  merges, supersessions, or rejections when appropriate.
- Keep generated candidates reviewable in UI even when later auto-PR is enabled.
- Write contributions to a branch, fork, or candidate import path.
- Prepare or open a GitHub pull request according to local policy.

Done when: sleep maintenance can produce a local organization candidate outbox
from eligible cards without exposing unrelated private cards.

### Phase 7: Card-Led Organization Skill Registry

Goal: share reusable capabilities through card-and-Skill bundles, with
organization maintenance deciding which bundles become approved organization
knowledge.

- Add read-only browsing for `skills/registry.yaml`.
- Show Skill owner, version, approval status, source repository, and local
  install state.
- Let cards reference required or recommended organization Skills.
- Detect local Skill dependencies from cards and observations.
- Generate card-bound Skill bundle candidates when a generated organization
  card depends on a Skill missing from the approved bundle set.
- Require supporting card evidence for normal Skill submission.
- Group card-bound Skill bundles by `bundle_id`; use `content_hash` for exact
  versions and `version_time` to select the latest approved version.
- Keep imported organization Skills read-only locally; original authors may
  update the same `bundle_id`, while non-author changes fork to a new
  `bundle_id`.
- Use three review states: `candidate`, `approved`, and `rejected`.
- Support policy-approved automatic installation of approved, version-time
  pinned, hash-pinned Skill bundles.
- Never silently install candidate or rejected Skills.
- Use organization-review guidance when available, but do not require it before
  ordinary organization Sleep-style card maintenance can run.

Done when: a generated organization card can carry its Skill dependency, and a
missing dependency can become a linked Skill candidate for bundle review.

### Phase 8: Maintainer Review and Advanced Maintenance

Goal: support organization cleanup as an opt-in local automation that prepares
reviewable organization maintenance proposals.

- Add organization maintenance UI for reviewing card-and-Skill bundles.
- Let any opted-in machine run scheduled organization maintenance scans and
  prepare review branches or pull requests.
- Gate merge into official organization knowledge through GitHub permissions and
  protected-branch rules.
- Let advanced maintenance detect duplicate cards, stale cards, superseded
  cards, and local evidence that should update an existing organization card
  rather than create a new one.
- Let organization maintenance approve or reject bundles using the three-state
  model, and record rejected reviews as audit signals.
- Coordinate maintenance through visible branches, pull requests, and run files
  before considering any separate server.

Done when: maintainers can promote, reject, merge, split, or deprecate
organization candidates through a review flow, while normal opted-in machines
can still prepare maintenance proposals without bypassing GitHub repository
permissions.

### Phase 9: Rollout and Hardening

Goal: validate the organization model with real multi-machine use before adding
more automation.

- Test with one private organization sandbox repo and two or three machines.
- Seed the sandbox with real shareable public/sanitized cards, not only fake demo
  cards.
- Verify that source labels remain clear in UI and retrieval output.
- Verify that organization card usage either reuses same-hash local knowledge
  or creates local adopted-candidate evidence without mutating organization
  trusted cards directly.
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

## Detailed Build Plan

This is the concrete implementation order to follow when organization-mode work
begins. The plan intentionally starts with a private sandbox and read-only
integration before contribution, Skill installation, or maintainer automation.

### Step 1: Create The Private Sandbox Repository

Create a private GitHub repository such as `khaos-org-kb-sandbox`.

Required initial files:

```text
khaos_org_kb.yaml
kb/
  trusted/
  candidates/
skills/
  registry.yaml
  candidates/
docs/
  sharing-policy.md
  privacy-policy.md
  maintainer-policy.md
```

Seed the sandbox with real shareable cards, not only fake demo cards. Use
`public` model cards, generic engineering heuristics, generic Codex workflow
cards, and sanitized candidates. Do not seed private preference cards,
user-specific interaction cards, credentials, local machine paths, or raw
unsanitized observations.

Done when: the private repo can be cloned manually and contains a valid
`khaos_org_kb.yaml` manifest plus at least one trusted card, one candidate card,
and one Skill registry entry.

### Step 2: Preserve The Personal-Mode Baseline

Before adding organization behavior, verify current personal mode.

- Run the desktop check.
- Run local search.
- Run feedback/history write.
- Confirm older cards with no organization metadata still load as local cards.
- Confirm the UI still opens without any organization settings.

Done when: personal KB behavior is unchanged and has a baseline check that can
be rerun after every organization-mode phase.

### Step 3: Add Settings Mode Selection

Add local settings for:

- `mode: personal | organization`;
- organization GitHub repo URL;
- local mirror path;
- organization id after validation;
- last validation status and message.

The UI should expose a personal/organization selector in Settings. Selecting
organization mode should require a GitHub repo URL, but it should not open the
organization UI until repo validation succeeds.

Done when: Settings can save personal mode, attempt organization mode, and fall
back to personal mode if the repo URL is missing or invalid.

### Step 4: Validate And Mirror The Organization Repo

Add organization-source tooling that can:

- clone or fetch the configured GitHub repo into a local mirror;
- read `khaos_org_kb.yaml`;
- validate `kind`, `schema_version`, `organization_id`, `kb/main`,
  `kb/imports`, and optional `skills/registry.yaml`;
- record sync status, last fetched commit, and last sync time.

GitHub identity discovery should happen only after this validation passes.

Done when: the private sandbox repo can be configured in Settings, mirrored
locally, validated as a Khaos Brain organization KB, and used to activate
organization mode.

### Step 5: Add Source And Provenance Metadata

Extend loaded card summaries with source metadata without requiring old local
cards to be rewritten.

Minimum source labels:

- `local/private`;
- `local/public`;
- `local/candidate`;
- `org/<org-id>/trusted`;
- `org/<org-id>/candidate`;
- `org/<org-id>/skill`.

Organization cards should also carry source repo, source commit, organization
id, contributor when available, and read-only status.

Done when: UI payloads and search payloads can tell whether every card is local
or organization, and old local cards default to `local`.

### Step 6: Add Multi-Source Search And Browsing

Load local entries and organization mirror entries as separate sources.

- Local results rank first by default.
- Organization results appear after local results unless a filter asks for org
  only.
- Search and route browsing show source badges.
- Organization cards are read-only in the mirror.
- Organization UI appears only after a validated source is active.

Done when: searching a term can return both local and sandbox organization
cards with clear source labels, and disabling organization mode returns to the
personal UI.

### Step 7: Add Hash-Based Use And Local Absorption

When an organization card is actually used, compute its normalized exchange
hash before creating any local file.

Rules:

- Do not copy cards that were merely shown in search results but not used.
- If the exchange hash already exists anywhere in the local KB, reuse that
  local card and do not create another adopted copy.
- If the exchange hash is new locally, create one local adopted copy under
  `kb/candidates/adopted/<org-id>/`.
- On later use of the same adopted copy, update usage metadata instead of
  creating another duplicate.
- Used organization content participates in local-first retrieval and local
  sleep maintenance.
- Track `hit_count`, `last_used_at`, `source_commit`, `source_path`,
  `source_exchange_hash`, and local evidence ids when an adopted file exists.

Done when: using a sandbox organization card either reuses an existing same-hash
local card or creates one adopted copy, and exact same-hash organization cards
are no longer shown as duplicate local/organization cards.

### Step 8: Track Clean, Diverged, And Feedback States

A local adopted copy should have a sync state:

- `clean`: copied from organization and only usage metadata changed;
- `diverged`: predictive content, route, wording, Skill dependency, or scope was
  changed locally;
- `feedback_ready`: local change appears reusable and can be proposed back;
- `locally_rejected`: local evidence suggests the organization card is weak,
  stale, or not applicable.

Automatic organization contribution should ignore clean adopted copies. Only
diverged or feedback-ready copies should be considered for organization
candidate updates.

Done when: a copied org card with only `hit_count` changes is not proposed back,
while a copied org card with content changes can enter the feedback outbox.

### Step 9: Add Organization Skill Registry And Review States

Read `skills/registry.yaml` from the organization mirror.

- Show candidate, approved, and rejected Skills.
- Show owner, version, status, source repo, and local install state.
- Show required or recommended Skill status on cards.
- Display card-and-Skill bundle links so reviewers can see which cards provide
  evidence for a Skill.
- Allow policy-approved automatic installation only for approved Skills that are
  version-pinned and hash-pinned.
- Do not automatically install candidate or rejected Skills.

Done when: organization cards can display missing, candidate, approved, or
rejected Skill dependencies from the sandbox registry, and approved Skills have
enough metadata for safe policy-based installation.

### Step 10: Add Automatic Candidate Outbox

Extend sleep maintenance to generate an organization outbox.

Inputs:

- eligible local `model` and `heuristic` cards;
- sanitized observations;
- diverged adopted copies from organization cards;
- Skill-use evidence.

Filters:

- exclude private preferences by default;
- exclude user-specific cards;
- exclude credentials, local paths, machine identifiers, and sensitive
  provenance;
- compare exchange hashes against local outbox items and current organization
  cards before proposing duplicates.

Outputs:

- new organization candidate;
- update existing organization card;
- merge/split proposal;
- supersede/deprecate proposal;
- linked Skill candidate when needed;
- card-and-Skill bundle proposal when a candidate card depends on a Skill.

Done when: sleep can generate a local organization outbox without writing to the
remote repository.

### Step 11: Add Branch And Pull Request Contribution

Convert outbox items into GitHub contribution branches or forks.

- Write contribution PRs only to `kb/imports` or `skills/candidates`.
- Include provenance and sanitization summary.
- Preserve links to local evidence ids.
- Prepare or open a PR.
- Never write directly to `kb/main` from contribution; organization
  maintenance is the only automated path that moves reviewed cards into
  `main`.

Done when: one generated candidate can be pushed to the private sandbox as a PR
against candidate/import paths.

### Step 12: Add GitHub Cloud Auto-Check And Auto-Merge

Configure the organization GitHub repository so maintenance can close the loop
without a local machine acting as the merger.

Required repository setup:

- enable pull requests and repository auto-merge or merge queue;
- protect the default branch;
- require GitHub Actions checks before protected paths can merge;
- configure a constrained merge actor, such as `github-actions[bot]`, an
  organization bot account, or a GitHub App;
- restrict direct pushes to trusted paths.

Required checks for organization-maintenance pull requests:

- manifest and schema validation;
- allowed-path validation;
- private data, credential, local path, and machine identifier scan;
- duplicate, merge, and supersession sanity check;
- card-and-Skill bundle evidence check;
- Skill registry state check using only `candidate`, `approved`, and
  `rejected`;
- approved Skill version and content-hash pinning check;
- organization-review guidance availability for full maintenance proposals.

Done when: a labeled low-risk import PR or reviewed maintenance PR can merge
automatically after all checks pass, while a PR that fails any required rule
remains unmerged.

### Step 13: Add Organization Sleep And Maintenance Workflows

Add a local "participate in organization maintenance" mode. This is an
automation switch, not a merge-permission switch.

Organization maintenance workflows should support:

- use local organization-review guidance when available before full automated
  review, without blocking ordinary Sleep-style card maintenance;
- review card-and-Skill bundles;
- merge, split, reject, supersede, or deprecate;
- compare local feedback against current organization card versions;
- approve or reject bundles using `candidate`, `approved`, and `rejected`;
- create reviewed branches or PRs for official organization KB changes.

Any opted-in machine can run the review automation and prepare a branch or PR.
GitHub permissions and repository rules decide whether that work is merged.
The local switch should not grant merge authority, but it should not block
ordinary contributors from producing maintenance proposals.

Done when: a machine with organization mode enabled can run Sleep-style
organization maintenance, apply exact selected actions with audit evidence, and
produce a reviewable maintenance branch or PR without bypassing GitHub protected
branch rules. Organization-review guidance improves judgment when present, but
is not required for ordinary card cleanup.

### Step 14: Multi-Machine Rollout Test

Test with at least two local installations or two machine profiles against the
same private sandbox repo.

Verify:

- both machines can validate and mirror the repo;
- each machine reuses same-hash local cards or creates its own local adopted
  copies only for new used organization hashes;
- clean adopted copies do not get proposed back;
- diverged adopted copies can become feedback candidates;
- GitHub identity is stable across machines for the same account;
- organization source labels stay clear in UI and search;
- private preferences never leave local storage.

Done when: organization mode behaves as a shared read source plus reviewed
feedback loop, not as uncontrolled multi-user writes.

## Current Implementation Status

As of the first organization-mode implementation pass, the local codebase has
the read-only and local-feedback foundations in place:

- desktop settings support personal mode by default and organization mode only
  after a GitHub/local repo mirror validates against `khaos_org_kb.yaml`;
- organization source validation, clone/fetch, and manifest checks live in
  `local_kb/org_sources.py`;
- search can merge local entries with read-only organization mirror entries,
  preserving local-first behavior, source/provenance metadata, and hash-based
  suppression of exact organization cards already present locally;
- route browsing, all-cards browsing, status/type filters, and search can merge
  local entries with organization mirror entries after organization mode is
  validated, while exact same-hash local duplicates are collapsed for browsing;
- the desktop UI exposes Local/Organization source filters only when a valid
  organization source is active;
- cards and details expose local/organization source labels, author fallback,
  read-only state, and card-declared Skill dependency review status;
- the desktop footer exposes a lightweight Organization status panel with
  source count, Skill registry counts, maintenance availability, and current
  maintenance recommendations;
- organization cards are absorbed locally on use by exchange hash: an existing
  same-hash local card is reused, otherwise one adopted candidate is created
  with `clean`, `diverged`, `feedback_ready`, and `locally_rejected` state
  support;
- automatic organization outbox generation filters to shareable model/heuristic
  cards, excludes private/preferences, skips duplicate exchange hashes within
  the outbox, and does not send clean adopted copies back;
- card-led Skill dependencies are attached to outbox proposals as card-bound
  Skill bundles with `bundle_id`, `content_hash`, `version_time`,
  `original_author`, and read-only import policy; approved/candidate/rejected
  status plus policy-based auto-install eligibility are surfaced in UI payloads;
  a safe script-level installer can install only approved, version-time pinned,
  hash-verified Skill bundles and refuses candidate/rejected/unknown/unpinned
  Skills;
- the local organization maintenance switch is now represented as
  "participate in organization maintenance"; it enables local maintenance
  proposal automation without granting GitHub merge authority;
- local maintainer and contribution helpers can inspect an organization mirror
  and prepare a local import branch under `kb/imports/<contributor>/`.
- a private sandbox organization repository exists and has been seeded with
  trusted cards, candidate cards, a Skill registry, GitHub Actions checks, and
  auto-merge workflow templates;
- GitHub cloud auto-check and auto-merge workflow templates are installed in
  the private sandbox repository, with required checks driven by
  `scripts/kb_org_check.py` locally and a vendored
  `.github/scripts/org_kb_check.py` checker inside the organization repo;
- GitHub API configuration successfully enabled the repository update step, but
  branch protection on the private sandbox returned GitHub 403 unless the repo
  is public or the account is upgraded; the sandbox therefore uses the
  GitHub-side workflow fallback that merges labeled PRs after the organization
  check workflow succeeds;
- live GitHub smoke test PRs verified the cloud loop: the organization KB check
  workflow passed, the PRs carried `org-kb:auto-merge`, and
  `github-actions[bot]` merged them automatically.

Current local script entry points:

```powershell
python scripts\kb_org_outbox.py --repo-root . --organization-id <org-id> --dry-run
python scripts\kb_org_maintainer.py --repo-root . --org-root <local-org-mirror>
python scripts\kb_org_contribute.py --repo-root . --org-root <local-org-mirror> --organization-id <org-id> --contributor-id <github-or-machine-id>
python scripts\kb_org_check.py --org-root <local-org-mirror> --changed-file kb/imports/example.yaml --enforce-low-risk
python scripts\kb_org_install_skill.py --org-root <local-org-mirror> --skill-id <approved-skill-id> --allow-auto-policy
python scripts\kb_org_install_github_automation.py --org-root <local-org-mirror>
python scripts\kb_org_configure_github_repo.py --repo-url <github-org-kb-url> --use-git-credential
```

Remote GitHub creation and initial push are complete for the private sandbox.
Pull request opening is still a later integration step: the current local tools
can prepare an import branch, and the GitHub connector can open a PR after a
branch is pushed, but the contribution PR flow has not yet been wired into the
desktop organization workflow.

## First MVP

The first useful organization MVP should include only:

- private GitHub sandbox repository seeded with real shareable cards;
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
- local organization-card adoption and fork evidence;
- card-led Skill dependency detection;
- branch or pull request preparation to candidate/import paths;
- GitHub Actions checks and auto-merge rules for eligible low-risk maintenance
  pull requests.

Organization-review Skill installation, policy-approved approved-Skill
auto-installation, and organization maintenance proposals should come after the
automatic candidate path is reliable. Direct trusted-card maintenance should
still go through reviewed GitHub branches or pull requests.

## Non-Goals For The First Organization Pass

- No central server.
- No SQL database requirement.
- No vector database.
- No direct multi-user writes to trusted cards.
- No automatic private-card upload.
- No automatic installation of candidate, rejected, unknown, or unpinned Skills.
- No separate enterprise edition unless later requirements demand SSO,
  centralized policy enforcement, or audit dashboards.
