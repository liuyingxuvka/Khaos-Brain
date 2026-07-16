# ContractExhaustionMesh Protocol

Use ContractExhaustionMesh for the narrow middle step between declaration and
evidence:

```text
declared finite boundary
-> coverage universe for broad/full claims
-> optional model-scoped axes and interaction groups
-> ContractMutationCase / ContractCombinationCase ids
-> oracle reactions, actionable feedback, fault profiles, and coverage receipts
-> observed-problem backfeed for real misses
-> composite handoff acceptance
-> MTA/TestMesh/ModelMesh/Risk Evidence Ledger handoff
```

It is not a global bug oracle. It exhausts the boundary the model has actually
declared. Missing declarations are model gaps. Cartesian generation is
per-model: the route combines declared axes inside one model boundary or a
declared parent-interface group, not every field in the repository.
For broad/full claims, missing universe declarations are also model gaps: the
route must name the finite universe it claims to cover before the generated
matrix can be treated as complete.

## Feeders

- StateClosure: use `state_closure_cases_to_contract_cases(...)` for unknown,
  malformed, old-schema, terminal replay, and missing-required-field cases.
- ScenarioMatrix: use `scenario_matrix_to_contract_cases(...)` for repeated,
  ABA, stale-state, partial-failure, delayed, and terminal-replay challenge
  scenarios.
- ObligationFamily/ModelMissReview: use
  `family_bad_case_seed_to_contract_cases(...)` after the observed bug class is
  abstracted into a family seed.
- ArtifactPayload: use `artifact_payload_cases_to_contract_cases(...)` for
  missing body, malformed payload, conflicting payload, stale evidence, and
  wrong-path evidence claims.
- TransitionCoverage: use `transition_coverage_to_contract_cases(...)` when
  transition cells are proof targets.
- ModelMesh: use `model_mesh_closure_to_contract_cases(...)` for stale child
  evidence, unconsumed child output, and repeat-without-delta loops.
- Behavior authority: use owner-declared stable intent/commitment/selected-path
  axes for missing identity, same-intent wrong path, parallel success after
  primary failure, and stale proof.
- ObligationFamily/ArchitectureReduction completeness: use independently
  expected member/candidate ids for omission cases; never infer completeness
  from the materialized subset.
- Similarity: materialize in-scope relation/test/code obligation ids into
  concrete member, candidate, obligation, or case targets; opaque ids fail.
- UI product language: generate illegal fourth visibility class, internal
  content leak, semantic drift, authority-changing exception, and valid
  presentation-only exception cases.
- Facades: prove retained delegation reaches the selected primary path and
  reject independent business success.

## Review

Create `ContractExhaustionPlan` with:

- `dimensions`: route-declared finite boundaries;
- `seed_cases`: feeder-projected cases;
- `oracles`: named reactions when the case cannot rely on the default;
- `model_id`, `parent_model_id`, and `model_level` when the coverage claim is
  model-scoped;
- `axes`: finite model-local values or dimension-derived mutations;
- `interaction_groups`: the axis sets that should be combined by Cartesian
  product;
- `coverage_universe`: dimensions, axes, groups, payload contracts, boundaries,
  case ids, receipts, and scoped exclusions claimed by this run;
- `required_child_receipt_ids` and `consumed_child_receipt_ids` when a parent
  model coverage run must consume child coverage;
- `require_actionable_oracle_feedback`: true when reject/block/reissue/repair
  cases must prove the receiver gets repairable feedback fields;
- `observed_problem_backfeed`: real misses that must map back to generated
  cases, same-class cases, and coverage receipts;
- `claim_scope`: routine, done, release, publish, production, or full;
- `required_route_ids`: routes that must receive at least one case.

Run `review_contract_exhaustion(plan)`.

Blockers mean a required bad case lacks a declared reaction or a broad claim is
trying to treat an unbounded dimension as exhaustive. Scoped findings mean the
route can continue only with a narrower claim.

For combination coverage, blockers also include missing model ids, unknown
axes, unknown dimensions, exceeded Cartesian limits, incomplete shards, stale
coverage receipts, or parent receipts that do not consume required child
coverage receipt ids. A generated combination id is only a candidate proof
target until TestMesh, Model-Test Alignment, ModelMesh, and Risk Evidence
Ledger consume the corresponding case, shard, receipt, and composite handoff
ids.

For universe coverage, blockers include a broad/full claim with no
`ContractCoverageUniverse`, a universe item that is not present in generated
coverage, an incomplete scoped exclusion, or an observed real miss that cannot
be mapped to generated cases, same-class cases, and a current coverage receipt.
For actionable feedback, reject/block/reissue/repair cases need a
`ContractOracle` with `expected_message_fields` and `required_repair_fields`.
`ContractFaultProfile` rows can then be used by downstream synthetic
contract-submitter rehearsals, but they remain synthetic-only evidence.

Matrix readiness is not full chain readiness. `composite_handoff_acceptances`
and `contract_exhaustion_to_composite_handoff_acceptance_ids(...)` are separate
acceptance items for cases that must be consumed by more than one route. A
single case/oracle pass cannot be cited as whole-model-chain confidence until
the named route owners close the same acceptance id.

## Consumers

- Model-Test Alignment consumes `contract_exhaustion_to_model_obligations(...)`;
  each generated combination obligation needs current test evidence that cites
  the obligation id.
- TestMesh consumes `contract_exhaustion_to_test_mesh_cell_ids(...)` for case
  ids and `contract_exhaustion_to_test_mesh_shard_ids(...)` for shard evidence.
- Risk Evidence Ledger consumes `contract_exhaustion_to_risk_gate_ids(...)` or
  route-owned gates that cite generated case, shard, receipt, or
  parent-consumed-child coverage ids.
- ModelMesh consumes `contract_exhaustion_to_coverage_receipt_ids(...)` and
  parent receipts whose `consumed_child_receipt_ids` close every required child
  receipt.
- DevelopmentProcessFlow and Risk Evidence Ledger can consume
  `contract_exhaustion_to_composite_handoff_acceptance_ids(...)` as the broad
  claim gate that proves the same case id crossed the required route chain.
- ModelMesh remains the owner of parent/child reattachment and closure evidence
  when generated cases came from closure hazards.

## Cleanup Rule

Old same-class generators, analogous-bug prompt paths, compatibility-like
fallbacks, and hand-written case lists are not canonical coverage. Keep them
only when they are the current declaration owner, current evidence consumer,
explicit public facade, negative legacy test, or archive-only record. Otherwise
delete or rewrite them to feed ContractExhaustionMesh.
