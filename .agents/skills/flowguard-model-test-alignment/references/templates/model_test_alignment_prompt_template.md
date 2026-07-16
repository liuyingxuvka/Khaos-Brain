# Model-Test Alignment Prompt Template

```text
Build a FlowGuard Model-Test Alignment review for this repository.

Treat the FlowGuard model as the obligation source, owner code contracts as the
implementation binding, and ordinary tests as evidence. Include owner code
external contracts as plain alignment rows between the model obligations and
tests. Keep test/code/model partition ownership with TestMesh, StructureMesh,
and ModelMesh. When evidence hierarchy is large, slow, layered, backgrounded,
stale-prone, or release-only, issue a typed TestMesh handoff with target ids;
TestMesh executes its own route while this review retains semantic alignment
ownership. Do not split tests, code, or models here or read mesh internals.
If the coverage claim includes state transitions, first derive a transition
coverage matrix and project its required cells into Model-Test Alignment
obligations and code contracts. For large or slow transition matrices, keep the
semantic obligations here and route child evidence ownership to TestMesh.
List each model obligation, owner code contract, and current test evidence
using grouped fields.

Use these groups:

- Model obligations: identity, required evidence, external boundary, and risk
  notes.
- Transition coverage matrix when in scope: cell id, source state, trigger,
  target state, expected output, owner code contract id, runtime node id,
  required test kinds, and scoped-out cells with reasons.
- Code external contracts: identity, obligation binding, external boundary, and
  source-audit status.
- Closed code boundaries or leaf matrices when in scope: boundary identity,
  allowed/rejected cases or matrix cells, observed result/evidence, and scoped
  gaps.
- State closure when finite inputs may be incomplete: representative unknown,
  malformed, missing, old-schema, or external-unknown cases and safe handling.
- Topology hazard obligations when a Model Topology Hazard Review promoted an
  anchored future-use hazard to model/test evidence.
- Test evidence: identity, result/freshness, obligation or contract binding,
  assertion scope, and risk notes. A row that proves a model obligation must
  cover a code contract implementing that same obligation.

If real Python source or tests are available, first perform a conservative AST
audit of code contracts and test assertions. Use it to generate or check the
CodeContract and TestEvidence rows, but do not treat it as a perfect semantic
proof or a conformance replay substitute. For real-code claims that name paths
and symbols, attach the audit report to `ModelTestAlignmentPlan` and set
`require_source_audit=True`.

For non-trivial bug repairs and post-runtime model-miss repairs, mark
observed-regression and same-class generalized evidence separately, and bind
both to the owner code contract for the repaired behavior. Do not let the
observed regression substitute for same-class closure evidence.
If a concrete counterexample or known-bad proof is in scope, add a
`ClosureEvidenceTarget` and require `counterexample_regression` or
`known_bad_replay` test evidence with the same `evidence_target_id`.

Return the final `ModelCodeTestBindingRow` closure summaries: owner code
contract ids, code paths, code symbols, test ids, boundary/runtime/payload ids,
source-audit decision, and open gap codes.

Flag missing model-obligation coverage, missing or mismatched code external
contracts, missing state-closure cases, unsafe unknown handling, boundary
observations that accept forbidden inputs or emit undeclared behavior, missing
external-contract test evidence, orphan tests,
orphan code contracts, unknown references, duplicate same-kind test claims,
duplicate code contract owners, internal-path-only tests, model-code-test
binding mismatches, happy-path-only coverage for risky obligations, stale or
non-passing evidence, partial source-audit support, dynamic or ambiguous
source-audit findings, manual-review-required findings, and overclaimed model
confidence. Flag transition-cell evidence that omits or mismatches the target
cell id.
```
