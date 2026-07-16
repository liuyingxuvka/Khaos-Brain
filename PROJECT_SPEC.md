# Project Specification: Khaos Brain

## Status

This document is the authoritative implementation brief for Khaos Brain in this repository.

The current implementation baseline is **LogicGuard-native v0.1**. Optimize for clarity, maintainability, executable argument structure, and explicit machine receipts. Do not jump ahead to vector databases, embeddings, MCP services, or mandatory subagent orchestration unless a later task explicitly asks for them.

Where older wording in this document calls a YAML card “current state” or treats
`related_cards` as navigation authority, the LogicGuard-native authority rules
below supersede it: readable cards are projections, exact model/mesh revisions
are semantic authority, and only grounded ModelMesh edges may expand context.

## 1. Objective

Build a **local, file-based predictive knowledge library** that Codex can consult before solving tasks.

The library is meant to store reusable local experience in a structured way. It is not a general encyclopedia and not a hidden global memory. Its role is narrower:

- preserve reusable patterns
- preserve user-specific preferences when appropriate
- preserve domain heuristics and lessons learned
- help Codex predict likely outcomes under known contexts
- help Codex choose better actions before answering or editing code

The first version should be simple enough that AI can replay every decision, explain every score from canonical evidence, and verify every update without requiring a human review step. Human inspection remains an optional observability benefit.

Khaos Brain deliberately supports one current runtime contract only. It has no
normal-operation compatibility layer, dual reader/writer, command alias,
alternate authority, or fallback launcher/model. A versioned upgrade may read
an exact retired format only inside a bounded transaction so AI can rewrite it
directly to the current format, remove the old authority, and prove zero
residuals. Unknown or incomplete old state blocks and rolls back the upgrade; it
does not broaden the daily software contract. Such a blocker remains an open
upgrade-AI work item: the AI must derive or add one explicit direct-to-current
migration from captured evidence and retry the transaction. It may not close
the upgrade by teaching normal software to understand the old form.

## 2. Core Concept

### 2.1 Each entry is an executable local LogicGuard model

Every knowledge entry in this repository is a **bounded predictive LogicGuard
model**, not merely a loose note, a YAML object, or a universal truth. The
human-readable card is a deterministic projection of one exact model revision.

A model card answers the following questions:

1. **In what scenario does this apply?**
2. **What action, input, or condition is under consideration?**
3. **What result is expected or likely?**
4. **What should Codex do with that prediction?**
5. **What evidence and warrant support the claim?**
6. **Which assumptions, rebuttals, counterexamples, or limitations constrain it?**
7. **How confident are we, and where did this come from?**

This means even a preference can be expressed predictively.

Example:

- Scenario: work email drafting
- Action/input: no language explicitly requested
- Predicted result: English is the preferred output
- Operational use: draft in English unless the user overrides it

This also applies to **user-specific interaction patterns** when they are written as bounded predictive models rather than vague impressions.

Example:

- Scenario: public GitHub release presentation for this user
- Action/input: hide version visibility and place developer-oriented setup before the user entry
- Predicted result: review friction is more likely and the page is less likely to match the user's preferred presentation order
- Operational use: keep these cards private by default and adapt release presentation to visible versioning, clear user entry, and the user's preferred ordering when the evidence is stable

Likewise, a debugging heuristic can also be predictive.

Example:

- Scenario: behavior changed after dependency upgrade
- Action/input: skip release notes and start deep debugging immediately
- Predicted result: investigation cost likely increases and obvious causes may be missed
- Operational use: check version, changelog, and release notes first

### 2.2 Local, partial, and conditional

Each model card is intentionally **local** and **conditional**. It is not meant to cover every situation.

A card should only claim what it can justify within a defined scope. A card may include case splits when outcomes differ across conditions.

### 2.3 Machine-replayable and inspectable over opaque

The system should remain understandable without hidden authority. If canonical receipts cannot explain why a card was retrieved, excluded, promoted, or downgraded, the design is too opaque for v0.1. A person may inspect those receipts, but routine operation and closure must not depend on that inspection.

### 2.4 LogicGuard authority and readable projection

Canonical semantic authority lives under
`.local/khaos-brain/logicguard-authority/` as physically separated public,
private, and candidate LogicGuard model stores plus scoped ModelMesh stores.
Every retrieval or maintenance decision binds an exact authority generation,
model id and revision, root node and ArgumentBlock, mesh id and revision, and
projection digest.

The files under `kb/public/`, `kb/private/`, and `kb/candidates/` remain useful
for people, Git diffs, exchange, and lexical indexing, but they are generated
views. They may not be used as a fallback semantic reader. Missing or
inconsistent exact authority fails visibly.

Each model has a root Claim and explicit Context and Method nodes. Evidence,
Warrant, Assumption, Rebuttal, and Limitation nodes exist only when supported by
the source material; absent roles are first-class gaps with a next evidence
need. This prevents fluent prose from being mistaken for justified knowledge.

## 3. Design Principles

1. **Local-first**  
   The first implementation runs entirely on local files.

2. **Path-first retrieval**  
   Retrieval should not depend on flat keyword matching alone. It should first locate the relevant direction of thought.

3. **Executable predictive representation**
   Store expectation structures as LogicGuard nodes, edges, ArgumentBlocks, and explicit gaps, not only descriptive notes.

4. **Route entry plus grounded model mesh**
   Entries should be reachable through a main route and additional cross routes; after selection, only exact grounded ModelMesh relations may expand the argument context.

5. **Candidate-first capture with AI-driven consolidation**  
   New experience should land in `kb/candidates/` or structured history first, then be consolidated during scheduled AI maintenance.

6. **Public/private separation**  
   User-specific or sensitive knowledge stays private by default.

7. **AI-driven maintenance with one model writer**
   Sleep alone may publish canonical model generations. The tooling remains file-based, logged, inspectable, atomic, and reversible.

   All lifecycle mutations and active-index activation share one current
   owner-identified writer lock. Its physical owner record binds the process,
   thread, and a unique token. A live owner is never displaced; the active
   owner thread may safely reenter; dead or interrupted owner state is
   recovered after a bounded creation grace; and a filesystem release failure
   is a visible non-success rather than a silently retained empty directory.

8. **Simple scoring**  
   Use explainable scoring heuristics instead of opaque retrieval models.

## 4. Retrieval Philosophy: Hierarchical Navigation Before Keyword Matching

The user intent for this project is not “search by isolated keywords only.” The intended behavior is closer to a **memory palace with multiple indexes**.

Codex should first determine the **direction** of the task, then progressively narrow to a sub-direction.

### 4.1 Main route

Each entry should have a `domain_path`, for example:

- `work / reporting / ppt`
- `engineering / debugging / version-change`
- `work / communication / email`
- `research / literature / summarization`
- `codex / runtime-behavior / tool-use`
- `codex / runtime-behavior / prompt-following`

This is the primary route through which the entry should be found.

The primary route should normally describe the reusable function or direction of the lesson, not the project where the evidence happened. Project, repository, and product names belong in provenance, tags, trigger keywords, or explanatory text unless the card is intentionally project-specific.

Skill, plugin, connector, and tool names are different from ordinary project names. If a lesson depends on a named Codex Skill, plugin, connector, or tool capability, the card may and often should keep that capability boundary visible in `domain_path`, `cross_index`, title, or guidance. The rule should still be predictive and bounded, but it does not need to be generalized into a capability-independent claim.

### 4.2 Cross routes

Each entry may also define `cross_index`, for example:

- `design/presentation/aesthetics`
- `communication/slides/visual-quality`
- `troubleshooting/dependency/regression`
- `ai/runtime/gpt-family`
- `prompting/constraint-following`
- `codex/workflow/planning`

These routes let one entry be discoverable from several conceptual directions without duplicating the file.

### 4.3 Retrieval order

The retrieval logic for v0.1 should follow this order:

1. Infer the **primary route** from the current task.
2. Infer up to **three secondary routes**.
3. Search for entries whose `domain_path` matches the primary route prefix.
4. Expand to entries whose `cross_index` overlaps with the primary or secondary routes.
5. Apply lexical matching on title, tags, trigger keywords, and body.
6. Re-rank by confidence and trust status.
7. For each selected entry, validate and read its exact LogicGuard binding,
   root ArgumentBlock, typed support/challenge nodes, and explicit gaps.
8. Expand only the small neighborhood licensed by current grounded ModelMesh
   relations. Never expand from a legacy `related_cards` value or mere co-use.

### 4.4 Why this matters

This structure is important because many useful entries do not share the same surface words. A flat keyword search can miss conceptually related entries, while a route-based search can preserve conceptual structure.

### 4.5 Navigation should stay structurally simple

As this library grows, retrieval should become **more navigable**, not more opaque.

The intended direction is:

- keep the library structure explicit and hierarchical
- let Codex narrow the search one route level at a time
- prefer deterministic structural choices over hidden synonym expansion
- keep the retrieval rules deterministic enough that AI can reproduce and explain what the next step will return

