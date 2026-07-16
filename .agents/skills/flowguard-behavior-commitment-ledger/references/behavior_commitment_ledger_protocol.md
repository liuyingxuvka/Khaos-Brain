# Behavior Commitment Ledger Protocol

Use the ledger as the upstream behavior inventory. Source surfaces are docs,
APIs, commands, UI capabilities, skills, tests, OpenSpec requirements, release
notes, or process docs that promise behavior. Commitments are the external
promises those surfaces make.

The ledger has one structure and three production owner planes:
`product_runtime` for application promises, `agent_operation` for AI/tool-use
promises, and `development_process` for build/test/release lifecycle promises.
`commitment_kind` remains the surface form; `actor_kind` records the structured
actor. Migration-only `unclassified` never passes runtime review.

Use the canonical `ledger.json` as authority and a thin `model.py` loader.
Before non-trivial work, query task terms and any exact commitment, path, tool,
workflow, or error-signature clues. Select same-plane hits as primary. Traverse
only registered typed relations for related-plane context, keep that context
separate from instructions, and preserve the ledger fingerprint. Ambiguous or
stale lookup is visible fallback evidence, not permission to guess.

Each commitment records actor, trigger, expected result, failure boundary,
source refs, one primary owner model, subordinate supporting or child models,
dependencies, evidence ids, validation boundary, and rationale. A scoped-out
row still needs owner, reason, validation boundary, and rationale.

Runtime relationships use typed `relations`, not legacy dependency ids.
Same-plane dependencies/invocations/validations and the allowed agent/process
cross-plane directions must reference registered targets. Every cross-plane
relation needs rationale. Reverse context may be derived during lookup; do not
duplicate inverse rows or merge the two owners.

Identity is the exact external promise, not the surface name. Compare actor,
trigger/preconditions, expected result/terminal, failure boundary, and material
state writes/side effects. Give that promise one stable `business_intent_id`
and one active commitment. Equivalent UI, API, CLI, alias, adapter, wrapper,
helper, and compatibility surfaces map to it and delegate to the selected path;
do not create a second surface/delegate commitment. A distinct intent requires
typed external differences, an owner, validation boundary, rationale, and
current evidence.

For `path_sensitive=true`, attach Primary Path Authority evidence with
`behavior_path_binding_from_primary_path_report()`. The ledger does not run a
second fallback checker. If PPA is blocked, the commitment is blocked.

The canonical binding emits singular `primary_path_id` for the same intent and
commitment. Accept legacy `primary_path_ids` input only when it contains one
distinct non-empty id and does not conflict with a singular value. Never choose
authority by list order; ambiguity blocks broad confidence.

For broad done, release, publish, archive, production, or full confidence,
project the ledger through `behavior_commitment_contract_exhaustion_plan()`.
Pass generated case ids, shard ids, receipt ids, and risk gate ids to
Model-Test Alignment, TestMesh, and Risk Evidence Ledger.
