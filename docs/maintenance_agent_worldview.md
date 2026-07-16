# Automatic Maintenance Worldview

This document gives Sleep, Dream, system update, and organization maintenance
one shared operating model. The core lifecycle is AI-only: no human-readable
file review, desktop interaction, or human review queue is required for a run to
make or verify a decision.

## Shared Goal

Khaos Brain is a predictive experience library for future AI work. It is not a
diary, transcript archive, generic note pile, or place to keep every idea. Its
active surface should answer:

- When this situation appears, what action should the agent choose?
- What result should it predict?
- Which evidence and warrant support that prediction, and how independent are they?
- Which assumptions, rebuttals, limitations, contradiction, or no-model condition should stop reuse?

Better means more accurate, timely, retrieval-safe, evidence-backed, and
convergent. It does not mean more cards or more maintenance activity.

## Automatic Roles

Sleep is the lifecycle owner and the sole canonical LogicGuard generation publisher.

- It incrementally admits and disposes every observation.
- It alone creates candidates and decides trusted, merged, superseded,
  rejected, parked, reopened, or downgraded outcomes.
- It calibrates confidence from verified outcomes and user corrections.
- It represents each admitted entry as an exact LogicGuard argument model, preserving absent evidence, warrant, assumptions, rebuttals, and boundaries as explicit gaps with stable open dispositions, grounded-input needs, and reopen conditions.
- It assembles exact revisions into scoped ModelMeshes; similarity or co-use remains an unresolved proposal unless qualifying non-AI provenance grounds the relation.
- It acknowledges Dream model-gap handoffs and atomically publishes models, meshes, deterministic card projections, the active index, manifests, and the generation pointer.
- A failed pass never advances its watermark or hides actionable backlog.

Dream is the immutable model-verification researcher.

- It pins exact LogicGuard generation, model, ArgumentBlock, and mesh revisions, then explores grounded bounded hypotheses using read-only simulations or sandbox checks.
- It pressures evidence removal, assumption removal, rebuttal/counterexample strengthening, and declared boundaries without committing a model revision.
- It closes unchanged evidence by stable fingerprint instead of repeating work.
- It writes experiment artifacts and at most one typed Sleep handoff per
  fingerprint.
- It never creates or edits models, meshes, card projections, candidates,
  ordinary observations, or the central history/lifecycle ledger.

System update is a narrow software-maintenance lane.

- It checks the canonical software-update state and invokes the recovery-
  oriented update workflow only when authorized.
- It does not review architecture, invent mechanism proposals, edit cards, or
  replace explicit development work.
- The former Architect Skill and automation are retired and removed on every
  supported upgrade.

Organization maintenance is an exchange-layer Sleep.

- The organization KB is a shared exchange surface, not central truth.
- It may repair, merge, split, promote, demote, reject, deprecate, or replace
  shared candidates and cards under the same evidence discipline.
- Privacy, credentials, machine identifiers, local absolute paths, private
  preferences, and unsafe or unpinned Skill bundles never cross the boundary.
- Local machines retain the final adoption and retrieval decision.

## Evidence Strength

- Strong: user correction, verified current test or validation, or another
  directly observable outcome.
- Medium: independent bounded sandbox evidence or distinct real episodes that
  support the same scoped prediction.
- Weak: AI self-report, one-off inference, or simulation without external
  confirmation.

One strong support item plus independent current validation, or two independent
medium supports plus independent current validation, may support promotion.
Weak evidence alone never does. One unresolved strong contradiction immediately
suspends retrieval and requires a Sleep downgrade decision.

## Machine Closure Loop

Every automatic pass must produce canonical, encoding-stable receipts that a
later gate can replay. Completion requires:

- declared input fingerprint and policy/schema version;
- explicit dispositions and remaining actionable backlog;
- current validation results, including failures and skipped checks;
- idempotency, rollback, and interruption-recovery evidence where state changes;
- exact source/stage/install parity for managed Skills and automations;
- no required gate that is failed, stale, skipped, running, or missing.

The desktop viewer and readable YAML/Markdown remain optional observability
surfaces. They are deterministic projections, do not grant authority, and
cannot turn incomplete machine evidence green.

## Sandbox and Upgrade Closure

Every sandbox experiment or upgrade trial records hypothesis, allowed writes,
disallowed writes, validation, observed result, evidence grade, rollback, and
the exact Sleep or system handoff. A result reaches live maintenance only when
it is bounded, reversible, validated, and owned by the correct lane.

Upgrade migration additionally inventories bytes and files, settles logical
debt, archives cold evidence by hash, prunes only receipt-covered derivations,
converts legacy cards directly to exact LogicGuard models and scoped meshes,
removes retired semantic authority, rebuilds deterministic projections and the
exact active index, publishes the generation pointer last, removes exact
retired Architect surfaces, preserves surviving pause states, and commits only
after the aggregate current-evidence gate passes.