In practice, this means the system should be able to support a navigation pattern such as:

1. list the top-level route choices
2. choose one or more route indices
3. return the next level under those routes
4. continue narrowing until the relevant cards are found

This style is compatible with multi-turn AI use:

- Codex can inspect the current route layer
- Codex can choose one branch or several branches in parallel
- Codex can quickly confirm that a branch is irrelevant and back out
- Codex does not need a large hidden synonym system if the route tree is clear

For this reason, future retrieval improvements should favor:

- route tree enumeration
- deterministic branch selection
- optional parallel expansion of multiple branches
- narrow, inspectable rules

They should not default to:

- large alias tables
- opaque query rewriting
- hidden semantic expansion that canonical machine receipts cannot reconstruct

This is an architectural principle for the library. The storage format should remain simple so that most adaptation happens during lookup, with Codex following clear navigation rules over explicit route structure.

## 5. v0.1 Scope

### 5.1 In scope

- local LogicGuard model and ModelMesh authority
- deterministic YAML card projections for human inspection and exchange
- public / private / candidate separation
- hierarchical `domain_path`
- `cross_index` support
- explainable scoring
- explicit taxonomy inspection
- one retrieval skill
- Codex-oriented sidecar sub-agent workflow guidance
- one candidate-capture script
- history or feedback logs
- AI-driven scheduled consolidation / “sleep” maintenance
- bounded Dream verification that simulates exact immutable models and writes only experiment artifacts plus typed Sleep model-gap handoffs
- example entries
- small evaluation cases
- documentation for Codex

### 5.2 Explicitly out of scope for v0.1

- embeddings or vector search
- external databases
- opaque autonomous promotion without AI-authored rationale or logged criteria
- hidden autonomous write-back without snapshots or rollback
- free-form autonomous capability growth or direct trusted-card mutation from dream-only evidence
- MCP-backed knowledge services
- opaque or mandatory subagent orchestration without an explicit current non-subagent route
- probabilistic calibration infrastructure
- graph databases (LogicGuard ModelMesh is a bounded local argument relation artifact, not a graph-database dependency)

Subagents are available in current Codex releases, but they are more expensive and only run when explicitly requested. For this repository they are optional, and are most useful as sidecar helpers for scout, recorder, or scheduled maintenance workflows.

## 6. Repository Architecture

The repository should be organized so the file system itself supports the conceptual hierarchy.

```text
.
├─ AGENTS.md
├─ PROJECT_SPEC.md
├─ README.md
├─ docs/
│  ├─ dream_runbook.md
│  └─ maintenance_runbook.md
├─ .agents/
│  └─ skills/
│     ├─ kb-sleep-maintenance/
│     │  ├─ SKILL.md
│     │  └─ agents/openai.yaml
│     ├─ kb-dream-pass/
│     │  ├─ SKILL.md
│     │  └─ agents/openai.yaml
│     └─ local-kb-retrieve/
│        ├─ SKILL.md
│        ├─ DREAM_PROMPT.md
│        ├─ MAINTENANCE_PROMPT.md
│        ├─ agents/openai.yaml
│        └─ scripts/
│           ├─ kb_nav.py
│           ├─ kb_search.py
│           ├─ kb_feedback.py
│           ├─ kb_capture_candidate.py
│           ├─ kb_consolidate.py
│           ├─ kb_dream.py
│           ├─ kb_sleep.py
│           ├─ kb_proposals.py
│           ├─ kb_rollback.py
│           └─ kb_taxonomy.py
├─ kb/
│  ├─ history/
│  ├─ taxonomy.yaml
│  ├─ public/       # deterministic readable projections
│  ├─ private/      # deterministic readable projections
│  └─ candidates/   # deterministic readable projections
├─ .local/
│  └─ khaos-brain/
│     └─ logicguard-authority/
│        ├─ generations/
│        ├─ public-models/
│        ├─ private-models/
│        ├─ candidate-models/
│        ├─ meshes/
│        └─ current-generation.json
├─ local_kb/
│  ├─ logicguard_models.py
│  ├─ model_projection.py
│  ├─ model_maintenance.py
│  ├─ search.py
│  ├─ routes.py
│  ├─ feedback.py
│  ├─ history.py
│  ├─ lifecycle.py
│  ├─ active_index.py
│  ├─ maintenance_migration.py
│  ├─ transactional_install.py
│  ├─ consolidate.py
│  ├─ proposals.py
│  ├─ snapshots.py
│  └─ taxonomy.py
├─ schemas/
│  └─ kb_entry.example.yaml
└─ tests/
   ├─ eval_cases.yaml
   ├─ test_kb_consolidate_scaffold.py
   ├─ test_kb_rollback_worker2.py
   └─ test_kb_taxonomy_worker1.py
```

Codex currently discovers repository skills from `.agents/skills/...`, and a skill is a directory containing `SKILL.md` plus optional scripts and metadata.

## 7. Canonical Model and Projection Schema

### 7.1 Canonical LogicGuard model

Each entry's semantic authority contains:

- stable entry id, scope, lifecycle state, confidence, routes, and provenance
- exact `model_id` and immutable `model_revision`
- one root `Claim` node expressing the bounded prediction
- explicit `Context` and `Method` nodes
- optional typed `Evidence`, `Warrant`, `Assumption`, `Rebuttal`, and
  `Limitation` nodes only when source material supports them
- deterministic node and edge ids
- one root `ArgumentBlock`
- explicit gap records for missing context, action, evidence, warrant,
  assumption review, opposition/rebuttal, or boundary conditions, each with a
  stable open disposition, required grounded input, and reopen condition
- exact scoped `mesh_id` and `mesh_revision`

A canonical ModelMesh contains exact member model revisions and explicit
relations. A relation becomes canonical only when its provenance includes a
qualifying non-AI source. AI inference, lexical similarity, simultaneous
retrieval, or legacy co-use may create an unresolved proposal but never an edge.

### 7.2 Deterministic readable projection

Each generated YAML card supports the following human-facing structure:

- `id`: stable system reference handle, not the content identity
- `title`: short readable title
- `type`: `model`, `preference`, `heuristic`, or `fact`
- `scope`: `public` or `private`
- `domain_path`: ordered list representing the main conceptual route
- `cross_index`: additional conceptual routes
- `projection_schema_version` and `projection_digest`: exact projection contract and content identity
- `authority_generation_id` and `authority_scope`: exact generation and physical scope
- `logicguard_model_id`, `logicguard_node_id`, `logicguard_block_id`, and `logicguard_revision_id`: exact model/root/ArgumentBlock binding
- `logicguard_mesh_id` and `logicguard_mesh_revision_id`: exact scoped mesh binding
- `logicguard_open_role_gaps`: human-visible summary of missing argument roles
- `related_cards`: optional derived display of current grounded mesh neighbors; never authority and never a retrieval input
- `tags`: lightweight retrieval hints
- `trigger_keywords`: lexical triggers
- `if`: applicability notes / conditions
- `action`: what action or input is being evaluated
- `predict`: expected result and optional case splits
- `use`: how Codex should apply the prediction
- `confidence`: 0 to 1
- `source`: origin metadata
- `status`: `candidate`, `trusted`, or `deprecated`
- `updated_at`: ISO date

### 7.3 Schema interpretation

A card is operational, not merely descriptive.

- `if` defines the situation
- `action` defines what is being attempted or observed
- `predict` defines the expected result
- `use` defines what Codex should do because of that prediction
- the complete top-level LogicGuard binding field set is the only route from projection to semantic authority; an incomplete or stale binding fails closed
- `related_cards` is a recomputable display field derived only from current grounded ModelMesh edges; it may be empty and cannot license traversal
- `id` is used for references, UI handles, history targets, and filenames. New card ids should be generated from a timestamp, a sanitized author or local-installation short label, and random code. They must not embed raw machine identifiers. Exact duplicate detection should use normalized `content_hash`, not `id`.

This keeps the knowledge unit useful for action selection.

Modeling discipline for v0.1:

- A valid model card should encode a directional claim such as: under condition `if`, taking `action` makes `predict.expected_result` more likely.
- Generic advice such as “should”, “avoid”, or “best practice” is not sufficient on its own.
- `use` must remain downstream of `predict`; operational guidance cannot replace the predictive claim itself.
- A missing Evidence or Warrant must remain a visible gap. Projection prose must not silently manufacture support that is absent from the model.
- Titles should preferably name the predicted relation or outcome, not only the recommended behavior.
- Cards about **model or runtime behavior** are allowed when they are still written as bounded predictive models rather than folklore.
- Cards about a **specific user** are also allowed when they stay bounded, evidence-based, and behaviorally framed.
- User-specific cards should be `private` by default unless the user explicitly wants them shared.
- Such cards should describe repeated task-conditioned interaction patterns, preferences, or judgments, not personality labels or broad character summaries.
- A good user-specific card answers: under what conditions, what request style, structure, or omission makes what user reaction or preference more likely.
- Such cards should be scoped to the most precise runtime identity that is actually known.
- If the exact model version is surfaced reliably, the card may name it directly.
- If the exact model version is not surfaced reliably, scope the card more conservatively to the active Codex runtime, current environment, or known model family instead of guessing a precise version.
- These cards should still preserve explicit `if / action -> predicted result -> use` structure and should avoid vague claims about “LLMs in general.”
- These cards often need more than one retrieval entry point. A runtime-focused route may be primary, while workflow, prompting, tool-use, or planning routes remain in `cross_index`.

