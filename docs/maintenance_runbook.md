# Automatic Sleep Maintenance Runbook

This runbook defines the repository-managed `KB Sleep` automation. Sleep is an
AI-only lifecycle and model-publication pass: it does not wait for a person to
read files, select cards, approve routine decisions, or operate the desktop
viewer.

`PROJECT_SPEC.md` is the product authority.
`docs/maintenance_agent_worldview.md` defines the shared Sleep/Dream/system
model. `.agents/skills/kb-sleep-maintenance/SKILL.md` and its SkillGuard V2
contract define the executable entry boundary.

## Single native entrypoint

From the repository root, run:

```powershell
python .agents/skills/local-kb-retrieve/scripts/kb_sleep.py --json
```

The native command owns lifecycle writes, candidate decisions, LogicGuard model
and ModelMesh publication, Dream handoff acknowledgements, calibration,
projection/index publication, and the final receipt. An AI
maintenance session may inspect its canonical JSON and repair a failed
supported step, but it must not create a parallel manual maintenance flow.

## Automatic pass

Each successful pass performs one bounded transaction:

1. Acquire the shared Sleep maintenance lane and keep one run identifier.
2. Read the prior committed watermark and the next bounded evidence increment.
3. Admit every new observation before deciding what it means.
4. Give every admitted observation exactly one current disposition.
5. Create or reuse candidates by stable prediction identity; repeated evidence
   converges on the same candidate instead of multiplying cards.
6. Build one exact LogicGuard revision for every admitted entry. The model owns
   the root Claim, Context, Method, typed support/challenge nodes, ArgumentBlock,
   and explicit gaps; it never invents a missing Evidence, Warrant, Assumption,
   Rebuttal, or Limitation.
7. Review every due candidate and end it as `trusted`, `merged`, `superseded`,
   `rejected`, or `parked` with an executable reopen condition.
8. Consume each typed Dream model-gap handoff at most once and record its acknowledgement.
9. Calibrate confidence only from graded, linked outcome evidence.
10. Assemble exact revisions into physically separated public, private, and
    candidate ModelMeshes. Canonical relations require qualifying non-AI
    provenance; similarity, co-use, and legacy links remain unresolved proposals.
11. Audit context, action, evidence, warrant, assumption, opposition/rebuttal,
    and boundary gaps. Give every gap one stable open disposition, concrete
    grounded input need, and machine-readable reopen condition.
12. Publish models, meshes, deterministic card projections, the active index,
    manifests, and the generation pointer as one rollbackable transaction, with
    the pointer last.
13. Commit the new watermark and success receipt only after all preceding state
    and validation writes are durable.

If any required step fails, Sleep keeps the prior watermark, records the exact
blocker, marks the lane failed, and leaves the evidence actionable for retry.
A failed pass never reports partial progress as completion.

## Decision standard

Sleep optimizes predictive usefulness and model support quality, not card count.

- A useful experience states a bounded situation, chosen action, expected
  result, and stop boundary as a claim model. Evidence and warrant strengthen
  it; if they are absent, the model keeps visible gaps rather than inventing them.
- History-only is correct for non-reusable evidence.
- Parking is correct when evidence is insufficient but a named future signal
  could change the decision.
- No-card is correct when no eligible experience should influence retrieval.
- Duplicate observations support an existing prediction identity; they do not
  justify duplicate candidates.

Promotion requires independent current validation plus either one strong
support episode or two independent medium episodes. Weak evidence, AI
self-report, duplicated evidence, or simulated success cannot promote a model.
One unresolved strong contradiction immediately suspends retrieval and forces
a downgrade decision in the same successful Sleep pass.

## Active retrieval boundary

The active index contains only current trusted entries and explicitly eligible
candidates. It excludes `merged`, `rejected`, `superseded`, `parked`,
`retired`, `deprecated`, `history_only`, provenance-incomplete, and strongly
contradicted entries.

Foreground queries validate the compact activation receipt plus only indexed
exact model/projection bindings. They do not scan all inactive cards or replay lifecycle history.
Observation-only intake leaves entry authority current. Every entry transition
durably invalidates before event commit; a full validated rebuild is the only
way to clear that marker. Missing or changed indexed source files also fail the
compact check and return an explicit unavailable result. Retrieval does not
switch to another reader or treat readable YAML as semantic authority.

A lexical hit is only the entry point. Retrieval reads the exact bound model,
root ArgumentBlock, typed nodes and edges, explicit gaps, and the grounded mesh
neighborhood. It never expands retired `related_cards`; only current canonical
ModelMesh edges may widen the context.

Read-only organization candidates may be visible to an organization-source
search as clearly labeled untrusted input. Visibility does not put them in the
local active index. An adopted local identity must pass the same local evidence
gate as any other candidate.

## Sleep and Dream boundary

Sleep alone may change knowledge lifecycle or canonical LogicGuard state. Dream
may write only bounded simulation artifacts and one typed model-gap handoff per
evidence fingerprint. Sleep validates that handoff, chooses the disposition,
acknowledges it once, and publishes any resulting model generation. Unchanged
Dream evidence is a no-op, and Dream must prove the pinned generation unchanged.

## Canonical and display boundary

Lifecycle fields, route values, CLI JSON, installer checks, and automation
payloads remain canonical, encoding-stable machine interfaces. Chinese display
text belongs in `i18n.zh-CN`, route display labels, and UI view models. Missing
display text may be repaired automatically, but display work must not rename
canonical routes or fields.

The desktop card browser and readable YAML/Markdown are deterministic optional
observability projections. They do not grant authority and are never required
for closure.

## Safety and recovery

- Sleep never edits product code, installer logic, Skills, automation specs, or
  system architecture. A reusable mechanism issue becomes a structured
  development observation owned by a later explicit software task.
- Sleep does not run concurrently with Dream or another local maintenance
  writer.
- Every state-changing operation is idempotent or carries a rollback reference.
- Every parked item has a machine-evaluable reopen condition and decision due
  boundary.
- Every skipped, failed, stale, missing, or running hard check remains visible
  and blocks a success claim.
- Architect is retired. Sleep never recreates its queue, Skill, automation,
  prompt, route, or handoff.

## Required receipt

The final machine receipt must include:

- run id, policy/schema versions, input range, watermark, and input digest;
- opening, admitted, disposed, terminal, parked, and closing backlog counts;
- candidate create/reuse, promotion, merge, rejection, parking, reopen, and
  downgrade decisions with evidence ids;
- Dream handoffs consumed and acknowledged;
- calibration changes and contradiction decisions;
- exact LogicGuard generation, model and mesh counts, gap counts, unresolved
  relation proposals, projection manifest, and rollback status;
- active-index generation, digest, exact bindings, eligible/excluded counts, and validation;
- failed, skipped, stale, or missing checks and exact blockers;
- committed or failed lane state.

The automation reports success only when this receipt is complete and all hard
checks pass. No human-readable review artifact substitutes for the receipt.
