---
name: khaos-brain-update
description: Apply an explicitly prepared, recovery-oriented Chaos Brain software update. Use for a user/UI-authorized update or the repository-managed system update automation; never decide on the user's behalf that an unprepared update is wanted.
---

# Khaos Brain Update

This is the narrow system-maintenance path. It updates software and installer-managed Codex integration; it does not maintain cards and it does not replace Sleep or Dream.

## Recovery boundary

The update must still work when retrieval, desktop settings, organization state, or the UI is unhealthy. Preserve `.local/`, private/history/candidate/outbox KB state, organization caches and Skill bundles, exchange ledgers, user-created untracked files, and user-owned Codex configuration outside managed paths.

## Apply contract

1. The native scheduled owner is `python scripts/run_khaos_brain_system_update.py --json`; it begins with the system check and continues only when the update was explicitly prepared and the result says `apply_ready=true`.
2. Mark the UI-blocking state as upgrading and close only identified Khaos Brain UI processes. Never broadly terminate Python, Node, Codex, or unrelated apps.
3. Inspect tracked source state. Do not overwrite dirty user/peer work or run reset, force checkout, rebase, or tag moves.
4. Fetch the configured upstream and update by fast-forward only.
5. Run the versioned maintenance migration for Chaos Brain. It must inventory and settle historical knowledge debt, archive retained evidence before pruning, remove derived copies, build exact LogicGuard model revisions and scoped ModelMeshes, write deterministic card projections and the exact active index, and publish the generation pointer last. It must resume idempotently after interruption.
   The migration is the only owner allowed to read an exact retired managed format. It must rewrite every valid legacy card directly into the sole current LogicGuard authority, remove old semantic authority including `then` and authoritative `related_cards`, and prove zero residuals. Readable YAML after migration is projection only. A discovered incompatible residual is an unfinished upgrade-AI work item: inspect its exact card path, projection digest, old/new generation ids, and binding; when the evidence licenses rebuilding that pulled current projection, run `python scripts/resolve_kb_upgrade_ai_work_item.py --work-item-id <id> --actor <AI> --rationale <evidence-bound reason> --json`, then rerun the idempotent installer inside the still-paused rollbackable upgrade. The resolver may only record the one direct-current projection-to-model action; it does not modify cards, models, meshes, indexes, or pointers itself. Unknown, incomplete, cross-scope, stale-digest, or unbound model state rolls back the entire generation and keeps the five retained automations paused; it never creates a compatibility layer, projection fallback, alternate reader, or silent downgrade and never counts as a completed upgrade.
   If exact old and current fields conflict, deterministic software must block. The upgrade AI may then select only a value present in those exact inputs, state its reason, and commit the selected value plus both source values and hashes in the one-time migration receipt. Daily code never performs that judgment.
6. Run `python scripts/install_codex_kb.py --json`. The installer must stage complete managed Skill and automation trees, compile/check repository-owned current SkillGuard contracts, compare complete manifests, block downgrade or concurrent drift, keep rollback copies, and activate all managed trees as one recovery-bound transaction.
7. The migration must precisely retire legacy `kb-architect-pass` and `kb-architect` managed surfaces, including machines with missing or old install manifests. Similar user-created names are outside scope.
8. Preserve every surviving automation's prior ACTIVE/PAUSED status and independent `user_paused` value. Pause all five surviving automations before mutation; the retired automation never resumes.
9. End the native update at `awaiting-skillguard` with all five survivors still paused. The first SkillGuard run selects only the authorization route and proves the exact native receipt; this authorizes preparation, not completion or restoration.
10. While live automations remain paused, derive a deterministic restoration plan containing the preserved target status, target `user_paused`, current source hashes, and exact target `automation.toml` hashes. Run the deferred install check and bind the plan, native receipt, non-terminal declared-check authorization receipt, and snapshot into an immutable finalization receipt.
11. Run fresh composed SkillGuard supervision over both `authorize` and `finalize`. Only the sole current `enforced` closure, full obligation coverage, exact declared-check receipts, and both native-output artifacts may authorize the staged plan. Do not invent a placeholder finalization witness.
12. After that closure passes, apply only the authorized target hashes, immediately read back every status, `user_paused`, and file hash, run the normal installation check, then mark CURRENT and write the immutable activation receipt. Any planning, supervision, apply, readback, or final-check failure marks FAILED and returns all five survivors to PAUSED.

## Report

Return previous and target revisions, preserved state inventory, migration version/receipt, retired surfaces, source/staged/installed manifest digests, the non-terminal declared-check authorization receipt and final enforced SkillGuard closure, staged restoration plan and hashes, activation readback receipt, transaction and rollback receipt, both deferred and normal install checks, blockers, and final status.

## SkillGuard completion boundary

For a scheduled run, intake, planning, or proposal-only output is incomplete. An install-only output or staged plan without an enforced SkillGuard closure receipt is also incomplete. Run `python scripts/run_kb_guarded_automation.py --skill khaos-brain-update --json`; do not call only the child system check. The guarded runner invokes the native full update owner once and writes its immutable receipt. For `prepared-update`, the authorize route first produces a non-terminal declared-check reconciliation receipt with `overall_complete=false`; it emits no closure. While every live task remains paused, a fresh composed `authorize+finalize` run must obtain the sole `enforced` closure over the exact native and staged-restoration receipts. Only `no-update`, `waiting-for-user`, and `ui-running` may close directly as enforced successful terminal no-op branches; `already-upgrading`, `failed-awaiting-user`, `concurrent-update`, and unknown blockers remain incomplete. Positive and shallow fixtures remain target-owned checks; SkillGuard supervises their exact receipts without interpreting their domain meaning. The installed SkillGuard builder—not caller-authored fields—binds the trigger, execution id, current installation receipt id/hash plus portable receipt-root reference, and installed runtime fingerprint. Terminal no-op and composed finalization execute `stage_depth` followed by `close` on the same request, target root, and run; close consumes the exact staged declared-check receipt and must not rerun target checks. SkillGuard supervises evidence and authorization; the native executor alone performs the later exact hash apply, readback, normal install check, and CURRENT transition.

If the native owner or any validation child times out, the run is incomplete until the guarded launcher terminates the complete owned process tree, confirms zero remaining descendants, and records that cleanup under the ordered native-to-scheduled-to-aggregate-to-installer timeout budget.

## SkillGuard boundary

The current authority is `.skillguard/contract-source.json` plus its declared FlowGuard model. `.skillguard/compiled-contract.json` and `.skillguard/check-manifest.json` are generated projections. No former work contract, underscore manifest, flat run record, compatibility, conversion, renewal, retirement-receipt, alias, or fallback closure route may exist. SkillGuard supervises the native update owner and cannot authorize an unrequested update, partial installation, downgrade, or early resume.
