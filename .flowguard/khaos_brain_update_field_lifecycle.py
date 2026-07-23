"""FieldLifecycleMesh for status-only Khaos Brain software updates."""

from __future__ import annotations

import json
from dataclasses import replace

from flowguard import (
    FieldLifecycleGroup,
    FieldLifecyclePlan,
    FieldLifecycleRow,
    FieldProjection,
    review_field_lifecycle,
)


DESIGN_REF = "openspec:replace-automatic-updates-with-status-only-ui/design"
MODEL_REF = "flowguard:khaos_brain_function_flow.SoftwareUpdateBlock"


def _projection(
    field_id: str,
    obligation: str,
    contract: str,
    *,
    inputs: tuple[str, ...] = (),
    outputs: tuple[str, ...] = (),
    reads: tuple[str, ...] = (),
    writes: tuple[str, ...] = (),
    side_effects: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
) -> FieldProjection:
    return FieldProjection(
        projection_id=f"projection:{field_id}",
        field_id=field_id,
        model_obligation_id=obligation,
        code_contract_id=contract,
        required_test_kinds=("happy_path", "failure_path", "negative_path", "replay"),
        external_inputs=inputs,
        external_outputs=outputs,
        state_reads=reads,
        state_writes=writes,
        side_effects=side_effects,
        error_paths=errors,
        risk_level="high",
        evidence_refs=(DESIGN_REF, MODEL_REF, f"test:planned:{field_id}"),
        rationale=f"Changed software-update field {field_id} implements {obligation}.",
    )


def _row(
    field_id: str,
    group_id: str,
    *,
    locations: tuple[str, ...],
    role: str,
    lifecycle: str,
    impacts: tuple[str, ...],
    readers: tuple[str, ...],
    writers: tuple[str, ...],
    obligation: str,
    contract: str,
    replacement: str = "",
    old_fields: tuple[str, ...] = (),
    disposition: str = "unknown",
    disposition_refs: tuple[str, ...] = (),
    inputs: tuple[str, ...] = (),
    outputs: tuple[str, ...] = (),
    state_reads: tuple[str, ...] = (),
    state_writes: tuple[str, ...] = (),
    side_effects: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
) -> FieldLifecycleRow:
    return FieldLifecycleRow(
        field_id=field_id,
        field_name=field_id.rsplit(".", 1)[-1],
        locations=locations,
        group_id=group_id,
        role=role,
        lifecycle=lifecycle,
        behavior_impacts=impacts,
        reader_ids=readers,
        writer_ids=writers,
        replacement_field_id=replacement,
        old_field_ids=old_fields,
        disposition=disposition,
        disposition_evidence_refs=disposition_refs,
        projection=_projection(
            field_id,
            obligation,
            contract,
            inputs=inputs,
            outputs=outputs,
            reads=state_reads,
            writes=state_writes,
            side_effects=side_effects,
            errors=errors,
        ),
    )


