"""Executable FlowGuard code-structure recommendation for LogicGuard-native Khaos Brain.

The recommendation keeps the existing Khaos Brain facades and assigns the new
LogicGuard-native semantics to three narrow helper modules.  It is deliberately
not a second controller: Sleep, Dream, retrieval, active-index publication, and
upgrade cutover retain their existing public owners.
"""

from __future__ import annotations

import json
from dataclasses import replace

from flowguard.code_structure import (
    CodeStructureRecommendation,
    TargetModuleRecommendation,
    review_code_structure_recommendation,
)


MODEL_ID = "khaos_brain_logicguard_authority_cutover"
RECOMMENDATION_ID = "khaos_brain_logicguard_native_code_structure"

MODELS = "local_kb.logicguard_models"
PROJECTION = "local_kb.model_projection"
MAINTENANCE = "local_kb.model_maintenance"
LIFECYCLE = "local_kb.lifecycle"
DREAM = "local_kb.dream"
SEARCH = "local_kb.search"
ACTIVE_INDEX = "local_kb.active_index"
MIGRATION = "local_kb.maintenance_migration"
DESKTOP = "local_kb.desktop_app"


FUNCTION_BLOCK_MAP = (
    ("BindCardModelBlock", MODELS),
    ("ValidateCardBindingBlock", PROJECTION),
    ("PlanSleepModelChangeBlock", MAINTENANCE),
    ("CommitSleepModelChangeBlock", MAINTENANCE),
    ("ValidateDreamMeshBlock", MAINTENANCE),
    ("RetrieveModelNeighborhoodBlock", MODELS),
    ("PublishAuthorityGenerationBlock", MIGRATION),
)

STATE_OWNER_MAP = (
    ("model_revision_heads", MODELS),
    ("mesh_revision_heads", MODELS),
    ("model_neighborhood_materialization", MODELS),
    ("projection_generation_stage", PROJECTION),
    ("projection_validation_state", PROJECTION),
    ("sleep_model_change_plan", MAINTENANCE),
    ("dream_experiment_state", MAINTENANCE),
    ("dream_handoff_state", MAINTENANCE),
    ("entry_lifecycle_state", LIFECYCLE),
    ("sleep_watermark", LIFECYCLE),
    ("retrieval_query_state", SEARCH),
    ("active_index_generation", ACTIVE_INDEX),
    ("authority_generation_pointer", MIGRATION),
    ("migration_rollback_state", MIGRATION),
    ("desktop_graph_view_state", DESKTOP),
)

SIDE_EFFECT_OWNER_MAP = (
    ("logicguard_model_revision_commit", MODELS),
    ("logicguard_mesh_revision_commit", MODELS),
    ("projection_generation_write", PROJECTION),
    ("logicguard_diagnostic_receipt_write", MAINTENANCE),
    ("dream_sleep_handoff_write", MAINTENANCE),
    ("lifecycle_event_commit", LIFECYCLE),
    ("sleep_watermark_advance", LIFECYCLE),
    ("dream_experiment_receipt_write", DREAM),
    ("retrieval_receipt_write", SEARCH),
    ("active_index_publication", ACTIVE_INDEX),
    ("authority_pointer_cutover", MIGRATION),
    ("prior_generation_restore", MIGRATION),
    ("desktop_model_graph_render", DESKTOP),
)

CONFIG_OWNER_MAP = (
    ("logicguard_model_store_roots", MODELS),
    ("logicguard_mesh_store_roots", MODELS),
    ("model_neighborhood_budgets", MODELS),
    ("card_projection_schema_version", PROJECTION),
    ("sleep_model_diagnostic_thresholds", MAINTENANCE),
    ("dream_simulation_budgets", MAINTENANCE),
    ("active_index_schema_version", ACTIVE_INDEX),
    ("maintenance_migration_version", MIGRATION),
)

