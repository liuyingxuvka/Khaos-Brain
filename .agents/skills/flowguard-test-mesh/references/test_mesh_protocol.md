# TestMesh Protocol

Use TestMesh when the question is not "does this FlowGuard model pass?" but
"can this parent/child test hierarchy support the parent validation claim?"

TestMesh is the test-side sibling of ModelMesh and StructureMesh. All three use
the same parent/child partition principle:

- ModelMesh partitions a large FlowGuard model into child model regions.
- TestMesh partitions a large test script, suite, or validation flow into child
  test scripts or child suites.
- StructureMesh partitions a large script, module, package, command, or API
  surface into child structural owners.

The parent TestMesh should consume child ownership and evidence contracts. It
should not inline every child test case, fixture, or internal state route. When
a child suite grows too large, it can become its own parent gate with another
local TestMesh.

For a same-intent behavior/product claim, declare the required inventory and
revision independently from the child suites that happened to run. Include
every required surface, materialized model/test obligation, family member,
transition cell, ContractExhaustion case, and shard. A smaller caller-selected
set cannot be promoted to complete evidence even when every declared child is
green. Inventory changes stale prior child evidence.

Before child suite evidence can support parent confidence, derive the target
child suite/script structure from a FlowGuard validation-structure model. The
target split derivation should name the source model, target suite ids, covered
partition items, state ownership fields, side-effect ownership fields, and the
rationale for the validation split. A flat list of suites is not enough.

Layered proof adds four evidence kinds that TestMesh must keep distinct:
parent coverage tests, child disjointness tests, child reattachment tests, and
leaf boundary-matrix tests. A broad parent test command cannot replace missing
leaf matrix evidence, and release-only/background progress cannot support a
routine parent proof until it has final current pass artifacts.

Transition coverage matrices can also feed TestMesh. When Model-Test Alignment
or UI Flow Structure produces required transition cell ids for a large, slow,
or browser-heavy matrix, TestMesh owns the parent/child evidence hierarchy for
those ids. It preserves the model obligation and code contract target ids for
downstream alignment. It does not decide the semantic transition obligation;
Model-Test Alignment still proves that model obligation, owner code contract,
and external-contract test evidence bind the same behavior.

ModelMesh closure models can feed this route after
`model_mesh_closure_to_transition_coverage(...)` projects parent/child closure
transitions into required cell ids. Retry or rejection cells from repeated input
tokens should have child-suite evidence for failure, negative, replay, and
repair-feedback/no-delta behavior before parent validation confidence is broad.

Artifact payload matrices can feed TestMesh the same way. When import/export,
generated artifact, or AI work-package validation has many accepted/rejected
payload cases, TestMesh owns child-suite partitioning, result artifacts,
background completion, execution proof refs, and freshness for those case ids.
It preserves payload contract ids and case ids for downstream Model-Test
Alignment, which still decides whether the real surface's observed output,
error path, state writes, side effects, and round-trip behavior match the
payload contract.

## Trigger

Create or update a TestMesh when:

- a test or regression command is slow enough that routine agents skip it,
  timeout, or cannot wait for it before continuing useful work;
- a large test script or suite is being split into smaller child suites or
  child test scripts;
- one large command mixes unrelated behavior, state, side effects, or release
  gates;
- a parent validation claim depends on several child suites, background jobs,
  adapters, or manual checks;
- skipped, stale, timeout, not-run, or progress-only evidence could be hidden
  inside a green summary;
- `review_auto_mesh_splits(...)` reports a required test split for slow,
  large, broad, progress-only, or release-only direct validation evidence;
- release-only suites should stay visible without blocking routine local
  confidence.
- a transition coverage matrix is too large, slow, browser/manual-heavy, or
  release-only for direct flat evidence rows.
- an artifact payload matrix for file import/export or AI work packages is too
  large, slow, browser/manual-heavy, or release-only for direct flat evidence.

When DevelopmentProcessFlow classifies a failed or blocked validation as
`test_too_thick`, slow/layered validation, stale/skipped/progress-only
evidence, release-only evidence, or automatic split evidence that is being
hidden inside a parent confidence claim, this protocol owns the handoff. Keep
the broad command as a parent gate or compatibility check, derive child
suites/scripts, record child evidence status, and require parent validation
confidence to consume current child evidence. A later green broad command by
itself does not close a
TestMesh handoff if child evidence remains hidden.

## Partition Checklist

## Target Split Derivation

For the parent test gate, record a target split derivation before green parent
confidence:

- source FlowGuard validation-structure model id;
- target child suite or script ids;
- parent partition items represented by the target validation split;
- state and side-effect owner fields that shaped the split;
- rationale for why these suites/scripts are the target validation structure.

Missing, source-less, target-less, unknown-suite, prose-only, or
coverage-incomplete derivations are blockers. TestMesh still does not run tests;
it derives the target validation layout, then reviews the evidence supplied by
the registered child suites/scripts.

For the parent test gate, list each partition item as a grouped ownership row:

- boundary: behavior, workflow, state, module, command, side effect, invariant,
  replay adapter, release-only obligation, or layered-proof obligation;
- owner: child, parent, read-only, or shared-kernel plus the owning suite when
  child-owned;
- overlap note: duplicate state or side-effect ownership and the explicit
  sharing rationale, if any.

Assign every item one owner: `child`, `parent`, `read_only`, or
`shared_kernel`. A child-owned item must name the owning suite. Duplicate state
or side-effect owners are blockers unless the overlap is explicitly allowed.

