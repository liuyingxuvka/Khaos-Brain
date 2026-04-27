from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from typing import Any

from local_kb.org_sources import _git_executable


def parse_github_owner_repo(repo_url: str) -> tuple[str, str]:
    text = str(repo_url or "").strip()
    if text.endswith(".git"):
        text = text[:-4]
    if text.startswith("git@github.com:"):
        text = text.removeprefix("git@github.com:")
    elif text.startswith("https://github.com/"):
        text = text.removeprefix("https://github.com/")
    else:
        match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/\s]+)", text)
        if not match:
            return "", ""
        return match.group("owner"), match.group("repo").removesuffix(".git")
    parts = [part for part in text.split("/") if part]
    if len(parts) < 2:
        return "", ""
    return parts[0], parts[1]


def build_branch_protection_payload(required_contexts: list[str]) -> dict[str, Any]:
    return {
        "required_status_checks": {
            "strict": True,
            "contexts": required_contexts,
        },
        "enforce_admins": False,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "required_linear_history": False,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": False,
        "required_conversation_resolution": False,
        "lock_branch": False,
        "allow_fork_syncing": True,
    }


def github_token_from_git_credential() -> str:
    payload = "protocol=https\nhost=github.com\n\n"
    result = subprocess.run(
        [_git_executable(), "credential", "fill"],
        input=payload,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values.get("password", "")


def _github_json_request(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return {"ok": 200 <= response.status < 300, "status": response.status, "body": json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = raw
        return {"ok": False, "status": exc.code, "body": body}
    except OSError as exc:
        return {"ok": False, "status": 0, "body": {"message": str(exc)}}


def _token_or_default(token: str) -> str:
    return str(token or os.environ.get("GITHUB_TOKEN") or github_token_from_git_credential() or "").strip()


def create_github_pull_request_for_branch(
    repo_url: str,
    *,
    branch: str,
    base_branch: str = "main",
    title: str,
    body: str = "",
    labels: list[str] | None = None,
    token: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    owner, repo = parse_github_owner_repo(repo_url)
    if not owner or not repo:
        return {"ok": True, "attempted": False, "reason": "repo_url is not a GitHub repository URL", "steps": []}
    resolved_token = _token_or_default(token)
    label_values = [label for label in (labels or []) if str(label or "").strip()]
    steps = [
        {
            "name": "create-pr",
            "method": "POST",
            "url": f"https://api.github.com/repos/{owner}/{repo}/pulls",
            "payload": {
                "title": title,
                "head": branch,
                "base": base_branch,
                "body": body,
                "draft": False,
            },
        }
    ]
    if label_values:
        steps.append(
            {
                "name": "add-labels",
                "method": "POST",
                "url": f"https://api.github.com/repos/{owner}/{repo}/issues/{{number}}/labels",
                "payload": {"labels": label_values},
            }
        )
    if dry_run:
        return {
            "ok": True,
            "attempted": True,
            "dry_run": True,
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "base_branch": base_branch,
            "labels": label_values,
            "steps": steps,
            "errors": [],
        }
    if not resolved_token:
        return {"ok": False, "attempted": True, "errors": ["GitHub token is required"], "steps": steps}

    pr_step = steps[0]
    pr_result = _github_json_request(pr_step["method"], pr_step["url"], resolved_token, pr_step["payload"])
    results: list[dict[str, Any]] = [{"name": "create-pr", **pr_result}]
    errors: list[str] = []
    if not pr_result.get("ok"):
        body_payload = pr_result.get("body")
        message = body_payload.get("message") if isinstance(body_payload, dict) else body_payload
        errors.append(f"create-pr failed: {message or pr_result.get('status')}")
        return {"ok": False, "attempted": True, "steps": results, "errors": errors}

    pr_body = pr_result.get("body") if isinstance(pr_result.get("body"), dict) else {}
    number = pr_body.get("number")
    html_url = str(pr_body.get("html_url") or "")
    if label_values and number:
        label_step = steps[1]
        label_url = str(label_step["url"]).replace("{number}", str(number))
        label_result = _github_json_request(label_step["method"], label_url, resolved_token, label_step["payload"])
        results.append({"name": "add-labels", **label_result})
        if not label_result.get("ok"):
            body_payload = label_result.get("body")
            message = body_payload.get("message") if isinstance(body_payload, dict) else body_payload
            errors.append(f"add-labels failed: {message or label_result.get('status')}")

    return {
        "ok": not errors,
        "attempted": True,
        "dry_run": False,
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "base_branch": base_branch,
        "number": number,
        "url": html_url,
        "labels": label_values,
        "steps": results,
        "errors": errors,
    }


def configure_github_org_kb_repository(
    repo_url: str,
    *,
    token: str,
    branch: str = "main",
    required_contexts: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    owner, repo = parse_github_owner_repo(repo_url)
    if not owner or not repo:
        return {"ok": False, "errors": ["repo_url is not a GitHub repository URL"], "steps": []}
    if not token and not dry_run:
        return {"ok": False, "errors": ["GitHub token is required"], "steps": []}

    contexts = required_contexts or ["organization-kb-checks"]
    protection_payload = build_branch_protection_payload(contexts)
    steps = [
        {
            "name": "enable-auto-merge",
            "method": "PATCH",
            "url": f"https://api.github.com/repos/{owner}/{repo}",
            "payload": {"allow_auto_merge": True},
        },
        {
            "name": "protect-default-branch",
            "method": "PUT",
            "url": f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}/protection",
            "payload": protection_payload,
        },
    ]
    if dry_run:
        return {"ok": True, "dry_run": True, "owner": owner, "repo": repo, "branch": branch, "steps": steps, "errors": []}

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for step in steps:
        result = _github_json_request(step["method"], step["url"], token, step["payload"])
        results.append({"name": step["name"], **result})
        if not result.get("ok"):
            message = result.get("body", {}).get("message") if isinstance(result.get("body"), dict) else result.get("body")
            errors.append(f"{step['name']} failed: {message or result.get('status')}")

    return {
        "ok": not errors,
        "dry_run": False,
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "steps": results,
        "errors": errors,
    }
