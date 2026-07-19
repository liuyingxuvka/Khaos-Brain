from __future__ import annotations

import json

import pytest

from scripts.evaluate_kb_retrieval import (
    DEFAULT_CASES,
    _active_entry_ids,
    _load_cases,
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


def test_production_cases_keep_the_exact_target_owned_integer_schema() -> None:
    payload = json.loads(DEFAULT_CASES.read_text(encoding="utf-8"))

    assert type(payload["schema_version"]) is int
    assert payload["schema_version"] == 1
    assert _load_cases(DEFAULT_CASES) == payload


@pytest.mark.parametrize("wrong_version", ["1", "1.0", 1.0, True])
def test_case_loader_rejects_compatibility_schema_coercion(
    tmp_path,
    wrong_version,
) -> None:
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps({"schema_version": wrong_version}),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="exact integer schema_version 1",
    ):
        _load_cases(cases)
