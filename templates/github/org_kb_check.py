from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


LOW_RISK_PREFIXES = ("kb/imports/", "kb/candidates/", "skills/candidates/")
MAINTENANCE_MAIN_PREFIXES = ("kb/main/",)
SKILL_REVIEW_STATES = {"candidate", "approved", "rejected"}
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
RAW_MACHINE_KEYS = {"hardware_id", "hardware_fingerprint", "machine_id", "device_id", "local_installation_id"}


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


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def append_machine_key_errors(payload: Any, errors: list[str], path_label: str, key_path: str = "") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_key = f"{key_path}.{key}" if key_path else str(key)
            if str(key) in RAW_MACHINE_KEYS and str(value or "").strip():
                errors.append(f"{path_label}: raw machine identifier is not allowed at {next_key}")
            append_machine_key_errors(value, errors, path_label, next_key)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            append_machine_key_errors(item, errors, path_label, f"{key_path}[{index}]")


def check_manifest(root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "khaos_org_kb.yaml"
    if not manifest_path.exists():
        return ["missing organization KB manifest: khaos_org_kb.yaml"]
    manifest = load_yaml(manifest_path)
    if manifest.get("kind") != "khaos-organization-kb":
        errors.append("manifest kind must be khaos-organization-kb")
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not str(manifest.get("organization_id") or "").strip():
        errors.append("organization_id is required")
    kb = manifest.get("kb") if isinstance(manifest.get("kb"), dict) else {}
    main_path = str(kb.get("main_path") or "").strip() or ("kb/main" if (root / "kb" / "main").exists() else "")
    card_paths = (main_path, "kb/imports") if main_path else ("kb/trusted", "kb/candidates", "kb/imports")
    for relative in (*card_paths, "skills/candidates"):
        if not relative:
            continue
        if not (root / relative).exists():
            errors.append(f"required path does not exist: {relative}")
    if not (root / "skills" / "registry.yaml").exists():
        errors.append("skills registry does not exist: skills/registry.yaml")
    return errors


def check_paths(changed_files: list[str], enforce_low_risk: bool, *, allow_maintenance_main: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    blockers: list[str] = []
    has_maintenance_audit = "maintenance/cleanup_audit.jsonl" in changed_files
    outside = []
    for path in changed_files:
        if path.startswith(LOW_RISK_PREFIXES):
            continue
        if allow_maintenance_main and has_maintenance_audit and path.startswith(MAINTENANCE_MAIN_PREFIXES):
            continue
        if allow_maintenance_main and has_maintenance_audit and path == "maintenance/cleanup_audit.jsonl":
            continue
        outside.append(path)
    if outside:
        blockers.append("changed files are not all low-risk paths")
        if enforce_low_risk:
            errors.extend(f"path is not eligible for low-risk auto-merge: {path}" for path in outside)
    if not changed_files:
        blockers.append("changed files are not all low-risk paths")
    return errors, blockers


def scan_content(root: Path, changed_files: list[str]) -> list[str]:
    errors: list[str] = []
    files = changed_files or [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts and path.suffix.lower() in {".yaml", ".yml", ".md", ".json", ".txt"}
    ]
    for relative in files:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            errors.append(f"{relative}: possible secret or credential pattern")
        if any(pattern.search(text) for pattern in LOCAL_PATH_PATTERNS):
            errors.append(f"{relative}: local machine path is not allowed")
        if path.suffix.lower() in {".yaml", ".yml"}:
            append_machine_key_errors(load_yaml(path), errors, relative)
    return errors


def check_skill_registry(root: Path) -> list[str]:
    errors: list[str] = []
    payload = load_yaml(root / "skills" / "registry.yaml")
    skills = payload.get("skills")
    if not isinstance(skills, list):
        return ["skills registry must contain a skills list"]
    seen: set[str] = set()
    for index, item in enumerate(skills):
        if not isinstance(item, dict):
            errors.append(f"skills[{index}] must be a mapping")
            continue
        skill_id = str(item.get("id") or item.get("name") or "").strip()
        status = str(item.get("status") or "").strip()
        if not skill_id:
            errors.append(f"skills[{index}] is missing id")
            continue
        if skill_id in seen:
            errors.append(f"duplicate skill id: {skill_id}")
        seen.add(skill_id)
        if status not in SKILL_REVIEW_STATES:
            errors.append(f"skill {skill_id} has invalid status: {status}")
        if status == "approved":
            if not str(item.get("version") or "").strip():
                errors.append(f"approved skill {skill_id} must pin version")
            if not str(item.get("content_hash") or "").startswith("sha256:"):
                errors.append(f"approved skill {skill_id} must pin sha256 content_hash")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-root", default=".")
    parser.add_argument("--changed-files-file", default="")
    parser.add_argument("--enforce-low-risk", action="store_true")
    parser.add_argument("--allow-maintenance-main", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    root = Path(args.org_root)
    changed_files = []
    if args.changed_files_file:
        changed_files = [
            path
            for path in (normalize_changed_file(line) for line in Path(args.changed_files_file).read_text(encoding="utf-8").splitlines())
            if path
        ]
    path_errors, blockers = check_paths(
        changed_files,
        args.enforce_low_risk,
        allow_maintenance_main=args.allow_maintenance_main,
    )
    errors = [
        *check_manifest(root),
        *path_errors,
        *scan_content(root, changed_files),
        *check_skill_registry(root),
    ]
    result = {
        "ok": not errors,
        "auto_merge_eligible": bool(changed_files) and not errors and not blockers,
        "errors": errors,
        "auto_merge_blockers": blockers,
        "changed_files": changed_files,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
