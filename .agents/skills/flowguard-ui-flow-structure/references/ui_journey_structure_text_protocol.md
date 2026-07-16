# UI Journey, Structure, And Text Protocol

Use this protocol after the interaction model is reviewed. Complete app claims require journey coverage before structure/text derivation; component-only scope may record a narrower boundary.

## Journey coverage

Use `UIJourneyCoverage`, `UIJourneyEntryPoint`, `UIFeatureJourney`, `UITerminalActionAllowance`, `UIResidualBlindspot`, and `review_ui_journey_coverage(...)`.

Record launch state; launch entry points; feature states/events; success terminals; failure/recovery/cancel/exit events; every reachable actionable control/event owner; allowed terminal actions; and blindspot reason, owner, validation boundary, and rationale.

Block missing/unreachable entries or success terminals, unknown paths, reachable actions/events without owner or blindspot, recoverable failures without handling, terminal outgoing actions without allowed purpose, and blindspots without disposition.

## Structure derivation

Derive parent surface, regions/screens/menus/panels/overlays, state/control/display/event-to-region maps, parent/child edges, stable global controls, contextual/local controls, admitted information ownership, overlay blocking scope, validation boundaries, and rationale. Structure placement never upgrades internal or unclassified content into user content.

Keep first-level persistent controls stable, second-level contextual controls with their owning workflow, third-level controls near their local data/state, and destructive actions separate. Block wrong-level controls, duplicate same-level functions, missing region owners, unstable global placement, or structure derived before model/journey review.

## Text hierarchy

Use `UITextHierarchyBlueprint`, `UITextElement`, `UITypographyToken`, and `review_ui_text_hierarchy(...)` to map approved page/region headings, control labels, status/progress/success/failure text, helper/validation/empty/recovery slots, display labels, state-to-text ownership, and repetition rationale. Bind state-exposing text to its content-visibility item; only exact normal labels for registered, in-scope task-owned controls with no extra state or metadata need no duplicate row.

Text hierarchy consumes only `user_visible` content or `user_on_demand` content in a state reached through its reveal event. Keep on-demand text absent from the default hierarchy and include it only in the revealed state. Internal and unclassified content cannot gain admission from a text owner, token, priority, typography, purpose, or rationale.

Semantic hierarchy levels are not a command to create a distinct visual font size per level. Text with similar jobs should reuse treatments; prefer grouping, spacing, weight, color role, or placement before a one-off visual text style. Preserve justified editorial/brand/warning/state-critical exceptions.

For a complete-product claim, compare equal semantic roles across declared surfaces rather than reviewing each blueprint in isolation. A primary page title, secondary-page title, dialog title, capsule label, body text, helper, and status role each reuse the canonical token/scale/weight wherever that role recurs. A typed presentation-only exception may vary a platform/native/accessibility/safety treatment, but it cannot waive content admission or behavior-authority identity.

Block labels that disagree with modeled consequence, state-exposing text without approved admission or state/control/display owner, on-demand text visible before reveal, error/recovery copy without its path, competing truth sources, and copy/design handoff that contains prose but no ownership maps.