def build_rows() -> tuple[FieldLifecycleRow, ...]:
    state_location = (".local/khaos_brain_update_state.json", "local_kb/software_update.py")
    status_reader = (
        "local_kb.software_update.load_update_state",
        "local_kb.desktop_app.KbDesktopApp",
        "scripts.run_khaos_brain_manual_update",
    )
    status_writer = (
        "local_kb.software_update.check_remote_update",
        "local_kb.software_update.mark_update_status",
        "local_kb.software_update.migrate_obsolete_update_state",
    )
    rows: list[FieldLifecycleRow] = []

    current_fields = (
        ("update.schema_version", "schema_version"),
        ("update.status", "state"),
        ("update.current_version", "presentation"),
        ("update.latest_version", "presentation"),
        ("update.current_revision", "persisted"),
        ("update.latest_revision", "persisted"),
        ("update.upstream_ref", "routing"),
        ("update.ahead_count", "state"),
        ("update.behind_count", "state"),
        ("update.update_available", "state"),
        ("update.last_checked_at", "persisted"),
        ("update.updated_at", "persisted"),
        ("update.error", "error"),
        ("update.started_at", "persisted"),
        ("update.completed_at", "persisted"),
    )
    for field_id, role in current_fields:
        rows.append(
            _row(
                field_id,
                "group:update-status-v2",
                locations=state_location,
                role=role,
                lifecycle="new" if field_id in {
                    "update.upstream_ref",
                    "update.ahead_count",
                    "update.behind_count",
                } else "current",
                impacts=("schema", "state", "routing", "external_contract"),
                readers=status_reader,
                writers=status_writer,
                obligation="req.update-status.read-only-upstream",
                contract="contract:software_update.status_v2",
                inputs=("configured @{u}", "git topology", "VERSION"),
                outputs=(field_id,),
                state_reads=("local update status cache",),
                state_writes=("status-only update cache",),
                side_effects=("atomic status cache write",),
                errors=("missing upstream", "fetch failure", "invalid topology", "unknown schema"),
            )
        )

    for field_id, role, owner in (
        ("ui.update_status_badge", "presentation", "local_kb.desktop_app.KbDesktopApp._draw_update_badge"),
        ("ui.update_status_check_worker", "routing", "local_kb.desktop_app.KbDesktopApp._start_update_status_check"),
    ):
        rows.append(
            _row(
                field_id,
                "group:update-status-ui",
                locations=("local_kb/desktop_app.py",),
                role=role,
                lifecycle="new",
                impacts=("routing", "external_contract"),
                readers=(owner,),
                writers=(owner,),
                obligation="req.update-status.no-ui-authorization",
                contract="contract:desktop.update_status_read_only",
                inputs=("status-only update cache",),
                outputs=("human-readable branch/version status",),
                state_reads=("update status v2",),
                state_writes=("in-memory repaint state",),
                side_effects=("desktop render", "one launch-time background fetch"),
                errors=("worker failure", "window closed before callback"),
            )
        )

    rows.append(
        _row(
            "manual_update.explicit_user_request",
            "group:manual-update-trigger",
            locations=("current AI conversation", "scripts/run_khaos_brain_manual_update.py"),
            role="routing",
            lifecycle="new",
            impacts=("routing", "side_effect", "external_contract"),
            readers=("scripts.run_khaos_brain_manual_update.run_manual_update",),
            writers=("current AI invocation only",),
            obligation="req.manual-update.explicit-conversation",
            contract="contract:manual_update.explicit_current_request",
            inputs=("explicit user request in current conversation",),
            outputs=("one invocation-scoped authorization boolean",),
            state_reads=("current invocation arguments",),
            state_writes=(),
            side_effects=("manual update gate only",),
            errors=("missing authorization", "replayed persisted authorization"),
        )
    )

    for field_id, role in (
        ("operator_activation.schema_version", "schema_version"),
        ("operator_activation.final_install_identity_hash", "persisted"),
        ("operator_activation.status_authority.receipt_hash", "authority"),
        ("operator_activation.status_authority.states", "routing"),
        ("operator_activation.skill_inventory.schema_version", "schema_version"),
        ("operator_activation.skill_inventory.maintained_skill_ids", "routing"),
        ("operator_activation.skill_inventory.scheduled_skill_ids", "routing"),
        ("operator_activation.skill_inventory.manual_only_skill_ids", "routing"),
    ):
        rows.append(
            _row(
                field_id,
                "group:operator-activation-inventory",
                locations=(
                    "local_kb/operator_activation.py",
                    ".khaos-brain-install/operator-activation/receipts",
                ),
                role=role,
                lifecycle="new",
                impacts=("schema", "routing", "external_contract"),
                readers=(
                    "local_kb.operator_activation.validate_activation_readiness",
                    "local_kb.operator_activation.validate_operator_activation_receipt",
                ),
                writers=(
                    "local_kb.operator_activation.activate_all_for_current_machine",
                ),
                obligation="req.automation.activation-inventory",
                contract="contract:operator_activation.five_four_one_inventory",
                inputs=(
                    "five maintained skill ids",
                    "four repository automation specs",
                ),
                outputs=(field_id,),
                state_reads=("current aggregate author assurance",),
                state_writes=("operator activation receipt",),
                side_effects=("activate exactly four scheduled automations",),
                errors=(
                    "manual skill treated as scheduled",
                    "overlapping inventory",
                    "non-exhaustive inventory",
                    "old receipt schema",
                    "runtime migration diagnostics used as receipt identity",
                    "activation exception leaves an unreceipted ACTIVE state",
                ),
            )
        )

    for field_id, role in (
        ("upgrade_attempt.head.schema_version", "schema_version"),
        ("upgrade_attempt.head.attempt_id", "routing"),
        ("upgrade_attempt.head.sequence", "state"),
        ("upgrade_attempt.head.current_receipt_hash", "persisted"),
        ("upgrade_attempt.head.current_ref.relative_path", "routing"),
        ("upgrade_attempt.head.current_ref.sha256", "persisted"),
        ("upgrade_attempt.head.head_hash", "persisted"),
        ("upgrade_attempt.current.schema_version", "schema_version"),
        ("upgrade_attempt.current.projection_schema_version", "schema_version"),
    ):
        rows.append(
            _row(
                field_id,
                "group:upgrade-attempt-current-authority",
                locations=(
                    "local_kb/install.py",
                    ".khaos-brain-install/attempts/HEAD.json",
                    ".khaos-brain-install/attempts/<attempt-id>/current.json",
                ),
                role=role,
                lifecycle="new",
                impacts=("schema", "state", "routing", "external_contract"),
                readers=(
                    "local_kb.install.current_upgrade_attempt_authority",
                    "local_kb.install.build_installation_check",
                ),
                writers=("local_kb.install._record_upgrade_attempt",),
                obligation="req.upgrade-attempt.bounded-current-authority",
                contract="contract:install.upgrade_attempt_head_current",
                inputs=("one current attempt checkpoint",),
                outputs=(field_id,),
                state_reads=("bounded HEAD", "bounded current projection"),
                state_writes=("HEAD written after current projection",),
                side_effects=("atomic current-authority publication",),
                errors=(
                    "missing or oversized HEAD",
                    "current hash mismatch",
                    "path escapes attempt root",
                    "history enumeration",
                    "install-manifest fallback",
                ),
            )
        )

    rows.append(
        _row(
            "install_state.upgrade_attempt.receipt_hash",
            "group:upgrade-attempt-current-authority",
            locations=(
                "local_kb/config.py",
                "predictive-kb/install.json",
            ),
            role="persisted",
            lifecycle="new",
            impacts=("schema", "state", "external_contract"),
            readers=("local_kb.install.build_installation_check",),
            writers=(
                "local_kb.config.build_install_state",
                "local_kb.config.save_install_state",
            ),
            obligation="req.upgrade-attempt.committed-install-state-binding",
            contract="contract:config.install_state_attempt_receipt_binding",
            inputs=("final bounded upgrade-attempt current projection",),
            outputs=("exact current attempt receipt hash",),
            state_reads=("upgrade_attempt.receipt_hash",),
            state_writes=("install_state.upgrade_attempt.receipt_hash",),
            side_effects=("atomic lightweight install-state publication",),
            errors=(
                "missing committed receipt hash",
                "attempt id or receipt hash mismatch",
                "internal check green but independent check red",
            ),
        )
    )

    retired = (
        ("update.v1.user_requested", "", "deleted"),
        ("update.v1.status.prepared", "update.status", "migrated"),
        ("ui.update_badge_hitbox", "", "deleted"),
        ("ui.update_click_action", "", "deleted"),
        ("automation.khaos-brain-system-update", "", "deleted"),
        ("routing.system_update_check", "manual_update.explicit_user_request", "migrated"),
        ("routing.architect_update_check", "", "deleted"),
        ("entrypoint.run_khaos_brain_system_update", "entrypoint.run_khaos_brain_manual_update", "migrated"),
        (
            "operator_activation.v1.scheduled_production_refs",
            "operator_activation.skill_inventory.scheduled_skill_ids",
            "blocked",
        ),
        (
            "upgrade_attempt.v1.current_projection",
            "upgrade_attempt.head.current_ref.relative_path",
            "blocked",
        ),
    )
    for field_id, replacement, disposition in retired:
        rows.append(
            _row(
                field_id,
                "group:retired-update-authority",
                locations=("versioned upgrade input only",),
                role="routing" if "status.prepared" not in field_id else "state",
                lifecycle="old",
                impacts=("migration", "routing", "side_effect", "external_contract"),
                readers=("local_kb.software_update.migrate_obsolete_update_state",) if field_id.startswith("update.v1") else (),
                writers=(),
                obligation=(
                    "req.update-state.direct-migration"
                    if field_id.startswith("update.v1")
                    else "req.automation.retired"
                ),
                contract="contract:update_retirement.direct_current_only",
                replacement=replacement,
                old_fields=(field_id,),
                disposition=disposition,
                disposition_refs=(DESIGN_REF, MODEL_REF),
                inputs=("exact former managed surface",),
                outputs=((replacement,) if replacement else ("zero residuals",)),
                state_reads=("upgrade inventory",),
                state_writes=((replacement,) if replacement else ()),
                side_effects=("direct migration or exact deletion",),
                errors=("normal-runtime legacy read", "unknown former shape", "residual authority"),
            )
        )

    return tuple(rows)


