from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from local_kb.org_sources import _run_git, connect_organization_source
from local_kb.logicguard_models import authority_generation_pointer_path
from local_kb.model_maintenance import publish_sleep_model_generation
from local_kb.settings import ORGANIZATION_MODE, load_desktop_settings, organization_sources_from_settings, save_desktop_settings
from local_kb.store import load_yaml_file, write_yaml_file
from tests.current_runtime_helpers import activate_current_kb_runtime


ORGANIZATION_ID = "sandbox"


def base_card(
    entry_id: str,
    title: str,
    guidance: str,
    *,
    status: str = "trusted",
    confidence: float = 0.8,
    route: list[str] | None = None,
    required_skills: list[str] | None = None,
    author: str = "sandbox",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": entry_id,
        "title": title,
        "type": "model",
        "scope": "public",
        "status": status,
        "confidence": confidence,
        "domain_path": route or ["shared", "organization"],
        "tags": ["shared", "organization"],
        "trigger_keywords": ["shared", "organization"],
        "author": author,
        "if": {"notes": "A reusable organization sandbox scenario."},
        "action": {"description": "Use this card in organization acceptance tests."},
        "predict": {"expected_result": "Organization mode keeps local and shared knowledge separated."},
        "use": {"guidance": guidance},
    }
    if required_skills:
        payload["required_skills"] = required_skills
        payload["use"]["unavailable_skill_guidance"] = (
            "If the Skill is unavailable, stop and report the missing governed dependency."
        )
    return payload


def sandbox_overlap_scan_card(entry_id: str = "sandbox-overlap-scan") -> dict[str, Any]:
    return base_card(
        entry_id,
        "Repository tasks scan local KB first",
        "Scan the local KB before repository work so prior models surface before implementation starts.",
        confidence=0.9,
        route=["system", "knowledge-library", "retrieval"],
    )


def sandbox_overlap_release_card(entry_id: str = "sandbox-overlap-release") -> dict[str, Any]:
    return base_card(
        entry_id,
        "Release hygiene before publishing",
        "Check release notes, version state, and public README claims before publishing repository changes.",
        confidence=0.86,
        route=["repository", "release", "hygiene"],
    )


def sandbox_unique_merge_card(entry_id: str = "sandbox-unique-merge") -> dict[str, Any]:
    return base_card(
        entry_id,
        "Organization auto-merge smoke test candidate",
        "Use a low-risk import branch when validating organization auto-merge checks.",
        status="candidate",
        confidence=0.55,
        route=["organization", "maintenance", "merge"],
    )


def sandbox_unique_skill_card(entry_id: str = "sandbox-unique-skill") -> dict[str, Any]:
    return base_card(
        entry_id,
        "Record meaningful Skill-use evidence",
        "When a card depends on a Skill, keep the card and Skill bundle together for organization review.",
        status="candidate",
        confidence=0.5,
        route=["codex", "workflow", "skills"],
        required_skills=["demo-skill"],
    )


def organization_sandbox_cards() -> dict[str, dict[str, Any]]:
    return {
        "overlap_scan": sandbox_overlap_scan_card(),
        "overlap_release": sandbox_overlap_release_card(),
        "unique_merge": sandbox_unique_merge_card(),
        "unique_skill": sandbox_unique_skill_card(),
    }


