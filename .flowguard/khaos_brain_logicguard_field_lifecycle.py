"""FieldLifecycleMesh for the Khaos Brain LogicGuard-native cutover."""

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


DESIGN_REF = "openspec:make-khaos-brain-logicguard-native/design"
MODEL_REF = "flowguard:khaos_brain_logicguard_authority_cutover"


def projection(
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
    tests: tuple[str, ...] = ("happy_path", "failure_path", "negative_path", "replay"),
) -> FieldProjection:
    return FieldProjection(
        projection_id=f"projection:{field_id}",
        field_id=field_id,
        model_obligation_id=obligation,
        code_contract_id=contract,
        required_test_kinds=tests,
        external_inputs=inputs,
        external_outputs=outputs,
        state_reads=reads,
        state_writes=writes,
        side_effects=side_effects,
        error_paths=errors,
        risk_level="high",
        evidence_refs=(
            f"gate:{MODEL_REF}",
            f"test:planned:{field_id}",
            f"replay:planned:{field_id}",
        ),
        rationale=f"Behavior-bearing current field {field_id} implements {obligation}.",
    )


def row(
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
        projection=projection(
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


def current_rows() -> tuple[FieldLifecycleRow, ...]:
    projection_location = ("kb/{public,private,candidates}/**/*.yaml", "local_kb/model_projection.py")
    projection_readers = (
        "local_kb.model_projection.validate_card_projection",
        "local_kb.active_index.rebuild_active_index",
        "local_kb.search.search_with_receipt",
        "local_kb.ui_data",
        "local_kb.desktop_app.KbDesktopApp",
    )
    projector = ("local_kb.model_projection.project_card",)

    rows: list[FieldLifecycleRow] = []
    for field_id, role, obligation in (
        ("card.projection_schema_version", "schema_version", "req.authority.exact-projection"),
        ("card.logicguard_model_id", "persisted", "req.authority.exact-projection"),
        ("card.logicguard_node_id", "persisted", "req.authority.exact-projection"),
        ("card.logicguard_block_id", "persisted", "req.authority.exact-projection"),
        ("card.logicguard_revision_id", "persisted", "req.authority.exact-projection"),
        ("card.logicguard_mesh_id", "persisted", "req.authority.atomic-publication"),
        ("card.logicguard_mesh_revision_id", "persisted", "req.authority.atomic-publication"),
        ("card.projection_digest", "persisted", "req.authority.exact-projection"),
        ("card.authority_scope", "permission", "req.authority.privacy"),
    ):
        rows.append(
            row(
                field_id,
                "group:card-current-binding",
                locations=projection_location,
                role=role,
                lifecycle="new",
                impacts=("schema", "external_contract", "routing", "migration"),
                readers=projection_readers,
                writers=projector,
                obligation=obligation,
                contract="contract:model_projection.validate_exact_binding",
                inputs=("canonical LogicGuard snapshot", "exact mesh revision"),
                outputs=(field_id,),
                state_reads=("scoped model store", "scoped mesh store"),
                state_writes=("card projection staging",),
                side_effects=("projection publication",),
                errors=("missing exact authority", "digest mismatch", "scope mismatch"),
            )
        )

    for field_id, replacement, obligation in (
        ("card.if.notes", "card.logicguard_node_id", "req.authority.projection-only"),
        ("card.action.description", "card.logicguard_block_id", "req.authority.projection-only"),
        ("card.predict.expected_result", "card.logicguard_node_id", "req.authority.projection-only"),
        ("card.use.guidance", "card.logicguard_block_id", "req.authority.projection-only"),
        ("card.related_cards", "card.logicguard_mesh_revision_id", "req.authority.projection-only"),
    ):
        rows.append(
            row(
                field_id,
                "group:card-derived-display",
                locations=projection_location,
                role="presentation" if field_id != "card.related_cards" else "routing",
                lifecycle="derived",
                impacts=("external_contract", "schema", "routing"),
                readers=projection_readers,
                writers=projector,
                obligation=obligation,
                contract="contract:model_projection.project_card",
                replacement=replacement,
                old_fields=(f"legacy-authority:{field_id}",),
                disposition="delegated_to_new_field",
                disposition_refs=(DESIGN_REF, MODEL_REF),
                inputs=("exact canonical nodes and mesh neighborhood",),
                outputs=(field_id,),
                state_reads=(replacement,),
                state_writes=("card projection staging",),
                side_effects=("localized display projection",),
                errors=("projection mismatch", "legacy semantic edit"),
            )
        )

    for field_id, obligation in (
        ("active_index.logicguard_model_id", "req.retrieval.current-index"),
        ("active_index.logicguard_node_id", "req.retrieval.current-index"),
        ("active_index.logicguard_revision_id", "req.retrieval.current-index"),
        ("active_index.logicguard_mesh_id", "req.retrieval.current-index"),
        ("active_index.logicguard_mesh_revision_id", "req.retrieval.current-index"),
        ("active_index.projection_digest", "req.retrieval.current-index"),
        ("active_index.authority_scope", "req.authority.privacy"),
        ("active_index.authority_generation_id", "req.authority.atomic-publication"),
    ):
        rows.append(
            row(
                field_id,
                "group:active-index-binding",
                locations=("kb/indexes/active.json", "local_kb/active_index.py"),
                role="persisted",
                lifecycle="new",
                impacts=("state", "routing", "external_contract", "replay"),
                readers=("local_kb.active_index.load_active_entries", "local_kb.search.search_with_receipt"),
                writers=("local_kb.active_index.rebuild_active_index",),
                obligation=obligation,
                contract="contract:active_index.model_bound_generation",
                inputs=("validated card projection",),
                outputs=(field_id,),
                state_reads=("card projection generation",),
                state_writes=("active index generation",),
                side_effects=("atomic index publication",),
                errors=("stale binding", "missing exact revision", "scope mismatch"),
            )
        )

    for field_id, obligation, contract in (
        ("sleep.model_revision_ids", "req.maintenance.sleep-owner", "contract:model_maintenance.execute_sleep_plan"),
        ("sleep.mesh_revision_id", "req.maintenance.mesh-consolidation", "contract:model_maintenance.execute_sleep_plan"),
        ("sleep.projection_generation_id", "req.authority.atomic-publication", "contract:lifecycle.run_incremental_sleep"),
        ("sleep.model_gap_dispositions", "req.maintenance.gap-review", "contract:model_maintenance.review_gaps"),
        ("dream.logicguard_mesh_revision_id", "req.maintenance.dream-read-only", "contract:dream.run_dream_maintenance"),
        ("dream.simulation_receipt_id", "req.maintenance.dream-read-only", "contract:dream.run_dream_maintenance"),
        ("dream.model_evidence_fingerprint", "req.maintenance.dream-convergence", "contract:dream.run_dream_maintenance"),
        ("dream.sleep_handoff_id", "req.maintenance.dream-convergence", "contract:lifecycle.record_dream_handoff"),
    ):
        group = "group:sleep-receipt" if field_id.startswith("sleep.") else "group:dream-receipt"
        writer = (
            "local_kb.lifecycle.run_incremental_sleep"
            if group == "group:sleep-receipt"
            else "local_kb.dream.run_dream_maintenance"
        )
        rows.append(
            row(
                field_id,
                group,
                locations=("kb/history/**/receipt*.json", "local_kb/lifecycle.py", "local_kb/dream.py"),
                role="persisted",
                lifecycle="new",
                impacts=("state", "side_effect", "replay", "external_contract"),
                readers=("Sleep/Dream receipt validators", "final readiness owner"),
                writers=(writer,),
                obligation=obligation,
                contract=contract,
                inputs=("exact model/mesh authority", "maintenance evidence"),
                outputs=(field_id,),
                state_reads=("Sleep/Dream execution state",),
                state_writes=("immutable maintenance receipt",),
                side_effects=("Sleep handoff" if field_id.startswith("dream.") else "authority generation",),
                errors=("stale revision", "duplicate fingerprint", "unauthorized write"),
            )
        )

    for field_id, obligation in (
        ("migration.model_authority_schema_version", "req.migration.only-legacy-reader"),
        ("migration.per_card_model_bindings", "req.migration.complete-conservative"),
        ("migration.zero_legacy_authority_residual_count", "req.migration.only-legacy-reader"),
        ("migration.rollback_generation_id", "req.migration.transactional"),
        (
            "migration.researchguard_logic_toolchain_identity",
            "req.migration.install",
        ),
    ):
        rows.append(
            row(
                field_id,
                "group:migration-authority",
                locations=(".local/maintenance-migration/**", "local_kb/maintenance_migration.py"),
                role="persisted" if "schema_version" not in field_id else "schema_version",
                lifecycle="new",
                impacts=("state", "migration", "replay", "side_effect", "external_contract"),
                readers=("local_kb.maintenance_migration.validate_migration", "installer readiness"),
                writers=("local_kb.maintenance_migration.run_maintenance_migration",),
                obligation=obligation,
                contract="contract:maintenance_migration.logicguard_authority_cutover",
                inputs=("legacy managed card inventory", "frozen toolchain identity"),
                outputs=(field_id,),
                state_reads=("migration journal", "prior authority generation"),
                state_writes=("migration journal", "current authority generation"),
                side_effects=("direct migration", "rollback"),
                errors=("concurrent change", "partial generation", "privacy failure", "zero residual failure"),
            )
        )

    for field_id, obligation, contract in (
        ("ui.model_binding_status", "req.retrieval.desktop", "contract:ui_data.model_graph_view"),
        ("ui.model_graph", "req.retrieval.desktop", "contract:ui_data.model_graph_view"),
        ("ui.model_gap_summary", "req.retrieval.desktop", "contract:ui_data.model_graph_view"),
        ("ui.model_revision_label", "req.retrieval.desktop", "contract:ui_data.model_graph_view"),
        ("prompt.logicguard_authority_rule", "req.assurance.surface-parity", "contract:skill_prompts.logicguard_authority"),
        ("prompt.sleep_model_maintenance_rule", "req.assurance.surface-parity", "contract:skill_prompts.sleep_owner"),
        ("prompt.dream_read_only_rule", "req.assurance.surface-parity", "contract:skill_prompts.dream_read_only"),
        ("prompt.retrieval_model_native_rule", "req.assurance.surface-parity", "contract:skill_prompts.model_retrieval"),
    ):
        is_ui = field_id.startswith("ui.")
        rows.append(
            row(
                field_id,
                "group:ui-model-view" if is_ui else "group:prompt-contracts",
                locations=("local_kb/ui_data.py", "local_kb/desktop_app.py") if is_ui else (".agents/skills/**/SKILL.md", "templates/**"),
                role="presentation" if is_ui else "prompt_config",
                lifecycle="new",
                impacts=("external_contract", "routing"),
                readers=("local_kb.desktop_app.KbDesktopApp",) if is_ui else ("installed Codex Skill runtime",),
                writers=("local_kb.ui_data",) if is_ui else ("repository-managed installer",),
                obligation=obligation,
                contract=contract,
                inputs=("exact retrieval/model receipt",) if is_ui else ("canonical architecture contract",),
                outputs=(field_id,),
                state_reads=("selected exact model binding",) if is_ui else ("managed Skill source",),
                state_writes=("UI view model",) if is_ui else ("installed Skill projection",),
                side_effects=("desktop render",) if is_ui else ("Skill installation",),
                errors=("stale binding", "private leakage") if is_ui else ("source/install drift", "stale contract"),
            )
        )

    for field_id, replacement, disposition in (
        ("legacy.card.schema_version", "card.projection_schema_version", "migrated"),
        ("legacy.card.then.guidance", "card.use.guidance", "deleted"),
        ("legacy.card.related_cards_authority", "card.logicguard_mesh_revision_id", "migrated"),
        ("legacy.runtime.flat_yaml_search", "active_index.logicguard_model_id", "deleted"),
        ("legacy.runtime.floating_model_head", "card.logicguard_revision_id", "blocked"),
    ):
        rows.append(
            row(
                field_id,
                "group:retired-authority",
                locations=("versioned upgrade input only",),
                role="schema_version" if "schema_version" in field_id else "routing",
                lifecycle="old",
                impacts=("migration", "routing", "external_contract"),
                readers=("local_kb.maintenance_migration.logicguard_authority_phase",),
                writers=(),
                obligation="req.migration.only-legacy-reader",
                contract="contract:maintenance_migration.legacy_input_only",
                replacement=replacement,
                old_fields=(field_id,),
                disposition=disposition,
                disposition_refs=(DESIGN_REF, MODEL_REF),
                inputs=("exact versioned legacy input",),
                outputs=(replacement,),
                state_reads=("migration inventory",),
                state_writes=("current authority generation",),
                side_effects=("direct migration",),
                errors=("legacy residual", "normal-runtime access"),
            )
        )

    return tuple(rows)


def build_plan() -> FieldLifecyclePlan:
    fields = current_rows()
    group_ids = (
        "group:card-current-binding",
        "group:card-derived-display",
        "group:active-index-binding",
        "group:sleep-receipt",
        "group:dream-receipt",
        "group:migration-authority",
        "group:ui-model-view",
        "group:prompt-contracts",
        "group:retired-authority",
    )
    groups = tuple(
        FieldLifecycleGroup(
            group_id,
            boundary_kind="schema/payload/prompt/UI",
            field_ids=tuple(field.field_id for field in fields if field.group_id == group_id),
            owner_route=(
                "ui_flow_structure"
                if group_id == "group:ui-model-view"
                else "field_lifecycle_mesh"
            ),
            evidence_refs=(DESIGN_REF, MODEL_REF),
            rationale="Changed or retired LogicGuard-native authority boundary fields.",
        )
        for group_id in group_ids
    )
    return FieldLifecyclePlan(
        mesh_id="khaos-brain-logicguard-native-field-lifecycle-v1",
        discovered_field_ids=tuple(field.field_id for field in fields),
        groups=groups,
        fields=fields,
        claim_scope="bounded",
        allow_scoped_confidence=False,
        notes=(
            "This inventory is complete for new/changed model-authority, projection, index, "
            "maintenance, migration, UI, prompt, and directly retired legacy fields. Unchanged "
            "general card metadata is outside this bounded cutover inventory."
        ),
    )


def broken_plan() -> FieldLifecyclePlan:
    plan = build_plan()
    fields = list(plan.fields[:-1])
    first_old = next(field for field in fields if field.field_id == "legacy.card.schema_version")
    fields[fields.index(first_old)] = replace(
        first_old,
        disposition="unknown",
        disposition_evidence_refs=(),
    )
    return FieldLifecyclePlan(
        mesh_id="khaos-brain-logicguard-native-field-lifecycle-known-bad",
        discovered_field_ids=plan.discovered_field_ids,
        groups=plan.groups,
        fields=tuple(fields),
        claim_scope="bounded",
        allow_scoped_confidence=False,
        notes="Known bad omits one discovered row and leaves an old-field disposition open.",
    )


def main() -> int:
    current = review_field_lifecycle(build_plan())
    broken = review_field_lifecycle(broken_plan())
    payload = {
        "artifact_type": "khaos_brain_logicguard_native_field_lifecycle",
        "current": current.to_dict(),
        "known_bad": broken.to_dict(),
        "field_count": len(build_plan().fields),
        "group_count": len(build_plan().groups),
        "ok": current.ok and not broken.ok,
        "claim_boundary": (
            "This report closes the bounded changed/retired field inventory and projections only. "
            "Planned test refs are not production evidence; Model-Test Alignment, UI Flow Structure, "
            "implementation tests, migration replay, and final freshness remain required."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
