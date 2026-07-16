# UI Human Operability Protocol

Use this protocol when the claim says usable, understandable, human-operable, complete, or release-ready.

Use `UIUserTaskFrame`, `UIUserTaskCoverageLedger`, `UIRegionSemanticMap`, `UIAffordanceContract`, `UIActionGrammar`, `UIDialogWindowContract`, `UIKeyboardFocusContract`, `UIHumanWalkthroughScenario`, `UIHumanWalkthroughStep`, `UIHumanOperabilityAssessment`, and `review_ui_human_operability(...)` when available.

Consume the current `UIContentVisibilityPlan` for the same model/revision. Human-operability review cannot accept internal/unclassified ordinary-UI content or treat an observed/direct display mapping as permission.

## Required package

- Inventory every supported user-visible feature and task, not one convenient happy path.
- Link feature -> task -> journey/control/functional chain, with owner/reason/boundary for scoped tasks.
- Give each task a goal, entry state, main/alternate/cancel/error path, success state, visible feedback, required controls/displays/dialogs, keyboard contract, and evidence refs.
- Give every prominent/primary control exactly one owning task/intent in a state.
- Classify region semantics: input, action, result, status, recovery, navigation, or dialog.
- Classify visible affordances as clickable, editable, selectable, read-only, status-only, or decorative.
- Define action grammar with intent, primary/alternate controls, conflicts, preconditions, next state, feedback, and duplicate policy.
- Define native/custom dialog success, cancel, error, selected value/path, focus return, feedback, native/manual boundary, and evidence.
- Define Tab/Enter/Escape, disabled-control skip, error focus, and dialog focus return.
- For each `user_on_demand` item, bind an in-scope task to a visible/enabled reveal control, discoverable affordance contract, action grammar whose feedback item resolves to that content, and a close, collapse, blur, Escape, or equivalent return path. Hover reveal also needs a distinct keyboard/focus event and operable keyboard contract.
- Record walkthrough prompt, action, expected/actual feedback, evidence, confusion, and mitigation.

## Blockers

Block incomplete feature/task coverage, primary controls without tasks, misleading affordances, two primary controls for one intent/state, on-demand details that are undiscoverable, visible before reveal, hover-only, or impossible to dismiss, dialogs without cancel/error/focus/feedback, unreachable keyboard tasks, walkthrough confusion without mitigation, and manual/native evidence without a structured boundary.

Human-operability evidence proves only the declared tasks and revision. It does not replace implementation click-through or geometry evidence.
