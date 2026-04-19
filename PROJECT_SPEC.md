# Project Specification: Local Predictive Knowledge Library for Codex

## Status

This document is the authoritative implementation brief for Codex in this repository.

Implement **v0.1 only**. Optimize for clarity, maintainability, and explicit review. Do not jump ahead to vector databases, autonomous memory growth, embeddings, MCP services, or subagent orchestration unless a later task explicitly asks for them.

## 1. Objective

Build a **local, file-based predictive knowledge library** that Codex can consult before solving tasks.

The library is meant to store reusable local experience in a structured way. It is not a general encyclopedia and not a hidden global memory. Its role is narrower:

- preserve reusable patterns
- preserve user-specific preferences when appropriate
- preserve domain heuristics and lessons learned
- help Codex predict likely outcomes under known contexts
- help Codex choose better actions before answering or editing code

The first version should be simple enough that a human can inspect every file, understand every score, and review every update.

## 2. Core Concept

### 2.1 Each entry is a local predictive model card

Every knowledge entry in this repository should be treated as a **bounded predictive model**, not merely a loose note and not a universal truth.

A model card answers the following questions:

1. **In what scenario does this apply?**
2. **What action, input, or condition is under consideration?**
3. **What result is expected or likely?**
4. **What should Codex do with that prediction?**
5. **How confident are we, and where did this come from?**

This means even a preference can be expressed predictively.

Example:

- Scenario: professional message drafting with an established default language or tone
- Action/input: no explicit override is requested
- Predicted result: the established local default is still preferred
- Operational use: draft with that default unless the user overrides it

Likewise, a debugging heuristic can also be predictive.

Example:

- Scenario: behavior changed after dependency upgrade
- Action/input: skip release notes and start deep debugging immediately
- Predicted result: investigation cost likely increases and obvious causes may be missed
- Operational use: check version, changelog, and release notes first

### 2.2 Local, partial, and conditional

Each model card is intentionally **local** and **conditional**. It is not meant to cover every situation.

A card should only claim what it can justify within a defined scope. A card may include case splits when outcomes differ across conditions.

### 2.3 Human-auditable over clever

The system should remain understandable without hidden model behavior. If a human cannot explain why a card was retrieved or why it was trusted, the design is too opaque for v0.1.

## 3. Design Principles

1. **Local-first**  
   The first implementation runs entirely on local files.

2. **Path-first retrieval**  
   Retrieval should not depend on flat keyword matching alone. It should first locate the relevant direction of thought.

3. **Predictive representation**  
   Store expectation structures, not only descriptive notes.

4. **Multi-index memory palace**  
   Entries should be reachable through a main route and additional cross routes.

5. **Candidate-first capture with AI-driven consolidation**  
   New experience should land in `kb/candidates/` or structured history first, then be consolidated during scheduled AI maintenance.

6. **Public/private separation**  
   User-specific or sensitive knowledge stays private by default.

7. **AI-driven maintenance with file-based tooling**  
   Maintenance decisions may be made automatically by AI, but the tooling around those decisions should remain file-based, logged, inspectable, and reversible.

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

This is the primary route through which the entry should be found.

### 4.2 Cross routes

Each entry may also define `cross_index`, for example:

- `design/presentation/aesthetics`
- `communication/slides/visual-quality`
- `troubleshooting/dependency/regression`

These routes let one entry be discoverable from several conceptual directions without duplicating the file.

### 4.3 Retrieval order

The retrieval logic for v0.1 should follow this order:

1. Infer the **primary route** from the current task.
2. Infer up to **three secondary routes**.
3. Search for entries whose `domain_path` matches the primary route prefix.
4. Expand to entries whose `cross_index` overlaps with the primary or secondary routes.
5. Apply lexical matching on title, tags, trigger keywords, and body.
6. Re-rank by confidence and trust status.

### 4.4 Why this matters

This structure is important because many useful entries do not share the same surface words. A flat keyword search can miss conceptually related entries, while a route-based search can preserve conceptual structure.

### 4.5 Navigation should stay structurally simple

As this library grows, retrieval should become **more navigable**, not more opaque.

The intended direction is:

- keep the library structure explicit and hierarchical
- let Codex narrow the search one route level at a time
- prefer deterministic structural choices over hidden synonym expansion
- keep the retrieval rules simple enough that a human can predict what the next step will return

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
- hidden semantic expansion that a human cannot audit easily

