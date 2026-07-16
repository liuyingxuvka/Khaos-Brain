# Core Modeling Protocol

Use this protocol before non-trivial behavior changes involving workflow order, state, retries, deduplication, idempotency, caching, side effects, or ordinary module boundaries.

## Preflight and Risk Intent

Verify `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"` and the target project's AGENTS.md managed adoption record. If the real package is unavailable, connect it or report blocked/partial; never create a replacement mini-framework.

Before constructing or materially changing a concrete model candidate, freeze a current model-instance purpose declaration: stable task and instance ids, a reviewable guarded purpose, one-or-many finite protected failure ids, and the claim boundary. The declaration belongs to this task-specific instance; a reusable model type, template, or skill is never permanently assigned one failure class.

Write a minimum valuable Risk Intent that names those protected error classes/harms, model-critical state and side effects, completion evidence, business path identity, adversarial/repeated inputs, hard invariants, representative known-bad paths, public/local template reuse or no-match, template harvest disposition, and residual blindspots. After candidate construction, bind the exact candidate fingerprint, one native known-good case, exactly one native known-bad case per declared failure, native oracle ids, and current evidence checks into the instance closure. Missing, duplicate, disconnected, post-hoc, or stale closure blocks the protection claim; there is one fixed workflow and no weaker mode or fallback.

## Finite model

1. List finite abstract input classes, including repeat/retry/partial-failure/order variants.
2. Use immutable, hashable abstract state only for facts that affect future behavior or invariants; never call live network, database, clock, random, LLM, or external services from the model.
3. Split named FunctionBlocks at behavioral boundaries. Every block implements `Input x State -> Set(Output x State)` and declares reads/writes.
4. Enumerate every possible abstract output and explicit terminal/error/no-result branch; do not hide outcomes in prose.
5. Inventory every production writer for invariant-critical state and classify modeled, scoped, or missing writers.
6. Define idempotency, deduplication, retry, cache/source-of-truth, side-effect, and ordering behavior where relevant.
7. Write hard invariants over all reachable state/trace paths; never weaken them merely to pass.
8. Use standard property factories or packs only when their declared selectors match the risk; helpers do not infer the model.

## Formal check plan

Bind `RiskIntent`, `MinimumModelContract`, current `KnownBadProof`, template reuse/no-match, and template harvest closure into `FlowGuardCheckPlan`; call `run_model_first_checks(plan)` with finite inputs/states and repeated-input sequences.

The formal runner may emit progress on stderr. Progress is liveness only. Inspect the final summary, finding ledger, counterexamples, skipped/not-run sections, and exit/result evidence.

Make one representative broken implementation/trace fail for every protected failure id, and make the declared native known-good case pass. Give counterexamples and known-bad proofs stable target ids and keep them bound to the current model-instance closure when they drive owner-code regression evidence.

Minimize failing sequences only to aid review; preserve the original trace. When a counterexample exposes a design bug, revise model and intended architecture. When it exposes model infidelity, revise the model/oracle/replay adapter. Rerun after any relevant input changes.

## Scenario and liveness review

Use scenario review for repeats, retries, refresh, queues, reprocessing, uncertain decisions, cache/deduplication, human loops, side effects, and rejected/missing-field/no-body repair packets. Broken-model expected violations are successful observations; policy uncertainty remains `needs_human_review`.

For retry/wait/refresh/queue/human-review cycles, review reachable-state SCCs, stuck non-terminals, required success reachability, terminal outgoing edges, and fairness/progress. An escape edge does not prove termination. Repeated rejected input requires repair feedback, a blocker, or a finite/progress rule.

## Implementation and replay

Implement production code only after the relevant model shape passes. Preserve state/side-effect ownership, idempotency, deduplication, contracts, and invariants.

Use conformance replay by default when multiple real writers, durable side effects, cleanup/finalizer paths, production-behavior claims, or projection adapters are involved. Compare projected real outputs/state/labels to representative model traces; do not demand internal state identity and do not silently diverge.

Reuse an old abstract result only when model, scenarios, oracle, invariants, risk boundary, task revision, and proof artifacts remain identical/current. Spend post-edit validation on focused tests or conformance when that is stronger; otherwise rerun.

## Core completion

Core modeling is complete only when the real engine ran, the model is faithful enough for the declared risk, the known-bad path fails, correct paths pass, counterexamples were resolved/scoped, required scenarios/liveness checks ran, template harvest closed, and missing production/conformance evidence remains visible in the claim boundary.
