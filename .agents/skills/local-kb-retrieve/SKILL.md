---
name: local-kb-retrieve
description: Retrieve relevant entries from the local predictive knowledge base as a lightweight preflight for repository work. Use route-first retrieval: infer the task direction, then search by domain path and cross-index before relying on flat keyword matching. In Codex, prefer a scout sidecar before non-trivial work and a recorder sidecar after work when sub-agents are available. Treat "no relevant entry" as useful signal, not a reason to skip the scan up front.
---

When this skill is used, follow this workflow:

Default stance: run a quick scan first for repository tasks; keep the scan lightweight unless the returned entries are clearly relevant.

Preferred Codex operating pattern:

- For non-trivial work, start a read-oriented `kb-scout` sidecar sub-agent before the main task so the primary agent can stay focused on the critical path.
- After the main task, start a `kb-recorder` sidecar sub-agent to append feedback, comments, misses, and candidate lessons without polluting the main task flow.
- Run deeper consolidation in a separate scheduled maintenance conversation or automation rather than inside the main task thread.
- If sub-agents are unavailable, or if the task is trivial, fall back to a lightweight inline scan and inline feedback note.

Independent maintenance thread:

- Use a separate maintenance chat or automation for the library's "sleep" workflow. Do not let deep consolidation interrupt the user's main task thread.
- In the current implementation, maintenance may safely write history events, consolidation artifacts, rollback manifests, and candidate scaffolds.
- Do not treat the current tooling as permission to rewrite trusted cards or restructure taxonomy silently inside a main task. Those deeper updates should remain AI-authored follow-up work until the maintenance layer grows beyond candidate-level application.
- A practical active-build cadence is once per day. For calmer periods, two or three times per week is usually enough.

1. Summarize the task in one short sentence.
2. Infer one primary conceptual route such as `work/reporting/ppt` or `engineering/debugging/version-change`.
3. Infer up to three alternative routes when the task may be reachable through more than one conceptual direction.
4. If sub-agents are available and the task is non-trivial, let `kb-scout` handle the initial scan. Otherwise run:
   `python .agents/skills/local-kb-retrieve/scripts/kb_search.py --repo-root . --path-hint "<primary route>" --query "<task summary plus useful keywords>" --top-k 5`
5. Read the returned entries.
6. Prefer entries with stronger route alignment, `status: trusted`, and higher `confidence`.
7. Use retrieved entries as bounded context. Do not overgeneralize beyond the entry scope.
8. If no relevant entries are found, continue without forcing the library into the answer; the absence of hits is still a useful signal.
9. At the end of the task, prefer letting `kb-recorder` append structured feedback so the scheduled AI consolidation flow can process it later.
10. If a reusable new lesson emerges during the task, record it into candidates or structured history rather than trying to fully consolidate it inside the active task thread.

Sleep maintenance checklist:

1. Inspect the explicit taxonomy layer:
   `python .agents/skills/local-kb-retrieve/scripts/kb_taxonomy.py --repo-root . --json`
2. Inspect the smallest undeclared taxonomy routes that are currently implied by observed entries:
   `python .agents/skills/local-kb-retrieve/scripts/kb_taxonomy.py --repo-root . --gaps-only --json`
3. Inspect recent route navigation if the taxonomy view exposes undeclared branches you need to understand:
   `python .agents/skills/local-kb-retrieve/scripts/kb_nav.py --repo-root . --json`
4. Run consolidation in report-only mode first:
   `python .agents/skills/local-kb-retrieve/scripts/kb_consolidate.py --repo-root . --json --apply-mode none`
5. If the grouped history looks clean, allow the lowest-risk automatic apply path:
   `python .agents/skills/local-kb-retrieve/scripts/kb_consolidate.py --repo-root . --json --apply-mode new-candidates`
6. Inspect the per-action proposal stubs for the run:
   `python .agents/skills/local-kb-retrieve/scripts/kb_proposals.py --repo-root . --run-id <run_id> --json`
7. Review the emitted `snapshot.json`, `proposal.json`, action stub paths, and `apply.json` paths from the consolidation result.
8. If a consolidation run needs recovery, inspect and optionally restore history events:
   `python .agents/skills/local-kb-retrieve/scripts/kb_rollback.py inspect --repo-root . --run-id <run_id> --write-manifest --json`
   `python .agents/skills/local-kb-retrieve/scripts/kb_rollback.py restore --repo-root . --run-id <run_id> --artifact history-events --json`
9. End the maintenance pass with a concise summary:
   run id, created candidates, skipped actions, undeclared taxonomy signals, and the next deeper changes AI should make later.

Output discipline:

- Briefly state which entry ids influenced the answer.
- If the entries are weak or ambiguous, say so.
- Do not expose private entry content unless the user is authorized to see it.
- Keep sidecar agents scoped: `kb-scout` should be read-mostly and `kb-recorder` should default to history, comments, and candidate writes rather than broad structural edits.
- In a maintenance thread, be explicit about what the tooling actually changed versus what still remains a proposal.