This is an architectural principle for the library. The storage format should remain simple so that most adaptation happens during lookup, with Codex following clear navigation rules over explicit route structure.

## 5. v0.1 Scope

### 5.1 In scope

- YAML-based local storage
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
- example entries
- small evaluation cases
- documentation for Codex

### 5.2 Explicitly out of scope for v0.1

- embeddings or vector search
- external databases
- opaque autonomous promotion without AI-authored rationale or logged criteria
- hidden autonomous write-back without snapshots or rollback
- MCP-backed knowledge services
- opaque or mandatory subagent orchestration without fallback behavior
- probabilistic calibration infrastructure
- graph databases

Subagents are available in current Codex releases, but they are more expensive and only run when explicitly requested. For this repository they are optional, and are most useful as sidecar helpers for scout, recorder, or scheduled maintenance workflows.

## 6. Repository Architecture

The repository should be organized so the file system itself supports the conceptual hierarchy.

```text
.
├─ AGENTS.md
├─ PROJECT_SPEC.md
├─ README.md
├─ docs/
│  └─ maintenance_runbook.md
├─ .agents/
│  └─ skills/
│     └─ local-kb-retrieve/
│        ├─ SKILL.md
│        ├─ MAINTENANCE_PROMPT.md
│        ├─ agents/openai.yaml
│        └─ scripts/
│           ├─ kb_nav.py
│           ├─ kb_search.py
│           ├─ kb_feedback.py
│           ├─ kb_capture_candidate.py
│           ├─ kb_consolidate.py
│           ├─ kb_proposals.py
│           ├─ kb_rollback.py
│           └─ kb_taxonomy.py
├─ kb/
│  ├─ history/
│  ├─ taxonomy.yaml
│  ├─ public/
│  ├─ private/
│  └─ candidates/
├─ local_kb/
│  ├─ search.py
│  ├─ routes.py
│  ├─ feedback.py
│  ├─ history.py
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

## 7. Knowledge Entry Schema

### 7.1 Required fields for v0.1

Each entry should support the following structure:

- `id`: stable identifier
- `title`: short readable title
- `type`: `model`, `preference`, `heuristic`, or `fact`
- `scope`: `public` or `private`
- `domain_path`: ordered list representing the main conceptual route
- `cross_index`: additional conceptual routes
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

### 7.2 Schema interpretation

A card is operational, not merely descriptive.

- `if` defines the situation
- `action` defines what is being attempted or observed
- `predict` defines the expected result
- `use` defines what Codex should do because of that prediction

This keeps the knowledge unit useful for action selection.

Modeling discipline for v0.1:

- A valid model card should encode a directional claim such as: under condition `if`, taking `action` makes `predict.expected_result` more likely.
- Generic advice such as “should”, “avoid”, or “best practice” is not sufficient on its own.
- `use` must remain downstream of `predict`; operational guidance cannot replace the predictive claim itself.
- Titles should preferably name the predicted relation or outcome, not only the recommended behavior.

## 8. Retrieval Algorithm for v0.1

The implementation should remain intentionally simple.

### 8.1 Inputs

The search tool should accept:

- `--query`: free-text task summary
- `--path-hint`: optional route hint such as `work/reporting/ppt`
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

- If `path-hint` exists, use it strongly.
- If no path hint exists, fall back to lexical search.
- Always return a small ranked list.
- Prefer `trusted` over `candidate` when relevance is similar.
- Never treat retrieval as certainty.

## 9. Skill Behavior

The repository should provide one initial skill: `local-kb-retrieve`.

The skill should do the following:

1. Summarize the task in one short sentence.
2. When sub-agents are available and the task is non-trivial, start a scout-style sidecar agent to handle route scan and retrieval without distracting the primary task thread.
3. Infer one primary `domain_path` and up to three alternative conceptual routes.
4. Run the local search script with both a path hint and a textual query.
5. Review the top results.
6. Prefer entries with stronger path alignment, `trusted` status, and higher confidence.
7. Use retrieved entries as bounded context.
8. At the end of the task, start a recorder-style sidecar agent, or an equivalent inline fallback, to append feedback, misses, and candidate lessons into history.
9. State which entry ids influenced the answer.

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

Promotion to `kb/public/` or `kb/private/` may happen automatically during scheduled AI maintenance if the repository's safety rails are satisfied. The deciding step should come from AI judgment over the stored history, while the resulting update should still be logged, snapshotted, and reversible.

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

### 10.5 Current state, history, and consolidation

The library should distinguish between:

- the **current merged card**, which represents the latest consolidated operational version of the model
- the **history of that card**, which preserves how the card reached its current form

The current merged card is the surface that Codex should retrieve and use during normal work. It should stay concise, stable, and directly actionable.

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
- let AI decide the needed card and taxonomy updates
- use tooling to apply the chosen updates to cards and taxonomy
- write snapshots and change reasons before finalizing updates
- preserve enough state to support rollback

It may update trusted cards during scheduled consolidation, but those updates should never be opaque. Every automatic merge should leave an audit trail that captures what AI changed and why.

In other words:

- the main card stores the current consolidated state
- the history preserves the reasoning and evidence trail
- AI-driven consolidation evaluates accumulated history
- tooling applies the AI-selected merge to produce the new main card state
- snapshots and rollback preserve recoverability

This repository is therefore allowed to maintain itself automatically, but the maintenance intelligence should live in AI rather than in a brittle hard-coded rule engine. The goal is not human-in-the-loop maintenance by default. The goal is AI-driven autonomous maintenance that remains inspectable after the fact.

This principle is compatible with the file-based design of the repository. The exact storage layout for history can remain simple, but the distinction between current state and historical record should remain clear. Code in this repository should provide the memory substrate, navigation, logging, snapshots, and patch application; AI should provide the maintenance judgment.

The scheduled maintenance flow should preferably run in an independent thread, chat, or automation so that deep memory upkeep does not interrupt the main task thread. A daily or periodic maintenance conversation is a valid operating model for this repository.

### 10.6 Observation-first card creation

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
- whether an existing card was hit
- whether the hit was useful, weak, or misleading
- whether a missing card was exposed
- whether the user corrected or reinforced the outcome
- why the observation may or may not be reusable
- timestamp and source context

Card creation should then happen mainly during scheduled AI consolidation:

- ignore weak or one-off observations
- append supporting history to an existing card
- update an existing card
- add a new candidate card
- merge several related observations into one stronger card
- split an existing card if repeated observations reveal case splits

This means the repository should optimize for collecting good evidence during active work, not for producing a large number of new cards during every dialogue.

In short:

- active task flow should capture observations
- scheduled maintenance should synthesize cards from observations
- durable cards should represent consolidated reusable experience, not raw task residue

## 11. Implementation Plan for Codex

Codex should treat the following as the implementation sequence.

### Phase 1 — Align the schema with the predictive model concept

Tasks:

1. Update `schemas/kb_entry.example.yaml`.
2. Update sample entries so they use `domain_path`, `cross_index`, `action`, `predict`, and `use`.
3. Keep backward compatibility where practical.

### Phase 2 — Refactor retrieval toward hierarchical routing

Tasks:

1. Update `kb_search.py` to accept `--path-hint`.
2. Add scoring for `domain_path` and `cross_index`.
3. Improve rendering so results show:
   - id
   - title
   - domain path
   - predicted result
   - operational guidance
   - score
4. Keep the logic file-based and deterministic.

### Phase 3 — Refactor candidate capture

Tasks:

1. Update `kb_capture_candidate.py` so it can write predictive model fields.
2. Support `domain_path`, `cross_index`, `action`, `expected_result`, and `guidance`.
3. Continue writing to `kb/candidates/` only.

### Phase 4 — Update the skill and repository guidance

Tasks:

1. Update `SKILL.md` to instruct path-first retrieval.
2. Keep `AGENTS.md` short and routing-focused.
3. Ensure `AGENTS.md` tells Codex to read this specification before architectural changes.

Codex reads `AGENTS.md` before work and merges project guidance by directory depth, so repository-level instructions should stay small and stable while deeper documents carry the full plan.

### Phase 5 — Add minimal evaluation coverage

Tasks:

1. Expand `tests/eval_cases.yaml`.
2. Include route-based examples, not only keyword examples.
3. Verify that relevant entries rank near the top for representative tasks.

## 12. Definition of Done for v0.1

The first version is done when all of the following are true:

- repository contains the predictive schema documentation
- repository contains at least two example model cards
- search script supports `--path-hint`
- search output exposes domain path, predicted result, and guidance
- capture script can write predictive candidate entries
- skill instructions reflect route-first retrieval
- `AGENTS.md` points Codex to this design brief
- evaluation cases exist for at least a few representative tasks
- no embeddings, no opaque AI-driven promotion, and no external services are required

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
