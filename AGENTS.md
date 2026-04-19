# Repository expectations

## Start here

- Read `PROJECT_SPEC.md` before making architectural changes.
- Treat `PROJECT_SPEC.md` as the authoritative v0.1 design brief.
- Keep `AGENTS.md` short; put detailed design rationale in `PROJECT_SPEC.md`.

## Purpose

This repository stores a local predictive knowledge library that Codex can consult before solving tasks.

## How to use the library

- When a task may depend on user preference, recurring workflow, domain heuristics, or prior lessons, invoke `$local-kb-retrieve` first.
- Infer a primary conceptual route before retrieval. Do not rely on flat keywords alone when a route is apparent.
- Treat KB entries as bounded context, not unquestionable truth.
- Prefer entries with `status: trusted`.
- If an entry conflicts with direct user instructions in the current conversation, follow the current user instruction.

## Update rules

- Never write directly into `kb/public/` or `kb/private/` without an explicit request.
- New lessons should first be proposed into `kb/candidates/`.
- Keep private data out of commits unless the user explicitly wants it versioned.
- Do not add embeddings, vector databases, MCP services, or subagent orchestration in v0.1 unless explicitly requested.

## Validation

- Before changing retrieval logic, run a quick manual search test.
- Keep the skill description narrow so it does not trigger on trivial tasks.
- Keep scoring logic explainable and easy to inspect.
