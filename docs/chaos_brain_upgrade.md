# Chaos Brain Upgrade Contract

Every fresh installation and upgrade uses the same automatic contract. It is
designed for AI execution and does not require a person to inspect files or
approve lifecycle decisions.

## One current system, no compatibility runtime

Chaos Brain has zero normal-runtime compatibility and zero normal-runtime
fallback. Retrieval, organization data, automation policy, installed Skills,
update state, command grammar, and UI launch each have one declared current
authority. A missing or invalid current authority is a visible failure; daily
software must not read an old shape, probe alternate paths, reinterpret an old
argument, insert a backup model, or silently switch launchers.

Old managed material is accepted only as input to the versioned AI-run upgrade.
That upgrade inventories the exact old surface, snapshots it for transaction
rollback, rewrites every valid legacy card directly into exact LogicGuard model
revisions and scoped ModelMeshes, generates deterministic readable projections
and the exact active index, publishes the generation pointer last, removes the
old semantic/readable/executable authority, and publishes a residual-zero
receipt. A repeated upgrade verifies the current form
and performs no compatibility work. An unknown format, collision, incomplete
rewrite, or nonzero residual rolls the affected transaction back and keeps all
five retained automations paused. It never causes a compatibility layer or
fallback branch to be added to the product.

Rollback is a safe checkpoint, not the finished response to an incompatible
residual. The upgrade AI must keep that residual on the same upgrade task,
inspect the captured old/current evidence, create or select one bounded
direct-to-current disposition, rerun the transaction, and continue until the
residual count is zero. It may pause only while a safe decision genuinely lacks
evidence; that paused state is explicitly incomplete and cannot activate any
automation.

For a valid pulled public projection whose stable generation differs from an
otherwise complete old-machine authority, the migration emits an exact
`upgrade-ai-*` work item and changes no authority. After checking its card path,
projection digest, scope, old/new generation ids, and binding, the AI may run
`python scripts/resolve_kb_upgrade_ai_work_item.py --work-item-id <id> --actor <AI> --rationale <reason> --json`.
The resolver records only the evidence-bound
`direct-current-projection-to-logicguard-model` decision. It cannot write cards,
models, meshes, indexes, or pointers. The installer retry rebuilds that one
projection, reuses every other exact local model, and publishes one new current
generation. A changed digest or malformed decision creates no alternate route
and remains blocked.

For organization knowledge this rule covers every consumer, not only the
connection screen: ordinary reads, contribution deduplication, card adoption,
scheduled maintenance, and the installed GitHub checker all accept only the
exact `kb/main` plus `kb/imports` layout. Any `kb/trusted` or `kb/candidates`
residual blocks normal use until the upgrade AI completes the direct migration.

This includes less visible formats as well as obvious files: old
`maintainer_*` desktop-setting keys become the one
`organization_maintenance_*` schema, and the retired Skill-guidance aliases
become the one `unavailable_skill_guidance` card field. The settings reader, UI,
organization contribution code, and scheduled tasks do not translate these
forms during normal operation.

When an exact old field and its current replacement disagree, the migrator
stops before mutation. The upgrade AI may resolve that one conflict only by
selecting a value present in the captured old/current inputs and recording the
reason, both source values, the selected value, and before/after hashes in the
migration receipt. This is an upgrade decision, not a software compatibility
rule; daily operation still accepts only the completed current document.

## What the upgrade changes

- installs the global predictive-KB defaults;
- installs the five current repository Skills;
- installs Sleep, Dream, system update, organization contribution, and
  organization maintenance automations;
- removes only the exact retired `kb-architect-pass` Skill and `kb-architect`
  automation, including old machines with incomplete manifests;
- settles historical observations, candidates, and the retired proposal queue;
- archives retention-required evidence by content hash;
- prunes only declared regenerable caches, sandboxes, snapshots, and completed
  maintenance workspaces covered by a current receipt;
- builds physically separated public/private/candidate LogicGuard models and meshes;
- validates deterministic card projections and exact projection bindings;
- rebuilds the exact active retrieval index and publishes the generation pointer last.

## Transaction and failure behavior

Before activation, the installer stages complete trees, validates the current
SkillGuard contracts with the exact compiler and target-owned generator inputs,
compares source and staged manifests, checks for concurrent source drift, and
creates rollback copies. An interruption is recovered before the next install
starts.

The five exact managed Skill paths use currentness-bound whole-tree replacement.
The incoming tree must pass the current compiler, target-owned generator and
depth calibration, complete manifest, and source/stage digest checks. A currently
confirmed installed tree receives semantic hard-authority comparison. Any absent
or non-current old managed tree is opaque: it is backed up byte-for-byte, never
parsed or converted, and then replaced as a whole. The attempt journal stores
the validation and disposition bindings and replay recomputes them. A missing,
partial, stale, or tampered incoming binding blocks before activation and leaves
the old installation plus all five paused tasks intact.

