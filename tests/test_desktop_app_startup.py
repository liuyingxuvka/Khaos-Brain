from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from local_kb.desktop_app import KbDesktopApp


def _startup_app() -> KbDesktopApp:
    app = object.__new__(KbDesktopApp)
    app._initial_route_loading = True
    app._initial_route_load_done = True
    app._initial_route_load_payload = {
        "deck": [{"entry_id": "model-004"}],
        "taxonomy": {
            "children": [{"segment": "workflow", "observed_subtree_count": 1}]
        },
    }
    app._initial_route_load_error = ""
    app.search_entry = Mock()
    app.children_by_route = {}
    app.expanded_routes = set()
    app.deck = []
    app.selected_index = 7
    app._card_selected_by_user = True
    app.hovered_index = 3
    app.language = "en"
    app.repo_root = Path(".")
    app._text = lambda key: {
        "predictive_memory_cards": "Predictive memory cards",
        "cards_load_failed": "Cards could not be loaded.",
    }[key]
    app._render_sidebar = Mock()
    app._render_main = Mock()
    return app


def test_initial_route_completion_enables_ui_and_applies_payload() -> None:
    app = _startup_app()

    app._complete_initial_route_load()

    assert app._initial_route_loading is False
    assert app.deck == [{"entry_id": "model-004"}]
    assert app.children_by_route[""][0]["segment"] == "workflow"
    assert app.selected_index == -1
    assert app.hovered_index == -1
    assert app._route_subtitle == "Predictive memory cards"
    app.search_entry.configure.assert_called_once_with(state="normal")
    app._render_sidebar.assert_called_once_with()
    app._render_main.assert_called_once_with()


def test_initial_route_failure_stays_visible_without_fake_empty_deck() -> None:
    app = _startup_app()
    app._initial_route_load_error = "authority unavailable"

    app._complete_initial_route_load()

    assert app._initial_route_loading is False
    assert app._route_subtitle == "Cards could not be loaded."
    app._render_sidebar.assert_not_called()
    app._render_main.assert_called_once_with()


def test_sidebar_navigation_is_inert_while_initial_route_loads() -> None:
    app = _startup_app()
    app.sidebar = Mock()
    app.sidebar.canvasy.side_effect = AssertionError("must not inspect hitboxes")

    app._on_sidebar_click(SimpleNamespace(x=20, y=20))

    app.sidebar.canvasy.assert_not_called()
