# Local KB Sleep Maintenance Prompt

Use this prompt in a separate Codex chat or scheduled automation that is dedicated to maintaining the local predictive knowledge library.

Goal:

- keep the library easy to navigate
- consolidate observations into candidate knowledge
- surface undeclared taxonomy branches
- leave an auditable trail of what changed

Current implementation boundary:

- you may inspect taxonomy, navigation, history, and consolidation artifacts
- you may let `kb_consolidate.py` auto-create low-risk candidate scaffolds with `--apply-mode new-candidates`
- you may inspect or restore `kb/history/events.jsonl` through `kb_rollback.py`
- do not silently rewrite trusted cards or official taxonomy during this maintenance pass

Checklist:

1. Inspect the explicit taxonomy tree:
   `python .agents/skills/local-kb-retrieve/scripts/kb_taxonomy.py --repo-root . --json`
2. Inspect the smallest undeclared taxonomy routes implied by current entries:
   `python .agents/skills/local-kb-retrieve/scripts/kb_taxonomy.py --repo-root . --gaps-only --json`
3. If route structure looks unclear, inspect the current route tree view:
   `python .agents/skills/local-kb-retrieve/scripts/kb_nav.py --repo-root . --json`
4. Inspect recent history in proposal mode:
   `python .agents/skills/local-kb-retrieve/scripts/kb_consolidate.py --repo-root . --json --apply-mode none`
5. If the grouped actions are coherent, run the lowest-risk apply mode:
   `python .agents/skills/local-kb-retrieve/scripts/kb_consolidate.py --repo-root . --json --apply-mode new-candidates`
6. Inspect the per-action proposal stubs for this run:
   `python .agents/skills/local-kb-retrieve/scripts/kb_proposals.py --repo-root . --run-id <run_id> --json`
7. Read the resulting `snapshot.json`, `proposal.json`, action stub paths, and `apply.json` paths from the consolidation output.
8. If the maintenance pass needs recovery, inspect and optionally restore history events:
   `python .agents/skills/local-kb-retrieve/scripts/kb_rollback.py inspect --repo-root . --run-id <run_id> --write-manifest --json`
   `python .agents/skills/local-kb-retrieve/scripts/kb_rollback.py restore --repo-root . --run-id <run_id> --artifact history-events --json`
9. Summarize the pass:
   - run id
   - observations processed
   - candidates created
   - actions skipped
   - proposal stub counts by action type
   - undeclared taxonomy branches
   - card updates or taxonomy changes still needed later

Default cadence:

- active buildout: once per day
- quieter maintenance: two or three times per week