Each upgrade attempt has its own durable checkpoint journal; it is not confused
with the last-known-good install manifest. The router is refreshed once before
aggregate assurance and again after the final managed Skill-tree write. Final
success requires the official current registry and managed-prompt checks to
match the live SkillGuard/global-router fingerprints. A later failure preserves
the prior successful manifest, records the exact retry point, and leaves all five
tasks `PAUSED` even when the file transaction had already committed.

For a current-to-current SkillGuard upgrade, anti-downgrade is semantic rather
than topology-based. The installer projects checks onto the obligations,
evidence classes, and mandatory owners they prove. Checks may be renamed, merged, split, or removed
only when the incoming projection still covers everything the active projection
covered. A conditional scheduled-production depth wrapper may move to its
unchanged independent hard owner only when the obligation and every active
closure profile still require that owner, and the transaction records the exact
reorganization. Losing any obligation, evidence class, or owner blocks the
transaction; losing only an obsolete check name, route, or redundant depth
membership does not. This is current-contract comparison, not a
legacy compatibility or fallback path.

The history-migration lock also survives crashes safely. Current holders write
a versioned owner token, process id, and heartbeat. A live owner or a recent
ownerless old lock is never stolen. A dead recorded owner, or an old ownerless
legacy lock with no matching migration process, is atomically quarantined,
recorded in `lock-recovery.jsonl`, and reacquired before checkpoint resume. No
manual lock deletion is part of the supported upgrade path.

The history migration follows:

`preflight -> snapshot -> classify -> canonicalize-runtime -> settle-logical-debt -> archive-cold-evidence -> prune-derived-data -> build-logicguard-authority -> publish-projections -> rebuild-index -> publish-pointer -> validate-zero-residual -> committed`

Historical observation and entry settlement is compiled into bounded atomic
lifecycle batches. Each batch replays the authoritative log once before and
once after publication, records created and reused event counts, and resumes
older partial per-item attempts by stable idempotency keys. A large old history
must therefore prove forward progress without weakening durability.

If Sleep was interrupted after lifecycle decisions were written but before its
watermark was committed, the next pass does not repeat those decisions. It
walks past already-terminal history, advances the watermark, and batches only
genuinely pending observations. A fresh maintenance lock whose recorded PID is
no longer alive is recovered immediately; a live owner is never displaced.
Candidate review likewise builds one shared calibration evidence index per
Sleep cycle instead of rereading full outcome and lifecycle files per entry.

Long validation commands use nested timeout budgets with cleanup margin. A
timed-out owner must terminate and confirm zero remaining descendants before
its evidence can be closed or another owner can start.

SkillGuard supervision treats a run label as display text, never as execution
authority. Only the exact repository Skill root may select source supervision,
and only the exact active Codex `skills/<skill-id>` root may select installed
supervision. Unknown or ambiguous roots stop the run. This keeps scheduled
labels from misrouting installed work and prevents the inverse source
substitution without adding a compatibility or fallback route.

Maintenance standard v3 also closes late physical drift. The final validation
scans managed files after long archive checks; if an old cache or workspace is
reintroduced during validation or after commit, the gate reopens and a stable,
resumable reconciliation pass inventories, archives, prunes, and receipts that
delta before installation or automation restoration may continue.
On Windows, the same boundary uses extended-length file operations, so deeply
nested legacy workspaces cannot disappear from inventory merely because their
absolute paths exceed the old Win32 limit.
Concurrent AI work may also admit new observations while the upgrade is long-
running. Those observations reopen the gate and are settled through bounded,
receipt-backed logical reconciliation passes before installation continues.

Routine retrieval uses a compact fail-closed authority receipt and rechecks
only exact model/projection bindings that could be returned. It then reads the
pinned root ArgumentBlock, explicit gaps, and bounded grounded ModelMesh
neighborhood. Projection YAML, legacy `related_cards`, and floating heads are
not fallback readers. Observation-only intake does not force a full replay.
Entry-state transitions invalidate before mutation, and only a full
Sleep/migration model-generation rebuild can activate the next generation.
Full model/mesh/projection manifests and lifecycle replay therefore remain an
audit cost, not a per-query cost.

All five surviving automations -- Sleep, Dream, system update, organization
contribution, and organization maintenance -- remain migration-paused through
the final composed SkillGuard gate. The updater first creates a no-mutation
restoration plan that binds the exact source and target hashes, runtime status,
and independent `user_paused` value for every task. SkillGuard authorizes that
exact staged plan while it is still unapplied. Only then may the updater write
and read back all five targets, run the normal install check, publish an
activation receipt, and mark the update current. Drift or failure re-pauses all
five. A previously paused automation stays paused, and Architect is never
restored.

## Scheduled-task completion contract

Each retained task has an independent SkillGuard target route, obligations,
exact declared checks, and immutable native artifact. A scheduled run is complete
only when the installed current runtime executes and reconciles that exact check
inventory and the sole `enforced` closure consumes the resulting receipt plus all
required target-owned artifacts. Capability/JUnit tests prove version capability;
they cannot substitute for the immutable receipt of a real scheduled execution.

