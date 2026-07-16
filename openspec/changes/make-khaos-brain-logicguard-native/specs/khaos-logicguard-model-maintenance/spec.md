## ADDED Requirements

### Requirement: Sleep is the sole canonical model maintenance owner
The existing Sleep entrypoint SHALL remain the only Khaos Brain maintenance route allowed to create or revise card LogicModels, ModelMesh revisions, card projections, and the resulting active-index generation. LogicGuard supplies model semantics and stores but MUST NOT become a second scheduler or lifecycle decision owner.

#### Scenario: Sleep processes a selected lifecycle delta
- **WHEN** the lifecycle owner supplies a bounded selected delta and the maintenance lane is acquired
- **THEN** Sleep SHALL produce a model change plan, commit it model-first, publish verified projections/index, and advance its watermark only after the complete generation validates

#### Scenario: Another route attempts a canonical write
- **WHEN** Dream, retrieval, UI, organization visibility, or an unowned helper attempts to commit model/mesh authority or publish projections
- **THEN** the operation SHALL be rejected and SHALL NOT advance lifecycle, mesh, projection, index, or watermark state

### Requirement: Sleep consolidates small models through ModelMesh
Sleep SHALL organize exact card-model revisions into larger logical structures by revision-pinned registry entries, memberships, and provenance-qualified cross-model edges. It SHALL preserve child model identities rather than copy nodes into one giant model.

#### Scenario: Two cards form a grounded higher-order model
- **WHEN** two exact card nodes have an evidence-backed support, contradiction, refinement, dependency, or shared-model relation
- **THEN** Sleep SHALL add the exact qualified nodes to a ModelMesh revision through memberships and/or a typed cross-model edge with admissible provenance

#### Scenario: AI suggests an ungrounded relationship
- **WHEN** an AI inference or legacy `related_cards` value proposes a relationship without admissible non-AI-only provenance
- **THEN** Sleep SHALL retain it as a gap or candidate for evidence and SHALL NOT commit it as a canonical cross-model edge

### Requirement: Sleep evaluates model completeness before strengthening knowledge
For every affected important claim, Sleep SHALL inspect missing evidence, warrant, assumption, opposition, boundary, scope, duplicate-support, and stale-revision diagnostics and SHALL record a bounded disposition before promotion or confidence strengthening.

#### Scenario: Important claim lacks a warrant and counterexample coverage
- **WHEN** an affected claim is otherwise retrievable but LogicGuard diagnostics expose missing warrant and opposition roles
- **THEN** Sleep SHALL keep those gaps visible, avoid broad promotion, and record the next evidence or Dream-validation action

#### Scenario: No material model change
- **WHEN** the selected evidence fingerprint, exact model revisions, diagnostics, and decisions equal a prior closed Sleep input
- **THEN** Sleep SHALL emit an idempotent no-delta receipt without new model, mesh, projection, index, or history writes

### Requirement: Dream validates one exact mesh revision without mutation authority
Dream SHALL pin an exact mesh revision and may run bounded evidence removal, rebuttal activation, edge removal, model-pin replacement, missing-role, or fragility experiments. Dream MUST write only experiment artifacts, simulation receipts, and typed idempotent Sleep handoffs.

#### Scenario: Counterexample weakens an important claim
- **WHEN** a bounded simulation on the pinned mesh shows that removing one evidence contribution or activating a rebuttal materially changes an important claim
- **THEN** Dream SHALL record the exact perturbation and result and emit one typed handoff for Sleep to review

#### Scenario: Dream attempts direct improvement
- **WHEN** an experiment indicates a missing evidence node, warrant, edge, or boundary
- **THEN** Dream SHALL NOT add or edit canonical authority or YAML and SHALL route the evidence and proposed action only through the Sleep handoff contract

### Requirement: Dream work is convergent and evidence-fingerprinted
Dream SHALL derive a stable fingerprint from the exact mesh revision, selected roots, perturbation plan, evidence inputs, and relevant toolchain identity. An already closed identical fingerprint MUST NOT rerun or write duplicate evidence.

#### Scenario: Identical dream input repeats
- **WHEN** the exact mesh revision and all decision-relevant experiment inputs match a prior terminal closure
- **THEN** Dream SHALL return no-delta and SHALL NOT write a new experiment, simulation receipt, handoff, or history row

#### Scenario: Model evidence changes
- **WHEN** a bound model/mesh revision or decision-relevant evidence changes
- **THEN** Dream MAY reopen the opportunity under a new fingerprint while preserving the prior immutable closure
