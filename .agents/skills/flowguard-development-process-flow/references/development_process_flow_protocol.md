# DevelopmentProcessFlow Protocol

Use `development_process_flow` as the public development-process simulator for
non-trivial planning, multi-skill work, staged execution, freshness, sync,
release/archive/publish, and final process claims. It owns lifecycle order and
evidence freshness; it consumes specialist evidence without taking over the
specialist's judgment.

## Modes

Record applicable modes in this order:

1. `plan_detailing`: delegate rough or underspecified plans to
   `flowguard-plan-detailing-compiler` when structured rows are needed.
2. `strategy_selection`: an internal, conditional process-optimization mode.
3. `agent_workflow`: delegate multi-skill/tool or external-side-effect
   rehearsal to `flowguard-agent-workflow-rehearsal`.
4. `execution_freshness`: review artifact versions, evidence, sync, and final
   claim closure here.

The internal mode id remains `strategy_selection`; it is not a public route or
a mandatory choice for every task.

## Conditional Local Material

- Read `process_optimization_protocol.md` only when `explicit_request`,
  `multiple_equivalent_routes`, `material_rework_risk`, or
  `diagnostic_boundary_choice` applies.
- Read `failure_triage_protocol.md` only after failed, stale, skipped,
  timeout, not-run, progress-only, ambiguous, or materially surprising
  evidence needs classification or root-cause grouping.

With no optimization reason, record `not_needed` and add no candidates, cost
records, repair groups, or optimization evidence gate.

## Ownership

- DevelopmentProcessFlow owns process order, artifact versions, invalidation,
  current decision references, peer-write handling, and process claims.
- PlanDetail owns structured plan rows, not execution proof.
- AgentWorkflowRehearsal owns AI-operation skill/tool order.
- TestMesh owns diagnostic boundaries, actual execution accounting, findings,
  skips, and terminal test receipts.
- Finding Ledger owns stable raw finding ids.
- SpecWorkPackage owns provider tasks, dependency graphs, sessions, receipts,
  and consumer fan-out.
- Model-Test Alignment owns ordinary obligation, primary CodeContract owner,
  and TestEvidence closure.
- Product models retain product-runtime behavior; process references are typed
  targets, not ownership transfers.

## Intake

Capture grouped rows for:

- Changed artifacts: id, type, current version/fingerprint, path/owner, upstream ids;
- Process steps: id/type, status, reads, writes, invalidations, order, actor plane,
  typed target planes/commitments/relations, required and produced evidence;
- simulator modes: reason, delegate, required evidence, scoped gaps;
- validations: obligation id, required artifacts/evidence kinds, scope,
  command, V-style pair where relevant;
- Validation evidence: id, kind, owner route, status, covered and verifier versions,
  command/result, skip/background/release caveats, and proof artifact;
- Freshness rules: upstream change, affected artifacts/evidence, and rationale;
- synchronization domains: source, shadow, formal repository, package,
  installed skills, and Git revision/receipt;
- final claim: routine versus release/archive/publish scope and consuming Risk
  Evidence Ledger evidence.

Keep provider, work-package, change, task, obligation, check, validation,
session, receipt, and consumer ids distinct.

## Execution Shape

Use a staged plan, but do not make every diagnostic depend on the previous
diagnostic's success. Independent focused diagnostics should all report their
findings within the chosen boundary so one ordinary failure does not hide the
rest of the issue surface. A hard blocker stops descendants whose results
would be invalid, unsafe, or unauthorized; those descendants stay visible as
not run with a reason.

After the diagnostic boundary closes, relate findings, repair the primary
owner/root cause, and rerun only affected obligations. Repeat diagnosis only
when the repair or new material evidence changes the remaining boundary.

Reserve broad full verification for a stable frozen integration snapshot.
Freeze source, toolchain, check inventory, dependencies, and exactly one owner
per heavy check. Run one all-model owner and one full-test owner; receipt
consumers project their immutable success and do not rerun them.

If a launcher times out or is interrupted, confirm that its descendant process
tree is gone before accepting evidence or starting another owner.

## Freshness And Sync

Repository source, shadow workspace, formal repository, editable/installed
package, installed skills, and local Git are separate evidence domains. A pass
in one cannot stand in for another.

Peer or unknown-writer changes are preserved. Re-read and merge them, stale
only affected evidence, and derive affected revalidation; never roll back peer
work to recover an older green snapshot.

Progress logs, PIDs, heartbeats, and running states prove liveness only. Final
evidence requires terminal status, exit code, concrete result artifact and
fingerprint, covered ids, inventory revision, and current artifact/verifier
versions.

## Specification Work Packages

For an active OpenSpec, Spec Kit, or supported provider, consume one bounded
`SpecWorkPackage`. Reconcile provider tasks with FlowGuard obligations/checks
in both directions. Canonical input snapshots exclude reports, logs, caches,
and receipts. One exact terminal receipt may serve several consumers without
being copied or counted as several executions. Cross-change reuse requires an
explicit safe scope and identical execution identity.

A failed dependency creates visible not-run descendants instead of launching
them. Archive remains blocked while mappings, frozen/post-run input stability,
provider-native verification, or receipt freshness is missing.

## Failure Routing

Classify non-pass evidence before editing or rerunning. Ordinary defects may
use the ordinary repair path. Route oversized models to ModelMesh; layered,
slow, hidden, or release-only validation to TestMesh; obligation/code/test
mismatch to Model-Test Alignment; new post-green behavior misses to Model Miss
Review; anchored future-use hazards to Model Topology Hazard Review; UI or
payload evidence changes to their native owners.

A later green command does not close a specialist handoff by itself. The
specialist must produce current evidence and the parent process must consume
its id.

## Hard Gates

- Use the real FlowGuard check engine and managed project record; never create
  a substitute mini-framework.
- Keep sibling semantics, provider authority, product behavior, and test
  execution with their native owners.
- Failed, skipped, timeout, not-run, running, stale, progress-only, or hidden
  evidence cannot satisfy a current requirement.
- A cheaper route is eligible only after outcome, obligation/evidence, safety,
  protected side effect, dependency authority, and execution-owner authority
  are equal.
- Estimated comparison may support a preferred route; `minimum` requires
  measured costs over an exhausted named finite set. Never claim a global
  optimum.
- Material new evidence stales the decision. A repair stays open until every
  affected obligation has current revalidation.
- Broad done/release/archive/publish claims require current proof artifacts,
  current Risk Evidence Ledger closure, and all required freshness domains.

## Output

Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`,
`claim_boundary`, `typed_next_actions`, selected modes, freshness status, and
required affected revalidation. Include process-optimization details only when
the mode is active. A diagram should show order, invalidation, hard stops, and
required revalidation rather than decorative detail.

## Completion

The process claim is supported only when references and owners resolve,
evidence covers current artifact/verifier versions, specialist handoffs are
reattached, skipped/not-run work remains visible, peer changes are preserved,
required synchronization domains are current, and the requested claim scope
has terminal proof. Otherwise return blocked or explicitly scoped confidence.
