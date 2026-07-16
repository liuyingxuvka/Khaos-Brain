from __future__ import annotations

from scripts.evaluate_kb_retrieval import (
    _active_entry_ids,
    _required_case_kinds,
)


def _index(*related_cards: str) -> dict:
    return {
        "records": [
            {
                "entry_id": "model-004",
                "data": {"related_cards": list(related_cards)},
            }
        ]
    }


def test_single_node_mesh_requires_current_retrieval_cases_without_fake_relation() -> None:
    required, not_applicable = _required_case_kinds(_index())

    assert required == {"lexical", "direct_id", "route_expansion", "no_card"}
    assert not_applicable == {"related_traversal"}
    assert _active_entry_ids(_index()) == {"model-004"}


def test_grounded_relation_makes_related_traversal_mandatory() -> None:
    required, not_applicable = _required_case_kinds(_index("model-005"))

    assert "related_traversal" in required
    assert not not_applicable