FIELD_OWNER_MAP = (
    ("card.projection_schema_version", PROJECTION),
    ("card.logicguard_model_id", MODELS),
    ("card.logicguard_node_id", MODELS),
    ("card.logicguard_block_id", MODELS),
    ("card.logicguard_revision_id", MODELS),
    ("card.logicguard_mesh_id", MODELS),
    ("card.logicguard_mesh_revision_id", MODELS),
    ("card.projection_digest", PROJECTION),
    ("card.authority_scope", MODELS),
    ("card.if.notes", PROJECTION),
    ("card.action.description", PROJECTION),
    ("card.predict.expected_result", PROJECTION),
    ("card.use.guidance", PROJECTION),
    ("card.related_cards", PROJECTION),
    ("index.authority_generation_id", ACTIVE_INDEX),
    ("index.logicguard_model_id", ACTIVE_INDEX),
    ("index.logicguard_node_id", ACTIVE_INDEX),
    ("index.logicguard_revision_id", ACTIVE_INDEX),
    ("index.logicguard_mesh_id", ACTIVE_INDEX),
    ("index.logicguard_mesh_revision_id", ACTIVE_INDEX),
    ("index.projection_digest", ACTIVE_INDEX),
    ("sleep.input_generation_id", MAINTENANCE),
    ("sleep.output_generation_id", MAINTENANCE),
    ("sleep.model_change_set", MAINTENANCE),
    ("sleep.mesh_change_set", MAINTENANCE),
    ("sleep.diagnostics", MAINTENANCE),
    ("sleep.commit_receipt", MAINTENANCE),
    ("dream.pinned_mesh_revision_id", MAINTENANCE),
    ("dream.simulation_plan", MAINTENANCE),
    ("dream.simulation_receipt", DREAM),
    ("dream.sleep_handoff", MAINTENANCE),
    ("migration.migration_version", MIGRATION),
    ("migration.input_generation_id", MIGRATION),
    ("migration.output_generation_id", MIGRATION),
    ("migration.rollback_pointer", MIGRATION),
    ("migration.residual_count", MIGRATION),
    ("migration.cutover_receipt", MIGRATION),
    ("ui.model_graph", DESKTOP),
    ("ui.selected_model_id", DESKTOP),
    ("ui.selected_node_id", DESKTOP),
    ("ui.diagnostic_summary", DESKTOP),
    ("prompt.card_projection_only", PROJECTION),
    ("prompt.sleep_model_maintenance", MAINTENANCE),
    ("prompt.dream_read_only", MAINTENANCE),
    ("retired.card.schema_version", MIGRATION),
    ("retired.then.guidance", MIGRATION),
    ("retired.related_cards_authority", MIGRATION),
    ("retired.flat_yaml_search", MIGRATION),
    ("retired.floating_head_resolution", MIGRATION),
)

FIELD_READER_MAP = (
    ("card.logicguard_model_id", PROJECTION),
    ("card.logicguard_node_id", PROJECTION),
    ("card.logicguard_revision_id", PROJECTION),
    ("card.logicguard_mesh_revision_id", PROJECTION),
    ("card.projection_digest", SEARCH),
    ("index.authority_generation_id", SEARCH),
    ("index.logicguard_model_id", SEARCH),
    ("index.logicguard_node_id", SEARCH),
    ("index.logicguard_revision_id", SEARCH),
    ("index.logicguard_mesh_revision_id", SEARCH),
    ("sleep.model_change_set", LIFECYCLE),
    ("sleep.mesh_change_set", LIFECYCLE),
    ("dream.pinned_mesh_revision_id", DREAM),
    ("dream.simulation_plan", DREAM),
    ("dream.sleep_handoff", LIFECYCLE),
    ("ui.model_graph", DESKTOP),
)

