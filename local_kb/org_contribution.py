from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote

from local_kb.org_sources import _run_git, current_git_commit, utc_timestamp, validate_organization_repo
from local_kb.store import load_yaml_file


def _safe_segment(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in "._-" else "-" for char in value.strip()).strip("-")
    return safe or "contributor"


def current_git_branch(repo_path: Path) -> str:
    result = _run_git(["branch", "--show-current"], cwd=repo_path)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def github_compare_url(remote_url: str, branch: str, *, base_branch: str = "main") -> str:
    remote = str(remote_url or "").strip()
    branch = str(branch or "").strip()
    base_branch = str(base_branch or "main").strip() or "main"
    if not remote or not branch:
        return ""
    if remote.endswith(".git"):
        remote = remote[:-4]
    if remote.startswith("git@github.com:"):
        repo = remote.removeprefix("git@github.com:")
        remote = f"https://github.com/{repo}"
    if not remote.startswith("https://github.com/"):
        return ""
    return f"{remote}/compare/{quote(base_branch)}...{quote(branch)}?expand=1"


def push_organization_branch(
    org_root: Path,
    branch_name: str,
    *,
    remote: str = "origin",
    base_branch: str = "main",
) -> dict[str, Any]:
    org_root = Path(org_root)
    branch_name = str(branch_name or "").strip() or current_git_branch(org_root)
    if not branch_name:
        return {"ok": False, "errors": ["branch_name is required"], "pushed": False, "pull_request_url": ""}

    result = _run_git(["push", "-u", remote, branch_name], cwd=org_root)
    remote_url_result = _run_git(["remote", "get-url", remote], cwd=org_root)
    remote_url = remote_url_result.stdout.strip() if remote_url_result.returncode == 0 else ""
    return {
        "ok": result.returncode == 0,
        "errors": [] if result.returncode == 0 else [result.stderr.strip() or result.stdout.strip()],
        "pushed": result.returncode == 0,
        "branch": branch_name,
        "remote": remote,
        "pull_request_url": github_compare_url(remote_url, branch_name, base_branch=base_branch),
    }


def _safe_outbox_path(outbox_dir: Path, path: Path) -> Path | None:
    try:
        resolved = Path(path).resolve()
        resolved.relative_to(outbox_dir.resolve())
    except (OSError, ValueError):
        return None
    return resolved


def _proposal_dependency_files(outbox_dir: Path, proposal_file: Path) -> list[Path]:
    try:
        payload = load_yaml_file(proposal_file)
    except Exception:
        return []
    proposal = payload.get("organization_proposal") if isinstance(payload.get("organization_proposal"), dict) else {}
    dependencies = proposal.get("skill_dependencies") if isinstance(proposal.get("skill_dependencies"), list) else []
    files: set[Path] = set()
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            continue
        for key in ("bundle_path", "bundle_metadata_path"):
            rel = str(dependency.get(key) or "").strip()
            if not rel:
                continue
            target = _safe_outbox_path(outbox_dir, outbox_dir / rel)
            if target is None or not target.exists():
                continue
            if target.is_file():
                files.add(target)
            elif target.is_dir():
                files.update(path for path in target.rglob("*") if path.is_file())
    return sorted(files)


def prepare_organization_import_branch(
    org_root: Path,
    outbox_dir: Path,
    *,
    contributor_id: str,
    branch_name: str = "",
    commit: bool = True,
    push: bool = False,
    remote: str = "origin",
    base_branch: str = "main",
    proposal_files: list[Path] | None = None,
) -> dict[str, Any]:
    org_root = Path(org_root)
    outbox_dir = Path(outbox_dir)
    validation = validate_organization_repo(org_root)
    if not validation.get("ok"):
        return {"ok": False, "errors": validation.get("errors") or ["invalid organization repository"], "created_files": []}
    if not (org_root / ".git").exists():
        return {"ok": False, "errors": ["organization repository mirror is not a git checkout"], "created_files": []}
    if not outbox_dir.exists():
        return {"ok": False, "errors": [f"outbox directory does not exist: {outbox_dir}"], "created_files": []}

    if proposal_files is None:
        proposal_files = sorted(outbox_dir.glob("*.yaml"))
        outbox_files = [path for path in sorted(outbox_dir.rglob("*")) if path.is_file()]
    else:
        proposal_files = [
            path
            for path in (_safe_outbox_path(outbox_dir, Path(item)) for item in proposal_files)
            if path is not None and path.exists() and path.is_file() and path.suffix == ".yaml"
        ]
        outbox_file_set: set[Path] = set(proposal_files)
        for proposal in proposal_files:
            outbox_file_set.update(_proposal_dependency_files(outbox_dir, proposal))
        outbox_files = sorted(outbox_file_set)
    if not proposal_files:
        return {"ok": False, "errors": ["outbox directory has no YAML proposals"], "created_files": []}

    safe_contributor = _safe_segment(contributor_id)
    branch = branch_name or f"contrib/{safe_contributor}/{utc_timestamp().replace(':', '').replace('-', '')}"
    checkout = _run_git(["checkout", "-B", branch], cwd=org_root)
    if checkout.returncode != 0:
        return {"ok": False, "errors": [checkout.stderr.strip() or checkout.stdout.strip()], "created_files": []}

    import_dir = org_root / "kb" / "imports" / safe_contributor
    import_dir.mkdir(parents=True, exist_ok=True)
    created_files: list[str] = []
    for proposal in outbox_files:
        relative = proposal.relative_to(outbox_dir)
        target = import_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(proposal, target)
        created_files.append(target.relative_to(org_root).as_posix())

    add = _run_git(["add", *created_files], cwd=org_root)
    if add.returncode != 0:
        return {"ok": False, "errors": [add.stderr.strip() or add.stdout.strip()], "created_files": created_files}

    committed = False
    commit_hash = ""
    if commit:
        result = _run_git(
            [
                "-c",
                "user.name=Khaos Brain",
                "-c",
                "user.email=khaos-brain@example.invalid",
                "commit",
                "-m",
                "Add organization KB import proposals",
            ],
            cwd=org_root,
        )
        if result.returncode != 0:
            return {"ok": False, "errors": [result.stderr.strip() or result.stdout.strip()], "created_files": created_files}
        committed = True
        commit_hash = current_git_commit(org_root)

    push_result = {"pushed": False, "pull_request_url": "", "errors": []}
    if push:
        push_result = push_organization_branch(org_root, branch, remote=remote, base_branch=base_branch)
        if not push_result.get("ok"):
            return {
                "ok": False,
                "errors": push_result.get("errors") or ["failed to push organization contribution branch"],
                "created_files": created_files,
                "branch": branch,
                "committed": committed,
                "commit": commit_hash,
                "push": push_result,
            }

    return {
        "ok": True,
        "errors": [],
        "organization_id": validation.get("organization_id"),
        "branch": branch,
        "created_files": created_files,
        "committed": committed,
        "commit": commit_hash,
        "push": push_result,
        "pull_request_url": push_result.get("pull_request_url") or "",
    }
