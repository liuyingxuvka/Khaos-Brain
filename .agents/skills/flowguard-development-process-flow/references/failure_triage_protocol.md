# Failure Triage And Root-Cause Repair

Use this reference after non-pass or materially surprising evidence. The goal
is to gather enough valid information for a root-cause repair without blindly
continuing past a hard blocker or repeatedly fixing one symptom at a time.

## Decide The Diagnostic Boundary First

- `targeted`: one affected component or high-information hypothesis;
- `declared_complete`: all valid diagnostics in a named finite boundary;
- `budgeted`: valid diagnostics until a named limit.

Independent diagnostics within that boundary may all run even when another
ordinary diagnostic fails. Stop only when continuation would be invalid,
unsafe, unauthorized, destructive, or unable to produce meaningful evidence.
Keep unrun descendants and reasons visible.

## Preserve Raw Evidence

TestMesh records campaign id, diagnostic boundary,
planned/executed/failed/not-run counts, not-run reason, and stable Finding
Ledger ids. It must satisfy:

- `planned = executed + not_run`;
- `failed <= executed`;
- `declared_complete` has no not-run work;
- other boundaries explain any not-run work;
- failures name stable finding ids.

Do not copy those counts into DPF or PlanDetail.

## Group Only Related Findings

Co-occurrence is not a root cause. A repair group needs:

- raw finding ids;
- current relation evidence;
- a falsifiable root-cause claim and disproof checks;
- affected obligation ids and repair actions;
- current primary-owner evidence;
- required and current affected revalidation ids.

Unrelated findings stay separate. Repair the lowest shared owner supported by
the evidence, not merely the first visible symptom.

## Route Specialist Failures

- ordinary implementation defect: repair through the ordinary owner;
- model too large/coarse/disconnected: ModelMesh;
- test too large/slow/layered/hidden: TestMesh;
- model, code owner, and test mismatch: Model-Test Alignment;
- stale transition or contract case inventory: regenerate through its owner;
- post-green runtime/test/replay/log/UI miss: Model Miss Review;
- topology-grounded future-use hazard: Model Topology Hazard Review;
- UI or payload evidence change: UI Flow Structure or payload owner;
- field/replacement/repair lifecycle change: its lifecycle owner.

The parent process consumes the specialist's current evidence id before
closure. A later broad green command alone does not erase an open handoff.

## Revalidate And Reconsider

After repair, rerun every affected obligation and any proof whose verifier or
input changed. Do not rerun unaffected heavy owners merely for ceremony. If
the repair or new evidence changes the diagnostic space, make a fresh bounded
decision; otherwise continue to the frozen final gate.
