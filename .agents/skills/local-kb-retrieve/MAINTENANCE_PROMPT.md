# Automatic incremental Sleep contract

Sleep is the sole knowledge-decision and canonical LogicGuard model-generation lane. It freezes one finite batch, resumes that exact batch before later arrivals, durably checkpoints settled items, calibrates current knowledge, and publishes exact models, scoped ModelMeshes, deterministic card projections, and the active index only as one complete generation.

Run `python .agents/skills/local-kb-retrieve/scripts/kb_sleep.py --json` from the repository root after acquiring the `kb-sleep` lane.

Required behavior:

- Resume the exact open `batch_plan` before admitting later work. Otherwise freeze one finite ordered batch with immutable item identities, input watermark and digest, current-generation identity, prior convergence streak, and a target within tested bounds. Require `batch_head` to bind the exact plan and checkpoint digests. Later arrivals wait for a later batch.
- Give each settled frozen item either one verified completed disposition or one explicit blocked disposition with a named owner and executable reopen condition. Persist its digest-bound result and `batch_checkpoint`; never repeat verified work merely because the prior overall attempt stopped.
- Use stable prediction identity so repeated evidence converges on one candidate.
- Represent every admitted entry as an exact LogicGuard model revision with a root Claim, Context, Method, typed support/challenge nodes, and explicit missing-role gaps. Never invent Evidence, Warrant, Assumption, Rebuttal, or Limitation.
- Keep promotion evidence-gated: one strong episode plus independent current validation, or two independent medium episodes plus independent current validation; duplicated/weak evidence does not count.
- Park unresolved items with executable reopen conditions and reopen only on material qualifying evidence.
- Immediately suspend strong contradicted trusted knowledge and complete its downgrade review.
- Consume typed Dream model-gap handoffs and acknowledge each exactly once.
- Assemble exact revisions into physically separated scoped ModelMeshes. Only qualifying non-AI provenance may ground a canonical relation; co-use, similarity, and legacy links stay unresolved proposals.
- Audit missing context, action, evidence, warrant, assumption, opposition/rebuttal, and boundary conditions; give every gap one stable open disposition, required grounded input, and machine-readable reopen condition.
- Stage models, meshes, readable projections, the exact active index, and generation manifests away from the current generation. Validate them completely and atomically switch the generation pointer last. Planning, `progress_saved`, timeout, and pre-activation failure leave the prior validated generation readable.
- Stop starting new items at the native soft deadline, atomically save progress, release the lane, and return `progress_saved` before the outer hard timeout. `progress_saved` never means generation completion, watermark advancement, or handoff acknowledgement.
- Commit the input watermark only after every frozen item is settled and lifecycle review, acknowledgements, generation publication, exact index validation, and the final pointer switch are durable. `progress_saved` and failure leave the prior committed watermark unchanged.
- Report `previous_remaining`, `newly_eligible`, `opening_remaining`, `target_batch_size`, `completed_this_attempt`, `blocked_this_attempt`, `closing_remaining`, `net_reduction`, and `convergence_status` under one counting rule. Later arrivals must not change the frozen batch.
- For `progress_saved`, failure, an open batch, or `backlog_growing`, record Dream and organization descendants in `downstream_stages` as `not_run`; do not launch them, invoke a second Sleep child, or run a status-helper retry.
- A malformed frozen item may settle as blocked only with a named owner and executable reopen condition. Publish settled siblings as `completed_with_blocks`, retain the blocked item for governed reopening, and record all three descendants as `not_run` with reason `sleep-completed-with-blocks`.
- Do not ask a human to read candidate or report files or choose ordinary maintenance actions.

Keep the canonical-interface checkpoint: CLI machine JSON, lifecycle fields, automation payloads, and route values remain encoding-stable canonical interfaces; Chinese display belongs in `i18n.zh-CN`, route display labels, and UI view models.

Report the complete Sleep receipt, including `batch_head`, `batch_plan`, `batch_checkpoint`, the canonical remainder counts, exact generation/model/mesh bindings, gap and unresolved-relation counts, `downstream_stages`, and index validation. A valid `progress_saved` receipt closes only this bounded attempt and keeps the batch open; do not claim generation completion when any item, blocker, or required evidence remains.
