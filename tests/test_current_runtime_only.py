from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.check_current_runtime_only import check_current_runtime_only


FLOWGUARD_SHADOW_MEMBER_IDS = {
    "model-first-function-flow",
    "flowguard-agent-workflow-rehearsal",
    "flowguard-architecture-reduction",
    "flowguard-behavior-commitment-ledger",
    "flowguard-code-structure-recommendation",
    "flowguard-contract-exhaustion-mesh",
    "flowguard-development-process-flow",
    "flowguard-existing-model-preflight",
    "flowguard-field-lifecycle-mesh",
    "flowguard-model-mesh",
    "flowguard-model-miss-review",
    "flowguard-model-test-alignment",
    "flowguard-model-topology-hazard-review",
    "flowguard-plan-detailing-compiler",
    "flowguard-structure-mesh",
    "flowguard-test-mesh",
    "flowguard-ui-flow-structure",
}

REQUIRED_PROJECT_SKILL_IDS = {
    "kb-dream-pass",
    "kb-organization-contribute",
    "kb-organization-maintenance",
    "kb-sleep-maintenance",
    "khaos-brain-open-ui",
    "khaos-brain-update",
    "local-kb-retrieve",
    "organization-review",
}


def test_repository_has_only_current_runtime_authority() -> None:
    report = check_current_runtime_only(Path(__file__).resolve().parents[1])

    assert report["ok"], report
    assert report["obsolete_update_state_migrator_refs"] == [
        "local_kb/install.py",
        "local_kb/software_update.py",
    ]
    assert report["retired_flowguard_shadow_skill_residuals"] == []
    assert report["missing_project_skill_surfaces"] == []
    assert report["retired_flowguard_shadow_control_residuals"] == []
    assert report["retired_standalone_logicguard_import_refs"] == []
    assert report["retired_standalone_logicguard_dependency_refs"] == []


def test_ordinary_project_has_no_flowguard_shadow_skill_suite() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    skills_root = repo_root / ".agents" / "skills"

    assert not any(
        (skills_root / member_id).exists()
        for member_id in FLOWGUARD_SHADOW_MEMBER_IDS
    )
    assert all(
        (skills_root / skill_id / "SKILL.md").is_file()
        for skill_id in REQUIRED_PROJECT_SKILL_IDS
    )
    assert not (
        skills_root / ".flowguard-skill-suite-ownership.json"
    ).exists()
    assert not (
        repo_root / ".skillguard" / "flowguard-suite" / "suite-map.json"
    ).exists()
    assert not (
        repo_root / "scripts" / "verify_skill_suite_markers.py"
    ).exists()


def test_flowguard_inventory_tracks_only_the_manual_update_entrypoint() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source = (repo_root / "scripts" / "run_flowguard_suite.py").read_text(
        encoding="utf-8"
    )

    assert 'REPO_ROOT / "scripts" / "run_khaos_brain_manual_update.py"' in source
    assert 'REPO_ROOT / "scripts" / "run_khaos_brain_system_update.py"' not in source


def test_retired_runtime_authority_is_a_hard_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "governed.py").write_text("retired-alternate-authority\n", encoding="utf-8")
        (root / "local_kb").mkdir()
        (root / "local_kb" / "install.py").write_text(
            "migrate_obsolete_update_state\n", encoding="utf-8"
        )
        (root / "local_kb" / "software_update.py").write_text(
            "def migrate_obsolete_update_state(): pass\n", encoding="utf-8"
        )
        (root / "scripts").mkdir()
        with patch.dict(
            "scripts.check_current_runtime_only.FORBIDDEN_BY_FILE",
            {"governed.py": ("retired-alternate-authority",)},
            clear=True,
        ), patch.dict(
            "scripts.check_current_runtime_only.REQUIRED_BY_FILE",
            {},
            clear=True,
        ):
            report = check_current_runtime_only(root)

    assert not report["ok"]
    assert report["issues"] == [
        "retired-runtime-authority:governed.py:retired-alternate-authority"
    ]
