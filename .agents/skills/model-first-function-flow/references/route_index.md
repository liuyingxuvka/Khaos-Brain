# FlowGuard Route Index

This compact projection is checked against `flowguard.route_topology` and the canonical suite map. It selects owners; it does not execute a route or prove current evidence.

## Kernel

| Route id | Role | Native owner | Skill |
| --- | --- | --- | --- |
| `model_first_function_flow` | kernel | `model_first_function_flow` | `model-first-function-flow` |

## Public owner routes

| Route id | Native owner | Skill |
| --- | --- | --- |
| `existing_model_preflight` | `existing_model_preflight` | `flowguard-existing-model-preflight` |
| `behavior_commitment_ledger` | `behavior_commitment_ledger` | `flowguard-behavior-commitment-ledger` |
| `architecture_reduction` | `architecture_reduction` | `flowguard-architecture-reduction` |
| `code_structure_recommendation` | `code_structure_recommendation` | `flowguard-code-structure-recommendation` |
| `contract_exhaustion_mesh` | `contract_exhaustion_mesh` | `flowguard-contract-exhaustion-mesh` |
| `development_process_flow` | `development_process_flow` | `flowguard-development-process-flow` |
| `field_lifecycle_mesh` | `field_lifecycle_mesh` | `flowguard-field-lifecycle-mesh` |
| `model_mesh_maintenance` | `model_mesh_maintenance` | `flowguard-model-mesh` |
| `model_miss_review` | `model_miss_review` | `flowguard-model-miss-review` |
| `model_test_alignment` | `model_test_alignment` | `flowguard-model-test-alignment` |
| `model_topology_hazard_review` | `model_topology_hazard_review` | `flowguard-model-topology-hazard-review` |
| `structure_mesh_maintenance` | `structure_mesh_maintenance` | `flowguard-structure-mesh` |
| `test_mesh_maintenance` | `test_mesh_maintenance` | `flowguard-test-mesh` |
| `ui_flow_structure` | `ui_flow_structure` | `flowguard-ui-flow-structure` |

## Delegated modes

| Route id | Role | Native owner | Skill |
| --- | --- | --- | --- |
| `plan_detailing_compiler` | delegated_mode | `development_process_flow` | `flowguard-plan-detailing-compiler` |
| `agent_workflow_rehearsal` | delegated_mode | `development_process_flow` | `flowguard-agent-workflow-rehearsal` |

Generic rough-plan or multi-skill requests enter `development_process_flow`; delegated modes open directly only when explicitly requested or delegated.

## Internal route ownership

- Kernel-owned: `flowguard_self_maintenance`, `template_structure`, `model_maturation_loop`, `risk_template_library`, `maintenance_obligation_memory`, `risk_evidence_ledger`, and `flowguard_closure_contract`.
- DevelopmentProcessFlow-owned: `development_process_simulator`, `maintenance_scan_router`, and `evidence_field_structure`.
- Behavior Commitment Ledger-owned: `primary_path_authority`.
- Existing Model Preflight-owned: `model_angle_deliberation` and `model_similarity_consolidation`.
- ContractExhaustionMesh-owned: `state_closure`.

Any public or delegated route absent from this projection, the suite map, or the canonical topology is a routing-parity blocker. Internal helpers never become parallel public skill owners.
