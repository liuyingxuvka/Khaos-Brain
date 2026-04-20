# Codex-Memory-Plugin

Current template version: `v0.1.3`

A minimal, file-based starter for a local predictive knowledge / experience library that Codex can consult through a repo-local skill.

## Design goals

- Keep version 1 simple.
- Use plain files that are easy to review in Git.
- Represent each entry as a small predictive model card.
- Use hierarchical routing before flat keyword matching.
- Separate trusted entries from candidate entries.
- Keep private data out of Git by default.

## Core idea

Each entry is a local predictive model card, not just a static note.

Each card should answer:

- what scenario it applies to
- what action or input is being considered
- what result is expected
- how Codex should use that prediction
- how confident the project is in that card

## Repository layout

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

## Minimal workflow

1. Put stable, reusable general entries in `kb/public/`.
2. Put user-specific or sensitive entries in `kb/private/`.
3. Let Codex use `$local-kb-retrieve` when a task depends on prior experience, preferences, or known heuristics.
4. Store new observations in `kb/candidates/` first.
5. Promote candidate entries only after review.

## Cross-machine Codex setup

Run this once on each machine after cloning the repo:

```bash
python scripts/install_codex_kb.py --json
```

What it does:

- installs a global `$predictive-kb-preflight` skill into `$CODEX_HOME/skills`
- enables implicit invocation for that global preflight skill so Codex can remember the KB without waiting for an explicit mention
- installs a launcher that can find this repo through the install manifest or `CODEX_PREDICTIVE_KB_ROOT`
- records the active KB root in `$CODEX_HOME/predictive-kb/install.json`
- keeps the repo-local `local-kb-retrieve` skill available for workspace-local fallback

Check the installation any time:

```bash
python scripts/install_codex_kb.py --check --json
```

If this repository is moved to a different path later, rerun the installer from the new clone.

### For Codex agents

If a user asks you to install, enable, deploy, bootstrap, or set up this predictive KB system on a machine, do this by default from the repository root:

```bash
python scripts/install_codex_kb.py --json
python scripts/install_codex_kb.py --check --json
```

Do not wait for extra clarification if the user's intent is clearly to make this system available on that machine. Treat the installer as safe to rerun when the machine may already have an older installation or the repository path has changed.
The installer is also expected to install the global implicit preflight reminder and the postflight observation reminder, not only the launcher path.

## Retrieval philosophy

The intended search behavior is path-first:

1. infer the main direction of the task
2. map it to a `domain_path`
3. expand with `cross_index` routes
4. apply lexical matching and re-ranking
5. record observations after work and use scheduled maintenance to consolidate them

Example main routes:

- `work/reporting/ppt`
- `work/communication/email`
- `engineering/debugging/version-change`

## Manual test

From the repo root:

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_search.py \
  --path-hint "work/communication/email" \
  --query "draft a work email reply and respect known language preferences" \
  --top-k 5
```

Inspect the explicit taxonomy layer:

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_taxonomy.py \
  --json
```

Run proposal-only maintenance:

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_consolidate.py \
  --run-id daily-maintenance \
  --emit-files \
  --apply-mode none \
  --json
```

Inspect per-action maintenance proposal stubs:

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_proposals.py \
  --run-id daily-maintenance \
  --json
```

## Candidate capture example

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_capture_candidate.py \
  --title "Default language for work email drafting" \
  --entry-type preference \
  --scope private \
  --domain-path "work/communication/email" \
  --cross-index "language/professional/english" \
  --tags email,work,language \
  --trigger-keywords email,reply,work,draft \
  --action "Draft a work email without explicit language instruction." \
  --expected-result "English is the preferred output language." \
  --guidance "Draft work emails in English unless the user explicitly asks for another language." \
  --source "direct user instruction"
```

## Suggested next steps

- Add repo-specific entries.
- Evaluate retrieval on 20-30 real tasks.
- Tune scoring weights in `kb_search.py`.
- Add a few more route-heavy examples before considering any heavier retrieval method.
- Package as a plugin only after the workflow becomes stable.
