# Chaos Brain Upgrade Contract

Every fresh installation and supported upgrade uses the same AI-executed,
rollbackable contract. No person has to inspect files or approve ordinary
lifecycle decisions.

## One current system, no compatibility runtime

Chaos Brain has zero normal-runtime compatibility and zero normal-runtime
fallback. Retrieval, organization data, automation policy, installed Skills,
update state, command grammar, and UI launch each have one current authority.
A missing or invalid current authority is a visible failure; daily software
does not probe old paths, reinterpret old arguments, insert backup models, or
silently switch launchers.

Old managed material is input only to the versioned upgrade. The upgrade
inventories and snapshots the old surface, rewrites valid material directly
into current LogicGuard revisions and scoped ModelMeshes, creates deterministic
projections and the exact active index, publishes the generation pointer last,
removes old authority, and proves zero residuals. Unknown or incomplete input
rolls back and keeps all four retained automations paused. It never adds a
compatibility reader or fallback.

When one captured old/current conflict cannot be resolved mechanically, the
upgrade emits one bounded evidence-backed AI work item. Its resolution records
the exact selected current disposition and hashes; the retry performs the
actual rebuild. The resolver cannot itself publish cards, models, meshes,
indexes, or pointers.

## Author school and independent consumer Skills

The repository maintains exactly five source Skills:

- `kb-sleep-maintenance`
- `kb-dream-pass`
- `kb-organization-contribute`
- `kb-organization-maintenance`
- `khaos-brain-update`

SkillGuard is an author-side school and examiner for these source Skills. Each
source Skill is one maintenance unit with its own promises, protected boundary,
declared checks, positive fixture, and named shallow failure. SkillGuard proves
that the unit has said what it owns and has enough target-authored evidence to
support that promise.

The five units do not share tests or receipts. If two units claim the same
obligation or evidence domain, that is a source-boundary defect to fix; it is
not an opportunity to make one unit consume the other's proof.

Graduation produces a clean consumer tree. An installed Skill contains its
target-owned instructions and runtime materials only. It contains no
`.skillguard`, SkillGuard command/import, router reference, author contract,
author receipt, or cross-unit receipt dependency. Ordinary use never discovers,
installs, snapshots, verifies, or calls SkillGuard. An author-side SkillGuard
upgrade therefore cannot stale an installed consumer Skill or its native run
receipt.

Official OpenSpec is an external development tool and is not one of the five
SkillGuard-maintained units.

## Transaction and failure behavior

Before activation, the installer:

1. runs the five author-side contract and depth audits;
2. compiles five clean consumer projections;
3. rejects author-only or cross-unit material in any projection;
4. compares source, staged, installed, and post-operation manifests;
5. detects concurrent source drift;
6. snapshots rollback state;
7. activates the complete managed group;
8. runs consumer currentness and aggregate assurance;
9. commits one versioned durable transaction receipt.

Author checks are a pre-installation quality gate, not a runtime dependency and
not part of the installed payload.

Every surviving automation preserves both its exact previous runtime status and
its independent `user_paused` value. A failed transaction or assurance step
restores the last known good files, re-pauses all four automations, records the
retry point, and leaves the attempt incomplete. Interruption recovery finishes
or rolls back the old transaction before a new attempt begins.

Ordinary install currentness is independent of attempt-history size. It reads
only `.khaos-brain-install/attempts/HEAD.json` and the bounded `current.json`
projection named and hash-bound by that HEAD. Prior attempt directories and
immutable event files remain historical evidence and are not scanned. A
missing, old-schema, oversized, escaping, or hash-mismatched current binding
fails immediately; there is no manifest fallback or historical latest-attempt
search.

After the final attempt checkpoint is published, the lightweight committed
install state stores that exact attempt's `attempt_id` and `receipt_hash`.
The independent `--check` command reloads both authorities and requires an
exact match. An installer-internal green result cannot substitute for this
durable post-command binding.

The history migration lock uses a versioned owner token, process id, and
heartbeat. A live owner is never displaced. A dead recorded owner is quarantined
with a recovery receipt before the migration resumes.

The migration sequence is:

`preflight -> snapshot -> classify -> settle-logical-debt -> archive-cold-evidence -> prune-derived-data -> build-logicguard-authority -> publish-projections -> rebuild-index -> publish-pointer -> validate-zero-residual -> committed`

Long validation owners must confirm that zero descendant processes remain after
a timeout or cancellation. Evidence from a cleanup-unconfirmed run is not
reusable.

## Scheduled and manual completion

The four scheduled Skills complete through their own target-native runners.
Each runner owns one exact command, one run identity, one non-overlapping
obligation inventory, and one immutable terminal receipt. Capability regression
proves that a software version can perform the behavior; it cannot replace the
receipt of a concrete scheduled run.

Installation and current-machine activation use one current five-member skill
inventory: the four runners above are `scheduled`, while
`khaos-brain-update` is the sole `manual-only` member. The operator transaction
activates and reads back exactly four automation IDs. It does not require or
invent a fifth scheduler, and its activation receipt is not evidence that a
future scheduled run completed.

The manual `khaos-brain-update` Skill has no scheduler. It begins only after an
explicit request in the current conversation and completes in one target-native
transaction:

`check request and topology -> pause/snapshot -> update -> migrate/install -> validate -> build restoration plan -> restore/read back -> normal install check -> native terminal receipt -> CURRENT`

All four automations remain paused until restoration and readback succeed.
Drift or failure re-pauses the group and marks the update failed. `no-update` is
the only successful no-op. An open UI, missing request, missing upstream, fetch
failure, dirty tracked work, local-ahead/diverged topology, concurrent execution,
or another unknown operational state remains blocked. There is no SkillGuard
authorization stage, composed finalization gate, or second activation receipt.

## Success evidence

An upgrade is healthy only when all applicable evidence is current:

- migration journal, archive hashes, prune receipt, zero hard debt, and active
  index integrity;
- exact absence of retired Architect and system-update surfaces;
- five current, unique author-side SkillGuard contracts and depth calibrations;
- five clean consumer projections with no `.skillguard` or SkillGuard runtime
  dependency;
- staged/install whole-tree parity and committed transaction receipt;
- FlowGuard scenario, conformance, progress, no-stuck, field-lifecycle, and
  model-test checks;
- exact target-native run receipts and no cross-unit receipt reuse;
- retrieval Top-3/no-card/P95 evaluation and the full regression owner;
- strict OpenSpec verification for the active changes;
- official OpenSpec installation containing only the official consumer Skills
  and no SkillGuard material.

Failed, stale, skipped, running, progress-only, shared, or missing evidence
cannot satisfy the gate.

## Commands

```powershell
python scripts/install_codex_kb.py --json
python scripts/install_codex_kb.py --check --json
python scripts/migrate_kb_maintenance.py --check --json
```

The installer is idempotent. Running it again is the supported recovery action
after moving the repository or completing an interrupted old-machine upgrade.
