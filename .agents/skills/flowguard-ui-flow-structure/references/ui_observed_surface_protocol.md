# UI Observed Surface Protocol

Use this protocol whenever a UI exists, has been migrated, or can run. The observed real surface is the first hard gate before broad UI modeling or completion claims. Observation records what exists; it does not authorize content to remain on an ordinary user surface.

## Inventory

Record each visible button, icon button, menu item, input, picker, dropdown, tab, toggle, table, displayed field, status/helper/placeholder text, dialog, toolbar, panel, and region with stable id, kind, label/text, enabled state, region, revision, and evidence reference.

Use `UIObservedSurfaceInventory`, `UIObservedSurfaceItem`, and `review_ui_observed_surface_inventory(...)` when available. Map every item to a `UIControl`, `UIDisplayElement`, or `UIVisibleSurfaceItem`, or create a blindspot with owner, reason, validation boundary, and rationale. Every non-action observed content item also resolves to an approved `UIContentVisibilityItem`; direct display mapping proves ownership, not admission.

## Content admission comparison

Build or consume a `UIContentVisibilityPlan` for displayed values, status/helper/metadata content, non-action labels, optional details, and other state-exposing content. Use exactly `user_visible`, `user_on_demand`, or `internal`; do not add audience, role, or persona categories. Only exact normal labels for registered, in-scope task-owned controls with no extra state, disabled reason, or metadata need no duplicate content row.

Treat `user_visible` and `user_on_demand` as the user-content group and require a typed/resolvable task, current-state, recovery, or safety need. Treat `internal` and unclassified content as ineligible for ordinary rendering. `user_on_demand` content remains absent from every default/closed mapping until its visible/enabled reveal control and returns to hidden through an operable close/collapse/blur/Escape-equivalent path; hover also needs a distinct focus/keyboard event.

## Visible surface review

Use `UIVisibleSurface`, `UIVisibleSurfaceItem`, and `review_ui_visible_surface(...)` to bind admitted helper copy, status, placeholders, metadata, and disabled reasons to the state/region/control/display that owns their user-facing purpose. Purpose is still required, but purpose alone cannot override the content-admission decision.

Block or scope when:

- the model lists intended controls but never counts the real page/window;
- a visible or enabled actionable item has no mapping;
- non-action observed content has no visibility classification or bypasses admission through a display/text mapping;
- `internal` or unclassified content appears on the ordinary observed surface;
- `user_on_demand` content appears in a default/closed state before reveal, lacks a return path, or uses hover without keyboard/focus equivalence;
- label similarity is treated as behavior evidence;
- a blindspot lacks owner, reason, validation boundary, or rationale;
- a disabled control is visible without a reason a user can understand;
- implementation terms such as debug route, hydration, backend, mock, or dataset id leak without user value;
- placeholders or containers are treated as completed capability proof;
- helper/status messages compete or repeat without rationale.

## Handoff

Send candidate-content classifications to the interaction/text/surface models, mapped controls/displays to the interaction model, capability owners to capability coverage, actionable blindspots to implementation evidence, and visible text ownership to the journey/structure/text protocol. Inventory completeness proves surface accounting only, not content permission, functional behavior, or runnable completion.
