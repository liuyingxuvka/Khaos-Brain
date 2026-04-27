from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from local_kb.adoption import card_exchange_hash
from local_kb.org_sources import validate_organization_repo
from local_kb.store import load_yaml_file


LOW_RISK_PREFIXES = ("kb/imports/", "kb/candidates/", "skills/candidates/")
PROTECTED_PREFIXES = ("kb/main/", "kb/trusted/")
PROTECTED_FILES = {"khaos_org_kb.yaml", "skills/registry.yaml"}
TEXT_SUFFIXES = {".yaml", ".yml", ".md", ".json", ".txt"}
SKILL_REVIEW_STATES = {"candidate", "approved", "rejected"}
SKILL_REQUIREMENTS = {"required", "recommended", "optional"}

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?im)^\s*(password|secret|api[_-]?key|access[_-]?token)\s*:\s*['\"]?[^'\"\s][^'\"]*"),
)
LOCAL_PATH_PATTERNS = (
    re.compile(r"[A-Za-z]:\\Users\\"),
    re.compile(r"/Users/[^/\s]+/"),
    re.compile(r"/home/[^/\s]+/"),
    re.compile(r"\.codex[\\/]+"),
    re.compile(r"AppData\\"),
)
RAW_MACHINE_KEYS = {
    "hardware_id",
    "hardware_fingerprint",
    "machine_id",
    "device_id",
    "local_installation_id",
}
CARD_HASH_MEANING_KEYS = {
    "title",
    "type",
    "domain_path",
    "cross_index",
    "tags",
    "trigger_keywords",
    "if",
    "action",
    "predict",
    "use",
}


def normalize_changed_file(value: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    if not text or text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        return ""
    parts = PurePosixPath(text).parts
    if any(part in {"", ".", ".."} for part in parts):
        return ""
    return "/".join(parts)


def _is_low_risk_path(path: str) -> bool:
    return path.startswith(LOW_RISK_PREFIXES)


def _is_protected_path(path: str) -> bool:
    return path in PROTECTED_FILES or path.startswith(PROTECTED_PREFIXES)


def _iter_yaml_files(root: Path, relative_roots: Iterable[str]) -> Iterable[Path]:
    for relative in relative_roots:
        target = root / relative
        if target.is_file() and target.suffix.lower() in {".yaml", ".yml"}:
            yield target
        elif target.is_dir():
            yield from sorted(target.rglob("*.yaml"))
            yield from sorted(target.rglob("*.yml"))


def _iter_scan_files(root: Path, changed_files: list[str]) -> Iterable[Path]:
    if changed_files:
        for relative in changed_files:
            path = root / relative
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                yield path
        return

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if ".git" in path.parts:
            continue
        yield path


def _append_yaml_machine_key_errors(
    payload: Any,
    *,
    path_label: str,
    errors: list[str],
    key_path: str = "",
) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            text_key = str(key)
            nested_key_path = f"{key_path}.{text_key}" if key_path else text_key
            if text_key in RAW_MACHINE_KEYS and str(value or "").strip():
                errors.append(f"{path_label}: raw machine identifier is not allowed at {nested_key_path}")
            _append_yaml_machine_key_errors(value, path_label=path_label, errors=errors, key_path=nested_key_path)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            _append_yaml_machine_key_errors(item, path_label=path_label, errors=errors, key_path=f"{key_path}[{index}]")


def _load_yaml_for_check(path: Path, errors: list[str], repo_root: Path) -> dict[str, Any]:
    try:
        payload = load_yaml_file(path)
    except Exception as exc:  # pragma: no cover - parser details vary
        errors.append(f"{path.relative_to(repo_root).as_posix()}: failed to parse YAML: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{path.relative_to(repo_root).as_posix()}: YAML document must be a mapping")
        return {}
    return payload


def _has_hash_meaning(payload: dict[str, Any]) -> bool:
    return any(payload.get(key) for key in CARD_HASH_MEANING_KEYS)


def _check_changed_paths(changed_files: list[str], *, enforce_low_risk: bool) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    invalid = [path for path in changed_files if not normalize_changed_file(path)]
    low_risk = [path for path in changed_files if _is_low_risk_path(path)]
    protected = [path for path in changed_files if _is_protected_path(path)]
    outside_low_risk = [path for path in changed_files if not _is_low_risk_path(path)]

    if invalid:
        errors.extend(f"invalid changed file path: {path}" for path in invalid)
    if protected:
        warnings.append("protected organization paths require organization maintenance evidence and merge rules")
    if enforce_low_risk and outside_low_risk:
        errors.extend(f"path is not eligible for low-risk auto-merge: {path}" for path in outside_low_risk)

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "low_risk_files": low_risk,
        "protected_files": protected,
        "outside_low_risk_files": outside_low_risk,
        "all_low_risk": bool(changed_files) and not outside_low_risk,
    }