## 8. Retrieval Algorithm for v0.1

The implementation should remain intentionally simple.

### 8.1 Inputs

The search tool should accept:

- `--query`: free-text task summary
- `--route-hint`: optional canonical route hint such as `work/reporting/ppt`
- `--top-k`: result count

### 8.2 Scoring components

The search score should combine:

- `domain_path` prefix match
- `domain_path` token overlap
- `cross_index` token overlap
- title match
- tag match
- trigger keyword match
- body match
- confidence bonus
- trusted / deprecated status bonus or penalty

A simple explainable formula is preferred. For example:

```text
score =
  8 * path_prefix_len
+ 5 * domain_path_overlap
+ 4 * cross_index_overlap
+ 3 * title_match
+ 5 * tag_match
+ 4 * trigger_match
+ 1 * body_match
+ 2 * confidence
+ trusted_bonus
- deprecated_penalty
```

The exact constants can be adjusted, but the logic should remain easy to inspect.

### 8.3 Retrieval behavior

- If `route-hint` exists, use it strongly.
- Without a route hint, lexical matching is the declared query-only mode; it is not selected after another reader fails.
- Always return a small ranked list.
- Prefer `trusted` over `candidate` when relevance is similar.
- Treat lexical/routing score as entry selection, not argument authorization.
- Return the exact bound LogicGuard context for every selected entry: generation,
  model and mesh revisions, root ArgumentBlock, typed nodes/edges, explicit gaps,
  and the small grounded mesh neighborhood.
- Within one process, different node reads in the same exact generation and
  authority scope may reuse one pinned read-only model/mesh store session. The
  authority pointer digest is part of the cache key, so a new Sleep generation
  necessarily opens a new session; cached stores never grant write authority or
  act as an alternate reader.
- Do not use projection `related_cards`, floating heads, or readable YAML as a
  fallback when exact authority is missing.
- Never treat retrieval as certainty.

## 9. Skill Behavior

The repository should provide one initial skill: `local-kb-retrieve`.

The skill should do the following:

1. Summarize the task in one short sentence.
2. When sub-agents are available and the task is non-trivial, start a scout-style sidecar agent to handle route scan and retrieval without distracting the primary task thread.
3. Infer one primary `domain_path` and up to three alternative conceptual routes.
4. Run the local search script with the canonical route hint and a textual query.
5. Review the top results.
6. Prefer entries with stronger path alignment, `trusted` status, and higher confidence.
7. Use retrieved entries as bounded context.
8. At the end of the task, use the explicitly selected recorder route—sidecar when requested and available, otherwise the current inline recorder—to append feedback, misses, and candidate lessons into history.
9. State which entry ids influenced the answer.
   These should be the cards that materially influenced the work, not every card that appeared in retrieval results.
10. When a reusable lesson is specifically about how the current model or runtime behaves, it may still be captured as a valid card if the runtime identity and triggering conditions are explicit enough to audit later.
11. When recording such a lesson, preserve both the runtime-facing route and any workflow or prompting routes that materially shaped the behavior, so later retrieval can find the card from more than one valid direction.
12. When a reusable lesson is specifically about how a user tends to respond, prefer a private predictive card that captures the task condition and likely user preference or reaction, rather than a vague impression about the user's personality.
13. When a reusable lesson is specifically about using another Codex skill or plugin, capture it as valid KB evidence when the skill choice, ordering, combination, fallback, or failure mode materially changes the result. Preserve both a skill-facing route such as `codex/workflow/skills` or `codex/skill-use/<skill-name>` and the task-facing route that made the skill relevant.
14. When a reusable lesson is specifically about Codex subagent or delegation use, capture it as valid KB evidence when the decision to spawn, avoid, sequence, wait for, or parallelize subagents materially changes speed, coordination overhead, context isolation, main-thread clarity, verification quality, or task outcome. Preserve both a workflow-facing route such as `codex/workflow/subagents` and the task-facing route that made delegation relevant.

Skill-use evidence should be captured as part of the personal KB, not only as a
future organization-sharing concern. This should not mean writing an observation
for every routine invocation. It does mean Codex should record a structured
observation when a Skill is new, repeatedly useful, task-critical, missing,
misleading, used as a fallback, combined with another Skill, or when the task
reveals that a Skill should be invoked earlier or avoided in a known scenario.

Subagent/delegation evidence should be captured at the same level as Skill-use
evidence. This should not mean writing an observation for every sidecar agent.
It does mean Codex should record a structured observation when delegation was
new, repeatedly useful, task-critical, slower than expected, avoided for good
reason, caused coordination overhead, protected the main thread from distraction,
or made retrieval, implementation, verification, or integration materially
clearer.

For non-trivial work, KB postflight should be treated as part of done rather than optional housekeeping. Before a task is considered complete, Codex should explicitly check whether the task exposed:

- a reusable lesson
- a skill/plugin or subagent/delegation usage lesson
- a retrieval miss
- a route gap
- a card weakness
- a KB-process failure

If the answer is yes, Codex should append one structured observation before ending the task. If the answer is no, the lack of meaningful signal should still be an explicit conclusion rather than a forgotten check.

Skills are the reusable workflow layer in Codex, while plugins are the installable distribution unit. This is the right reason to keep the workflow local first and package later only when stable.

For Codex specifically, a good operating pattern is:

- `kb-scout` sidecar before the main task for route scan and card retrieval
- primary task agent stays focused on the user request
- `kb-recorder` sidecar after the main task for comments, misses, and candidate capture
- independent scheduled maintenance thread or automation for deeper “sleep” consolidation

This keeps memory interaction from derailing the main task while still letting the system improve itself continuously.

## 10. Update and Governance Rules

### 10.1 Promotion policy

All new knowledge should enter `kb/candidates/` or structured history first.

Promotion to `kb/public/` or `kb/private/` is decided automatically during scheduled Sleep maintenance only when the lifecycle, provenance, independent-validation, confidence, and contradiction gates are satisfied. Every result remains logged, reproducible from the lifecycle ledger, atomically indexed, and reversible.

The semantic maintenance boundary should preserve AI agency without allowing uncontrolled churn:

- thresholds, repeated reviews, and weak-hit counts are review triggers, not final decisions
- AI should decide whether a card should be kept, rewritten, promoted, demoted, deprecated, split, or merged after reading the card and supporting evidence
- tooling should require an explicit semantic-review plan with evidence ids, rationale, risk level, utility assessment, expected retrieval effect, and rollback notes before applying meaning-bearing changes
- a parked entry whose evidence fingerprint is unchanged is skipped without another semantic review; when the digest changes but does not satisfy reopening, Sleep writes one same-state calibration snapshot and then skips that exact digest on later cycles; only a new evidence digest satisfying its reopen condition can re-enter candidate review
- keep, rewrite, confidence-adjustment, and promotion decisions must judge the card as future-useful; demotion and deprecation are the supported path for cards judged low-utility, obsolete, misleading, unclear, or insufficiently evidenced
- each semantic-review apply run should modify at most 3 trusted cards, including trusted rewrites, confidence changes, deprecations, demotions, and candidate promotions into trusted scope
- candidate and trusted-card text changes should trigger display-translation cleanup before the sleep pass is considered complete

For the current implementation, keep the operational boundary simpler:

- active task threads should prefer `kb/candidates/` or structured history writes
- trusted-scope rewrites and promotions should be treated as dedicated semantic maintenance work
- if the current tooling does not yet implement a specific semantic change cleanly, record a `parked` machine disposition with the missing capability, owner, due boundary, and executable reopen condition instead of leaving loose proposal debt or implying that the path already exists

### 10.2 Conflict handling

Priority order:

1. direct user instruction in the current conversation
2. explicit repository instructions
3. trusted KB entry
4. candidate KB entry

### 10.3 Privacy

- user-specific preferences go to `private`
- general engineering heuristics may go to `public`
- private content should stay out of public commits by default

### 10.4 Deprecation

Entries should never be silently deleted when they become weak or obsolete. Prefer `status: deprecated` with an updated note if needed.

### 10.5 Weak evidence, rejection, and forgetting

The repository should distinguish between:

- evidence that is not yet strong enough to become a card
- candidate cards that were reviewed and rejected
- trusted cards that later become weak or obsolete

The correct handling is different for each case:

