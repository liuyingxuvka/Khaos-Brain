# StructureMesh Protocol

Use StructureMesh when a large script, package, module, command surface, or API
surface is being split into smaller owned children and the risk is structural:
lost public entrypoints, duplicated state, duplicated side effects, dependency
cycles, config drift, or overclaimed behavior parity.

StructureMesh is a parent/child ownership model. It does not refactor code,
parse files, or run tests. Project adapters or agents collect source inventory,
FlowGuard model-derived target structure, dependency, facade, and parity
evidence, then pass that evidence into `review_structure_mesh(...)`.

## Trigger

Create or update a StructureMesh when any of these are true:

- a large script or module is split into two or more child modules;
- a public import path, CLI command, API route, JSON/data shape, or plugin entry
  point is moved;
- state, config, cache, side effects, or external writes are divided across
  children;
- a child module depends on another child and cycles may appear;
- routine refactor confidence and release confidence require different
  evidence.

## Target Structure Derivation

Before reviewing ownership, derive the target child script/module structure
from a FlowGuard functional model. This step is mandatory for existing
large-script or large-module splits. It is not an optional call to another
skill and it does not make StructureMesh a no-code architecture planner.

Record:

- source FlowGuard model id and path;
- target child modules and paths;
- FunctionBlock-to-module ownership;
- state-owner mapping;
- side-effect-owner mapping;
- config-owner mapping when config/defaults matter;
- public entrypoint or facade plan;
- validation boundaries that will prove parity;
- rationale for grouping related blocks and avoiding mechanical one-block-per-file
  over-splitting.

## Partition Checklist

Inventory the parent boundary as `StructurePartitionItem` rows:

- functions and classes;
- state fields, caches, registries, and durable records;
- config keys, defaults, environment variables, and path conventions;
- side effects such as writes, publishes, external calls, logs, migrations, or
  generated artifacts;
- public entrypoints and behavior contracts.

Every partition should have one clear owner:

- `child` for normal extracted child ownership;
- `parent` for retained orchestration or facade responsibilities;
- `read_only` for inspected data that must not be written;
- `shared_kernel` only when duplication is intentional and documented.

## Evidence Checklist

For each `ModuleStructureEvidence`, record:

- child module id, path, layer, and source parent;
- owned functions, state, config, side effects, and behavior contracts;
- dependency list and any dependency cycles;
- whether the compatibility facade remains;
- whether behavior parity evidence is current and which evidence tier supports
  it;
- whether config/default behavior changed;
- whether the module is routine evidence or release-required evidence.

For each `PublicEntrypointEvidence`, record:

- old path and new path;
- entrypoint type such as import, CLI, API route, command, data shape, or plugin;
- whether compatibility is preserved;
- whether a facade or compatibility layer is available;
- whether parity evidence is current;
- whether release scope must block until this entrypoint is green.

## Routine And Release Scope

Use `decision_scope="routine"` for ordinary refactor confidence. Routine scope
may defer release-only modules or entrypoints when
`release_deferred_allowed=True`, but the report must keep the release
obligation visible.

Use `decision_scope="release"` before publishing, tagging, deployment, broad
completion claims, or compatibility claims. Release scope should block when
release-required parity evidence is missing or stale.

## Required Hazards

Before trusting parent refactor confidence, the StructureMesh model must make
these known-bad variants fail:

- missing model-derived target structure;
- target structure not derived from a FlowGuard functional model;
- target structure missing FunctionBlock, state, side-effect, facade, or
  validation mappings;
- missing partition owner;
- unregistered partition owner;
- duplicate partition owner;
- duplicate state owner;
- duplicate side-effect owner;
- duplicate config owner;
- public entrypoint removed;
- compatibility facade missing;
- unsafe dependency cycle;
- config/default drift;
- missing behavior parity;
- stale behavior parity;
- insufficient evidence tier;
- missing release-required parity under release scope.

## Prompt Template

Use this compact prompt when asking an agent to build or review a
StructureMesh:

```text
Build a FlowGuard StructureMesh for this refactor. Treat the original module as
the parent and the extracted files as child modules. First derive the target
child structure from a FlowGuard functional model, including FunctionBlock,
state, side-effect, facade, and validation mappings. Inventory functions,
state, config, side effects, public entrypoints, behavior contracts, dependency
edges, facades, and parity evidence. Do not inline each child implementation.
Review routine scope and release scope separately. The mesh must catch missing
model-derived target structure, missing owners, unregistered owners, duplicate
ownership, removed entrypoints, missing facades, dependency cycles, config
drift, stale parity, and release-only parity gaps before parent refactor
confidence is claimed.
```

## Completion Standard

A StructureMesh is complete when:

- the parent partition map covers the moved or retained structure;
- the target child structure is derived from a named FlowGuard functional model
  and maps model blocks, state, side effects, facades, and validation
  boundaries into structured evidence;
- every owner is registered or explicitly parent/read-only/shared-kernel;
- duplicate state, side-effect, and config ownership is absent or documented as
  allowed shared ownership;
- public entrypoints remain compatibility-preserved through facades;
- dependency cycles are absent or explicitly allowed with evidence;
- config/default changes are either absent or treated as behavior changes;
- routine/release obligations are visible;
- public-entrypoint parity ids and deferred release obligations are available
  to the Risk Evidence Ledger before broader final confidence claims;
- stale facade, public-entrypoint, or parity gaps are exported as maintenance
  obligations so later scans can reopen StructureMesh when related files move;
- known-bad hazards fail in executable evidence.

## Layered Boundary Handoff

When a structure split is motivated by a leaf model being too large for full
boundary-matrix coverage, StructureMesh owns the existing-code split evidence,
but the layered proof stays blocked until the new child modules expose complete
leaf inputs, outputs, state writes, side effects, and error paths. Facade
compatibility proves public shape; it does not prove the leaf
`Input x State -> Set(Output x State)` matrix by itself.