def _check_sensitive_content(root: Path, changed_files: list[str]) -> dict[str, Any]:
    errors: list[str] = []
    scanned: list[str] = []
    for path in _iter_scan_files(root, changed_files):
        relative = path.relative_to(root).as_posix()
        scanned.append(relative)
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"{relative}: possible secret or credential pattern")
                break
        for pattern in LOCAL_PATH_PATTERNS:
            if pattern.search(text):
                errors.append(f"{relative}: local machine path is not allowed")
                break
        if path.suffix.lower() in {".yaml", ".yml"}:
            payload = _load_yaml_for_check(path, errors, root)
            _append_yaml_machine_key_errors(payload, path_label=relative, errors=errors)
    return {"ok": not errors, "errors": errors, "scanned_files": scanned}


def _check_skill_registry(root: Path, registry_relative: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    skills_by_id: dict[str, dict[str, Any]] = {}
    skills_by_bundle_hash: set[tuple[str, str]] = set()
    registry_path = root / registry_relative
    if not registry_path.exists():
        return {"ok": False, "errors": [f"skills registry does not exist: {registry_relative}"], "warnings": []}

    payload = _load_yaml_for_check(registry_path, errors, root)
    skills = payload.get("skills")
    if not isinstance(skills, list):
        return {"ok": False, "errors": errors + ["skills registry must contain a skills list"], "warnings": []}

    for index, item in enumerate(skills):
        if not isinstance(item, dict):
            errors.append(f"{registry_relative}: skills[{index}] must be a mapping")
            continue
        skill_id = str(item.get("id") or item.get("name") or "").strip()
        status = str(item.get("status") or "").strip()
        if not skill_id:
            errors.append(f"{registry_relative}: skills[{index}] is missing id")
            continue
        if skill_id in skills_by_id:
            warnings.append(f"{registry_relative}: duplicate skill id handle: {skill_id}")
        skills_by_id[skill_id] = item
        if status not in SKILL_REVIEW_STATES:
            errors.append(f"{registry_relative}: skill {skill_id} has invalid status: {status}")
        if status == "approved":
            version = str(item.get("version") or item.get("version_time") or "").strip()
            content_hash = str(item.get("content_hash") or "").strip()
            if not version:
                errors.append(f"{registry_relative}: approved skill {skill_id} must pin version")
            if not content_hash.startswith("sha256:"):
                errors.append(f"{registry_relative}: approved skill {skill_id} must pin sha256 content_hash")
        bundle_id = str(item.get("bundle_id") or "").strip()
        content_hash = str(item.get("content_hash") or "").strip()
        if bundle_id and content_hash:
            key = (bundle_id, content_hash)
            if key in skills_by_bundle_hash:
                warnings.append(f"{registry_relative}: duplicate Skill bundle version {bundle_id} {content_hash}")
            skills_by_bundle_hash.add(key)
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "skills_by_id": {skill_id: {"status": str(item.get("status") or "")} for skill_id, item in skills_by_id.items()},
    }


