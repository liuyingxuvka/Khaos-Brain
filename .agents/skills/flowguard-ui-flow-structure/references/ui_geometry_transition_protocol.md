# UI Geometry, Responsiveness, And Transition Protocol

Use geometry/responsiveness only when layout or interaction-latency confidence is in scope. Use transition projection only when the claim says tests cover modeled UI transitions.

## Geometry and responsiveness

Use `UIGeometryLayoutEvidenceSet`, `UIGeometryLayoutEvidence`, `UIResponsivenessContract`, `UIHotPathAction`, `UIColdPathWork`, `UIStableRegionRule`, and their review helpers.

Record text overflow, control overlap, viewport/container bounds, dialog/menu/popover bounds, focus and keyboard reachability, scroll owner, immediate hot-path feedback, deferred cold-path work, stale-result guard/cancellation/coalescing, and stable-region preservation.

Block overflow/overlap/out-of-bounds surfaces, unreachable focus/keyboard paths, unclear scroll ownership, hot actions without immediate feedback, cold results that can overwrite newer state, and stable regions without preservation rules.

## Transition projection

Project a reviewed interaction model with `ui_interaction_model_to_transition_coverage(...)`. Each cell carries visible event/control, source state, target state, expected output, handler/FunctionBlock, and owner code contract/runtime node.

Send small matrices through `transition_coverage_to_model_obligations(...)` and `transition_coverage_to_code_contracts(...)` to Model-Test Alignment. Send large/browser-heavy matrices through `transition_coverage_to_required_leaf_cell_ids(...)` to TestMesh while preserving semantic target ids.

Projection creates stable proof targets; it is not implementation or test pass evidence. Missing owner cells, stale model revision, absent required test kinds, or scoped cells without reasons block a broad transition-test claim.
