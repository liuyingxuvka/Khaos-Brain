# Automatic incremental Sleep contract

Sleep is the sole knowledge-decision and canonical LogicGuard model-generation lane. It automatically consumes new observations and Dream model-gap handoffs, settles lifecycle decisions, calibrates current knowledge, and publishes exact models, scoped ModelMeshes, deterministic card projections, and the active index as one generation.

Run `python .agents/skills/local-kb-retrieve/scripts/kb_sleep.py --json` from the repository root after acquiring the `kb-sleep` lane.

Required behavior:

- Start from the last committed watermark and process only the next bounded increment for decision work.
- Admit each observation before classification and commit exactly one current disposition by the end of the successful pass.
- Use stable prediction identity so repeated evidence converges on one candidate.
- Represent every admitted entry as an exact LogicGuard model revision with a root Claim, Context, Method, typed support/challenge nodes, and explicit missing-role gaps. Never invent Evidence, Warrant, Assumption, Rebuttal, or Limitation.
- Keep promotion evidence-gated: one strong episode plus independent current validation, or two independent medium episodes plus independent current validation; duplicated/weak evidence does not count.
- Park unresolved items with executable reopen conditions and reopen only on material qualifying evidence.
- Immediately suspend strong contradicted trusted knowledge and complete its downgrade review.
- Consume typed Dream model-gap handoffs and acknowledge each exactly once.
- Assemble exact revisions into physically separated scoped ModelMeshes. Only qualifying non-AI provenance may ground a canonical relation; co-use, similarity, and legacy links stay unresolved proposals.
- Audit missing context, action, evidence, warrant, assumption, opposition/rebuttal, and boundary conditions; give every gap one stable open disposition, required grounded input, and machine-readable reopen condition.
- Publish models, meshes, readable projections, exact active index, generation manifests, and the pointer atomically with pointer last. Failure restores the prior complete generation.
- Commit the input watermark only after dispositions, lifecycle review, acknowledgements, generation publication, and exact index validation are durable. Failure leaves the prior watermark unchanged.
- Do not ask a human to read candidate or report files or choose ordinary maintenance actions.

Keep the canonical-interface checkpoint: CLI machine JSON, lifecycle fields, automation payloads, and route values remain encoding-stable canonical interfaces; Chinese display belongs in `i18n.zh-CN`, route display labels, and UI view models.

Report the complete Sleep receipt, including exact generation/model/mesh bindings, gap and unresolved-relation counts, rollback status, and index validation. Do not claim closure when any blocker or missing required evidence remains.
