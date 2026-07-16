"""FlowGuard ModelMesh for the LogicGuard-native Khaos Brain architecture."""

from __future__ import annotations

import json
from dataclasses import replace

from flowguard import (
    ChildModelEvidence,
    ChildReattachmentContract,
    HierarchyCoverageItem,
    HierarchyPartitionMap,
    MeshClosureJoin,
    MeshClosureModel,
    MeshClosureTerminal,
    MeshClosureTransition,
    ModelTargetSplitDerivation,
    review_hierarchical_mesh,
)


PARENT_ID = "khaos_brain_product_model_mesh"
LIFECYCLE = "kb_convergence_upgrade_model.LifecycleConvergenceBlock"
GOVERNANCE = "khaos_brain_governance_flow.GovernanceBlock"
AUTHORITY = "khaos_brain_logicguard_authority_cutover"
INTERFACE = "kb_canonical_interface_flow.CanonicalDataBlock"
VISUAL = "card_visual_merge_flow.ProductionVisualMergeBlock"
LOGICGUARD = "logicguard-p0-p2-runtime"


def children() -> tuple[ChildModelEvidence, ...]:
    return (
        ChildModelEvidence(
            model_id=LIFECYCLE,
            evidence_id="focused:lifecycle-known-bad-13-of-13:20260714",
            risk_boundary="observation/candidate lifecycle, eligibility, Sleep watermark, and active-index publication",
            inputs_accepted=("observation", "candidate transition", "Sleep commit result", "Dream handoff acknowledgement"),
            outputs_emitted=(
                "lifecycle_delta_selected",
                "retrieval_eligibility_snapshot",
                "sleep_watermark_committed",
                "active_index_generation_published",
            ),
            state_owned=("entry_lifecycle_state", "retrieval_eligibility", "sleep_watermark", "active_index_pointer"),
            side_effects_owned=("lifecycle_event_commit", "active_index_publication", "sleep_watermark_advance"),
            functional_areas=("lifecycle_and_index",),
            contracts_in=("contract:authority.complete_generation",),
            contracts_out=("contract:lifecycle.selected_delta", "contract:lifecycle.current_index"),
            depends_on=(GOVERNANCE, AUTHORITY),
            evidence_tier="hazard_green",
            functions_owned=("LifecycleConvergenceBlock",),
            invariants_owned=("eligible_status_only", "watermark_after_complete_commit"),
            risk_classes=("lifecycle_debt", "stale_index", "watermark_partial_commit"),
            validation_evidence=("model_check:pass", "known_bad:13/13 rejected"),
        ),
        ChildModelEvidence(
            model_id=GOVERNANCE,
            evidence_id="abstract:khaos-governance:20260714-current",
            risk_boundary="Sleep/Dream decision ownership, handoff closure, and route governance",
            inputs_accepted=("lifecycle delta", "model gap summary", "Dream simulation evidence", "candidate review debt"),
            outputs_emitted=("sleep_model_change_decision", "dream_handoff_decision"),
            state_owned=("sleep_decision_state", "dream_handoff_review_state", "route_governance_state"),
            side_effects_owned=("sleep_action_selection", "dream_handoff_disposition"),
            functional_areas=("maintenance_governance",),
            contracts_in=("contract:authority.gap_summary", "contract:authority.dream_handoff"),
            contracts_out=("contract:governance.sleep_decision", "contract:governance.dream_disposition"),
            depends_on=(LIFECYCLE, AUTHORITY),
            evidence_tier="hazard_green",
            functions_owned=("GovernanceBlock",),
            invariants_owned=("dream_handoff_must_close", "candidate_backlog_must_close"),
            risk_classes=("duplicate_sleep_owner", "unreviewed_dream_handoff", "unsafe_promotion"),
            validation_evidence=("accepted:pass", "known_bad:12/12 rejected"),
        ),
        ChildModelEvidence(
            model_id=AUTHORITY,
            evidence_id="abstract:khaos-logicguard-authority-cutover:20260714-current",
            risk_boundary="exact model/mesh authority, projection binding, model-native retrieval, Dream read-only, and atomic cutover",
            inputs_accepted=("Sleep model change decision", "versioned legacy card input", "retrieval query", "Dream experiment request"),
            outputs_emitted=(
                "model_generation_committed",
                "model_binding_validated",
                "model_native_retrieval_result",
                "dream_simulation_handoff",
                "rollback_safe",
            ),
            state_owned=("model_revision_heads", "mesh_revision_heads", "projection_generation_stage", "authority_generation_pointer"),
            side_effects_owned=("model_mesh_cas_commit", "projection_staging", "migration_generation_cutover"),
            functional_areas=("logicguard_authority_cutover",),
            contracts_in=("contract:governance.sleep_decision", "contract:lifecycle.selected_delta"),
            contracts_out=(
                "contract:authority.complete_generation",
                "contract:authority.exact_binding",
                "contract:authority.model_retrieval",
                "contract:authority.dream_handoff",
            ),
            depends_on=(LOGICGUARD, LIFECYCLE, GOVERNANCE),
            evidence_tier="hazard_green",
            functions_owned=(
                "BindCardModelBlock",
                "ValidateCardBindingBlock",
                "PlanSleepModelChangeBlock",
                "CommitSleepModelChangeBlock",
                "ValidateDreamMeshBlock",
                "RetrieveModelNeighborhoodBlock",
                "PublishAuthorityGenerationBlock",
            ),
            invariants_owned=(
                "exact_current_authority",
                "model_first_publication",
                "sole_owner_boundaries",
                "dream_exact_read_only",
                "retrieval_model_native",
                "privacy_scope_closed",
                "migration_atomic_or_blocked",
            ),
            risk_classes=("dual_authority", "partial_generation", "flat_fallback", "privacy_scope_leak"),
            validation_evidence=(
                "correct:4/4 pass",
                "known_bad:14/14 rejected",
                "contracts:154 steps pass",
                "loop/progress/refinement:pass",
            ),
        ),
        ChildModelEvidence(
            model_id=INTERFACE,
            evidence_id="abstract:canonical-interface:20260714-current",
            risk_boundary="canonical machine identities and localized display projection",
            inputs_accepted=("exact model-native retrieval result", "canonical model graph payload"),
            outputs_emitted=("localized_model_projection",),
            state_owned=("canonical_display_projection_state",),
            side_effects_owned=("localized_view_model_projection",),
            functional_areas=("canonical_display_interface",),
            contracts_in=("contract:authority.model_retrieval",),
            contracts_out=("contract:interface.localized_model_view",),
            depends_on=(AUTHORITY,),
            evidence_tier="hazard_green",
            functions_owned=("CanonicalDataBlock", "MachineCliBlock", "UiDisplayBlock"),
            invariants_owned=("no_localized_route_in_canonical_state", "no_raw_unicode_at_cli_boundary"),
            risk_classes=("canonical_localization_mix",),
            validation_evidence=("accepted:pass", "known_bad:2/2 rejected"),
        ),
        ChildModelEvidence(
            model_id=VISUAL,
            evidence_id="abstract:card-visual:20260714-current",
            risk_boundary="desktop graph/detail rendering without data or route mutation",
            inputs_accepted=("localized model projection",),
            outputs_emitted=("desktop_graph_rendered",),
            state_owned=("desktop_model_view_render_state",),
            side_effects_owned=("desktop_graph_render",),
            functional_areas=("desktop_visual_projection",),
            contracts_in=("contract:interface.localized_model_view",),
            contracts_out=("contract:desktop.model_graph_visible",),
            depends_on=(INTERFACE,),
            evidence_tier="hazard_green",
            functions_owned=("ProductionVisualMergeBlock",),
            invariants_owned=("no_data_or_route_mutation", "production_entry_preserved"),
            risk_classes=("stale_or_mutating_desktop_projection",),
            validation_evidence=("explorer:pass", "known_bad:3/3 rejected", "loop/contracts:pass"),
        ),
        ChildModelEvidence(
            model_id=LOGICGUARD,
            evidence_id="logicguard:p0-p2:current-local-receipts:20260714",
            risk_boundary="immutable argument models, exact ModelMesh, structural evaluation, and sparse simulation",
            inputs_accepted=("canonical argument payload", "mesh definition", "materialization request", "simulation perturbation"),
            outputs_emitted=("exact_model_revision", "exact_mesh_revision", "structural_diagnostic", "simulation_delta"),
            state_owned=("logicguard_model_store_internal", "logicguard_mesh_store_internal", "logicguard_overlay_catalog_internal"),
            side_effects_owned=("logicguard_immutable_revision_commit", "logicguard_simulation_receipt"),
            functional_areas=("argument_model_runtime",),
            contracts_in=("contract:authority.logicguard_payload",),
            contracts_out=("contract:logicguard.exact_revision", "contract:logicguard.diagnostics", "contract:logicguard.simulation"),
            evidence_tier="conformance_green",
            functions_owned=("FileModelStore", "FileModelMeshStore", "materialize_mesh", "evaluate_materialized_mesh", "simulate_mesh"),
            invariants_owned=("immutable_revision", "revision_pinned_mesh", "typed_provenance", "sparse_simulation_no_mutation"),
            risk_classes=("argument_store_corruption", "mesh_head_drift", "ungrounded_cross_model_edge"),
            validation_evidence=("P0:177 pass", "P1:265 pass", "P2:35 pass", "scale receipt:pass"),
        ),
    )