- **weak, one-off, or low-utility observations** should usually be forgotten by the retrieval surface but retained in history
- **complete and future-useful single observations** may create low-confidence candidate scaffolds when the route is specific, the task summary is present, and the observation already states scenario, action, observed result, and concrete operational use; these are retrieval seeds, not trusted rules
- **rejected candidates** should leave a rejection trace in history and should not remain in the active candidate queue
- **obsolete trusted cards** should usually become `deprecated`, not silently deleted

In practice, this means:

- if an observation is clearly one-off, generic, noisy, or not reusable, scheduled maintenance may mark it as ignored or non-reusable and leave it in history only
- if an observation has complete predictive structure but no concrete future action-selection value, scheduled maintenance should keep it history-only rather than creating a card
- if a candidate is reviewed and not promoted, maintenance should record that rejection, including why it was rejected and which evidence supported the decision
- if a trusted card is no longer reliable, maintenance should prefer `status: deprecated` plus updated notes over deletion

The guiding principle is:

- the **retrieval layer may forget**
- the **history layer should remember**

This keeps the active memory surface clean without erasing the evidence trail behind prior decisions.

For v0.1, the simplest acceptable implementation is:

- weak observations stay in `kb/history/events.jsonl`
- rejected candidates leave a history event such as candidate rejection or ignored evidence
- active retrieval should prefer trusted cards, then viable candidates, and should ignore rejected or one-off evidence

An archive directory for rejected candidates is optional. It is acceptable to remove a rejected candidate from the active candidate area as long as the rejection reason remains in history.

### 10.6 Confidence rise, weakening, and review

The repository should not introduce a separate “execution score” in v0.1. The existing `confidence` field is the simple operational proxy for how strongly Codex should rely on a card during normal work.

This means:

- `confidence` may rise when repeated use supports the model
- `confidence` may fall when observations show weak hits, contradictions, misleading outcomes, or narrower scope than the current card claims
- lowering confidence is a normal maintenance action, not a failure state

The intended behavior is:

- one contradictory or weak observation should usually lower confidence or trigger watchful review, not force an immediate rewrite
- repeated contradictory evidence should trigger an `update-card` or `deprecated` review
- if the model still looks directionally right but less universal than before, prefer narrowing scope and lowering confidence over deleting the card

For v0.1, a simple review interpretation is enough:

- `confidence >= 0.75`: normal trusted use
- `0.50 <= confidence < 0.75`: still usable, but maintenance should review the card if weakening evidence continues
- `confidence < 0.50`: the card should be revised, narrowed, split, or deprecated before continued normal reliance

The exact numeric thresholds may be adjusted later, but the behavior should stay simple:

- confidence can go up
- confidence can go down
- lower confidence means weaker reliance
- sufficiently low confidence triggers review

Every confidence change should leave a history trace that records:

- the previous confidence
- the new confidence
- why it changed
- which observations or maintenance pass motivated the change

### 10.6.1 Generalization review during sleep maintenance

Sleep maintenance should classify the evidence scope before creating candidates or changing existing card surfaces:

- `project-local`: the lesson depends on a named project, repository, workspace, or unique local mechanism
- `skill-specific`: the lesson depends on a named Skill, plugin, connector, or tool capability
- `single-project-generalizable`: evidence comes from one project or workspace, but the causal rule is written as a reusable functional rule
- `cross-project-general`: evidence spans multiple independent projects or workspaces
- `insufficient-evidence`: evidence is not yet strong enough to change the active card surface

Same-project repetition should strengthen chronology and correction evidence; it should not by itself prove that a rule is universal. Cross-project evidence strengthens generality. Skill-specific evidence is a valid bounded outcome and should not be stripped of its Skill/plugin/tool context merely to make a card look more general.

When Sleep rewrites older cards, it should ask whether a project-shaped card can become a functional rule. If yes, project names should move into provenance, source, tags, or notes. If the card is genuinely project-local or skill-specific, the boundary should stay visible and the card should remain bounded rather than being forced into a generic rule.

### 10.7 Card splitting during sleep maintenance

Repeated hits on the same card should not automatically trigger a split.

Instead, repeated hits are a **split review signal**:

- sometimes they mean the card is the correct high-level entry point
- sometimes they mean the card has become overloaded and is no longer one bounded predictive model

Maintenance should therefore distinguish between:

- a **hub card**
  - still expresses one bounded predictive relation
  - is frequently retrieved because many tasks naturally pass through that route
  - should usually stay intact, even if it remains a common first hit
- an **overloaded card**
  - has started to carry multiple scenarios, actions, predicted results, or route-specific case branches
  - is no longer acting as one bounded predictive model
  - should usually move toward a split proposal

The intended maintenance rule is:

- high hit count alone is not enough to split a card
- split review should look for predictive overload, not raw popularity
- if the card still expresses one stable predictive relation, keep it as a hub card
- if the card now mixes several predictive relations, split it into smaller sibling cards

When a split is needed:

- the split cards may remain under the same main `domain_path`
- a lighter hub card may stay in place as the route entry point
- sibling models may receive a grounded mesh relation only when qualifying provenance supports it; otherwise the proposed relationship stays unresolved

Every split or split-rejection should leave a history trace describing:

- which card was reviewed
- why it was kept as a hub or marked as overloaded
- what child or sibling cards were proposed or created
- which observations triggered the review

### 10.8 Current state, history, and consolidation

The library should distinguish between:

- the **current exact LogicGuard generation**, which pins every canonical model and mesh revision
- the **readable card projection**, which presents that exact model concisely for people and lexical indexing
- the **history of that model**, which preserves how it reached its current form

Codex uses the exact model as reasoning context. The readable card remains a
concise observability and entry-selection surface, never an alternate authority.

The history layer should preserve the evidence trail behind the card, including items such as:

- usage records
- feedback after retrieval or application
- comments about when the model did or did not hold
- score changes, confidence changes, or importance changes
- reasons for narrowing or expanding scope
- reasons for modifying the main card text
- timestamps for these events

Every meaningful memory mutation should leave a timeline trace. This includes:

- card creation
- card updates
- confidence or importance changes
- comments and feedback writes
- candidate promotion or rejection
- taxonomy changes
- merges, splits, moves, and deprecations

Each such event should preserve enough information to answer:

- what changed
- when it changed
- why it changed
- which prior state it came from
- what source observation, feedback, or maintenance pass triggered it

This history matters because the library should not only store the latest conclusion. It should also preserve why that conclusion changed over time.

As the repository evolves, it is reasonable to add a consolidation or “sleep” layer in which AI periodically reviews this history and applies updates automatically. That layer should:

- read accumulated feedback and usage history
- identify cards that need clarification, scope adjustment, splitting, merging, re-scoring, or deprecation
- let AI decide the needed card and taxonomy updates, including whether a card or observation has enough future utility to remain on the retrieval surface
- use tooling to apply the chosen updates to cards and taxonomy
- write snapshots and change reasons before finalizing updates
- preserve enough state to support rollback
- cap each automated semantic-review pass to a small trusted-card budget; the current default is 3 trusted cards per run

It may update trusted cards during scheduled consolidation, but those updates should never be opaque. Every automatic merge should leave an audit trail that captures what AI changed and why.

In other words:

- the exact LogicGuard model stores the current consolidated semantic state
- the readable card is regenerated from that model
- the history preserves the reasoning and evidence trail
- AI-driven consolidation evaluates accumulated history
- Sleep tooling applies the AI-selected revision to produce a complete new model generation
- snapshots and rollback preserve recoverability

This repository is therefore allowed to maintain itself automatically, but the maintenance intelligence should live in AI rather than in a brittle hard-coded rule engine. The goal is not human-in-the-loop maintenance by default. The goal is AI-driven autonomous maintenance that remains inspectable after the fact.

This principle is compatible with the file-based design of the repository. The exact storage layout for history can remain simple, but the distinction between current state and historical record should remain clear. Code in this repository should provide the memory substrate, navigation, logging, snapshots, and patch application; AI should provide the maintenance judgment.

The scheduled maintenance flow should preferably run in an independent thread, chat, or automation so that deep memory upkeep does not interrupt the main task thread. A daily or periodic maintenance conversation is a valid operating model for this repository.

The sleep flow is itself a KB task. Each sleep pass should therefore begin with a
small route-first retrieval against prior maintenance lessons, usually under
`system/knowledge-library/maintenance`, before it inspects taxonomy, proposals, or
apply actions. Retrieved maintenance cards are bounded context, not authority over
the current repository state.

Each sleep pass should also create and maintain a machine-readable execution plan before
stateful maintenance work begins. The plan should list the concrete checkpoints for
the pass and track each item as pending, in progress, completed, skipped with a
reason, or blocked with a concrete blocker. A sleep pass should not stop after a
short proposal or one successful command while safe required checkpoints remain.
If a command exposes a supported low-risk repair, the maintenance agent should try
that repair and rerun the relevant validation before finalizing. Unsupported or
higher-risk issues should receive a bounded `parked`, `history_only`, or explicit
development-observation disposition with an owner and reopen condition; they must
not remain as unowned proposal debt. The pass should then continue through remaining
safe checkpoints.