FIELD_WRITER_MAP = (
    ("card.projection_schema_version", PROJECTION),
    ("card.projection_digest", PROJECTION),
    ("card.if.notes", PROJECTION),
    ("card.action.description", PROJECTION),
    ("card.predict.expected_result", PROJECTION),
    ("card.use.guidance", PROJECTION),
    ("card.related_cards", PROJECTION),
    ("index.authority_generation_id", ACTIVE_INDEX),
    ("index.logicguard_model_id", ACTIVE_INDEX),
    ("index.logicguard_node_id", ACTIVE_INDEX),
    ("index.logicguard_revision_id", ACTIVE_INDEX),
    ("index.logicguard_mesh_id", ACTIVE_INDEX),
    ("index.logicguard_mesh_revision_id", ACTIVE_INDEX),
    ("index.projection_digest", ACTIVE_INDEX),
    ("sleep.model_change_set", MAINTENANCE),
    ("sleep.mesh_change_set", MAINTENANCE),
    ("sleep.diagnostics", MAINTENANCE),
    ("sleep.commit_receipt", MAINTENANCE),
    ("dream.pinned_mesh_revision_id", MAINTENANCE),
    ("dream.simulation_plan", MAINTENANCE),
    ("dream.simulation_receipt", DREAM),
    ("dream.sleep_handoff", MAINTENANCE),
    ("migration.output_generation_id", MIGRATION),
    ("migration.rollback_pointer", MIGRATION),
    ("migration.residual_count", MIGRATION),
    ("migration.cutover_receipt", MIGRATION),
    ("ui.model_graph", DESKTOP),
    ("ui.selected_model_id", DESKTOP),
    ("ui.selected_node_id", DESKTOP),
    ("ui.diagnostic_summary", DESKTOP),
)

PUBLIC_ENTRYPOINT_MAP = (
    ("local_kb.lifecycle.run_incremental_sleep", LIFECYCLE),
    ("local_kb.dream.run_dream_maintenance", DREAM),
    ("local_kb.search.search_with_receipt", SEARCH),
    ("local_kb.active_index.build_active_index", ACTIVE_INDEX),
    ("local_kb.desktop_app.KbDesktopApp", DESKTOP),
    ("local_kb.maintenance_migration.run_versioned_migration", MIGRATION),
)

VALIDATION_BOUNDARIES = (
    "unit:logicguard-model-store-and-exact-revision",
    "unit:card-projection-roundtrip-and-digest",
    "unit:sleep-dream-model-maintenance-primitives",
    "integration:sleep-model-mesh-projection-index-atomic-generation",
    "integration:dream-pinned-simulation-read-only-handoff",
    "integration:search-exact-model-neighborhood-no-flat-fallback",
    "integration:migration-direct-to-current-or-rollback",
    "integration:public-private-candidate-store-isolation",
    "ui:desktop-single-recommended-model-graph",
)


def _items_for(mapping: tuple[tuple[str, str], ...], module_id: str) -> tuple[str, ...]:
    return tuple(item_id for item_id, owner in mapping if owner == module_id)


def _module(module_id: str, path: str, layer: str, rationale: str) -> TargetModuleRecommendation:
    return TargetModuleRecommendation(
        module_id=module_id,
        path=path,
        layer=layer,
        owns_function_blocks=_items_for(FUNCTION_BLOCK_MAP, module_id),
        owns_state=_items_for(STATE_OWNER_MAP, module_id),
        owns_side_effects=_items_for(SIDE_EFFECT_OWNER_MAP, module_id),
        owns_config=_items_for(CONFIG_OWNER_MAP, module_id),
        owns_fields=_items_for(FIELD_OWNER_MAP, module_id),
        reads_fields=_items_for(FIELD_READER_MAP, module_id),
        writes_fields=_items_for(FIELD_WRITER_MAP, module_id),
        public_entrypoints=_items_for(PUBLIC_ENTRYPOINT_MAP, module_id),
        validation_boundaries=VALIDATION_BOUNDARIES,
        rationale=rationale,
    )


