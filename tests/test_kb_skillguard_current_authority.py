from __future__ import annotations

import json
from pathlib import Path

from local_kb.transactional_install import consumer_skill_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_IDS = (
    "kb-sleep-maintenance",
    "kb-dream-pass",
    "kb-organization-contribute",
    "kb-organization-maintenance",
    "khaos-brain-update",
)
FORMER_PATHS = [
    ".skillguard/work-contract.json",
    ".skillguard/check_manifest.json",
    ".skillguard/skillguard_manifest.json",
    ".skillguard/skillguard_profile.json",
    ".skillguard/skillguard_skill_contract.json",
    ".skillguard/skillguard_evidence_rules.json",
    ".skillguard/skillguard_closure_policy.json",
    ".skillguard/skillguard_progress_ledger.jsonl",
]


def _load(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_all_five_source_skills_have_current_author_contracts_and_clean_consumers() -> None:
    for skill_id in SKILL_IDS:
        skill_root = REPO_ROOT / ".agents" / "skills" / skill_id
        control = skill_root / ".skillguard"
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        source = _load(control / "contract-source.json")
        compiled = _load(control / "compiled-contract.json")
        manifest = _load(control / "check-manifest.json")
        consumer = consumer_skill_manifest(skill_root)
        assert "Ordinary use" in skill_text, skill_id
        assert "author-maintenance" in skill_text, skill_id
        assert consumer["file_count"] >= 1, skill_id
        assert all(
            ".skillguard" not in str(row["path"])
            for row in consumer["files"]
        ), skill_id
        assert source["skill_id"] == skill_id
        assert compiled["skill_id"] == skill_id
        assert manifest["skill_id"] == skill_id
        for forbidden in (
            "The V2 authority is",
            "former V1 runtime",
            "formally declared transition evidence",
            "keeps retirement receipts",
            "shared receipt",
            "external closure",
        ):
            assert forbidden not in skill_text, (skill_id, forbidden)
        assert "v1_runtime_authority" not in source, skill_id
        assert "v1_runtime_authority" not in compiled, skill_id
        for relative in FORMER_PATHS:
            assert not (skill_root / relative).exists(), (skill_id, relative)
        assert not (control / "checks").exists(), skill_id
        assert not (control / "evidence").exists(), skill_id
        assert not (control / "reports").exists(), skill_id
        assert not (control / "ai_judgments").exists(), skill_id
        assert not list((control / "runs").glob("*.json")), skill_id