def _check_cards(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    hashes: dict[str, list[str]] = {}
    bundle_count = 0

    for relative_root, expected_statuses in (
        ("kb/main", {"trusted", "approved", "candidate", "rejected", "deprecated"}),
        ("kb/trusted", {"trusted", "approved", "deprecated"}),
        ("kb/candidates", {"candidate", "rejected", "deprecated"}),
        ("kb/imports", {"candidate", "rejected", "deprecated"}),
    ):
        for path in _iter_yaml_files(root, [relative_root]):
            relative = path.relative_to(root).as_posix()
            payload = _load_yaml_for_check(path, errors, root)
            status = str(payload.get("status") or "").strip()
            if _has_hash_meaning(payload):
                hashes.setdefault(card_exchange_hash(payload), []).append(relative)
            if status and status not in expected_statuses:
                errors.append(f"{relative}: status {status} is not valid under {relative_root}")

            proposal = payload.get("organization_proposal") if isinstance(payload.get("organization_proposal"), dict) else {}
            dependencies = proposal.get("skill_dependencies") if isinstance(proposal.get("skill_dependencies"), list) else []
            if dependencies:
                bundle_count += 1
                if not str(proposal.get("source_path") or "").strip():
                    warnings.append(f"{relative}: card-and-Skill bundle is missing source_path evidence")
                for index, dependency in enumerate(dependencies):
                    if not isinstance(dependency, dict):
                        errors.append(f"{relative}: skill_dependencies[{index}] must be a mapping")
                        continue
                    skill_id = str(dependency.get("id") or "").strip()
                    bundle_id = str(dependency.get("bundle_id") or "").strip()
                    requirement = str(dependency.get("requirement") or "required").strip()
                    if not skill_id:
                        errors.append(f"{relative}: skill_dependencies[{index}] is missing id")
                    if dependency.get("sharing_mode") == "card-bound-bundle":
                        if not bundle_id:
                            errors.append(f"{relative}: skill dependency {skill_id} is missing bundle_id")
                        if not str(dependency.get("content_hash") or "").strip().startswith("sha256:"):
                            errors.append(f"{relative}: skill dependency {skill_id} must include sha256 content_hash")
                        if not str(dependency.get("version_time") or "").strip():
                            errors.append(f"{relative}: skill dependency {skill_id} must include version_time")
                        bundle_path = str(dependency.get("bundle_path") or "").strip()
                        if not bundle_path:
                            errors.append(f"{relative}: skill dependency {skill_id} must include bundle_path")
                        else:
                            normalized_bundle_path = normalize_changed_file(bundle_path)
                            if not normalized_bundle_path:
                                errors.append(f"{relative}: skill dependency {skill_id} has invalid bundle_path")
                            elif not (path.parent / normalized_bundle_path / "SKILL.md").exists():
                                errors.append(f"{relative}: skill dependency {skill_id} bundle_path does not contain SKILL.md")
                    if requirement not in SKILL_REQUIREMENTS:
                        errors.append(f"{relative}: skill dependency {skill_id} has invalid requirement: {requirement}")

    duplicate_hashes = {content_hash: paths for content_hash, paths in hashes.items() if content_hash and len(paths) > 1}
    for content_hash, paths in duplicate_hashes.items():
        warnings.append(f"duplicate card content hash {content_hash}: {', '.join(paths)}")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "duplicate_content_hashes": duplicate_hashes,
        "bundle_count": bundle_count,
    }


def check_organization_repository(
    org_root: Path,
    *,
    changed_files: Iterable[str] | None = None,
    enforce_low_risk: bool = False,
) -> dict[str, Any]:
    org_root = Path(org_root)
    normalized_changed_files = [
        normalize_changed_file(path)
        for path in (changed_files or [])
        if str(path or "").strip()
    ]
    normalized_changed_files = [path for path in normalized_changed_files if path]

    validation = validate_organization_repo(org_root)
    checks: dict[str, Any] = {
        "manifest": {
            "ok": bool(validation.get("ok")),
            "errors": validation.get("errors") or [],
        }
    }
    errors: list[str] = list(validation.get("errors") or [])
    warnings: list[str] = []
    auto_merge_blockers: list[str] = []

    path_policy = _check_changed_paths(normalized_changed_files, enforce_low_risk=enforce_low_risk)
    checks["path_policy"] = path_policy
    errors.extend(path_policy["errors"])
    warnings.extend(path_policy["warnings"])
    if not path_policy["all_low_risk"]:
        auto_merge_blockers.append("changed files are not all low-risk paths")
    if path_policy["protected_files"]:
        auto_merge_blockers.append("protected path changes require explicit organization review")

    sensitive = _check_sensitive_content(org_root, normalized_changed_files)
    checks["privacy_scan"] = sensitive
    errors.extend(sensitive["errors"])

    registry_relative = str(validation.get("skills_registry_path") or "skills/registry.yaml")
    registry = _check_skill_registry(org_root, registry_relative)
    checks["skill_registry"] = registry
    errors.extend(registry["errors"])
    warnings.extend(registry["warnings"])

    cards = _check_cards(org_root)
    checks["cards"] = cards
    errors.extend(cards["errors"])
    warnings.extend(cards["warnings"])
    if cards.get("duplicate_content_hashes"):
        auto_merge_blockers.append("duplicate card content hashes require organization maintenance")

    auto_merge_eligible = bool(normalized_changed_files) and not errors and not auto_merge_blockers
    if enforce_low_risk and auto_merge_blockers:
        errors.extend(auto_merge_blockers)

    return {
        "ok": not errors,
        "auto_merge_eligible": auto_merge_eligible,
        "errors": errors,
        "warnings": warnings,
        "auto_merge_blockers": auto_merge_blockers,
        "changed_files": normalized_changed_files,
        "checks": checks,
    }
