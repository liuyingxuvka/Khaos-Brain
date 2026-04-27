from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.search import render_search_payload, search_multi_source_entries
from local_kb.store import write_yaml_file
from local_kb.ui_data import (
    build_card_detail_payload,
    build_route_view_payload,
    build_search_payload,
    build_skill_registry_payload,
    build_source_view_payload,
)


class MultiSourceSearchTests(unittest.TestCase):
    def _write_card(self, path: Path, entry_id: str, title: str, route: list[str], *, status: str = "trusted") -> None:
        write_yaml_file(
            path,
            {
                "id": entry_id,
                "title": title,
                "type": "model",
                "scope": "public",
                "status": status,
                "confidence": 0.9,
                "domain_path": route,
                "tags": ["shared", "organization"],
                "trigger_keywords": ["shared", "organization"],
                "required_skills": ["demo-skill"],
                "if": {"notes": "Shared search test scenario."},
                "action": {"description": "Use the shared test card."},
                "predict": {"expected_result": "The shared test card is found."},
                "use": {"guidance": "Use this card for multi-source search tests."},
            },
        )

    def test_multi_source_search_keeps_local_results_before_organization_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_card(root / "kb" / "public" / "local.yaml", "local-card", "Local shared card", ["shared"])
            self._write_card(org / "kb" / "trusted" / "org.yaml", "org-card", "Organization shared card", ["shared"])

            results = search_multi_source_entries(
                root,
                query="shared organization",
                path_hint="shared",
                top_k=5,
                organization_sources=[{"path": str(org), "organization_id": "sandbox", "repo_url": "https://example.invalid/org.git"}],
            )
            payload = render_search_payload(results, root)

        self.assertEqual([item["id"] for item in payload], ["local-card", "org-card"])
        self.assertEqual(payload[0]["source_info"]["label"], "local/public")
        self.assertEqual(payload[0]["source_label"], "local/public")
        self.assertEqual(payload[1]["source_info"]["label"], "org/sandbox/trusted")
        self.assertEqual(payload[1]["source_label"], "org/sandbox/trusted")
        self.assertEqual(payload[1]["author_label"], "sandbox")
        self.assertTrue(payload[1]["source_info"]["read_only"])
        self.assertTrue(payload[1]["read_only"])

    def test_ui_search_payload_can_include_organization_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_card(org / "kb" / "trusted" / "org.yaml", "org-card", "Organization shared card", ["shared"])

            payload = build_search_payload(
                root,
                query="shared organization",
                route_hint="shared",
                organization_sources=[{"path": str(org), "organization_id": "sandbox"}],
            )

        self.assertEqual(payload["results"][0]["id"], "org-card")
        self.assertEqual(payload["results"][0]["source_info"]["kind"], "organization")

    def test_organization_reads_only_main_active_statuses_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_card(org / "kb" / "main" / "trusted.yaml", "trusted-card", "Organization trusted card", ["shared"])
            self._write_card(
                org / "kb" / "main" / "candidate.yaml",
                "candidate-card",
                "Organization candidate card",
                ["shared"],
                status="candidate",
            )
            rejected = {
                "id": "rejected-card",
                "title": "Organization rejected card",
                "type": "model",
                "scope": "public",
                "status": "rejected",
                "confidence": 0.1,
                "domain_path": ["shared"],
                "tags": ["shared"],
                "trigger_keywords": ["shared"],
                "if": {"notes": "Rejected organization material."},
                "action": {"description": "Do not use."},
                "predict": {"expected_result": "It is filtered."},
                "use": {"guidance": "Filtered."},
            }
            write_yaml_file(org / "kb" / "main" / "rejected.yaml", rejected)
            self._write_card(org / "kb" / "imports" / "import.yaml", "import-card", "Organization import card", ["shared"])

            payload = build_search_payload(
                root,
                query="Organization",
                route_hint="shared",
                organization_sources=[{"path": str(org), "organization_id": "sandbox"}],
            )
            result_ids = {item["id"] for item in payload["results"]}

        self.assertIn("trusted-card", result_ids)
        self.assertIn("candidate-card", result_ids)
        self.assertNotIn("rejected-card", result_ids)
        self.assertNotIn("import-card", result_ids)

    def test_route_and_source_views_include_organization_sources_when_connected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_card(root / "kb" / "public" / "local.yaml", "local-card", "Local shared card", ["shared"])
            self._write_card(org / "kb" / "trusted" / "org.yaml", "org-card", "Organization shared card", ["shared"])
            sources = [{"path": str(org), "organization_id": "sandbox"}]

            route_payload = build_route_view_payload(root, route="shared", organization_sources=sources)
            local_payload = build_source_view_payload(root, "local", organization_sources=sources)
            organization_payload = build_source_view_payload(root, "organization", organization_sources=sources)

        self.assertEqual([item["id"] for item in route_payload["deck"]], ["local-card", "org-card"])
        self.assertEqual([item["id"] for item in local_payload["deck"]], ["local-card"])
        self.assertEqual([item["id"] for item in organization_payload["deck"]], ["org-card"])

    def test_card_detail_payload_can_resolve_organization_search_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_card(org / "kb" / "trusted" / "org.yaml", "org-card", "Organization shared card", ["shared"])
            search_payload = build_search_payload(
                root,
                query="shared organization",
                route_hint="shared",
                organization_sources=[{"path": str(org), "organization_id": "sandbox"}],
            )

            detail = build_card_detail_payload(
                root,
                "org-card",
                organization_sources=[{"path": str(org), "organization_id": "sandbox"}],
                source_info=search_payload["results"][0]["source_info"],
            )

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["id"], "org-card")
        self.assertEqual(detail["source_label"], "org/sandbox/trusted")
        self.assertTrue(detail["read_only"])
        self.assertEqual(detail["recent_history"], [])

    def test_card_detail_payload_prefers_organization_source_info_over_same_id_local_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_card(root / "kb" / "candidates" / "adopted" / "sandbox" / "org-card.yaml", "org-card", "Local adopted copy", ["shared"])
            self._write_card(org / "kb" / "trusted" / "org.yaml", "org-card", "Organization shared card", ["shared"])
            search_payload = build_search_payload(
                root,
                query="shared organization",
                route_hint="shared",
                organization_sources=[{"path": str(org), "organization_id": "sandbox"}],
            )
            organization_summary = next(
                item for item in search_payload["results"] if item["source_info"]["kind"] == "organization"
            )

            detail = build_card_detail_payload(
                root,
                "org-card",
                organization_sources=[{"path": str(org), "organization_id": "sandbox"}],
                source_info=organization_summary["source_info"],
            )

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["title"], "Organization shared card")
        self.assertEqual(detail["source_info"]["kind"], "organization")
        self.assertEqual(detail["source_label"], "org/sandbox/trusted")
        self.assertTrue(detail["read_only"])

    def test_card_detail_payload_annotates_organization_skill_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_card(org / "kb" / "trusted" / "org.yaml", "org-card", "Organization shared card", ["shared"])
            write_yaml_file(
                org / "skills" / "registry.yaml",
                {
                    "skills": [
                        {
                            "id": "demo-skill",
                            "status": "approved",
                            "version": "1.0.0",
                            "source_repo": "https://example.invalid/skills.git",
                            "content_hash": "sha256:" + "a" * 64,
                        }
                    ]
                },
            )
            sources = [{"path": str(org), "organization_id": "sandbox"}]

            detail = build_card_detail_payload(
                root,
                "org-card",
                organization_sources=sources,
                local_policy_allows_skill_auto_install=True,
            )
            registry = build_skill_registry_payload(sources, local_policy_allows_auto_install=True)

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["skill_dependencies"][0]["registry_status"], "approved")
        self.assertTrue(detail["skill_dependencies"][0]["auto_install"]["eligible"])
        self.assertEqual(registry["counts"]["approved"], 1)
        self.assertTrue(registry["skills"][0]["auto_install"]["eligible"])


if __name__ == "__main__":
    unittest.main()
