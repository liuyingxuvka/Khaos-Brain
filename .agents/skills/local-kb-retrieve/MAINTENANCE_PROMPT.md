# Local KB Sleep Maintenance Prompt

Use this prompt in a separate Codex chat or scheduled automation that is dedicated to maintaining the local predictive knowledge library.

Rule authority:

- `PROJECT_SPEC.md` is the canonical source for thresholds, governance rules, and maintenance boundaries.
- `docs/maintenance_runbook.md` is the canonical operational reference for what the current tooling safely supports.
- This prompt should stay operational. If this prompt and the spec disagree, the spec wins.

Goal:

- keep the library easy to navigate
- consolidate observations into candidate knowledge
- surface undeclared taxonomy branches
- leave an auditable trail of what changed

Current implementation boundary:

- you may inspect taxonomy, navigation, history, and consolidation artifacts
- you may let `kb_consolidate.py` auto-create low-risk candidate scaffolds with `--apply-mode new-candidates`
- you may let `kb_consolidate.py` update stable direct `related_cards` with `--apply-mode related-cards`
- you may let `kb_consolidate.py` update low-risk direct `cross_index` routes with `--apply-mode cross-index`
- you may record explicit maintenance decisions with `kb_maintenance.py` so ignored observations, rejected candidates, and confidence reviews leave durable history traces
- you may inspect or restore `kb/history/events.jsonl` through `kb_rollback.py`
- do not silently rewrite trusted cards or official taxonomy during this maintenance pass
- if a trusted-scope promotion or rewrite is not clearly implemented and supported by the current tooling, leave it as proposal-only

Checklist:

1. Inspect the explicit taxonomy tree:
`python .agents/skills/local-kb-retrieve/scripts/kb_taxonomy.py --json`
2. Inspect the smallest undeclared taxonomy routes implied by current entries:
`python .agents/skills/local-kb-retrieve/scripts/kb_taxonomy.py --gaps-only --json`
3. If route structure looks unclear, inspect the current route tree view:
`python .agents/skills/local-kb-retrieve/scripts/kb_nav.py --json`
4. Inspect recent history in proposal mode:
`python .agents/skills/local-kb-retrieve/scripts/kb_consolidate.py --json --apply-mode none`
5. While reviewing observations, distinguish between:
   - generic retrospectives or advice summaries
   - predictive-model evidence with a clear scenario, action, observed result, and operational use
   Only the second category should be promoted directly toward cards. Generic summaries should be rewritten, split, or left as weak evidence.
6. Preserve and inspect provenance for each observation when available: timestamp, agent name, thread reference, project reference, and workspace root. This metadata matters when deciding whether a lesson is one-off, project-local, or worth re-review by a similar agent flow later.
   Do not read those observations as isolated bullets only. When the same project, workspace, or thread appears repeatedly, inspect the chronology and use it to reconstruct the episode: what was tried earlier, what changed later, and which revision actually improved the result.
7. If the grouped actions are coherent, run the lowest-risk apply mode:
`python .agents/skills/local-kb-retrieve/scripts/kb_consolidate.py --json --apply-mode new-candidates`
   Only do this when the eligible routes are semantically specific enough; in the current implementation, broad routes and routes with fewer than 3 segments should stay proposal-only.
For entry-link maintenance, `python .agents/skills/local-kb-retrieve/scripts/kb_consolidate.py --json --apply-mode related-cards` may update direct `related_cards` fields when repeated co-use evidence is already stable.
For alternate-route maintenance, `python .agents/skills/local-kb-retrieve/scripts/kb_consolidate.py --json --apply-mode cross-index` may update direct `cross_index` fields when repeated route evidence is already stable enough to justify a low-risk change.
8. Inspect the per-action proposal stubs for this run:
`python .agents/skills/local-kb-retrieve/scripts/kb_proposals.py --run-id <run_id> --json`
9. If a weak observation should stay history-only, a candidate should be rejected, a confidence review should be recorded, or a split review should be closed without rewriting the card yet, append a maintenance decision trace:
`python .agents/skills/local-kb-retrieve/scripts/kb_maintenance.py --decision-type observation-ignored|candidate-rejected|confidence-reviewed|split-reviewed --action-key <action_key> --resolved-event-ids <csv_event_ids> --reason "<why>" --json`
   For `split-reviewed`, always bind the decision to the concrete supporting event ids from the current review. Do not close split review with empty `resolved-event-ids`.
10. If the same trusted card keeps recurring in observations or proposal stubs, run a split review:
   - keep a **hub card** when it still expresses one bounded predictive relation and mainly serves as an entry point
   - mark an **overloaded card** for split proposal when it now mixes multiple scenarios, actions, results, or route-specific case branches, even if those branches are still arriving through the same route
   - repeated hits alone are a review signal, not an automatic split rule
11. When drafting or updating cards, rewrite the evidence into predictive form: `if / action -> predicted result -> operational use`. Reject “should / avoid / best practice” wording unless the causal prediction is explicit.
12. Model/runtime behavior cards are valid when they stay bounded and auditable. Scope them to the most precise runtime identity that is actually known. If exact model identity is not surfaced reliably, scope them more conservatively to the active Codex runtime, current environment, or known model family.
13. When maintaining those cards, prefer more than one retrieval path when justified: a runtime-facing route such as `codex/runtime-behavior/...` or `ai/runtime/...`, plus any prompting, tool-use, workflow, or planning routes that materially exposed the behavior.
14. User-specific cards are also valid when they stay bounded, evidence-based, and behaviorally framed. Keep them private by default, prefer task-conditioned preference or reaction models over personality summaries, and reject broad character-label wording even when the interaction signal feels strong.
15. For `review-related-cards` actions, only keep direct related-card links that are supported by repeated co-use of actually used `entry_ids`. Keep the card surface simple: no recursive graph expansion and no more than 3 related cards per entry.
16. For `review-cross-index` actions, only keep direct alternate retrieval paths that are supported by repeated actual route usage. Low-risk auto-apply should strengthen stable `cross_index` paths; pruning should stay proposal-first until stronger removal evidence exists. Do not use this to perform broad taxonomy rewrites.
17. Read the resulting `snapshot.json`, `proposal.json`, action stub paths, and `apply.json` paths from the consolidation output.
18. If the maintenance pass needs recovery, inspect and optionally restore history events:
`python .agents/skills/local-kb-retrieve/scripts/kb_rollback.py inspect --run-id <run_id> --write-manifest --json`
`python .agents/skills/local-kb-retrieve/scripts/kb_rollback.py restore --run-id <run_id> --artifact history-events --json`
19. Summarize the pass:
   - run id
   - observations processed
   - candidates created
   - related-card updates applied
   - cross-index updates applied
   - actions skipped
   - maintenance decisions recorded
   - proposal stub counts by action type
   - undeclared taxonomy branches
   - cards reviewed for keep-as-hub vs split-review
   - card updates or taxonomy changes still needed later

Default cadence:

- active buildout: once per day
- quieter maintenance: two or three times per week