def build_plan() -> FieldLifecyclePlan:
    fields = build_rows()
    group_specs = (
        ("group:update-status-v2", "status_schema", "field_lifecycle_mesh"),
        ("group:update-status-ui", "ui_projection", "ui_flow_structure"),
        ("group:manual-update-trigger", "invocation_routing", "model_first_function_flow"),
        ("group:operator-activation-inventory", "activation_schema", "field_lifecycle_mesh"),
        ("group:upgrade-attempt-current-authority", "currentness_schema", "field_lifecycle_mesh"),
        ("group:retired-update-authority", "retired_surface", "field_lifecycle_mesh"),
    )
    groups = tuple(
        FieldLifecycleGroup(
            group_id,
            boundary_kind=boundary_kind,
            field_ids=tuple(field.field_id for field in fields if field.group_id == group_id),
            owner_route=owner_route,
            evidence_refs=(DESIGN_REF, MODEL_REF),
            rationale="Status visibility is separate from invocation-scoped manual update authority.",
        )
        for group_id, boundary_kind, owner_route in group_specs
    )
    return FieldLifecyclePlan(
        mesh_id="khaos-brain-status-only-update-field-lifecycle-v1",
        discovered_field_ids=tuple(field.field_id for field in fields),
        groups=groups,
        fields=fields,
        claim_scope="bounded",
        allow_scoped_confidence=False,
        notes=(
            "Complete inventory for changed status schema, UI projection, manual "
            "trigger, exact five/four/one activation inventory, bounded upgrade-attempt "
            "HEAD/current authority plus its exact committed install-state receipt "
            "binding, and retired update authority.",
        ),
    )


