"""Full existing-model preflight for the LogicGuard-native Khaos Brain cutover."""

from __future__ import annotations

import json

from flowguard import (
    BehaviorCommitmentHit,
    DuplicateBoundaryRisk,
    ExistingIntentSurface,
    ExistingModelPreflight,
    ExistingOwnershipSnapshot,
    ModelContextHit,
    REUSE_DECISION_ADD_CHILD_MODEL,
    review_existing_model_preflight,
)


LEDGER_FINGERPRINT = (
    "66468c3985e7ed6f0ab59d2bd16b9d0f77b27b08070481bf5c0a5e32207e8c50"
)


def current_preflight() -> ExistingModelPreflight:
    """Reuse current owners and add one child boundary for model authority."""

    return ExistingModelPreflight(
        "khaos-brain-logicguard-native-20260714",
        (
            "Replace standalone YAML card authority with canonical LogicGuard models; "
            "make cards projections, Sleep assemble ModelMesh revisions, Dream validate "
            "model gaps/counterexamples, and retrieval navigate model neighborhoods."
        ),
        mode="full",
        existing_modeled_system=True,
        model_search_performed=True,
        search_paths=(
            ".flowguard/behavior_commitment_ledger/ledger.json",
            ".flowguard/khaos_brain_function_flow.py",
            ".flowguard/khaos_brain_governance_flow.py",
            ".flowguard/kb_convergence_upgrade_model.py",
            ".flowguard/kb_canonical_interface_flow.py",
            ".flowguard/card_visual_merge_flow.py",
            "PROJECT_SPEC.md",
            "openspec/changes/converge-kb-learning-and-upgrade-migration",
            "local_kb",
            ".agents/skills/local-kb-retrieve",
            "../LogicGuard_20260518/logicguard",
        ),
        behavior_lookup_required=True,
        behavior_lookup_status="performed",
        primary_behavior_plane="product_runtime",
        primary_commitment_hits=(
            BehaviorCommitmentHit(
                "commitment:kb-retrieval-current-index",
                "product_runtime",
                "kb_convergence_upgrade_model.LifecycleConvergenceBlock",
                175,
                match_reasons=(
                    "path_pattern:local_kb/search.py",
                    "task_term:retrieval",
                    "task_term:active-index",
                ),
            ),
        ),
        plane_ambiguity=False,
        ledger_fingerprint=LEDGER_FINGERPRINT,
        behavior_lookup_reason=(
            "The current ledger owns indexed retrieval but has no exact product-runtime "
            "commitment for canonical card models, Sleep model assembly, or Dream model "
            "validation. Those are coverage gaps under the same Khaos Brain product plane, "
            "not reasons to promote automation-policy matches into product owners."
        ),
        relevant_models=(
            ModelContextHit(
                "kb_convergence_upgrade_model.LifecycleConvergenceBlock",
                model_path=".flowguard/kb_convergence_upgrade_model.py",
                evidence_id="focused:lifecycle-known-bad:20260714",
                evidence_tier="abstract_green",
                responsibilities=(
                    "observation and candidate lifecycle",
                    "active index authority",
                    "Sleep watermark and Dream handoff convergence",
                ),
                function_blocks=("LifecycleConvergenceBlock",),
                state_owned=(
                    "dispositions",
                    "entry_statuses",
                    "active_index",
                    "watermark",
                    "dream_closed",
                    "sleep_handoffs",
                ),
                side_effects_owned=(
                    "index_publish",
                    "sleep_handoff",
                    "dream_write",
                ),
                public_entrypoints=(
                    "local_kb.lifecycle.run_incremental_sleep",
                    "local_kb.search.search_with_receipt",
                ),
                fields_owned=(
                    "field:entry.status",
                    "field:entry.lifecycle",
                    "field:active_index.generation",
                    "field:sleep.watermark",
                    "field:dream.evidence_fingerprint",
                ),
                validation_evidence=(
                    "model_check:pass",
                    "known_bad_proof:13/13 rejected",
                    "aggregate automation child is separately not_run_timeout",
                ),
            ),
            ModelContextHit(
                "khaos-governance",
                model_path=".flowguard/khaos_brain_governance_flow.py",
                evidence_id="model-inventory:khaos-governance:20260714",
                evidence_tier="candidate_only",
                responsibilities=(
                    "candidate review debt",
                    "Dream-to-Sleep handoff",
                    "route governance before card creation",
                ),
                function_blocks=(
                    "CandidateBacklogBlock",
                    "DreamSleepHandoffBlock",
                    "RouteGovernanceBlock",
                    "GovernanceBlock",
                ),
                state_owned=(
                    "candidate_review_debt",
                    "dream_handoff_status",
                    "route_status",
                ),
                side_effects_owned=("candidate_action", "dream_handoff_review"),
                public_entrypoints=("scheduled Sleep governance",),
                validation_evidence=("inventory current; full governance replay pending"),
            ),
            ModelContextHit(
                "khaos-canonical-interface",
                model_path=".flowguard/kb_canonical_interface_flow.py",
                evidence_id="model-inventory:canonical-interface:20260714",
                evidence_tier="candidate_only",
                responsibilities=(
                    "canonical machine fields and routes",
                    "localized UI projection",
                ),
                function_blocks=(
                    "CanonicalDataBlock",
                    "MachineCliBlock",
                    "UiDisplayBlock",
                ),
                state_owned=(
                    "canonical_route",
                    "cli_output_surface",
                    "ui_output_surface",
                ),
                side_effects_owned=("machine_json", "localized_display"),
                public_entrypoints=("CLI payload", "desktop card UI"),
                validation_evidence=("owner runner scheduled after preflight"),
            ),
            ModelContextHit(
                "khaos-card-visual",
                model_path=".flowguard/card_visual_merge_flow.py",
                evidence_id="model-inventory:card-visual:20260714",
                evidence_tier="candidate_only",
                responsibilities=("desktop card grid and detail projection",),
                function_blocks=("ProductionVisualMergeBlock",),
                state_owned=("card_payload_hash", "retrieval_route"),
                side_effects_owned=("render_grid", "render_detail"),
                public_entrypoints=("local_kb.desktop_app.KbDesktopApp",),
                validation_evidence=("owner runner scheduled after preflight"),
            ),
            ModelContextHit(
                "logicguard-p0-p2-runtime",
                model_path="../LogicGuard_20260518/logicguard",
                evidence_id="logicguard:p0-p2:current-local-receipts",
                evidence_tier="production_or_conformance",
                responsibilities=(
                    "canonical ArgumentBlock storage",
                    "revision-pinned ModelMesh",
                    "structural evaluation and sparse simulation",
                    "source-library and project graph projection",
                ),
                public_entrypoints=(
                    "logicguard.ModelStore",
                    "logicguard.ModelMeshStore",
                    "logicguard.evaluate_mesh_revision",
                    "logicguard.simulate_mesh_revision",
                ),
                rationale=(
                    "This is the implementation dependency and model authority substrate; "
                    "it does not take over Khaos lifecycle or scheduling ownership."
                ),
            ),
        ),
        ownership_snapshot=ExistingOwnershipSnapshot(
            function_block_owners=(
                (
                    "LifecycleConvergenceBlock",
                    "kb_convergence_upgrade_model.LifecycleConvergenceBlock",
                ),
                ("GovernanceBlock", "khaos-governance"),
                ("CanonicalDataBlock", "khaos-canonical-interface"),
                ("ProductionVisualMergeBlock", "khaos-card-visual"),
            ),
            state_owners=(
                (
                    "entry lifecycle and retrieval eligibility",
                    "kb_convergence_upgrade_model.LifecycleConvergenceBlock",
                ),
                ("Sleep/Dream governance", "khaos-governance"),
                ("canonical/display split", "khaos-canonical-interface"),
                ("desktop visual projection", "khaos-card-visual"),
            ),
            field_owners=(
                (
                    "field:entry.status",
                    "kb_convergence_upgrade_model.LifecycleConvergenceBlock",
                ),
                (
                    "field:active_index.generation",
                    "kb_convergence_upgrade_model.LifecycleConvergenceBlock",
                ),
                ("field:card.i18n", "khaos-canonical-interface"),
                ("field:card.yaml_shape", "local_kb.store"),
            ),
            side_effect_owners=(
                (
                    "active index publication",
                    "kb_convergence_upgrade_model.LifecycleConvergenceBlock",
                ),
                ("Dream-to-Sleep handoff", "khaos-governance"),
                ("desktop render", "khaos-card-visual"),
            ),
            public_entrypoint_owners=(
                (
                    "local_kb.search.search_with_receipt",
                    "kb_convergence_upgrade_model.LifecycleConvergenceBlock",
                ),
                (
                    "local_kb.lifecycle.run_incremental_sleep",
                    "kb_convergence_upgrade_model.LifecycleConvergenceBlock",
                ),
                ("local_kb.dream.run_dream_maintenance", "khaos-governance"),
                ("local_kb.desktop_app.KbDesktopApp", "khaos-card-visual"),
            ),
            responsibility_owners=(
                (
                    "lifecycle and eligibility",
                    "kb_convergence_upgrade_model.LifecycleConvergenceBlock",
                ),
                ("maintenance decision ownership", "khaos-governance"),
                ("argument graph semantics", "logicguard-p0-p2-runtime"),
            ),
        ),
        reuse_decision=REUSE_DECISION_ADD_CHILD_MODEL,
        downstream_routes=(
            "field_lifecycle_mesh",
            "model_mesh_maintenance",
            "code_structure_recommendation",
            "development_process_flow",
            "model_test_alignment",
            "test_mesh_maintenance",
            "ui_flow_structure",
        ),
        rationale=(
            "Add one child model for the authority cutover while extending the existing "
            "lifecycle, governance, retrieval, and UI owners. LogicGuard owns argument "
            "semantics; Khaos Brain continues to own lifecycle, scheduling, privacy, and "
            "retrieval policy. No parallel search, Sleep, Dream, or YAML authority survives."
        ),
        proposed_new_boundaries=(
            "child-model:khaos-brain-logicguard-authority-cutover",
            "module:local_kb.logicguard_models",
            "module:local_kb.model_projection",
            "module:local_kb.model_maintenance",
        ),
        duplicate_risks=(
            DuplicateBoundaryRisk(
                "state",
                "entry lifecycle and retrieval eligibility",
                "kb_convergence_upgrade_model.LifecycleConvergenceBlock",
                proposed_owner_id="child-model:khaos-brain-logicguard-authority-cutover",
                resolution="existing_owner_retained",
                rationale="The child consumes lifecycle state and never owns status or eligibility.",
                resolved=True,
            ),
            DuplicateBoundaryRisk(
                "side_effect",
                "active index publication",
                "kb-convergence-lifecycle",
                proposed_owner_id="module:local_kb.model_projection",
                resolution="delegated_projection",
                rationale="Projection supplies index rows; the lifecycle owner alone commits the index.",
                resolved=True,
            ),
            DuplicateBoundaryRisk(
                "responsibility",
                "Sleep decision ownership",
                "khaos-governance",
                proposed_owner_id="module:local_kb.model_maintenance",
                resolution="existing_owner_retained",
                rationale="The module executes a selected model plan; Sleep remains the sole decision owner.",
                resolved=True,
            ),
            DuplicateBoundaryRisk(
                "public_entrypoint",
                "predictive retrieval",
                "local_kb.search.search_with_receipt",
                proposed_owner_id="module:local_kb.logicguard_models",
                resolution="extend_existing_entrypoint",
                rationale="The current search API reads model-native index authority; no second search API is added.",
                resolved=True,
            ),
            DuplicateBoundaryRisk(
                "authority",
                "standalone YAML card semantics",
                "local_kb.store",
                proposed_owner_id="logicguard-p0-p2-runtime",
                resolution="direct_current_replacement",
                rationale="Upgrade migrates every card to LogicGuard authority and leaves YAML only as a validated projection.",
                resolved=True,
            ),
        ),
        behavior_field_ids=(
            "field:card.logicguard_model_id",
            "field:card.logicguard_node_id",
            "field:card.logicguard_revision_id",
            "field:card.projection_digest",
            "field:sleep.mesh_revision_id",
            "field:dream.simulation_receipt_id",
            "field:card.yaml_shape",
            "field:card.related_cards",
        ),
        field_lifecycle_required=True,
        field_lifecycle_model_ids=(
            "kb_convergence_upgrade_model.UpgradeMigrationBlock",
            "child-model:khaos-brain-logicguard-authority-cutover",
        ),
        affected_business_intent_id="intent:serve-predictive-retrieval",
        selected_commitment_id="commitment:kb-retrieval-current-index",
        selected_primary_path_id="path:kb-retrieval-current-index",
        expected_surface_ids=(
            "surface:card-yaml-storage",
            "surface:active-index-helper",
            "surface:retrieval-api",
            "surface:retrieval-cli",
            "surface:desktop-card-ui",
            "surface:old-card-authority-migration",
        ),
        intent_surfaces=(
            ExistingIntentSurface(
                "surface:card-yaml-storage",
                surface_kind="helper",
                business_intent_id="intent:serve-predictive-retrieval",
                behavior_commitment_id="commitment:kb-retrieval-current-index",
                business_path_id="local_kb.store.load_entries",
                primary_path_id="path:kb-retrieval-current-index",
                expected_terminal="current_card_loaded_or_visible_failure",
                state_writes=("kb/public", "kb/private", "kb/candidates"),
                side_effects=("yaml_write",),
                owner_id="local_kb.store",
                source_ref="local_kb/store.py",
                evidence_ids=("inventory:store:20260714",),
                validation_boundary="direct migration and projection parity",
            ),
            ExistingIntentSurface(
                "surface:active-index-helper",
                surface_kind="helper",
                business_intent_id="intent:serve-predictive-retrieval",
                behavior_commitment_id="commitment:kb-retrieval-current-index",
                business_path_id="local_kb.active_index.load_active_entries",
                primary_path_id="path:kb-retrieval-current-index",
                expected_terminal="validated_current_index_or_visible_unavailable",
                owner_id="kb_convergence_upgrade_model.LifecycleConvergenceBlock",
                source_ref="local_kb/active_index.py",
                evidence_ids=("commitment:kb-retrieval-current-index",),
            ),
            ExistingIntentSurface(
                "surface:retrieval-api",
                surface_kind="api",
                business_intent_id="intent:serve-predictive-retrieval",
                behavior_commitment_id="commitment:kb-retrieval-current-index",
                business_path_id="local_kb.search.search_with_receipt",
                primary_path_id="path:kb-retrieval-current-index",
                expected_terminal="ranked_current_results_or_no_card",
                owner_id="kb_convergence_upgrade_model.LifecycleConvergenceBlock",
                source_ref="local_kb/search.py",
                evidence_ids=("commitment:kb-retrieval-current-index",),
            ),
            ExistingIntentSurface(
                "surface:retrieval-cli",
                surface_kind="cli",
                business_intent_id="intent:serve-predictive-retrieval",
                behavior_commitment_id="commitment:kb-retrieval-current-index",
                business_path_id="scripts.kb_search.main",
                primary_path_id="path:kb-retrieval-current-index",
                expected_terminal="canonical_json_results_or_visible_failure",
                owner_id="kb_convergence_upgrade_model.LifecycleConvergenceBlock",
                source_ref=".agents/skills/local-kb-retrieve/scripts/kb_search.py",
                evidence_ids=("surface:retrieval-cli",),
            ),
            ExistingIntentSurface(
                "surface:desktop-card-ui",
                surface_kind="ui",
                business_intent_id="intent:serve-predictive-retrieval",
                behavior_commitment_id="commitment:kb-retrieval-current-index",
                business_path_id="local_kb.desktop_app.KbDesktopApp",
                primary_path_id="path:kb-retrieval-current-index",
                expected_terminal="card_projection_and_model_neighborhood_visible",
                owner_id="khaos-card-visual",
                source_ref="local_kb/desktop_app.py",
                evidence_ids=("model-inventory:card-visual:20260714",),
            ),
            ExistingIntentSurface(
                "surface:old-card-authority-migration",
                surface_kind="compatibility",
                business_intent_id="intent:serve-predictive-retrieval",
                behavior_commitment_id="commitment:kb-retrieval-current-index",
                business_path_id="local_kb.maintenance_migration",
                primary_path_id="path:kb-retrieval-current-index",
                expected_terminal="all_cards_model_bound_zero_old_authority_or_rollback",
                state_writes=("migration_journal", "model_store", "card_projection"),
                side_effects=("direct_current_replacement",),
                owner_id="kb_convergence_upgrade_model.UpgradeMigrationBlock",
                source_ref="local_kb/maintenance_migration.py",
                evidence_ids=("model-inventory:migration:20260714",),
            ),
        ),
        surface_inventory_revision="khaos-logicguard-native-surfaces:v1",
        surface_inventory_evidence_ids=(
            "ledger:66468c3985e7",
            "inventory:local-kb-definitions:20260714",
            "inventory:flowguard-models:20260714",
        ),
        typed_external_difference_ids=(
            "difference:logicguard-is-argument-runtime-not-khaos-lifecycle-owner",
            "difference:openspec-is-development-process-provider-not-product-owner",
        ),
        require_complete_surface_inventory=True,
    )


