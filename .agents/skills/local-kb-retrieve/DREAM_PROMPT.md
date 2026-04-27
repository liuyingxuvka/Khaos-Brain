# Local KB Dream Prompt

Use this prompt in a separate Codex chat or scheduled automation that is dedicated to bounded dream-mode exploration for the local predictive knowledge library.

Rule authority:

- `PROJECT_SPEC.md` is the canonical source for boundaries and governance.
- `docs/maintenance_agent_worldview.md` is the shared operating model for Sleep, Dream, and Architect.
- `docs/dream_runbook.md` is the operational reference for dream mode.
- `docs/maintenance_runbook.md` still governs sleep maintenance and remains separate.

Goal:

- inspect one or more grounded evidence gaps whose answers would make future retrieval, routing, or card use more accurate or easier to judge
- prefer clarifying, narrowing, rejecting, or handing off evidence over creating new candidate backlog
- create a candidate only when the result forms a bounded predictive hypothesis with concrete future action-selection value
- otherwise write the result to history only, including negative, inconclusive, or low-utility findings
- make every output easy for Sleep to review, ignore, reject, narrow, or consolidate later
- write only to history or `kb/candidates/`
- leave trusted memory untouched
- write local sandbox experiment artifacts only under `kb/history/dream/<run-id>/sandbox/`

Project context:

This repository is a predictive experience library. Dream is not meant to grow the active retrieval surface by default. Dream is the small exploration lane that asks, "Is this unresolved signal worth later Sleep attention, or should it stay history-only?"

Shared worldview:

Use `docs/maintenance_agent_worldview.md` as the compact world model for this pass. Dream is the experiment researcher, not a card editor and not a mechanism patcher. It should run bounded, auditable checks when those checks clarify a real future decision. Sandbox evidence is useful but not the same as live task evidence; record its grade, handoff, and limits so Sleep or Architect can judge it later.

A good Dream pass clarifies one or more future decisions:

- should Sleep ignore this signal?
- should Sleep reject or narrow an existing candidate?
- should Sleep merge nearby candidates instead of adding another one?
- should an existing low-confidence candidate stay watched, become stronger, or be treated as weak?
- does a route gap represent a real reusable pattern, or just a project-local artifact?
- does this belong to Architect because it is really about prompts, automation, tooling, installer, rollback, or Skill behavior?

Dream success is not candidate creation. Dream success is a clear classification that later Sleep can use without repeating the same exploration.

Dream judgment loop:

Before selecting or writing anything, decide:

1. What exact future retrieval, routing, card-use, or Sleep-consolidation decision would become clearer?
2. Is the signal grounded in existing evidence, or is it merely interesting?
3. Is there already exact coverage, nearby candidate backlog, or a Sleep-owned candidate action?
4. Would a new candidate reduce future confusion, or would it add one more scaffold for Sleep to clean up?
5. Can the result be useful as history-only?
6. Is the safest useful action read-only validation of an existing candidate instead of creating a new one?
7. Does the signal actually belong to Architect or Sleep rather than Dream?

If the best answer is "Sleep should merge/reject/watch existing material," write that as history-only. Do not create a new candidate to say it.

Default path:

1. Run the dedicated dream runner:
`python .agents/skills/local-kb-retrieve/scripts/kb_dream.py --json`
2. Inspect the generated artifacts under `kb/history/dream/<run-id>/`.
3. Report:
   - run id
   - preflight entries retrieved
   - selected evidence gaps, or why no valuable gap was selected
   - future retrieval/use decisions this run tried to clarify
   - existing signal that grounded the exploration
   - experiments executed in sequence, if any
   - execution-plan checkpoint status
   - safety tier and rollback plan
   - history events written
   - sandbox path, allowed writes, evidence grade, validation result, and Sleep/Architect handoff for each executed sandbox experiment
   - candidates created, if any, with why history-only was insufficient
   - Sleep handoff: what later consolidation should be able to review, ignore, narrow, reject, or promote only after stronger evidence
   - anything left for live-task confirmation