The target Skill owns domain behavior, applicability, target terminal receipts,
and positive/shallow fixture meaning. SkillGuard owns declared-check execution,
receipt reconciliation, installed-runtime currentness, and the sole closure. A
positive fixture must pass all applicable target obligations; the shallow fixture
must fail for its named important gap. Missing, repeated, stale, generic, or
caller-authored check evidence fails closed.

For a prepared system update, the first supervisor request emits a non-terminal
declared-check authorization receipt and no closure. The updater binds that
receipt to the exact paused restoration plan. A fresh composed authorize+finalize
request then obtains the sole `enforced` closure while all five automations remain
PAUSED. That closure authorizes but does not perform activation: exact application,
read-back, the normal install check, and the activation receipt still must succeed
before `CURRENT`. The legal `no-update`, `waiting-for-user`, and `ui-running`
branches skip restoration but still require target-owned terminal evidence and
the same enforced closure. Operational blockers remain incomplete.

 ## Success evidence

## Success evidence

An upgrade is healthy only when all applicable checks are current and passing:

- migration journal, archive hashes, prune receipt, zero hard debt, and active
  index integrity;
- exact Architect absence and no active legacy handoff;
- source/stage/install whole-tree parity and committed transaction receipt;
- FlowGuard normal scenarios, progress checks, and known-bad rejection;
- FieldLifecycleMesh, finite ContractExhaustionMesh, model-code-test alignment,
  five independent current SkillGuard depth closures, exact native artifacts and
  no-skip JUnit capability evidence, retrieval Top-3/no-card/P95 evaluation, and
  full regression;
- strict OpenSpec verification for the release change.

Failed, stale, skipped, running, progress-only, or missing evidence cannot satisfy
the gate.

Before the long gate starts, the installer freezes the complete SkillGuard /
global-router source pair, installs it through the official SkillGuard
transaction owner inside a short attempt-owned temporary `.codex`, captures the
official current installation receipt, and freezes the imported FlowGuard
package. Compiler, router, depth, model, and child-test consumers use those exact
installed/snapshotted identities. The isolated SkillGuard root is removed after
the gate and receives a separate cleanup receipt; the user's global SkillGuard
is neither reinstalled nor rewritten. A concurrent source or FlowGuard change
invalidates currentness and keeps the five automations paused for an idempotent
retry.

Installed execution uses two short repository-local content-addressed
projections: exact bytes for the installed Skill's five current control files,
and behavior-only bytes for the frozen SkillGuard program plus the current
global-router sibling. Runtime receipts, interpreter caches, and bytecode are
excluded; the behavior projection's official fingerprint must exactly equal the
verified installed runtime identity. These projections are not nested below a
deep scheduled-run directory, so Windows path length cannot create a hidden
second behavior. Any missing sibling or identity mismatch blocks the run without
source substitution or fallback.

The portable install rule still preserves each computer's previous status and
user-pause choice. When an operator has explicitly requested all five tasks be
enabled on the current computer, run
`python scripts/activate_khaos_brain_automations.py --json` only after the
deferred upgrade gate passes. The command consumes the current aggregate and
all five real scheduled-production results, applies one hash-bound group change
to `ACTIVE` plus `user_paused=false`, writes an immutable machine receipt, and
re-pauses the whole group if any write, read-back, receipt, or install-health
check fails.

The five retained Skills expose only the current contract source, compiled
contract, and exact check manifest. Their exact former work contract, underscore
manifest, flat run records, and empty runtime directories are removed after
target-native positive and shallow calibration pass. No compatibility,
conversion, renewal, retirement-receipt, alias, or fallback surface remains; any
reintroduced residual blocks installation.

Aggregate test children are sandboxed from the real Codex home, live shell-tools
directory, user PATH, migration lock, and automation state. One aggregate
readiness owner executes each expensive leaf command at most once; the full
repository regression runs once in its own exclusive lane and publishes a JUnit
node inventory. Model alignment, focused capability claims, semantic checks,
and OpenSpec closure consume that immutable evidence graph instead of launching
the same tests again. A fixture that omits any required isolation input fails
before writing. Any source, owner command, environment, verifier, canonical
receipt, proof, or JUnit change makes the reusable receipt stale. Adding or
removing an unrelated aggregate sibling check does not invalidate a still-current
full-regression owner receipt; the aggregate records both the source and current
consumer inventory revisions when it projects that exact receipt.
Package import and direct-file launch of the aggregate resolve sibling owners
from the explicit repository root; an ambiguous external `scripts` namespace
blocks readiness before any automation restoration.

After that long aggregate gate passes, the installer performs a bounded final
data catch-up before restoring anything. It settles observations admitted by
peer AI work during assurance, rebuilds the active index, reruns retrieval
thresholds, and rechecks migration currentness. Failure leaves all five tasks
paused at a retryable checkpoint.

## Commands

```powershell
python scripts/install_codex_kb.py --json
python scripts/install_codex_kb.py --check --json
python scripts/migrate_kb_maintenance.py --check --json
```

The installer is idempotent. Running it again is the supported recovery action
after moving the repository or completing an interrupted old-machine upgrade.
