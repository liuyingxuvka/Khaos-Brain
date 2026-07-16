from __future__ import annotations

from datetime import date
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from local_kb.org_checks import check_organization_repository, validate_shareable_payload
from local_kb.store import write_yaml_file


class OrganizationChecksTests(unittest.TestCase):
    def _write_org_repo(self, root: Path) -> None:
        write_yaml_file(
            root / "khaos_org_kb.yaml",
            {
                "kind": "khaos-organization-kb",
                "schema_version": 1,
                "organization_id": "sandbox",
                "kb": {
                    "main_path": "kb/main",
                    "imports_path": "kb/imports",
                },
                "skills": {
                    "registry_path": "skills/registry.yaml",
                    "candidates_path": "skills/candidates",
                },
            },
        )
        write_yaml_file(root / "kb" / "main" / "trusted" / "trusted.yaml", {"id": "trusted-card", "status": "trusted"})
        write_yaml_file(root / "kb" / "main" / "candidates" / "candidate.yaml", {"id": "candidate-card", "status": "candidate"})
        (root / "kb" / "imports").mkdir(parents=True)
        write_yaml_file(
            root / "skills" / "registry.yaml",
            {
                "skills": [
                    {
                        "id": "approved-skill",
                        "status": "approved",
                        "version": "1.0.0",
                        "content_hash": "sha256:" + "a" * 64,
                    },
                    {"id": "candidate-skill", "status": "candidate"},
                    {"id": "rejected-skill", "status": "rejected"},
                ]
            },
        )
        (root / "skills" / "candidates").mkdir(parents=True)

    def test_low_risk_candidate_change_is_auto_merge_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_org_repo(root)

            result = check_organization_repository(
                root,
                changed_files=["kb/imports/candidate.yaml"],
                enforce_low_risk=True,
            )

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["auto_merge_eligible"], result)

    def test_protected_trusted_change_blocks_low_risk_auto_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_org_repo(root)

            result = check_organization_repository(
                root,
                changed_files=["kb/trusted/trusted.yaml"],
                enforce_low_risk=True,
            )

        self.assertFalse(result["ok"], result)
        self.assertFalse(result["auto_merge_eligible"])
        self.assertIn("path is not eligible for low-risk auto-merge: kb/trusted/trusted.yaml", result["errors"])

    def test_rejects_unpinned_approved_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_org_repo(root)
            write_yaml_file(root / "skills" / "registry.yaml", {"skills": [{"id": "bad", "status": "approved"}]})

            result = check_organization_repository(root, changed_files=["skills/registry.yaml"])

        self.assertFalse(result["ok"], result)
        self.assertIn("skills/registry.yaml: approved skill bad must pin version", result["errors"])
        self.assertIn("skills/registry.yaml: approved skill bad must pin sha256 content_hash", result["errors"])

    def test_repeated_skill_id_is_allowed_when_bundle_versions_are_pinned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_org_repo(root)
            write_yaml_file(
                root / "skills" / "registry.yaml",
                {
                    "skills": [
                        {
                            "id": "demo-skill",
                            "bundle_id": "bundle-a",
                            "status": "approved",
                            "version_time": "2026-04-24T10:00:00Z",
                            "content_hash": "sha256:" + "1" * 64,
                        },
                        {
                            "id": "demo-skill",
                            "bundle_id": "bundle-b",
                            "status": "approved",
                            "version_time": "2026-04-24T11:00:00Z",
                            "content_hash": "sha256:" + "2" * 64,
                        },
                    ]
                },
            )

            result = check_organization_repository(root, changed_files=["skills/registry.yaml"])

        self.assertTrue(result["ok"], result)
        self.assertTrue(any("duplicate skill id handle" in warning for warning in result["warnings"]))

    def test_rejects_secret_and_local_path_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_org_repo(root)
            write_yaml_file(
                root / "kb" / "imports" / "alice" / "leaky.yaml",
                {
                    "id": "leaky",
                    "status": "candidate",
                    "note": "C:\\Users\\alice\\.codex\\token",
                    "api_key": "sk-" + "a" * 32,
                },
            )

            result = check_organization_repository(root, changed_files=["kb/imports/alice/leaky.yaml"])

        self.assertFalse(result["ok"], result)
        self.assertTrue(any("possible secret" in error for error in result["errors"]), result["errors"])
        self.assertTrue(any("local machine path" in error for error in result["errors"]), result["errors"])

    def test_shareable_payload_serializes_yaml_dates_canonically(self) -> None:
        result = validate_shareable_payload(
            {"id": "dated-card", "reviewed_on": date(2026, 7, 14)}
        )

        self.assertTrue(result["ok"], result)

    def test_privacy_scanner_does_not_flag_its_own_path_regex_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_org_repo(root)
            checker = root / ".github" / "scripts" / "org_kb_check.py"
            checker.parent.mkdir(parents=True)
            checker.write_text(
                "import re\n"
                "LOCAL_PATH_PATTERNS = (re.compile(r'[A-Za-z]:\\\\Users\\\\'), "
                "re.compile(r'AppData\\\\'))\n",
                encoding="utf-8",
            )

            result = check_organization_repository(root)

        self.assertTrue(result["ok"], result)

    def test_privacy_scanner_still_rejects_an_actual_python_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_org_repo(root)
            source = root / "tools" / "leak.py"
            source.parent.mkdir(parents=True)
            source.write_text(
                "LOCAL = 'C:\\\\Users\\\\alice\\\\private.txt'\n",
                encoding="utf-8",
            )

            result = check_organization_repository(root)

        self.assertFalse(result["ok"], result)
        self.assertTrue(
            any("local machine path" in error for error in result["errors"]),
            result["errors"],
        )

    def test_rejects_secret_in_skill_bundle_source_before_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_org_repo(root)
            source = root / "kb" / "imports" / "alice" / "skills" / "bundle" / "helper.py"
            source.parent.mkdir(parents=True)
            source.write_text('TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz123456"\n', encoding="utf-8")

            result = check_organization_repository(
                root,
                changed_files=["kb/imports/alice/skills/bundle/helper.py"],
            )

        self.assertFalse(result["ok"], result)
        self.assertTrue(any("possible secret" in error for error in result["errors"]), result["errors"])

    def test_reports_duplicate_card_content_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_org_repo(root)
            card = {
                "id": "first",
                "title": "Shared duplicate",
                "type": "model",
                "scope": "public",
                "status": "trusted",
                "domain_path": ["shared"],
                "if": {"notes": "Same content."},
                "action": {"description": "Use same content."},
                "predict": {"expected_result": "Duplicate is detected."},
                "use": {"guidance": "Do not keep exact duplicate payloads."},
            }
            duplicate = dict(card)
            duplicate["id"] = "second"
            duplicate["status"] = "candidate"
            write_yaml_file(root / "kb" / "main" / "trusted" / "first.yaml", card)
            write_yaml_file(root / "kb" / "imports" / "alice" / "second.yaml", duplicate)

            result = check_organization_repository(root)

        duplicate_hashes = result["checks"]["cards"]["duplicate_content_hashes"]
        self.assertTrue(duplicate_hashes, result)
        self.assertTrue(any("duplicate card content hash" in warning for warning in result["warnings"]))

    def test_duplicate_card_content_hash_blocks_low_risk_auto_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_org_repo(root)
            card = {
                "id": "first",
                "title": "Shared duplicate",
                "type": "model",
                "scope": "public",
                "status": "candidate",
                "domain_path": ["shared"],
                "if": {"notes": "Same content."},
                "action": {"description": "Use same content."},
                "predict": {"expected_result": "Duplicate is detected."},
                "use": {"guidance": "Do not keep exact duplicate payloads."},
            }
            duplicate = dict(card)
            duplicate["id"] = "second"
            write_yaml_file(root / "kb" / "imports" / "alice" / "first.yaml", card)
            write_yaml_file(root / "kb" / "imports" / "alice" / "second.yaml", duplicate)

            result = check_organization_repository(
                root,
                changed_files=["kb/imports/alice/first.yaml", "kb/imports/alice/second.yaml"],
                enforce_low_risk=True,
            )

        self.assertFalse(result["ok"], result)
        self.assertIn("duplicate card content hashes require organization maintenance", result["errors"])

    def test_cli_outputs_json_and_exits_nonzero_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_org_repo(root)
            write_yaml_file(root / "skills" / "registry.yaml", {"skills": [{"id": "bad", "status": "blocked"}]})

            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/kb_org_check.py",
                    "--org-root",
                    str(root),
                    "--changed-file",
                    "skills/registry.yaml",
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 2)
        self.assertFalse(payload["ok"])
        self.assertIn("skills/registry.yaml: skill bad has invalid status: blocked", payload["errors"])


if __name__ == "__main__":
    unittest.main()