def broken_parallel_authority() -> ExistingModelPreflight:
    """Known-bad calibration: a second search and Sleep authority must fail."""

    base = current_preflight()
    return ExistingModelPreflight(
        "khaos-brain-parallel-logicguard-authority-bad",
        "Add separate LogicGuard search and Sleep controllers beside Khaos Brain.",
        mode="full",
        model_search_performed=True,
        search_paths=base.search_paths,
        behavior_lookup_required=True,
        behavior_lookup_status="performed",
        primary_behavior_plane="product_runtime",
        primary_commitment_hits=base.primary_commitment_hits,
        ledger_fingerprint=LEDGER_FINGERPRINT,
        relevant_models=base.relevant_models,
        ownership_snapshot=base.ownership_snapshot,
        reuse_decision=REUSE_DECISION_ADD_CHILD_MODEL,
        downstream_routes=("model_mesh_maintenance",),
        proposed_new_boundaries=("parallel-logicguard-search", "parallel-logicguard-sleep"),
        duplicate_risks=(
            DuplicateBoundaryRisk(
                "public_entrypoint",
                "predictive retrieval",
                "local_kb.search.search_with_receipt",
                proposed_owner_id="parallel-logicguard-search",
            ),
            DuplicateBoundaryRisk(
                "responsibility",
                "Sleep decision ownership",
                "khaos-governance",
                proposed_owner_id="parallel-logicguard-sleep",
            ),
        ),
        rationale="The proposed controllers duplicate current owners and have no disposition.",
    )


def main() -> int:
    current = review_existing_model_preflight(current_preflight())
    broken = review_existing_model_preflight(broken_parallel_authority())
    payload = {
        "artifact_type": "khaos_brain_logicguard_native_existing_model_preflight",
        "current": current.to_dict(),
        "known_bad": broken.to_dict(),
        "ok": current.ok and not broken.ok,
        "claim_boundary": (
            "This full preflight proves existing-owner lookup, surface inventory, reuse, "
            "and duplicate-boundary disposition only. It does not prove the new model, "
            "implementation, migration, tests, SkillGuard, UI, or release."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