def write_valid_org_repo(root: Path, *, include_sandbox_cards: bool = True) -> None:
    write_yaml_file(
        root / "khaos_org_kb.yaml",
        {
            "kind": "khaos-organization-kb",
            "schema_version": 1,
            "organization_id": ORGANIZATION_ID,
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
    if include_sandbox_cards:
        cards = organization_sandbox_cards()
        write_yaml_file(root / "kb" / "main" / "trusted" / "overlap-scan.yaml", cards["overlap_scan"])
        write_yaml_file(root / "kb" / "main" / "trusted" / "overlap-release.yaml", cards["overlap_release"])
        write_yaml_file(root / "kb" / "main" / "candidates" / "unique-merge.yaml", cards["unique_merge"])
        write_yaml_file(root / "kb" / "main" / "candidates" / "unique-skill.yaml", cards["unique_skill"])
    else:
        write_yaml_file(root / "kb" / "main" / "seed.yaml", {"id": "seed", "status": "trusted"})
    (root / "kb" / "main" / ".gitkeep").write_text("", encoding="utf-8")
    (root / "kb" / "imports").mkdir(parents=True, exist_ok=True)
    (root / "kb" / "imports" / ".gitkeep").write_text("", encoding="utf-8")
    write_yaml_file(root / "skills" / "registry.yaml", {"skills": []})
    (root / "skills" / "candidates").mkdir(parents=True, exist_ok=True)
    (root / "skills" / "candidates" / ".gitkeep").write_text("", encoding="utf-8")


def write_legacy_org_repo(root: Path, *, include_sandbox_cards: bool = True) -> None:
    """Exact retired format used only to prove the one-time migration boundary."""
    write_yaml_file(
        root / "khaos_org_kb.yaml",
        {
            "kind": "khaos-organization-kb",
            "schema_version": 1,
            "organization_id": ORGANIZATION_ID,
            "kb": {
                "trusted_path": "kb/trusted",
                "candidates_path": "kb/candidates",
                "imports_path": "kb/imports",
            },
            "skills": {
                "registry_path": "skills/registry.yaml",
                "candidates_path": "skills/candidates",
            },
        },
    )
    cards = organization_sandbox_cards()
    if include_sandbox_cards:
        write_yaml_file(root / "kb" / "trusted" / "overlap-scan.yaml", cards["overlap_scan"])
        write_yaml_file(root / "kb" / "candidates" / "unique-merge.yaml", cards["unique_merge"])
    else:
        write_yaml_file(root / "kb" / "trusted" / "seed.yaml", {"id": "seed", "status": "trusted"})
        (root / "kb" / "candidates").mkdir(parents=True, exist_ok=True)
    (root / "kb" / "imports").mkdir(parents=True, exist_ok=True)
    write_yaml_file(root / "skills" / "registry.yaml", {"skills": []})
    (root / "skills" / "candidates").mkdir(parents=True, exist_ok=True)


def init_git_repo(root: Path, *, message: str = "seed") -> None:
    result = _run_git(["init"], cwd=root)
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    commit_all(root, message=message)


def commit_all(root: Path, *, message: str) -> str:
    add = _run_git(["add", "."], cwd=root)
    if add.returncode != 0:
        raise AssertionError(add.stderr or add.stdout)
    commit = _run_git(
        ["-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", message],
        cwd=root,
    )
    if commit.returncode != 0:
        raise AssertionError(commit.stderr or commit.stdout)
    rev = _run_git(["rev-parse", "HEAD"], cwd=root)
    if rev.returncode != 0:
        raise AssertionError(rev.stderr or rev.stdout)
    return rev.stdout.strip()


def connect_profile_to_org(profile_root: Path, org_repo: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = connect_organization_source(profile_root, str(org_repo))
    if not result.get("ok"):
        return result, []
    save_desktop_settings(
        profile_root,
        {
            "mode": ORGANIZATION_MODE,
            "organization": result["settings"],
        },
    )
    settings = load_desktop_settings(profile_root)
    activate_current_kb_runtime(profile_root)
    return result, organization_sources_from_settings(settings)


def write_local_skill(repo_root: Path, skill_id: str = "demo-skill", *, body: str = "Use this Skill.") -> Path:
    skill_dir = repo_root / ".agents" / "skills" / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_id}\ndescription: Demo Skill for organization acceptance tests.\n---\n\n{body}",
        encoding="utf-8",
    )
    return skill_dir


def write_local_skill_backed_card(repo_root: Path, entry_id: str = "skill-backed-card") -> Path:
    write_local_skill(repo_root)
    path = repo_root / "kb" / "public" / f"{entry_id}.yaml"
    payload = base_card(
        entry_id,
        "Skill backed organization contribution",
        "Export the card and its Skill bundle together for organization review.",
        confidence=0.82,
        route=["codex", "workflow", "skills"],
        required_skills=["demo-skill"],
        author="machine-a",
    )
    if authority_generation_pointer_path(repo_root).exists():
        publication = publish_sleep_model_generation(
            repo_root,
            reason="test-local-skill-backed-card",
            card_upserts={path.relative_to(repo_root).as_posix(): payload},
        )
        if not publication.get("ok"):
            raise RuntimeError(f"Unable to publish model-native test card: {publication}")
    else:
        write_yaml_file(path, payload)
        activate_current_kb_runtime(repo_root)
    return path


def publish_accepted_outbox_to_org_main(
    org_root: Path,
    outbox_dir: Path,
    *,
    message: str = "Publish accepted organization knowledge",
) -> list[str]:
    org_root = Path(org_root)
    outbox_dir = Path(outbox_dir)
    created: list[str] = []
    main_dir = org_root / "kb" / "main"
    main_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(outbox_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(outbox_dir)
        target = main_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        created.append(target.relative_to(org_root).as_posix())
    if created:
        commit_all(org_root, message=message)
    return created


def load_first_yaml(path: Path) -> dict[str, Any]:
    files = sorted(Path(path).glob("*.yaml"))
    if not files:
        return {}
    return load_yaml_file(files[0])