Each non-empty sleep pass should also end with an explicit postflight check. If the
pass exposed a reusable maintenance lesson, route gap, card weakness, split signal,
translation gap, process weakness, or apply hazard, the pass should append one
structured observation to history before finalizing. That final observation is a
record for a future maintenance pass; it should not trigger an immediate recursive
consolidation loop in the same pass.

#### Grounded ModelMesh relations

Direct knowledge relationships live only in the scoped LogicGuard ModelMesh.
Every edge pins exact model revisions and carries typed provenance. Qualifying
non-AI evidence is required before the edge becomes canonical.

- repeated co-use, lexical similarity, or visibility creates at most an
  unresolved relationship proposal
- `related-cards` apply mode batches those proposals for Sleep; it does not
  edit a card or create an edge
- a model revision invalidates incident relations until Sleep revalidates them
- cross-scope relations are rejected; public, private, and candidate stores stay
  physically and semantically separated
- projection `related_cards`, when present for display, is derived from the
  current grounded mesh and may never drive retrieval

#### Display-language translations

The canonical card text should stay in English in the top-level fields. Human-facing translations may be stored under an optional `i18n` block.

For v0.1, the supported display translation is:

- `i18n.zh-CN`

Localizable fields are limited to the human text surfaces:

- `title`
- `if.notes`
- `action.description`
- `predict.expected_result`
- `predict.alternatives[].when`
- `predict.alternatives[].result`
- `use.guidance`

Route values are not localizable source fields. `domain_path`, `cross_index`, taxonomy
routes, search hints, and file paths should remain canonical English route segments.
Human-facing UIs may render those route segments through a display-label map such as
`zh-CN`, but that display layer must not rename the stored route or change retrieval
behavior.

Retrieval and maintenance should treat the English top-level fields as the source of truth. The UI may render `i18n.zh-CN` when the user chooses Chinese, but it must fall back to the English field whenever a translation is missing.

Chinese text should normally be filled during sleep maintenance, not opportunistically during every active task. The maintenance pattern is:

- detect which cards are missing zh-CN display fields
- detect which route segments are missing zh-CN display labels
- ask AI maintenance to produce an auditable translation plan
- apply that plan with file-based tooling
- write an `i18n-updated` history event that records the plan path and remaining missing fields

For route segment display labels, the current low-risk output is a review action that asks
AI maintenance to patch the display-label map. It should not auto-translate unknown
segments at runtime and should not rewrite canonical route fields.

The code should not use an external translation service, embedding model, vector database, or hidden remote process. AI provides the translation judgment; the repository tooling only applies and logs the selected text.

#### Canonical machine interfaces

The canonical/display split also applies to command-line and automation
interfaces. CLI tools, installed launchers, scheduled automation entry points,
installer checks, and GitHub automation scripts are machine interfaces by
default. They should emit canonical payload keys, canonical English route
values, and encoding-stable JSON without requiring a Windows console code-page
change.

This is not a fallback path. The normal path is:

- storage keeps UTF-8 files with readable human text
- core card fields and routes remain canonical English source fields
- UI view models render `i18n.zh-CN` and route display labels for human display
- CLI and automation JSON use an ASCII-safe machine serialization so any
  localized values still round-trip through JSON parsers without raw Unicode
  being written to fragile consoles

Scripts should use the shared CLI output helper for machine JSON rather than
calling `print(json.dumps(... ensure_ascii=False))` at terminal boundaries.
This rule does not apply to durable file writes under `kb/`, which should remain
UTF-8 and human-auditable.

### 10.9 Observation-first card creation

New cards should not be generated mechanically from every conversation or every project summary.

The preferred unit of memory capture is an **episode** or **task observation**:

- a non-trivial task or task fragment finishes
- Codex can describe the scenario, action, and observed result
- Codex can say whether an existing card helped, failed, or was missing
- Codex can judge whether the observation looks reusable beyond the immediate moment

During normal work, the system should prefer recording structured observations first, rather than immediately committing a new durable card.

An observation may include fields such as:

- task or episode summary
- inferred route or route hint
- scenario / condition
- action taken
- observed result
- operational use implied by the result
- whether an existing card was hit
- whether the hit was useful, weak, or misleading
- whether a missing card was exposed
- whether the user corrected or reinforced the outcome
- why the observation may or may not be reusable
- timestamp and source context

The source context should preserve provenance when available, such as:

- which agent or maintenance sidecar recorded the observation
- which thread or conversation it came from
- which project or repository produced the evidence
- which workspace root or local path context it came from

This provenance should explain where the evidence came from, but it should not automatically become the card's main retrieval route during sleep consolidation.

During sleep maintenance, this provenance should not be treated as passive metadata only. Timestamps plus `project_ref`, `thread_ref`, and `workspace_root` should let AI reconstruct **chronological episodes** inside the same project or workflow, so maintenance can see that one path was tried earlier and a better path emerged later.

When an observation is intended to support a future card, it should preserve predictive-model clues rather than stopping at a generic retrospective. In practice, the evidence should make it possible to reconstruct:

- the scenario or condition
- the action or input under consideration
- the observed or expected result
- the operational use implied by that result

When the task included a mistake, weak path, or later correction, the strongest observation is often **contrastive evidence** rather than a single-path summary. In that case, preserve both:

- the earlier action or condition that produced the weaker result
- the weaker or failed result that followed
- the revised action or condition
- the improved result after the revision

This style is especially valuable because later card creation can often map it directly into `predict.expected_result` plus one or more `predict.alternatives` branches, instead of forcing maintenance to infer the negative branch from vague prose.

Observations that only say “should”, “avoid”, or “best practice” without a clear scenario-action-result relation should be treated as weak evidence until AI rewrites or splits them into a proper predictive model hypothesis.

Observations about **model/runtime behavior** should follow the same rule. They are valid when they answer:

- which runtime or model identity was actually in use
- under what concrete conditions or prompts the behavior appeared
- what behavior became more likely
- how Codex should operationally adapt because of that result

If the runtime identity is uncertain, the observation should explicitly scope itself to the known environment level rather than claiming an exact model version.

Observations about **skill or plugin use** should follow the same predictive rule. They are valid when they answer:

- which Codex skill or plugin was selected, skipped, sequenced, or used as a fallback
- under what task conditions that skill behavior mattered
- what outcome changed because of the skill choice or skill limitation
- how future Codex work should adapt its skill invocation, ordering, or fallback behavior

These observations should avoid generic praise for a skill. The useful evidence is the trigger condition, action, and observed result, especially when one skill should be invoked earlier, paired with another skill, or avoided for a particular class of task.

Skill-use observations are especially important when a Skill may later be shared
or registered for an organization. A local Skill that is frequently used but has
no supporting cards is a gap: maintenance should request or create a
Skill-use observation before proposing that Skill as reusable organization
capability. The observation should explain the card-facing evidence for the
Skill, not merely state that the Skill exists.

Observations about **subagent or delegation use** should follow the same
predictive rule. They are valid when they answer:

- which subagent, sidecar role, or delegation pattern was selected, skipped,
  sequenced, waited on, or used as a fallback
- under what task conditions that delegation choice mattered
- what outcome changed because of the delegation choice, coordination cost, or
  isolation benefit
- how future Codex work should adapt its subagent spawning, waiting,
  integration, or fallback behavior

These observations should avoid generic praise for parallelism. The useful
evidence is the trigger condition, delegation action, observed result, and
future operational rule, especially when subagents made the task faster or
slower, kept the main thread clearer, prevented context pollution, improved
verification coverage, or added unnecessary coordination overhead.

Observations about a **specific user** should also stay predictive and bounded. They are strongest when they answer:

- in what task or interaction context the behavior appeared
- what structure, omission, or request style preceded the reaction
- what user preference, correction, or judgment became more likely
- how Codex should adapt next time

These observations should avoid personality summaries and should default to `private` handling unless the user explicitly asks for them to be shared.

When later card creation is likely, Codex should preserve enough route context that the resulting card can be found from more than one valid direction. Runtime-behavior cards are usually strongest when they are reachable from both:

- a runtime-focused route such as `codex/runtime-behavior/...` or `ai/runtime/...`
- a task-facing route such as `prompting/...`, `codex/workflow/...`, or another route that captures the condition that exposed the behavior

Skill-use observations should be similarly reachable from both a skill-facing route, such as `codex/workflow/skills` or `codex/skill-use/<skill-name>`, and the task-facing route that made the skill relevant.

Subagent-use observations should likewise be reachable from both a workflow
route such as `codex/workflow/subagents` or `codex/delegation/<pattern>` and
the task-facing route that made delegation relevant.

Card creation should then happen mainly during scheduled AI consolidation:

- ignore weak or one-off observations
- append supporting history to an existing card
- update an existing card
- add a new candidate card
- merge several related observations into one stronger card
- split an existing card if repeated observations reveal case splits

