# Sleep Maintenance Runbook

This runbook is for the independent `kb-sleeper` maintenance pass. It is operational on purpose: use the current file-based tools, keep every change logged, emit snapshots before risky steps, and prefer reversible updates.

## When To Run

- Run after active work sessions that produced multiple observations or misses.
- Run at least daily while the repository is evolving quickly.
- Run before changing retrieval behavior or route structure.
- Do not run inside the main task thread unless the task is blocked by KB drift.

## Roles

- `kb-scout`: read-only preflight before non-trivial work. Finds likely routes and cards.
- `kb-recorder`: post-task logger. Appends observations, misses, and candidate hints.
- `kb-sleeper`: separate maintenance pass. Reviews accumulated history, emits snapshots/proposals, applies only low-risk changes, and prepares the next maintenance queue.

## Maintenance Checklist

1. Confirm the repo root and work from the repository root.
2. If the last task did not already do it, append missing observations with `kb_feedback.py`.
3. Run consolidation in proposal mode first and inspect the grouped actions.
4. If the grouped actions are low-risk, rerun consolidation with `--apply-mode new-candidates`.
5. Inspect per-action proposal stubs with `kb_proposals.py`.
6. Inspect emitted artifacts under `kb/history/consolidation/<run-id>/`.
7. If needed, generate a rollback manifest with `kb_rollback.py inspect --write-manifest`.
8. If the pass produced a bad low-risk apply, restore `history-events` from the snapshot.
9. Leave higher-risk work as proposal-only for a later AI maintenance pass.

## Commands To Run Now

Record an observation after a task:

```powershell
python .agents/skills/local-kb-retrieve/scripts/kb_feedback.py `
  --repo-root . `
  --task-summary "Adjusted local KB maintenance workflow" `
  --route-hint "system/knowledge-library/retrieval" `
  --entry-ids "example-entry-001" `
  --hit-quality hit `
  --outcome "Workflow stayed aligned with current repo tooling" `
  --comment "Maintenance pass needs a reusable runbook" `
  --suggested-action new-candidate `
  --json
```

Inspect consolidation without applying changes:

```powershell
python .agents/skills/local-kb-retrieve/scripts/kb_consolidate.py `
  --repo-root . `
  --run-id daily-maintenance `
  --emit-files `
  --apply-mode none `
  --json
```

Apply the only currently supported low-risk change type:

```powershell
python .agents/skills/local-kb-retrieve/scripts/kb_consolidate.py `
  --repo-root . `
  --run-id daily-maintenance `
  --emit-files `
  --apply-mode new-candidates `
  --json
```

Inspect per-action proposal stubs for the maintenance run:

```powershell
python .agents/skills/local-kb-retrieve/scripts/kb_proposals.py `
  --repo-root . `
  --run-id daily-maintenance `
  --json
```

Inspect restorable artifacts for a consolidation run:

```powershell
python .agents/skills/local-kb-retrieve/scripts/kb_rollback.py inspect `
  --repo-root . `
  --run-id daily-maintenance `
  --write-manifest `
  --json
```

Dry-run or execute the current low-risk restore path:

```powershell
python .agents/skills/local-kb-retrieve/scripts/kb_rollback.py restore `
  --repo-root . `
  --run-id daily-maintenance `
  --artifact history-events `
  --dry-run `
  --json
```

Inspect the explicit taxonomy tree:

```powershell
python .agents/skills/local-kb-retrieve/scripts/kb_taxonomy.py `
  --repo-root . `
  --json
```

Inspect the smallest undeclared taxonomy routes currently implied by entries:

```powershell
python .agents/skills/local-kb-retrieve/scripts/kb_taxonomy.py `
  --repo-root . `
  --gaps-only `
  --json
```

## Outputs To Inspect

- `kb_feedback.py --json`
  - confirm `event.event_id`, `event.event_type`, `event.created_at`, and `history_path`
- `kb_consolidate.py --json`
  - inspect `candidate_action_count`
  - inspect each action's `action_type`, `target`, `signals`, `apply_eligibility`, and `recommended_next_step`
  - inspect `apply_summary` and `artifact_paths`
- `kb/history/consolidation/<run-id>/snapshot.json`
  - confirms which history events were included in the pass
- `kb/history/consolidation/<run-id>/proposal.json`
  - main review artifact for grouped maintenance actions
- `kb/history/consolidation/<run-id>/actions/*.json`
  - one per-action stub for deeper AI maintenance follow-up
- `kb/history/consolidation/<run-id>/apply.json`
  - only present when `--apply-mode new-candidates` was used
- `kb/history/consolidation/<run-id>/rollback_manifest.json`
  - present after `kb_rollback.py inspect --write-manifest`
- `kb_proposals.py --run-id <run-id> --json`
  - inspect the per-action stub summary by `action_type` and `suggested_artifact_kind`
- `kb_taxonomy.py --json`
  - inspect the declared route layer and current observed coverage counts
- `kb_taxonomy.py --gaps-only --json`
  - inspect undeclared route branches that AI may later turn into taxonomy proposals

## Low-Risk Changes Currently Allowed

- Append new observation events with `kb_feedback.py`
- Create explicit manual candidate cards with `kb_capture_candidate.py`
- Run consolidation in proposal mode
- Auto-apply grouped `consider-new-candidate` actions only when:
  - the target is a route
  - there are at least 2 grouped supporting observations
  - the observations include task summaries
- Restore `kb/history/events.jsonl` from a consolidation snapshot

## Still Proposal-Only

- Updating existing cards
- Promoting candidates into `kb/public/` or `kb/private/`
- Taxonomy changes, including route add/rename/move/split/merge
- Code-change suggestions from history
- Single-observation candidate creation
- Any rollback beyond `history-events`

## Suggested Maintenance Thread Prompt

Use this as the opening prompt for an independent maintenance chat or future automation:

```text
Run a local KB sleep-maintenance pass for this repository.

Goals:
1. Read recent observation history and keep the run file-based, logged, and reversible.
2. Use kb_consolidate.py in proposal mode first.
3. Only use --apply-mode new-candidates if the grouped actions are clearly low-risk and eligible.
4. Inspect snapshot/proposal/apply artifacts for the run.
5. If the apply looks wrong, prepare or execute kb_rollback.py restore for history-events.
6. Do not rewrite trusted cards or taxonomy directly; leave those as proposal-only notes.

Report:
- run id used
- observation count reviewed
- candidates created, if any
- actions left proposal-only
- whether rollback inspection was generated
- concrete next maintenance targets
```