def build_recommendation() -> CodeStructureRecommendation:
    modules = (
        _module(
            MODELS,
            "local_kb/logicguard_models.py",
            "shared-kernel",
            "Owns scope-separated LogicGuard stores, exact revision binding, and bounded graph materialization.",
        ),
        _module(
            PROJECTION,
            "local_kb/model_projection.py",
            "projection",
            "Derives every human-readable card field from one exact canonical model binding and digest.",
        ),
        _module(
            MAINTENANCE,
            "local_kb/model_maintenance.py",
            "domain-service",
            "Provides staged Sleep changes, model diagnostics, and read-only Dream simulation helpers without becoming a public controller.",
        ),
        _module(
            LIFECYCLE,
            "local_kb/lifecycle.py",
            "facade",
            "Retains the sole Sleep entrypoint, lifecycle decision, watermark, and completion boundary.",
        ),
        _module(
            DREAM,
            "local_kb/dream.py",
            "facade",
            "Retains the sole Dream entrypoint and immutable experiment-receipt owner.",
        ),
        _module(
            SEARCH,
            "local_kb/search.py",
            "facade",
            "Retains the sole retrieval API while consuming exact model-neighborhood results.",
        ),
        _module(
            ACTIVE_INDEX,
            "local_kb/active_index.py",
            "projection-index",
            "Publishes the sole active generation index with exact model, mesh, and digest bindings.",
        ),
        _module(
            MIGRATION,
            "local_kb/maintenance_migration.py",
            "upgrade-owner",
            "Owns versioned direct-to-current conversion, residual proof, atomic cutover, and rollback.",
        ),
        _module(
            DESKTOP,
            "local_kb/desktop_app.py",
            "ui-facade",
            "Renders the recommended model graph and diagnostics without owning canonical data or route decisions.",
        ),
    )
    return CodeStructureRecommendation(
        recommendation_id=RECOMMENDATION_ID,
        source_model_id=MODEL_ID,
        source_model_path=".flowguard/khaos_brain_logicguard_authority_cutover.py",
        source_model_evidence_tier="hazard_green",
        parent_module_id="local_kb",
        target_modules=modules,
        function_block_map=FUNCTION_BLOCK_MAP,
        state_owner_map=STATE_OWNER_MAP,
        side_effect_owner_map=SIDE_EFFECT_OWNER_MAP,
        config_owner_map=CONFIG_OWNER_MAP,
        field_owner_map=FIELD_OWNER_MAP,
        field_reader_map=FIELD_READER_MAP,
        field_writer_map=FIELD_WRITER_MAP,
        public_entrypoint_map=PUBLIC_ENTRYPOINT_MAP,
        facade_module_id=LIFECYCLE,
        shared_kernel_module_id=MODELS,
        variant_adapter_module_ids=(PROJECTION, MAINTENANCE),
        validation_boundaries=VALIDATION_BOUNDARIES,
        rationale=(
            "The FlowGuard child model divides immutable LogicGuard authority, deterministic display projection, "
            "shared maintenance primitives, and existing public facades.  This prevents a monolithic controller "
            "and preserves exactly one Sleep, Dream, search, index-publication, and migration owner."
        ),
        hierarchical_model_used=True,
    )


def build_known_bad() -> CodeStructureRecommendation:
    current = build_recommendation()
    return replace(
        current,
        function_block_map=(*current.function_block_map, ("CommitSleepModelChangeBlock", LIFECYCLE)),
        side_effect_owner_map=(*current.side_effect_owner_map, ("hidden_parallel_index_write", "local_kb.logicguard_controller")),
        field_owner_map=tuple(pair for pair in current.field_owner_map if pair[0] != "dream.sleep_handoff"),
        public_entrypoint_map=(*current.public_entrypoint_map, ("local_kb.logicguard_controller.search", "local_kb.logicguard_controller")),
    )


def main() -> int:
    current = review_code_structure_recommendation(build_recommendation())
    known_bad = review_code_structure_recommendation(build_known_bad())
    payload = {
        "artifact_type": "khaos_brain_logicguard_native_code_structure_recommendation",
        "current": current.to_dict(),
        "known_bad": known_bad.to_dict(),
        "target_module_count": len(build_recommendation().target_modules),
        "function_block_count": len(FUNCTION_BLOCK_MAP),
        "field_owner_count": len(FIELD_OWNER_MAP),
        "ok": current.ok and not known_bad.ok,
        "claim_boundary": (
            "This artifact proves that the planned modules have registered, non-duplicated FunctionBlock, state, "
            "side-effect, config, field, and public-entrypoint owners and that representative parallel-controller "
            "shapes are rejected. It does not prove implementation, imports, tests, migration, UI behavior, "
            "installed skill parity, or release readiness."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