This means observation capture should not rely on memory alone. During normal work, Codex should perform an explicit postflight question before finishing the task:

- did this task produce meaningful evidence for the KB?

If yes, write one structured observation.
If no, end the KB flow explicitly.

The goal is to prevent the common failure mode where preflight recall happens but useful new evidence is never written back.

This means the repository should optimize for collecting good evidence during active work, not for producing a large number of new cards during every dialogue.

In short:

- active task flow should capture observations
- scheduled maintenance should synthesize cards from observations
- durable cards should represent consolidated reusable experience, not raw task residue

### 10.10 Separate dream exploration maintenance

The repository may also support a separate **dream** lane, but it must remain distinct from sleep maintenance.

The purpose of Sleep is canonical model consolidation:

- review accumulated real observations
- repair, merge, split, rerank, or deprecate exact model revisions
- audit missing evidence, warrant, assumptions, opposition, and boundaries
- publish one atomic model/mesh/projection/index generation

The purpose of Dream is immutable whole-model pressure testing:

- pin exact generation/model/ArgumentBlock/mesh revisions
- remove or weaken declared evidence and assumptions in simulation overlays
- strengthen rebuttals or counterexamples and pressure declared boundaries
- expose unsupported conclusions, fragile dependencies, and missing model roles

This distinction matters because the repository should not treat speculative exploration as if it were already trusted experience.

The required operating rules are:

- dream and sleep must run in separate automations, threads, or maintenance sessions
- they must not run concurrently on the same repository state
- dream should not duplicate route-candidate creation that current sleep consolidation already marks as eligible
- dream should write only bounded simulation/experiment artifacts plus typed, idempotent Sleep model-gap handoffs
- dream must not append ordinary observations, create candidates, or mutate the central lifecycle/history ledger directly
- dream must never commit models or meshes, rewrite readable projections, or advance the canonical generation pointer
- dream must prove the pinned generation unchanged before closure
- dream-derived evidence should preserve explicit provenance so later maintenance can tell it apart from normal task evidence
- dream-derived evidence alone is not enough to promote or strongly raise confidence on a trusted card
- user-specific predictions discovered during dream mode should stay especially conservative; they should not become trusted private cards without later confirmation in live interaction

Dream mode should stay grounded in existing evidence. Eligible inputs are things such as:

- repeated retrieval misses
- repeated weak hits
- low-confidence candidates that need a narrow validation attempt
- parked maintenance observations whose executable reopen condition names a missing evidence class
- taxonomy gaps that repeatedly appear in observed routes
- explicit user-supplied hypotheses such as “maybe the system could learn X this way”

Each dream run should create a bounded experiment record before acting. That record should say:

- which exact generation, model nodes/edges, ArgumentBlock, and mesh neighborhood the verification is about
- what hypothesis is being tested
- what the maximum allowed action surface is
- what success, failure, or inconclusive result would look like
- what write-back is permitted afterward

For v0.1, Dream should prefer:

- read-only inspection
- local dry-runs
- evidence-removal and assumption-removal simulations
- rebuttal/counterexample strengthening
- boundary-pressure, cross-edge-removal, and neighbor-pin-replacement simulations
- narrow retrieval experiments
- model-gap handoff generation
- evaluation against explicit tests or route checks

It should avoid:

- repo-wide formatting
- dependency installs
- lockfile churn
- destructive changes
- broad refactors
- any canonical model, mesh, or trusted-card projection rewrite
- open-ended “try anything interesting” behavior

The write-back policy is convergent:

- compute a stable fingerprint from the exact authority bindings, route, experiment mode, source ids, and decision-relevant evidence
- if the same fingerprint already closed with passed, failed, weak, or inconclusive evidence, record `no_delta_closed` in the run artifact and perform no knowledge write
- reopen only when the evidence fingerprint or relevant lifecycle disposition changes materially
- if a simulation exposes a material gap, emit one typed Sleep handoff with exact generation/model/mesh bindings, gap kind, affected node/edge ids, provenance, and requested disposition; Sleep alone decides whether and how to revise authority
- trusted promotion still requires independent current validation plus either one strong support item or two independent medium support items

Dream mode is therefore not a second consolidation pass or a model writer. It
is an immutable argument-verification lane whose outputs remain provisional
until Sleep admits evidence and publishes a new exact generation.

### 10.11 Automatic convergence, system maintenance, and upgrade migration

The scheduled Architect lane is retired. There is no replacement self-modifying
mechanism-maintenance agent and no human review queue in the core lifecycle.
Ordinary prompt, Skill, installer, or product changes remain explicit development
work with OpenSpec, FlowGuard, SkillGuard, tests, and release evidence as applicable.

The fully automatic local maintenance roles are:

- `KB Sleep` at 12:00: the only owner of observation disposition, candidate creation and terminal outcomes, promotion, downgrade, merge, confidence calibration, Dream-handoff acknowledgement, and atomic LogicGuard model/mesh/projection/index generation publication
- `KB Dream` at 13:00: exact immutable model simulations and at-most-once typed Sleep model-gap handoffs; no direct model, mesh, projection, candidate, observation, or central-history writes
- `Khaos Brain System Update` at 14:00: a narrow software-update check using `python scripts/khaos_brain_update.py --system-check --json`; it is not a general architecture or mechanism-maintenance lane
- organization contribution and organization maintenance in their stable repository-derived windows

Sleep acknowledges a Dream handoff only after the selected disposition and any staged candidate/model projection commit to the current LogicGuard generation. Admission or disposition alone is not acknowledgement authority. A recovered dead Sleep owner without a completed receipt reopens only its own uncommitted acknowledgements so the next run can retry them idempotently.

Sleep and Dream share the local-maintenance lock, wait and recheck instead of
silently skipping, recover stale locks with an audit record, and publish final
receipts. A failed pass must not advance its durable watermark or hide actionable
debt. The desktop card viewer is optional: no human-readable file review or UI
interaction is required for admission, disposition, promotion, migration, or
completion.

Each of the five scheduled roles is independently guarded by SkillGuard. Every
role has its own target route, obligation set, exact declared checks, and immutable
native run artifact bound to one run id and content hash. Capability tests prove
that a version can perform the behavior; they are never accepted as proof that a
particular scheduled run completed. A real terminal succeeds only when the current
installed runtime executes and reconciles the target's exact check inventory and
the sole `enforced` closure consumes that exact declared-check receipt plus every
required target-owned artifact. Intake, planning, partial native work, or a shared
aggregate green result cannot satisfy a task's terminal claim.

SkillGuard owns declared-check execution, receipt reconciliation, installation
binding, currentness replay, and the single closure. Each target Skill remains the
sole owner of domain obligations, applicability, native terminal construction,
positive/shallow fixture meaning, finalization, and failure judgment. The positive
fixture must satisfy the target obligations; the shallow fixture must be rejected
for one named important target gap. Capability/JUnit evidence and fixture evidence
remain separate from `scheduled_production` evidence tied to the exact scheduler
execution, current installation receipt, and installed runtime fingerprint.

System update uses one non-terminal authorization stage and one closure profile.
For a prepared update, the first request emits a declared-check authorization
receipt with `overall_complete=false` and no closure. While all five automations
remain PAUSED, the updater binds that receipt, the native receipt, preserved status
and `user_paused`, exact source/target hashes, and the deferred install check into
an immutable staged-restoration artifact. A fresh composed authorize+finalize run
must obtain the sole `enforced` closure before native restore, readback, the normal
install check, activation receipt, and CURRENT. The legal no-op branches skip
restoration but still need a target-owned terminal receipt and the same enforced
closure. Any authorization-stage closure, alternate profile, missing declared
check, repeated check, stale runtime, caller-authored pass flag, or proposal-only
receipt is an explicit failure.

 The former SkillGuard runtime pair for each retained task is not allowed to
The former SkillGuard runtime pair for each retained task is not allowed to
remain as a parallel closure route. Once the current contract, target-native
positive calibration, intentionally shallow blocker, native owner/route/check
binding, and portable contract-depth report pass, the repository keeps only the
current contract source, compiled contract, and exact check manifest.
Installation and upgrades delete the exact former work contract, underscore
check manifest, flat run records, and empty former runtime directories. No
compatibility, conversion, renewal, retirement-receipt, alias, or fallback
runtime survives; any reintroduced residual blocks installation and readiness.

Fresh installation and every supported upgrade provision only
`kb-sleep-maintenance`, `kb-dream-pass`, `kb-organization-contribute`,
`kb-organization-maintenance`, and `khaos-brain-update`, plus the surviving
automations. The installer must delete only the exact retired
`kb-architect-pass` Skill and `kb-architect` automation, even when an old machine
has missing or stale install manifests; similarly named user assets remain
untouched. Historical Architect records are inert provenance and may remain only
in integrity-checked cold history.

