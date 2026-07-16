from __future__ import annotations

import json
from pathlib import Path


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


def test_all_five_skills_expose_only_the_current_runtime_authority() -> None:
    for skill_id in SKILL_IDS:
        skill_root = REPO_ROOT / ".agents" / "skills" / skill_id
        control = skill_root / ".skillguard"
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        source = _load(control / "contract-source.json")
        compiled = _load(control / "compiled-contract.json")
        assert "The current authority is" in skill_text, skill_id
        for forbidden in (
            "The V2 authority is",
            "former V1 runtime",
            "formally declared transition evidence",
            "keeps retirement receipts",
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