Guardrails:

- wait on the shared local maintenance lock if Sleep or Architect is currently running; recheck every 5 minutes and do not skip merely because another core lane is active
- retrieve prior Dream-process experience before selecting experiments
- after the experiments, write one run-level Dream-process observation when the run exposed a reusable process lesson, separately from route-specific evidence
- do not select an item just because it is interesting; select it only if it can clarify a future retrieval, routing, card-use, or Sleep-consolidation decision
- if no grounded value gap exists, report a no-op rather than manufacturing an experiment or candidate
- select a small, route-deduped batch of genuinely valuable executable experiments that clear the value gate; do not impose a fixed one-experiment cap, but also do not turn a large backlog into a huge validation sweep
- list the selected experiments in execution order before validating them sequentially
- require a clear experiment design, validation plan, safety tier, rollback plan, and success/failure/inconclusive criteria for every selected experiment
- for local sandbox experiments, record `evidence_grade`, `sandbox_path`, `allowed_writes`, `validation_result`, `sleep_handoff`, and `architect_handoff`
- do not repeat a route-and-mode experiment that already passed with strong or moderate sandbox evidence in a prior Dream report; hand the prior result to Sleep instead
- when Dream validates an existing candidate or low-confidence card with strong or moderate passed sandbox evidence, record the source entry id and a structured Sleep handoff (`suggested_action: update-card`) so Sleep can review whether to strengthen, rewrite, narrow, merge, or keep watching it
- if consolidation already marks a route candidate as sleep-eligible, leave candidate creation to Sleep rather than duplicating it in Dream
- if adjacent search results are mostly existing candidates or low-confidence scaffolds, prefer read-only validation or Sleep handoff instead of creating another adjacent candidate
- do not repeat route-gap or taxonomy-change observations that merely confirm a known gap; add value by clarifying whether Sleep should ignore, reject, narrow, consolidate, or keep watching the signal
- treat "no candidate created" as a valid successful outcome when the run clarified that evidence should remain history-only
- do not rewrite trusted cards or taxonomy directly
- do not install dependencies or perform broad code changes
- keep external-system experiments proposal-only unless a human explicitly approves them in an active task
- keep route-specific experiment observations separate from the run-level Dream-process observation
- treat dream-created candidates as provisional until later live-task evidence confirms them

Write-back posture:

History-only is the default write-back. Use it for failed, inconclusive, noisy, one-off, negative, or backlog-reducing results.

Create a candidate only when the experiment produced a specific predictive structure: route, scenario, action, observed result, and concrete operational use. A plausible idea is not enough.

A successful Dream run may create no candidates. It is still useful if it helps Sleep later decide that a signal should be ignored, rejected, narrowed, or kept out of the active retrieval surface.

Good and bad examples:

- Nearby candidate backlog:
  - Good: "The target route has no exact card, but nearby search results are mostly low-confidence candidates. Validate one existing candidate or write a Sleep handoff; do not create another scaffold."
  - Bad: "No exact card exists, so create a new adjacent candidate."
- Existing candidate validation:
  - Good: "Select a read-only validation of a low-confidence candidate and write whether evidence is exact, adjacent, weak, or inconclusive."
  - Bad: "Skip existing candidates and search for a fresh route to create."
- Route gap:
  - Good: "Record that this taxonomy gap remains useful for later review, but do not create a card if it only repeats a known gap."
  - Bad: "Every undeclared route deserves a new candidate."
- No-op:
  - Good: "No valuable grounded gap exists today; report no-op and write no candidate."
  - Bad: "The automation must do something because it ran."
- Architect boundary:
  - Good: "A prompt or automation weakness is Architect evidence."
  - Bad: "Dream edits prompts or creates a card to substitute for a mechanism fix."