def coverage_items() -> tuple[HierarchyCoverageItem, ...]:
    values = (
        ("item:observation-candidate-lifecycle", "function", LIFECYCLE),
        ("item:retrieval-eligibility", "state", LIFECYCLE),
        ("item:sleep-watermark", "state", LIFECYCLE),
        ("item:active-index-publication", "side_effect", LIFECYCLE),
        ("item:sleep-decision", "function", GOVERNANCE),
        ("item:dream-handoff-decision", "function", GOVERNANCE),
        ("item:route-governance", "state", GOVERNANCE),
        ("item:exact-model-mesh-binding", "function", AUTHORITY),
        ("item:model-first-generation", "side_effect", AUTHORITY),
        ("item:model-native-retrieval-contract", "function", AUTHORITY),
        ("item:dream-read-only-contract", "invariant", AUTHORITY),
        ("item:privacy-scope-boundary", "invariant", AUTHORITY),
        ("item:canonical-display-separation", "function", INTERFACE),
        ("item:desktop-model-graph-render", "side_effect", VISUAL),
        ("item:argument-model-semantics", "shared_kernel", LOGICGUARD),
        ("item:revision-pinned-model-mesh", "shared_kernel", LOGICGUARD),
        ("item:structural-evaluation-simulation", "shared_kernel", LOGICGUARD),
    )
    return tuple(
        HierarchyCoverageItem(
            item_id,
            item_type=item_type,
            owner_model_id=owner,
            ownership="child",
            description="Single child owner in the LogicGuard-native Khaos Brain parent boundary.",
        )
        for item_id, item_type, owner in values
    )