Installation is one whole-tree transaction. It stages complete Skill and
automation trees, compiles and checks the current SkillGuard authority, compares
source, stage, installed, and post-operation manifests, detects concurrent source
drift, rejects any unvalidated or incomplete incoming hard authority, creates rollback
copies, activates all managed trees, validates the result, and commits a versioned
durable receipt with immutable replay evidence. Interruption recovery restores
any incomplete transaction before a new one begins. Every surviving automation
retains both its exact prior runtime status and independent `user_paused` value.
Failed aggregate validation leaves all five migration-paused survivors paused.

The target-owned contract generator, complete current SkillGuard executable
tree, complete current FlowGuard package tree, and each managed Skill source
tree must retain one content identity from immediately before through
immediately after the validation that issues its receipt. The upgrader copies
the complete Guard sources into immutable snapshots before long assurance. The
SkillGuard/global-router pair then passes through the official SkillGuard
transaction installer inside an attempt-local directory whose Codex home is an
isolated `.codex`; the upgrader captures and replays the official current
installation receipt there. Every child check consumes that installed isolated
identity, while FlowGuard checks consume their frozen package snapshot. No child
rediscovers, installs, or rewrites the user's mutable global SkillGuard. A
temporary live-tree replacement therefore cannot split one run across tool
versions, but a genuinely different source or isolated installed identity at
final currentness fails the upgrade while all surviving automations remain
paused. A later automatic attempt may start only from newly frozen identities.

Installed supervision never imports that frozen snapshot together with its
runtime receipts or interpreter caches. It creates a short, repository-local,
content-addressed behavior projection containing the frozen SkillGuard program
and current global-router sibling, excluding `.sg-runtime`, `__pycache__`,
`.pyc`, and `.pyo`, and requires its official fingerprint to equal the verified
installed runtime identity. The five exact installed control files use a second
short exact-byte projection. Neither projection is nested below a deep scheduled
run root, so Windows path length cannot silently decide whether the same current
installation is executable. A missing router, identity mismatch, or residual
runtime state fails closed; it does not switch to live source or a fallback.

For each concrete scheduled Sleep, Dream, organization, or update execution,
the guarded entrypoint establishes one official persistent supervision session
before invoking the native owner. That session freezes and retains the sealed
verified installation context, exact SkillGuard behavior projection, exact
installed target-control projection, and six-field scheduled identity. The
same authority builds any target-native terminal and closes the run after the
native owner finishes; it never reopens live global SkillGuard currentness at
the end of a long task. A newer global SkillGuard or target Skill version is
eligible only for the next execution. Updating a supervised target Skill does
not itself authorize or require reinstalling global SkillGuard.

The frozen session separates immutable authority from evidence that is born
after native execution. SkillGuard code, the installation context, the behavior
projection, and installed target control never change within the run. The native
receipt path/hash, run id, scheduled identity, fixture gate, and update
finalization receipt cross into that retained session only through the exact
seven declared dynamic keys. Missing declared keys clear inherited values and
undeclared keys cannot become evidence. This prevents both stale-run closure and
the false conclusion that a missing receipt requires a global SkillGuard
reinstall.

Aggregate assurance also separates resource owners. The repository-wide suite
runs first, ordinary read-oriented children may then run in parallel,
performance-sensitive LogicGuard runtime benchmarks run next on their own
exclusive lane, and the child that executes real scheduled production runs
last on another exclusive lane. This prevents a healthy benchmark, Sleep, or
Dream route from exhausting its declared budget only because broad sibling
checks are competing for the same machine. Inside one Sleep cycle, the final
active-index generation has one publication/validation owner: unchanged
intermediate work defers to that owner, and an already current receipt is reused
unless a later lifecycle decision actually changes index eligibility.

Within one exact authority generation and scope, model-bound reads open one
immutable ModelMesh view and reuse it across distinct cards. The generation
pointer digest, scope, mesh id, and mesh revision are all cache keys; publishing
a new generation clears every process-local read session. Runtime latency and
catalog memory are measured in separate probes so memory instrumentation cannot
inflate the latency claim. The release gate includes a real current local
generation plus a same-class distinct-card test; a tiny fixture alone cannot
license the broad retrieval-performance claim.

The caller decides source versus installed supervision only from the exact
managed target root. The canonical repository Skill root selects source; the
active Codex `skills/<skill-id>` root selects installed execution. Scheduled,
calibration, and other surface names are display labels only. A missing,
outside, or ambiguously resolved root blocks before execution, so neither an
installed target can silently run as source nor a source target masquerade as
installed authority.

The portable installer continues to preserve each machine's pre-upgrade runtime
status and independent user-pause choice. This machine has a separate explicit
operator override: all five surviving automations remain `PAUSED` with
`user_paused=true` after installation and final assurance. The closeout stages
and hash-binds that whole five-member state, reads every result back, writes an
immutable machine receipt, and blocks if any member becomes active or loses its
user-pause bit.

Aggregate-assurance installer fixtures are also isolated from the live Codex
shell-tools directory and user PATH, not only from migration and automation
state. Fixture mode requires an explicit non-default Codex home, fixture-local
shell-tools directory, and disabled PATH persistence. The aggregate readiness
owner runs the full repository regression once in an exclusive validation lane;
model alignment consumes its node-level JUnit evidence instead of racing or
restarting the same installer fixtures on Windows.

That alignment uses declared logical validation-owner ids, not raw receipt file
or producer names. An unknown owner is represented as missing failed evidence
and keeps the aggregate red; it never raises an uncaught lookup exception or
selects another receipt as fallback.

Peer AI work may still admit observations during that long assurance window.
Before any restoration transaction, the installer therefore runs a bounded
post-assurance data convergence loop: production debt settlement, atomic index
rebuild, real retrieval-threshold evaluation, and a fresh migration check must
all be current together. Non-convergence is a recoverable PAUSED attempt, never
a partial success.

The five exact repository-managed automation Skill paths use a currentness-bound
whole-tree replacement policy. The incoming tree must pass the current compiler,
target-owned contract generation, native depth calibration, complete manifest,
and source/stage parity before activation. A current installed tree is compared
for semantic hard-authority loss by projecting checks onto covered
obligations, evidence classes, and mandatory owners. Check identifiers may be renamed, merged,
split, or removed when the incoming semantic projection remains a superset;
check-id, native-route, and depth-dimension subset preservation are not
capability evidence. A conditional depth wrapper may move to its unchanged
independent hard owner only with an exact closure-preserving reorganization
proof, while any lost obligation, evidence class, or owner remains a hard downgrade. An absent or non-current
managed tree is never interpreted or converted and is used only as the rollback backup before the
validated incoming tree replaces it. Unknown, partial, shrunk, or tampered
incoming trees fail before activation and preserve the paused old tree.

Every attempt also writes a durable checkpoint journal outside the
last-known-good install manifest. Router refresh is run and journaled before
aggregate assurance, then run again after the last transaction that can replace
a managed Skill tree. Final success requires the current official global
registry and managed-prompt checks to match the live SkillGuard/global-router
surface fingerprints and the current transaction. If assurance or any later
post-commit check fails, the previous successful manifest is preserved, the
failed attempt remains explicitly retryable, and all five tasks remain or return
to `PAUSED`.

The history migration lock must be interruption-safe too. A current holder
publishes a versioned owner token, process id, and heartbeat. A live owner or a
recent ownerless legacy lock cannot be displaced. A dead recorded owner, or an
old ownerless legacy lock with no matching migration process, is atomically
quarantined and recorded in a durable recovery receipt before the migration
reacquires the lock and resumes. Manual deletion is not a valid success path.

The upgrade also runs the versioned Chaos Brain maintenance migration:

`preflight -> snapshot -> classify -> settle-logical-debt -> archive-cold-evidence -> prune-derived-data -> build-logicguard-authority -> publish-projections -> rebuild-index -> publish-pointer -> validate-zero-residual -> committed`

The migration inventories files, counts, bytes, hashes, ownership, dependencies,
and prune eligibility before deletion. It gives unresolved observations and
candidates explicit lifecycle outcomes, parks only with machine-evaluable reopen
conditions, settles the retired Architect proposal queue, archives retention-
required evidence in content-addressed verified cold storage, and removes only
receipt-covered regenerable caches, sandboxes, completed workspaces, duplicate
snapshots, and other declared derivations. It is journaled, idempotent, resumable,
rollbackable, writer-exclusive, and must publish before/after debt and storage
accounting plus an atomic exact model/mesh/projection/index generation receipt.
The migration is the only code allowed to read the exact retired card format.
It converts every valid entry directly into the current LogicGuard authority,
removes retired semantic fields, writes the generation pointer last, and proves
zero legacy authority residuals. An incompatible residual blocks and rolls back;
normal runtime never gains a compatibility reader.

