# Invariant Examples

Invariants are executable rules over reachable states and traces. They should be small, concrete, and tied to the failure mode that matters.

## No Duplicate Records

Use when a workflow persists records, events, applications, scores, or decisions.

Intent:

```text
For every reachable state, each persisted id appears at most once.
```

Example:

```python
def no_duplicate_records(state, trace):
    return len(state.record_ids) == len(set(state.record_ids))
```

This catches missing deduplication and non-idempotent retries.

## No Repeated Scoring Without Refresh

Use when scoring, ranking, classification, or matching should happen once unless a refresh input exists.

Intent:

```text
For every reachable state, each job_id appears in score_attempts at most once.
```

Example:

```python
def no_repeated_scoring_without_refresh(state, trace):
    return len(state.score_attempts) == len(set(state.score_attempts))
```

This catches blocks that ignore score cache and recompute on repeated input.

## Every Downstream Object Has Source Traceability

Use when downstream objects must be derived from upstream validated or scored objects.

Intent:

```text
Every persisted or decided object can be traced to a prior source object in state or trace.
```

Example:

```python
def every_record_has_source_score(state, trace):
    scored = {entry.job_id for entry in state.score_cache}
    return all(job_id in scored for job_id in state.application_records)
```

This catches persistence from raw input or missing upstream state.

## No Contradictory Final Decisions

Use when the same object cannot receive mutually exclusive outcomes.

Intent:

```text
No job has both apply and ignore decisions.
```

Example:

```python
def no_contradictory_final_decisions(state, trace):
    actions_by_job = {}
    for decision in state.decisions:
        actions_by_job.setdefault(decision.job_id, set()).add(decision.action)
    return all(
        not {"apply", "ignore"}.issubset(actions)
        for actions in actions_by_job.values()
    )
```

This catches branches that make incompatible decisions across repeated inputs.

## Cache Consistency

Use when state contains both cached derived data and source-of-truth records.

Intent:

```text
Cache entries and source records must not disagree about the same object.
```

Example:

```python
def cache_matches_source_of_truth(state, trace):
    source = dict(state.source_scores)
    return all(source.get(job_id) == score for job_id, score in state.score_cache)
```

This catches stale cache writes and hidden alternate scoring paths.

## Exactly One State Owner

Use when only one function block should write a given state field.

Intent:

```text
Only the owning block writes each protected state field.
```

Example:

```python
def only_record_block_writes_records(state, trace):
    return all(
        step.function_name == "RecordScoredJob"
        for step in trace.steps
        if step.old_state.application_records != step.new_state.application_records
    )
```

This catches state mutation from the wrong module.

## Idempotent Record Operation

Use when recording the same object twice should not create a second side effect.

Intent:

```text
Repeating the same recordable object leaves at most one persisted record.
```

Example:

```python
def record_operation_is_idempotent(state, trace):
    return len(state.application_records) == len(set(state.application_records))
```

This catches append-only broken record blocks.

## No Hidden Second Source Of Truth

Use when a workflow has one authoritative state field and other fields are derived.

Intent:

```text
No block should derive decisions from a shadow copy that can diverge from the authoritative state.
```

Example:

```python
def decisions_use_record_state(state, trace):
    recorded = set(state.application_records)
    return all(
        decision.action in {"ignore"} or decision.job_id in recorded
        for decision in state.decisions
    )
```

This catches duplicated state ownership and divergent caches.

## No Output That Downstream Cannot Consume

Use when a composed workflow must pass each block output to the next block.

Intent:

```text
The report has no non-consumable branch unless explicitly modeled as terminal.
```

Example check:

```python
report = explorer.explore()
assert not report.dead_branches
```

This catches output type drift, missing adapters, and incomplete workflow composition.
