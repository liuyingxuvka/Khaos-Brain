from __future__ import annotations

from scripts import check_kb_model_test_alignment as alignment


def test_alignment_has_one_owner_for_every_obligation() -> None:
    report = alignment.build_report()
    assert report["ok"], report
    assert report["exactly_one_primary_owner"]
    assert set(report["owner_counts"].values()) == {1}


def test_alignment_forbids_cross_unit_test_evidence_reuse() -> None:
    report = alignment.build_report()
    assert report["cross_unit_test_evidence_overlaps"] == []
    owners: dict[str, str] = {}
    for row in report["alignment"]["binding_rows"]:
        for node_id in row["test_nodes"]:
            prior = owners.get(node_id)
            assert prior in {None, row["maintenance_unit_id"]}
            owners[node_id] = row["maintenance_unit_id"]


def test_each_alignment_row_binds_model_code_and_tests() -> None:
    report = alignment.build_report()
    for row in report["alignment"]["binding_rows"]:
        assert row["status"] == "aligned"
        assert row["model_path"].startswith(".flowguard/")
        assert row["code_path"]
        assert row["test_nodes"]


def test_each_unit_has_only_itself_as_member() -> None:
    report = alignment.build_report()
    for skill_id, row in report["maintenance_units"].items():
        assert row["ok"]
        assert row["maintenance_unit_id"] == f"unit:{skill_id}"
        assert row["member_skill_ids"] == [skill_id]
