# UI Implementation Evidence Protocol

Use this protocol only when claiming that a running UI is implemented, runnable, complete, or functionally wired. Model, journey, structure, and text artifacts are design evidence, not runtime proof.

Use `UIContentVisibilityPlan`, `UIFeatureContract`, `UIImplementationValidation`, `UIImplementationJourneyRun`, `UIImplementationStepEvidence`, `UIImplementationBlindspot`, `UIRenderEvidenceSet`, `UIRenderEvidence`, `UIControlFunctionalChainSet`, and the corresponding review helpers.

## Functional chain

Every reachable enabled non-pure-UI action requires:

```text
visible control -> UI event -> code owner -> backend/local function
-> UI state update -> click/test evidence
```

Record implementation target/revision, model revision, feature/journey/control/event mappings, step source/target states, observed result/state, evidence reference, and failure/recovery/cancel/exit evidence. API/route existence and label matching are insufficient.

Bind the current content-visibility plan and observed inventory to the implementation revision. Use structured `UIContentVisibilityEvidence` rows for every content item: default-visible for `user_visible`; default-hidden, reveal, revealed, and return-hidden for `user_on_demand`; and internal-absent for `internal`. Positive visible rows must resolve to the same content item in the declared state; an unrelated observed item cannot prove the row. Absence rows cannot cite unrelated visible items. Hover evidence also includes the distinct keyboard/focus event. A boolean or opaque evidence reference is insufficient. Reveal/return may be pure UI, but they still need current state-transition evidence for a runnable or usable claim.

## Source-based and mixed semantics

Use `UISourceBaseline`, `UISourceTargetMapping`, `UIObservedSourceAlignment`, `UISourceBaselineInteractionGate`, and their reviewers. Preserve trigger, confirm, cancel, selected value, result feedback, external effect, error, navigation, command, and no-handler/no-op disposition for native pickers, saves, external opens, custom dialogs, and source controls. Greenfield work must not invent a source baseline.

## Evidence kinds

Screenshot, browser/desktop click-through, DOM text, computed style, geometry, accessibility/ARIA, runtime trace/log, test result, and manual observation require a current visibility plan, observed inventory, model/implementation revision, and per-content evidence reference when content admission is in scope. Evidence must show admitted default-visible content, default-hidden/reveal/revealed/returned on-demand content, and the absence of internal content from the ordinary observed UI. Manual/native-dialog steps need structured observed-result rows and scoped boundaries.

Block enabled controls/events without feature/pure-UI/run/blindspot ownership, capability outputs without assertions, missing or stale visibility-plan bindings, internal/unclassified observed content, direct display-mapping admission bypass, on-demand content visible while closed or lacking reveal/return accessibility evidence, missing implementation runs, unknown states/events/controls, stale/failed/skipped/not-run evidence, missing failure/recovery/cancel paths, or blindspots without owner/reason/boundary/rationale.

Implementation validation proves only the executed current paths and observed content boundary. It does not prove unvisited controls, future behavior, visual quality, authorization roles, or semantic transition coverage.
