# Codex Memory Starter

A lightweight, file-based starter kit for building a local memory layer that Codex can check before it works.

Use it to help Codex recall preferences, recurring workflows, and reusable lessons before it writes, edits, or plans. This repository publishes the architecture and tooling only. You bring your own cards, taxonomy, and history.

## Why This Exists

- keep memory local, inspectable, and easy to review
- let Codex search by conceptual route instead of flat keywords alone
- record observations and maintenance history without shipping your real data

## What You Get

- file-based KB storage
- route-first retrieval and navigation
- observation logging after work
- consolidation scaffolding for maintenance passes
- rollback and proposal inspection helpers
- Codex skill wiring for scout, recorder, and maintenance flows

## What Stays Out Of The Public Repo

- your real cards
- your private preferences
- your accumulated history or maintenance logs
- your existing trusted KB content

## Daily Workflow

1. Run a quick memory lookup before work.
2. Do the real task.
3. Record any useful observation, miss, or new lesson.
4. Let a separate maintenance pass consolidate that history later.

## Repository Layout

```text
.
├─ AGENTS.md
├─ PROJECT_SPEC.md
├─ README.md
├─ requirements.txt
├─ .agents/
│  └─ skills/
│     └─ local-kb-retrieve/
├─ docs/
│  └─ maintenance_runbook.md
├─ kb/
│  ├─ public/
│  ├─ private/
│  ├─ candidates/
│  ├─ history/
│  └─ taxonomy.yaml
├─ local_kb/
├─ schemas/
└─ tests/
```

## Getting Started

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start with an empty taxonomy and empty KB folders.

3. Add your own cards under:

- `kb/public/` for reusable shared heuristics
- `kb/private/` for user- or org-specific knowledge
- `kb/candidates/` for newly surfaced lessons that still need consolidation

4. Use the repo-local skill before work:

```text
$local-kb-retrieve
```

## Core Commands

Search the KB:

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_search.py \
  --repo-root . \
  --path-hint "your/route/hint" \
  --query "task summary plus useful keywords" \
  --top-k 5 \
  --json
```

Inspect the taxonomy:

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_taxonomy.py \
  --repo-root . \
  --json
```

Record an observation after work:

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_feedback.py \
  --repo-root . \
  --task-summary "what the task was" \
  --route-hint "best/route/hint" \
  --hit-quality "hit" \
  --outcome "short result" \
  --comment "what was learned or what was missing" \
  --suggested-action "new-candidate" \
  --json
```

Run proposal-only maintenance:

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_consolidate.py \
  --repo-root . \
  --run-id "daily-maintenance" \
  --emit-files \
  --apply-mode none \
  --json
```

Inspect per-action maintenance stubs:

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_proposals.py \
  --repo-root . \
  --run-id "daily-maintenance" \
  --json
```

## Template Notes

- Keep `kb/private/` and `kb/history/` out of public publication by default.
- Keep live `kb/public/` cards out of this public template unless you intentionally want them versioned.
- If you want to use this as a real memory system, prefer a private clone or a separate private repository for your evolving cards and taxonomy.
- Treat this repository as a starter kit for your own memory system.
- The most important asset here is the workflow discipline, not the sample content.

## Validation

Run the bundled template-safe tests:

```bash
python -m unittest \
  tests.test_history_event_model \
  tests.test_kb_consolidate_scaffold \
  tests.test_kb_consolidate_apply \
  tests.test_kb_consolidate_action_stubs \
  tests.test_kb_rollback \
  tests.test_kb_proposals \
  tests.test_kb_taxonomy
```