## Evidence Checklist

For each child suite or child test script, record grouped evidence:

- identity: suite id, command, layer, and owned leaf matrix cell ids when the
  layer is `leaf_matrix_cell`, `leaf_boundary_matrix`, or `artifact_payload`;
- result summary: status, evidence tier, freshness or stale reason, selected
  and skipped counts, duration, timeout, exit code, and result path;
- visibility caveats: skipped visibility, not-run reason, background log root,
  final exit/result artifact flags, proof artifact, and test-result reuse
  ticket when an old result is reused;
- ownership summary: owned state, side effects, partition items, and release
  scope.
- payload ownership summary when applicable: payload contract ids, required
  case ids, result artifact path, and downstream Model-Test Alignment owner.

For a diagnostic child, also record `diagnostic_boundary` as `targeted`,
`declared_complete`, or `budgeted`; planned, executed, failed, and not-run
counts; campaign id; not-run reason; and stable Finding Ledger ids. Require
`planned = executed + not_run` and `failed <= executed`.
`declared_complete` cannot contain not-run work. Other boundaries may leave a
remainder only with a visible reason. TestMesh reports this evidence; it does
not choose DPF process optimization or group findings into root causes.

Progress output is liveness evidence only. It is not completion evidence.
An old `passed` result is not reusable parent evidence unless
`TestResultReuseTicket` and `ProofArtifactRef` are both current for the command,
test source, tested artifact, dependency, environment, result fingerprint, and
coverage scope.
When a final confidence claim depends on the parent gate, export child evidence
ids, status, freshness, and release-scope gaps to the Risk Evidence Ledger.
Background runs need final exit/result artifacts before a parent gate can treat
them as complete.

A valid background final receipt names the run identity, terminal status/exit
code, result artifact, fingerprint, covered required ids, inventory revision,
and covered artifact and verifier versions. PIDs, heartbeats, logs, and
progress-only/running status are never final evidence.

When `required_leaf_cell_ids` are declared on the parent gate, every required
cell must be owned by a registered child suite/script with current passing
evidence. A leaf matrix-cell suite that does not name its cells is a blocker,
because the parent cannot tell which finite boundary cell was proved.
Transition coverage cells use the same required id surface when they are routed
through TestMesh.
ModelMesh-derived closure cells use that same required id surface after
projection; do not collapse all retry/rejection closure behavior into a single
generic suite result.

## Routine And Release Scope

Use `TEST_SCOPE_ROUTINE` for fast local confidence. Release-only suites may be
deferred only when the report keeps the release obligation visible.

Use `TEST_SCOPE_RELEASE` for publish, tag, deployment, or broad completion
claims. Release-required suites must be current and passed.

## Prompt Template

```text
Build a FlowGuard TestMesh for this repository's validation flow. Treat the
current broad test command or suite as the parent test gate and the extracted
or selected suites/scripts as child validation regions. Do not inline every
child test case into the parent; expose each child through ownership and
evidence contracts.

Use these groups:

- Parent gate: identity and routine/release scope.
- Ownership map: boundary, owner, and overlap note.
- Child suite evidence: identity, result summary, visibility caveats, and
  ownership summary.
- Required cell ids: transition or leaf matrix cells that child suites must own
  with current evidence, plus the model obligation and code contract targets
  that downstream Model-Test Alignment must bind.
- Target split derivation: source model, target suites, coverage, and
  rationale.

Known hazards that must fail:
- missing target split derivation;
- target split derivation not sourced from a FlowGuard model;
- target split derivation omits target suites or partition coverage;
- missing child owner;
- unregistered owner suite;
- flat test split with no parent/child ownership map;
- parent gate expands every child test case instead of consuming child
  contracts;
- duplicate partition or state owner;
- hidden skipped tests;
- stale evidence;
- timeout or failed suite;
- background progress without final exit/result artifacts;
- release-required suite missing under release scope.
- transition coverage required cell id missing child evidence.
- DevelopmentProcessFlow `test_too_thick` handoff treated as an ordinary
  implementation failure without child validation structure.
```

## Completion Standard

A TestMesh review can support the parent only when:

- every partition item is owned;
- the target suite/script layout is derived from a FlowGuard model and covers
  the parent partition items used by the decision;
- every child owner is registered;
- sibling ownership conflicts are absent or explicitly shared;
- parent confidence is based on child contracts rather than expanded child
  internals;
- all required suites have current pass evidence for the requested scope;
- all required transition or leaf matrix cell ids have current passing child
  evidence;
- skipped, not-run, timeout, and stale evidence remain visible;
- background jobs have final completion artifacts;
- DevelopmentProcessFlow `test_too_thick` handoffs have explicit child
  evidence status and parent consumption;
- release-only obligations are either current or explicitly deferred only under
  routine scope.
## Specification-check receipt children

Provider checks are ordinary TestMesh children with extra consumer bindings.
Record the provider session id, all consumer ids, canonical execution state,
immutable receipt id/fingerprint, stable validation-obligation coverage, and
explicit cross-change scope. `executed` and `reused-current` may support a pass
only when the underlying `EvidenceReceipt` is independently current and exact.
`stale`, `not-run`, `blocked`, timeout, running, skipped, or progress-only rows
remain non-passing.

One receipt with several consumers is one execution, not duplicated evidence.
Changing a provider-local obligation does not necessarily change a neutral
execution receipt; consumer bindings attach provider task/check ids afterward.
Never split a broad combined command into unsupported child claims without an
independent node/coverage inventory.