Maintenance standard v3 treats the managed physical surface as a convergent
boundary, not a one-time scan. Validation rescans it after long integrity work;
late or post-commit reintroduction of old caches, sandboxes, or workspaces
reopens the gate and runs stable receipt-backed reconciliation passes until the
surface is empty or a real blocker leaves the upgrade paused.
Canonical receipts keep normal relative paths, while Windows filesystem I/O
uses extended-length syntax so deeply nested legacy debt remains visible to
inventory, hashing, archive, prune, and residual checks.
Observations admitted by concurrent AI work during or after a long migration
also reopen the gate and receive bounded atomic settlement, index rebuild, and
their own logical-reconciliation receipts before completion.

Foreground retrieval must not pay the cost of that full maintenance audit.
The active index publishes a compact activation receipt; each query validates
that receipt and only the few exact model/projection bindings it could return.
For selected entries it then reads the immutable model, root block, explicit
gaps, and bounded grounded mesh neighborhood. Observation-only
intake does not invalidate entry authority. Any entry-lifecycle transition must
write a durable fail-closed invalidation marker before its event, and only a
full validated rebuild may reactivate the index. A changed or missing indexed
binding also fails the compact check; there is no projection or legacy fallback.
Full model/mesh/projection manifests and lifecycle replay
remain mandatory for Sleep, migration, rebuild, and aggregate assurance.

Historical lifecycle settlement must remain scale-bounded. It compiles missing
admission, disposition, and entry-snapshot events into bounded atomic batches,
replays the lifecycle authority at most once before and once after each batch,
and records requested, created, reused, replay, batch, and final-sequence counts.
Pending Dream handoffs are observation sources inside that same Sleep-owned
batch; they must not admit and dispose one item at a time through separate full
lifecycle replays. Each full replay preserves the ordered durable key projection
but uses a separate in-memory membership index, so duplicate validation grows
linearly with lifecycle event count rather than rescanning every prior key.
An older partially completed per-item attempt must resume through stable
idempotency keys and candidate identities without duplicate cards or events.

Software update coordination uses `.local/khaos_brain_update_state.json`. The
desktop UI may display update state, but the machine interface and automation use
canonical encoding-stable JSON. `$khaos-brain-update` remains recovery-oriented:
it preserves local KB and organization state, updates only through the supported
Git path, runs the maintenance migration and transactional installer, removes
retired surfaces, requires exact LogicGuard authority and zero residuals, and
reports success only when every current aggregate gate is green.

The aggregate readiness runner is the sole owner of expensive release leaf
execution. It executes each exact command identity at most once, runs the full
repository regression once on an exclusive lane, and publishes content-addressed
command receipts plus a complete JUnit node inventory. Model-test alignment,
focused and semantic coverage claims, and OpenSpec closure consume that evidence
graph. They do not relaunch overlapping pytest or model commands. Reuse is valid
only while source, normalized command, environment, verifier, inventory revision,
terminal status, skips, and proof-artifact hashes remain exact and current.

The updater uses a strict two-stage SkillGuard boundary. Its first route
authorizes the completed native update work. While all five live automations are
still `PAUSED`, the updater then builds a no-mutation restoration plan that binds
each source hash, target hash, prior status, `user_paused` value, and desired
state. A composed authorization-plus-finalization route must close that exact
plan before activation. Only then may the updater apply the five writes, read
back every state and hash, run the ordinary install check, publish an immutable
activation receipt, and mark the software state `CURRENT`. Drift or failure at
any point re-pauses all five and leaves the state `FAILED`.

The update gate has exactly three successful no-op branches: `no-update`,
`waiting-for-user`, and `ui-running`. States such as `already-upgrading`,
`failed-awaiting-user`, `concurrent-update`, and unknown operational blockers
remain blocked or retryable and must not be converted into completed native or
SkillGuard receipts.

The install check should also verify that the global predictive KB defaults
name both skill/plugin usage lessons and subagent/delegation usage lessons as
recordable KB signals, so cross-machine installs inherit both workflow-learning
paths.

Automation specs must encode model intent as `model_policy = "strongest-available"` and `reasoning_effort_policy = "deepest"` rather than pinning a fixed model slug. During installation, the repo installer resolves that policy against the current machine's Codex model cache/config, writes the concrete runtime values into the automation files, and records the policy fields so future machines can pick newer models without changing the spec.

## 11. LogicGuard-Native Implementation Sequence

Codex should treat the following as the current implementation and validation
sequence. A later change must preserve this ownership order.

### Phase 1 — Build exact argument models

1. Bind the real installed LogicGuard package and fail visibly if unavailable.
2. Convert every admitted entry into a deterministic model revision with a root
   Claim, Context, Method, supported typed nodes, ArgumentBlock, and explicit gaps.
3. Keep public, private, and candidate authority physically separated.

### Phase 2 — Build grounded meshes and projections

1. Pin exact member revisions in scoped ModelMeshes.
2. Require qualifying non-AI provenance for every canonical relation.
3. Generate readable YAML cards deterministically and bind each projection to
   its exact model, node, block, mesh, generation, and digest.
4. Publish an exact active index; never add a projection or legacy fallback.

### Phase 3 — Make Sleep the sole publisher

1. Route all card/candidate semantic writes through one Sleep generation publisher.
2. Consume observations and Dream handoffs once, update models and meshes, audit
   gaps, then write every projection and index before publishing the pointer last.
3. Roll back the complete generation on any model, mesh, projection, index, or
   pointer failure.

### Phase 4 — Make Dream an immutable verifier

1. Pin exact authority identities before experiment selection.
2. Plan evidence removal, assumption removal, rebuttal/counterexample
   strengthening, boundary pressure, cross-edge removal, and neighbor-pin
   replacement, then execute every applicable path through a separate
   simulation overlay.
3. Emit typed exact model-gap handoffs and prove canonical authority unchanged.

### Phase 5 — Cut over existing machines

1. Let only the versioned migration read retired formats.
2. Convert directly to current models, meshes, projections, index, and pointer.
3. Remove legacy semantic authority and require zero residuals.
4. Keep the transaction rollbackable and every retained automation paused until
   installation, SkillGuard, migration, and aggregate readiness gates pass.

### Phase 6 — Validate one frozen snapshot

1. Freeze one TestMesh/SkillGuard execution-owner plan.
2. Run affected model, migration, retrieval, UI, privacy, and automation checks.
3. Run the aggregate readiness owner exactly once on the stable snapshot.
4. Reuse its immutable receipts rather than relaunching equivalent checks.

When a pulled current public projection carries a different stable generation
than an otherwise complete old-machine local authority, deterministic software
must emit an immutable upgrade-AI work item and change no authority. The AI may
inspect the exact projection digest, card identity, old/new generation ids, and
binding, then record only the current `direct-current-projection-to-logicguard-model`
disposition with an evidence hash, actor, rationale, timestamp, and decision
hash. The resolver itself writes no card, model, mesh, index, or pointer. The
idempotent migration retry consumes the exact decision, rebuilds only that
projection's semantic model, reuses all other exact local models, publishes one
new generation pointer last, and proves zero open work items and retired
authority. Any stale or malformed decision remains blocked; there is no
automatic rebind, compatibility reader, alias, or fallback route.

## 12. Definition of Done for LogicGuard-Native v0.1

The version is done only when all of the following are true:

- every active entry has an exact valid LogicGuard model and scoped mesh binding
- missing evidence, warrant, assumptions, rebuttals, and boundaries remain
  visible gaps rather than generated claims
- readable cards validate as deterministic projections and cannot act as fallback authority
- retrieval enters the exact root ArgumentBlock and expands only grounded mesh edges
- Sleep is the sole normal-runtime canonical generation publisher
- Dream simulations do not advance or rewrite canonical authority
- the versioned migration is idempotent, rollbackable, direct-to-current, and proves zero legacy semantic residuals
- SkillGuard current contracts and install projections are exact and current
- the unique aggregate readiness owner passes the frozen model/test contract
- no embeddings, external database, graph database, compatibility reader, or opaque fallback is required

## 13. GitHub Publication Plan

Do not publish immediately.

First stabilize locally.

Only after local usage confirms the structure is helpful should the repository be prepared for sharing. At that point:

1. remove or exclude private examples
2. keep only public examples and generic templates
3. add a concise public README
4. document the schema and workflow clearly
5. include a small evaluation set
6. keep the project opinionated but narrow

The shared repository should distribute the **workflow and schema**, not private memory.

## 14. Non-Goals and Anti-Patterns

Do not let the first version drift into these patterns:

- a generic note-taking pile
- a memory system that rewrites itself without logs, thresholds, snapshots, or rollback
- a vector-search project before there is enough data
- a graph database project before there is enough operational value
- a fully autonomous self-belief system
- a tool that treats weak hypotheses as durable truth

## 15. Operational Reminder for Codex

When modifying this repository:

- prefer the simplest working implementation
- preserve human readability
- make scoring explainable
- make automatic maintenance explainable and reversible
- do not silently introduce heavy dependencies
- do not expand scope beyond v0.1
- keep changes incremental and reviewable

The purpose of this repository is not to simulate a perfect mind. The purpose is to build a practical local scaffold that helps Codex retrieve reusable predictive experience in a controlled way.
