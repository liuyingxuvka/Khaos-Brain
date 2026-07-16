# Model Topology Hazard Review Protocol

Use this route when a FlowGuard model appears locally green but its shape may
imply future-use risk. Start from topology, not a fixed checklist.

## Trigger

Create or update a review when:

- broad done, release, publish, archive, production, or full-confidence claims
  depend on a model that only proved local paths;
- the topology contains repeatable side effects, shared state writers, external
  confirmation boundaries, broad terminal states, old/new compatibility paths,
  migration/history surfaces, duplicate or conflicting business paths,
  unproven important business paths, or parent/child compression;
- a model pass and ordinary tests pass but an experienced engineer would still
  ask what future real use could expose;
- state-closure, model-test alignment, model maturation, process freshness, or
  risk ledger evidence points to a hidden model-shape hazard.

Do not trigger this route for generic risk brainstorming with no model topology.
Unanchored concerns stay as observations and cannot block confidence.

## Input Checklist

Use grouped rows instead of blank field lists:

- usage intent: local/CLI/library/plugin/service/release/migration, final claim,
  history or compatibility possibility, compatibility policy, and goal;
- topology digest: state nodes, input nodes, block nodes, workflow edges,
  reads/writes, side effects, external boundaries, terminal nodes, old/new
  paths, business path identities, parent/child links, and landmark ids;
- business path identities: stable path id, business intent, trigger,
  preconditions, expected terminal, state writes, side effects, equivalent
  paths, exclusive paths, superseded old paths, compatibility disposition,
  source labels, and evidence ids;
- candidate hazards: anchor ids, rationale from topology shape, future failure
  mode, affected state/edge/side effect/terminal/boundary, disposition,
  required routes, handled/scoped status, and proof ids.

## Review Rules

Every hard hazard must name a concrete topology anchor. Valid anchors include a
state, edge, side-effect edge, terminal/success node, compatibility path,
business path, external boundary, shared writer, or parent/child compression
landmark.

Classify dispositions:

- model patch or maturation when the model is too coarse;
- model-test alignment when a model obligation lacks ordinary test evidence;
- Risk Evidence Ledger when broad user-risk confidence depends on the hazard;
- DevelopmentProcessFlow when local evidence is being overclaimed as release or
  process confidence;
- Architecture Reduction plus ledger when old/new compatibility paths need a
  preserve, migrate, block, delete, or latest-schema-first decision;
- Architecture Reduction plus Model Similarity when two business paths do the
  same useful job;
- Model Maturation plus Model-Test Alignment when business paths conflict or
  lack path-specific evidence;
- scoped out only with a concrete reason.
Anchored hazards that remain scoped or unresolved should become maintenance
obligations so later scans can reopen the owner route when the same model,
entrypoint, or artifact changes.

## Prompt Template

Use `references/templates/topology_hazard_prompt_template.md` only when a fresh
AI review needs scaffolding. Ordinary route use should follow the checklist
above and the public helper APIs.

## Completion Standard

A topology hazard review can support broad confidence only when:

- unanchored hard candidates have been downgraded to observation-only;
- each anchored unresolved hazard has an owner route or is handled/scoped with
  current evidence;
- scoped anchored hazards are exported as maintenance obligations when they can
  affect later work;
- compatibility/history surfaces have an explicit disposition;
- duplicate, conflicting, or unproven business paths have owner routes or
  current evidence;
- repeatable side effects and external boundaries are covered by current
  model-test, process, or risk-ledger evidence when broad usage is possible;
- scoped confidence is carried into the final Risk Evidence Ledger instead of
  being described as a clean pass.
