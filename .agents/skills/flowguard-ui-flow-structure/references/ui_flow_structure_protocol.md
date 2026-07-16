# UI Flow Structure Protocol Index

Use `ui_flow_structure` only after classifying work as `greenfield`, `source_based`, or `mixed`. Greenfield work derives accepted capabilities and UI candidate content from user/product scope. Source-based and mixed work additionally require source authority, target mapping, approved differences, source interaction semantics, and observed-source alignment.

Load only the directly routed protocol needed for the active claim:

- `ui_observed_surface_protocol.md`: existing/runnable visible-surface inventory, content-admission comparison, and blindspots.
- `ui_capability_interaction_protocol.md`: candidate-content admission, capability/output contracts, and UI event x UI state modeling.
- `ui_journey_structure_text_protocol.md`: launch-to-terminal journeys, regions, hierarchy, stable placement, and text blueprint.
- `ui_human_operability_protocol.md`: tasks, affordances, action grammar, dialogs, keyboard/focus, and walkthroughs.
- `ui_implementation_evidence_protocol.md`: functional chains, source semantics, click-through, screenshot, DOM text, and other evidence kinds.
- `ui_geometry_transition_protocol.md`: geometry, responsiveness, and transition coverage projection.

## Route sequence

1. Declare work mode and accepted UI boundary.
2. For an existing or runnable UI, complete Observed Visible Surface Review first; observation records reality but does not authorize content to remain visible, and a disabled control is visible without a reason is still a gap.
3. Build `UIContentVisibilityPlan` for in-scope displayed values, status/helper/metadata content, non-action labels, and optional details. Use exactly `user_visible`, `user_on_demand`, or `internal`; use typed/resolvable task/state/recovery/safety needs. Exempt only exact normal labels for registered, in-scope task-owned controls with no extra state, disabled reason, or metadata.
4. Inventory required user-visible capabilities and output contracts, then build the interaction model with admitted displays and default-hidden on-demand state.
5. For complete app claims, review launch-to-terminal journeys before structure and text derivation.
6. For complete-product language claims, declare the expected surface inventory and compare canonical typography, component, navigation, interaction, feedback, recovery, and transition rules. Bind business-bearing UI rows to the existing intent, commitment, and singular selected path.
7. For usable/human-operable claims, run the task and human-operability package, including reveal and return accessibility.
8. For implemented/runnable/complete claims, require current visibility, click-through, and evidence-kind rows; design/model evidence is insufficient.
9. Add geometry/responsiveness and transition projection only when those claims are in scope.

## Shared hard boundary

Every reachable enabled action needs a modeled event and either a complete control -> owner -> function -> UI update -> evidence chain, a valid pure-UI disposition, or an owned blindspot. Missing recovery/cancel/error branches remain explicit.

Content admission has two conceptual groups and no audience/role/persona taxonomy. `user_visible` and `user_on_demand` are ordinary user content; `internal` is not. Unclassified content fails closed, internal content never maps to ordinary UI, and a free-text purpose or direct display mapping cannot grant admission. Both user-facing values need a typed `task:`, `state:`, `recovery:`, or `safety:` reference whose target resolves when the owning model is supplied.

`user_on_demand` content is hidden in the default/closed state across display, text, visible-surface, and observed mappings, appears only after a visible/enabled/labeled reveal control, binds to a task-owned affordance and content-specific feedback, and returns through an operable close, collapse, blur, Escape, or equivalent path. Hover reveal also needs a distinct keyboard/focus event.

Source-based work preserves success, cancel, error, selected-value, no-handler, and external-effect semantics; greenfield work must not invent a source baseline.

Typography handoff stays semantic and calm: semantic hierarchy levels are not a command to create one size per level; text with similar jobs should reuse treatments; avoid a one-off visual text style without a named attention/meaning role.

Complete-product consistency is still this route, not a new design-language owner. Equal semantic roles across pages, windows, dialogs, menus, and repeated components reuse the same rule and typography token/scale/weight. A bounded presentation exception records scope, reason, owner, validation boundary, current evidence, and preserves the same behavior authority and external result. Internal intent/commitment/path/evidence/audit ids never become ordinary UI content.

Screenshot, DOM text, event traces, geometry, accessibility/ARIA, test results, and manual observation are evidence kinds only when tied to a current model/implementation revision and an evidence reference. Label/API existence alone is not functional proof.

The route returns its content-visibility plan plus evidence, failures, blockers, skipped checks, residual risk, claim boundary, and typed next actions. It does not replace visual design, final copywriting, frontend implementation, Code Structure Recommendation, StructureMesh, Model-Test Alignment, or TestMesh.
