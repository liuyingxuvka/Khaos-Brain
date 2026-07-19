## Context

Postflight uses the same lifecycle writer lock as other KB writers. The lock may wait for a live owner for 120 seconds, but postflight currently labels 30 seconds as its terminal budget, and an external agent used an approximately 34-second launcher timeout. The outer process can therefore stop before the sole valid inner route has exhausted its own wait policy. The existing event-id and terminal-receipt design already prevents duplicate durable events; the missing contract is ordered timeout ownership.

## Goals / Non-Goals

**Goals:**

- Make every allowed internal wait fit inside the postflight terminal budget.
- Make the caller's launcher timeout strictly larger than the terminal budget.
- Preserve exactly one event id and one execution owner until terminal JSON or exact-episode inspection.
- Validate the ordering in the existing FlowGuard model and focused tests.

**Non-Goals:**

- No second writer, retry daemon, alternate launcher, compatibility reader, or fallback route.
- No change to Sleep, Dream, retrieval, ResearchGuard, or lifecycle authority.
- No reduction of functional correctness checks and no full-suite rerun for this isolated change.

## Decisions

1. The existing 120-second writer-lock acquisition limit remains the source constraint. Postflight receives a 150-second terminal budget: 120 seconds for lock acquisition plus 30 seconds for the bounded append, fsync, lock release, receipt write, and scheduling overhead.
2. The documented outer launcher timeout is 180 seconds: the complete 150-second terminal budget plus 30 seconds for process startup, JSON transport, and cleanup confirmation.
3. The runtime receipt records the terminal budget as before. Focused tests additionally prove `writer lock < terminal budget < launcher timeout`; the FlowGuard model makes the same ordering part of success licensing.
4. A launcher timeout preserves the original event id. The caller first checks whether the original process still exists; it waits if live, and inspects the same event id after confirmed exit. It never launches a second writer or selects another route.

Alternatives rejected:

- Keeping a 30-second budget would continue to misclassify a valid 120-second lock wait.
- Reducing the writer-lock timeout would turn ordinary contention into functional failure.
- Retrying automatically would create competing owners and violate the one-path contract.
- Running a full regression after each text/model edit would add latency without new evidence beyond the affected owner set.

## Risks / Trade-offs

- [A genuinely blocked live owner may now take longer to report failure] → The same bounded path still fails visibly after 120 seconds; the extra headroom only lets it write and return a trustworthy terminal receipt.
- [External callers may ignore the documented 180-second timeout] → Installation currentness checks and focused template tests require the timeout wording on the installed predictive-KB skill.
- [A process can still be externally killed] → Same-event inspection remains mandatory and duplicate execution remains forbidden until the descendant process tree is confirmed empty.

## Migration Plan

Update the runtime constants, FlowGuard model, OpenSpec delta, skill templates, author skill, focused tests, installer currentness checks, and release notes. Run only the postflight/model/template/install-check affected tests. Once implementation and the canonical spec are frozen, archive this change, perform one transactional local installation and one final GitHub `main` validation, then tag and publish v0.6.7.