def reattachments(models: tuple[ChildModelEvidence, ...]) -> tuple[ChildReattachmentContract, ...]:
    return tuple(
        ChildReattachmentContract(
            child_model_id=child.model_id,
            consumed_evidence_id=child.evidence_id,
            expected_inputs=child.inputs_accepted,
            expected_outputs=child.outputs_emitted,
            expected_state_owned=child.state_owned,
            expected_side_effects_owned=child.side_effects_owned,
            expected_contracts_out=child.contracts_out,
            rationale="The parent consumes this exact current child boundary without expanding its internal state graph.",
        )
        for child in models
    )


def closure_model(models: tuple[ChildModelEvidence, ...]) -> MeshClosureModel:
    all_outputs = tuple(output for child in models for output in child.outputs_emitted)
    return MeshClosureModel(
        parent_model_id=PARENT_ID,
        root_entries=("observation_or_versioned_legacy_input",),
        transitions=(
            MeshClosureTransition(
                "lifecycle_selects_delta",
                consumes=("observation_or_versioned_legacy_input",),
                emits=("lifecycle_delta_selected", "retrieval_eligibility_snapshot"),
                consumer_model_id=LIFECYCLE,
                code_contract_id="contract:lifecycle.selected_delta",
                rationale="Existing lifecycle authority admits/selects the bounded delta and eligibility snapshot.",
            ),
            MeshClosureTransition(
                "governance_selects_sleep_action",
                consumes=("lifecycle_delta_selected",),
                emits=("sleep_model_change_decision",),
                consumer_model_id=GOVERNANCE,
                code_contract_id="contract:governance.sleep_decision",
                rationale="The existing governance model remains the Sleep decision owner.",
            ),
            MeshClosureTransition(
                "logicguard_builds_exact_revisions",
                consumes=("sleep_model_change_decision",),
                emits=("exact_model_revision", "exact_mesh_revision", "structural_diagnostic"),
                consumer_model_id=LOGICGUARD,
                code_contract_id="contract:logicguard.exact_revision",
                rationale="LogicGuard supplies exact canonical semantics and diagnostics.",
            ),
            MeshClosureTransition(
                "authority_commits_complete_generation",
                consumes=("exact_model_revision", "exact_mesh_revision", "structural_diagnostic", "retrieval_eligibility_snapshot"),
                emits=("model_generation_committed", "model_binding_validated", "rollback_safe"),
                consumer_model_id=AUTHORITY,
                code_contract_id="contract:authority.complete_generation",
                rationale="The child authority model validates and stages one complete generation or safe rollback.",
            ),
            MeshClosureTransition(
                "lifecycle_publishes_index_and_watermark",
                consumes=("model_generation_committed", "model_binding_validated"),
                emits=("active_index_generation_published", "sleep_watermark_committed"),
                consumer_model_id=LIFECYCLE,
                code_contract_id="contract:lifecycle.current_index",
                rationale="The existing lifecycle owner alone publishes the active index and advances Sleep watermark.",
            ),
            MeshClosureTransition(
                "authority_returns_model_native_retrieval",
                consumes=("active_index_generation_published", "model_binding_validated"),
                emits=("model_native_retrieval_result",),
                consumer_model_id=AUTHORITY,
                code_contract_id="contract:authority.model_retrieval",
                rationale="The existing search facade consumes exact authority through the child contract.",
            ),
            MeshClosureTransition(
                "interface_localizes_model_view",
                consumes=("model_native_retrieval_result",),
                emits=("localized_model_projection",),
                consumer_model_id=INTERFACE,
                code_contract_id="contract:interface.localized_model_view",
                rationale="Localization projects display labels without mutating canonical identities.",
            ),
            MeshClosureTransition(
                "desktop_renders_model_graph",
                consumes=("localized_model_projection",),
                emits=("desktop_graph_rendered",),
                consumer_model_id=VISUAL,
                code_contract_id="contract:desktop.model_graph_visible",
                rationale="The desktop owner renders the single recommended graph.",
            ),
            MeshClosureTransition(
                "logicguard_simulates_exact_mesh",
                consumes=("exact_mesh_revision",),
                emits=("simulation_delta",),
                consumer_model_id=LOGICGUARD,
                code_contract_id="contract:logicguard.simulation",
                rationale="Dream simulation is sparse and does not mutate canonical revisions.",
            ),
            MeshClosureTransition(
                "authority_packages_dream_handoff",
                consumes=("simulation_delta",),
                emits=("dream_simulation_handoff",),
                consumer_model_id=AUTHORITY,
                code_contract_id="contract:authority.dream_handoff",
                rationale="The child packages immutable experiment evidence only.",
            ),
            MeshClosureTransition(
                "governance_disposes_dream_handoff",
                consumes=("dream_simulation_handoff",),
                emits=("dream_handoff_decision",),
                consumer_model_id=GOVERNANCE,
                code_contract_id="contract:governance.dream_disposition",
                rationale="The existing governance/Sleep owner reviews, watches, or rejects the handoff.",
            ),
        ),
        joins=(
            MeshClosureJoin(
                "join:logicguard-native-khaos-whole-flow",
                required_inputs=all_outputs,
                emits=("logicguard_native_khaos_closed",),
                rationale="Every child output is reachable and consumed before the parent can claim whole-flow closure.",
            ),
        ),
        terminals=(
            MeshClosureTerminal(
                "terminal:normal-current-generation",
                consumes=("logicguard_native_khaos_closed",),
                terminal_kind="normal_exit",
                rationale="A complete model-native generation, retrieval/UI route, Dream handoff route, and rollback capability are closed.",
            ),
        ),
        required_outputs=all_outputs,
        require_normal_exit=True,
        rationale="Model-of-models closure; child state graphs remain separate.",
    )


