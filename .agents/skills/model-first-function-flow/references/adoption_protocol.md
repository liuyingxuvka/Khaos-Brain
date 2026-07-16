# Real Adoption Protocol

Use this reference when applying flowguard in another project or when the user
asks whether flowguard is ready to use in real work.

## Trigger

Use flowguard before production edits when a task involves behavior,
workflows, state, retries, deduplication, idempotency, caching, repeated inputs,
module boundaries, uncertain decisions, or side effects.

## Record

Keep a project-local adoption record:

- `.flowguard/adoption_log.jsonl` for machine-readable entries;
- `docs/flowguard_adoption_log.md` for human-readable entries.

Each entry should include:

- task id;
- project name;
- task summary;
- trigger reason;
- status;
- model files;
- commands run;
- elapsed time;
- findings;
- counterexamples;
- skipped steps and reasons;
- friction points;
- next actions.

Allowed status values:

- `in_progress`: the agent has started the model-first work but has not
  finished the adoption evidence yet;
- `completed`: the model-first work is finished and executable checks were
  recorded;
- `blocked`: the task could not finish because a real blocker remains, such as
  a missing formal flowguard toolchain;
- `skipped_with_reason`: a step was intentionally skipped and the reason is
  recorded;
- `failed`: a command, model check, conformance replay, or oracle review failed.

Do not treat `in_progress`, `blocked`, `skipped_with_reason`, or `failed` as a
successful adoption. They are evidence states for review, not passes.

## Minimal Python API

```python
from flowguard.adoption import (
    AdoptionCommandResult,
    AdoptionTimer,
    append_jsonl,
    append_markdown_log,
)

timer = AdoptionTimer(
    task_id="task-001",
    project="my-project",
    task_summary="Add idempotent retry handling",
    trigger_reason="retry and side-effect risk",
    status="in_progress",
)

entry = timer.finish(
    status="completed",
    model_files=("flowguard_model/model.py",),
    commands=(
        AdoptionCommandResult(
            "python -m flowguard scenario-review",
            ok=True,
            duration_seconds=1.2,
            summary="expected outcomes matched",
        ),
    ),
    findings=("Repeated input stayed idempotent.",),
    skipped_steps=("conformance replay skipped: no production code yet",),
)

append_jsonl(".flowguard/adoption_log.jsonl", entry)
append_markdown_log("docs/flowguard_adoption_log.md", entry)
```

## Minimal CLI

When the installed FlowGuard version supports it, use the thin CLI to reduce
logging drift:

```powershell
python -m flowguard adoption-start --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>"
python -m flowguard adoption-finish --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>" --command "<check command>"
```

The CLI appends both `.flowguard/adoption_log.jsonl` and
`docs/flowguard_adoption_log.md`. It does not replace executable model checks.

## Review

At the end of the task, summarize:

- whether flowguard was useful;
- which bug class it checked;
- what it caught or failed to catch;
- which step was slow or confusing;
- what should improve in the next flowguard iteration.

Do not treat skipped checks, `needs_human_review`, or known limitations as
passes.