def broken_plan() -> FieldLifecyclePlan:
    plan = build_plan()
    fields = list(plan.fields)
    target = next(field for field in fields if field.field_id == "update.v1.user_requested")
    fields[fields.index(target)] = replace(
        target,
        disposition="unknown",
        disposition_evidence_refs=(),
    )
    fields = [field for field in fields if field.field_id != "automation.khaos-brain-system-update"]
    return FieldLifecyclePlan(
        mesh_id="khaos-brain-status-only-update-field-lifecycle-known-bad",
        discovered_field_ids=plan.discovered_field_ids,
        groups=plan.groups,
        fields=tuple(fields),
        claim_scope="bounded",
        allow_scoped_confidence=False,
        notes="Known bad leaves persisted authorization unresolved and omits the retired scheduler.",
    )


def main() -> int:
    current = review_field_lifecycle(build_plan())
    broken = review_field_lifecycle(broken_plan())
    payload = {
        "artifact_type": "khaos_brain_status_only_update_field_lifecycle",
        "current": current.to_dict(),
        "known_bad": broken.to_dict(),
        "field_count": len(build_plan().fields),
        "group_count": len(build_plan().groups),
        "ok": current.ok and not broken.ok,
        "claim_boundary": (
            "This closes only the changed/retired update field inventory. Production tests, UI evidence, "
            "installer replay, source-only author contract depth, and release freshness remain separate."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