def build_partition() -> HierarchyPartitionMap:
    models = children()
    items = coverage_items()
    return HierarchyPartitionMap(
        parent_model_id=PARENT_ID,
        coverage_items=items,
        child_models=models,
        target_split_derivation=ModelTargetSplitDerivation(
            source_model_id=PARENT_ID,
            source_model_path=".flowguard/khaos_brain_logicguard_model_mesh.py",
            target_child_model_ids=tuple(child.model_id for child in models),
            covered_partition_item_ids=tuple(item.item_id for item in items),
            state_owner_fields=tuple(field for child in models for field in child.state_owned),
            side_effect_owner_fields=tuple(effect for child in models for effect in child.side_effects_owned),
            rationale=(
                "Lifecycle/index, maintenance governance, LogicGuard authority cutover, canonical/display, "
                "desktop rendering, and argument runtime are distinct cohesive ownership regions."
            ),
            derived_from_flowguard_model=True,
        ),
        reattachment_contracts=reattachments(models),
        required_evidence_tier="abstract_green",
        allowed_shared_areas=(),
        closure_model=closure_model(models),
    )


def broken_partition() -> HierarchyPartitionMap:
    current = build_partition()
    models = list(current.child_models)
    governance = next(child for child in models if child.model_id == GOVERNANCE)
    models[models.index(governance)] = replace(
        governance,
        state_owned=(*governance.state_owned, "model_revision_heads"),
        evidence_current=False,
    )
    return replace(current, child_models=tuple(models))


def main() -> int:
    current = review_hierarchical_mesh(build_partition(), model_count=6)
    broken = review_hierarchical_mesh(broken_partition(), model_count=6)
    payload = {
        "artifact_type": "khaos_brain_logicguard_native_flowguard_model_mesh",
        "current": current.to_dict(),
        "known_bad": broken.to_dict(),
        "child_count": len(build_partition().child_models),
        "partition_item_count": len(build_partition().coverage_items),
        "ok": current.ok and not broken.ok,
        "claim_boundary": (
            "This mesh proves current abstract parent/child ownership, exact evidence-id reattachment, "
            "partition coverage, no duplicate state/side-effect ownership, and token-level whole-flow "
            "closure. It does not prove production code, runtime conformance, tests, UI observation, "
            "migration, SkillGuard, or release readiness."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
