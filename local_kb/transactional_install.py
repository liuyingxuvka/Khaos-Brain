"""Recovery-bound whole-tree installation for Chaos Brain managed runtime trees."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Callable, Mapping
from uuid import uuid4

from local_kb.common import utc_now_iso


INSTALL_SCHEMA_VERSION = 4
CONTROL_ROOT_NAME = ".khaos-brain-install"
COMMITTED_BACKUP_RETENTION = 3
TRANSIENT_DIRS = {"__pycache__", ".pytest_cache", "runs", "locks", "bootstrap", "test-results"}
TRANSIENT_SUFFIXES = {".pyc", ".pyo"}
SKILLGUARD_SOURCE_VALIDATION_SCHEMA = "chaos_brain.skillguard_source_validation.v1"
SKILLGUARD_WHOLE_TREE_POLICY_ID = "skillguard.managed-whole-tree-currentness.v1"


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _canonical_hash(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _portable_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if set(relative.parts) & TRANSIENT_DIRS or path.suffix.lower() in TRANSIENT_SUFFIXES:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def tree_manifest(root: Path) -> dict[str, Any]:
    rows = []
    for path in _portable_files(root):
        body = path.read_bytes()
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        )
    return {
        "file_count": len(rows),
        "byte_count": sum(int(row["size"]) for row in rows),
        "files": rows,
        "digest": _canonical_hash(rows),
    }


def _copytree(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "runs", "locks", "bootstrap", "test-results"),
    )


def _json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def _row_id(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(row.get(key) or "")
        if value:
            return value
    return ""


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if str(item)}


def _former_skillguard_runtime_residuals(skill_root: Path) -> list[str]:
    exact_files = (
        ".skillguard/work-contract.json",
        ".skillguard/check_manifest.json",
        ".skillguard/skillguard_closure_policy.json",
        ".skillguard/skillguard_evidence_rules.json",
        ".skillguard/skillguard_manifest.json",
        ".skillguard/skillguard_profile.json",
        ".skillguard/skillguard_skill_contract.json",
        ".skillguard/skillguard_progress_ledger.jsonl",
    )
    exact_directories = (
        ".skillguard/ai_judgments",
        ".skillguard/checks",
        ".skillguard/evidence",
        ".skillguard/reports",
    )
    residuals = [relative for relative in exact_files if (skill_root / relative).exists()]
    residuals.extend(
        relative for relative in exact_directories if (skill_root / relative).exists()
    )
    return sorted(residuals)


def _current_authority_shape(
    *,
    skill_id: str,
    source: Mapping[str, Any],
    manifest: Mapping[str, Any],
    compiled: Mapping[str, Any],
    residuals: list[str],
) -> bool:
    source_depth = source.get("depth_profile", {})
    compiled_depth = compiled.get("depth_profile", {})
    contract_hashes = {
        str(manifest.get("contract_hash") or ""),
        str(compiled.get("contract_hash") or ""),
    }
    expected_depth_fields = {
        "schema_version",
        "profile_id",
        "target_skill_id",
        "integration_mode",
        "native_owner_id",
        "native_route_ids",
        "native_check_ids",
        "skillguard_adds_domain_route",
        "enforcement_level",
        "required_closure_profiles",
        "provider_runtime",
        "claim_boundary",
    }
    closures = [
        row
        for row in compiled.get("closure_profiles", [])
        if isinstance(row, Mapping)
    ]
    obligation_ids = {
        str(row.get("obligation_id") or "")
        for row in compiled.get("obligations", [])
        if isinstance(row, Mapping)
    }
    native_check_ids = _string_set(source_depth.get("native_check_ids"))
    compiled_check_ids = {
        str(row.get("check_id") or "")
        for row in compiled.get("checks", [])
        if isinstance(row, Mapping)
    }
    return bool(
        not residuals
        and skill_id
        and source.get("skill_id") == skill_id
        and manifest.get("skill_id") == skill_id
        and compiled.get("skill_id") == skill_id
        and len(contract_hashes) == 1
        and "" not in contract_hashes
        and isinstance(source_depth, dict)
        and isinstance(compiled_depth, dict)
        and source_depth.get("target_skill_id") == skill_id
        and compiled_depth.get("target_skill_id") == skill_id
        and source_depth == compiled_depth
        and set(source_depth) == expected_depth_fields
        and source_depth.get("schema_version") == "skillguard.depth_profile.v2"
        and source_depth.get("integration_mode") == "native-integrated"
        and source_depth.get("native_owner_id") == skill_id
        and source_depth.get("skillguard_adds_domain_route") is False
        and source_depth.get("enforcement_level") == "enforced"
        and source_depth.get("required_closure_profiles") == ["enforced"]
        and bool(native_check_ids)
        and native_check_ids.issubset(compiled_check_ids)
        and isinstance(source_depth.get("provider_runtime"), dict)
        and bool(source_depth.get("provider_runtime"))
        and isinstance(compiled_depth.get("provider_runtime"), dict)
        and bool(compiled_depth.get("provider_runtime"))
        and len(closures) == 1
        and closures[0].get("profile_id") == "enforced"
        and _string_set(closures[0].get("required_obligation_ids"))
        == obligation_ids
    )


def _skillguard_authority(skill_root: Path) -> dict[str, Any]:
    control = skill_root / ".skillguard"
    v2_source = control / "contract-source.json"
    v2_manifest = control / "check-manifest.json"
    v2_compiled = control / "compiled-contract.json"
    if v2_source.is_file() and v2_manifest.is_file() and v2_compiled.is_file():
        try:
            source = _json_object(v2_source)
            manifest = _json_object(v2_manifest)
            compiled = _json_object(v2_compiled)
        except (OSError, ValueError, json.JSONDecodeError):
            return {"generation": -1, "check_count": 0, "issues": ["invalid-v2-json"]}
        if (
            source.get("schema_version") != "skillguard.contract_source.v2"
            or manifest.get("schema_version") != "skillguard.check_manifest.v2"
            or compiled.get("schema_version") != "skillguard.compiled_contract.v2"
        ):
            return {"generation": -1, "check_count": 0, "issues": ["invalid-v2-schema"]}
        checks = manifest.get("checks", []) if isinstance(manifest, dict) else []
        if not isinstance(checks, list):
            return {"generation": -1, "check_count": 0, "issues": ["invalid-v2-checks"]}
        skill_id = str(compiled.get("skill_id") or manifest.get("skill_id") or source.get("skill_id") or "")
        residuals = _former_skillguard_runtime_residuals(skill_root)
        return {
            "generation": 2,
            "check_count": len(checks),
            "source": source,
            "manifest": manifest,
            "compiled": compiled,
            "current_shape": _current_authority_shape(
                skill_id=skill_id,
                source=source,
                manifest=manifest,
                compiled=compiled,
                residuals=residuals,
            ),
            "former_runtime_residuals": residuals,
            "issues": [f"former-runtime-residual:{item}" for item in residuals],
        }
    if v2_source.exists() or v2_manifest.exists() or v2_compiled.exists():
        return {"generation": -1, "check_count": 0, "issues": ["incomplete-v2-authority"]}
    residuals = _former_skillguard_runtime_residuals(skill_root)
    return {
        "generation": 0,
        "check_count": 0,
        "current_shape": False,
        "former_runtime_residuals": residuals,
        "issues": [f"former-runtime-residual:{item}" for item in residuals],
    }


def _indexed_rows(payload: Mapping[str, Any], field: str, *id_keys: str) -> dict[str, dict[str, Any]]:
    rows = payload.get(field, [])
    if not isinstance(rows, list):
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        identity = _row_id(row, *id_keys)
        if identity:
            indexed[identity] = row
    return indexed


def _native_check_coverage(
    checks: Mapping[str, Mapping[str, Any]], check_ids: set[str]
) -> tuple[set[str], dict[str, set[str]], set[str]]:
    """Project native-check identity onto the obligations it actually proves."""

    covered: set[str] = set()
    evidence_by_obligation: dict[str, set[str]] = {}
    unresolved: set[str] = set()
    for check_id in check_ids:
        row = checks.get(check_id)
        if not isinstance(row, Mapping):
            unresolved.add(check_id)
            continue
        evidence_class = str(row.get("evidence_class") or "")
        for obligation_id in _string_set(row.get("covers_obligation_ids")):
            covered.add(obligation_id)
            if evidence_class:
                evidence_by_obligation.setdefault(obligation_id, set()).add(
                    evidence_class
                )
    return covered, evidence_by_obligation, unresolved


def _exact_active_fields(
    *,
    label: str,
    identity: str,
    active: Mapping[str, Any],
    incoming: Mapping[str, Any],
    fields: tuple[str, ...],
) -> list[str]:
    issues: list[str] = []
    for field in fields:
        if field in active and incoming.get(field) != active.get(field):
            issues.append(f"{label}:{identity}:changed-{field}")
    return issues


def _conditional_depth_wrapper_reorganizations(
    incoming: Mapping[str, Any], active: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    """Recognize a conditional depth wrapper replaced by its unchanged hard owner.

    This is deliberately narrow: the removed check must be a scheduled-production
    depth wrapper whose declared dependencies remain required, hard, and
    semantically unchanged for the same conditional obligation and closure.
    """

    incoming_compiled = incoming.get("compiled", {})
    active_compiled = active.get("compiled", {})
    incoming_manifest = incoming.get("manifest", {})
    active_manifest = active.get("manifest", {})
    if not all(
        isinstance(value, dict)
        for value in (
            incoming_compiled,
            active_compiled,
            incoming_manifest,
            active_manifest,
        )
    ):
        return {}
    incoming_obligations = _indexed_rows(
        incoming_compiled, "obligations", "obligation_id"
    )
    active_obligations = _indexed_rows(
        active_compiled, "obligations", "obligation_id"
    )
    incoming_checks = _indexed_rows(incoming_manifest, "checks", "check_id", "id")
    active_checks = _indexed_rows(active_manifest, "checks", "check_id", "id")
    incoming_closures = _indexed_rows(
        incoming_compiled, "closure_profiles", "profile_id"
    )
    active_closures = _indexed_rows(
        active_compiled, "closure_profiles", "profile_id"
    )
    reorganizations: dict[str, dict[str, Any]] = {}
    for obligation_id, active_obligation in active_obligations.items():
        incoming_obligation = incoming_obligations.get(obligation_id)
        if not isinstance(incoming_obligation, dict):
            continue
        if active_obligation.get("conditional") is not True or incoming_obligation.get(
            "conditional"
        ) is not True:
            continue
        if not bool(active_obligation.get("required")) or not bool(
            incoming_obligation.get("required")
        ):
            continue
        if active_obligation.get("invariant_id") != incoming_obligation.get(
            "invariant_id"
        ):
            continue
        active_required = _string_set(active_obligation.get("required_check_ids"))
        incoming_required = _string_set(incoming_obligation.get("required_check_ids"))
        removed_check_ids = active_required - incoming_required
        if not removed_check_ids or not incoming_required:
            continue
        active_closure_ids = {
            profile_id
            for profile_id, row in active_closures.items()
            if obligation_id in _string_set(row.get("required_obligation_ids"))
        }
        incoming_closure_ids = {
            profile_id
            for profile_id, row in incoming_closures.items()
            if obligation_id in _string_set(row.get("required_obligation_ids"))
        }
        if not active_closure_ids or not active_closure_ids.issubset(
            incoming_closure_ids
        ):
            continue
        replacement_check_ids: set[str] = set()
        removed_route_ids: set[str] = set()
        valid = True
        for check_id in removed_check_ids:
            active_check = active_checks.get(check_id)
            if not isinstance(active_check, dict):
                valid = False
                break
            if (
                active_check.get("depth_evidence_domain") != "scheduled_production"
                or active_check.get("evidence_class") != "hard"
                or obligation_id
                not in _string_set(active_check.get("covers_obligation_ids"))
            ):
                valid = False
                break
            dependencies = _string_set(active_check.get("depends_on_check_ids"))
            if not dependencies or not dependencies.issubset(incoming_required):
                valid = False
                break
            for dependency_id in dependencies:
                active_dependency = active_checks.get(dependency_id)
                incoming_dependency = incoming_checks.get(dependency_id)
                if not isinstance(active_dependency, dict) or not isinstance(
                    incoming_dependency, dict
                ):
                    valid = False
                    break
                if (
                    active_dependency.get("evidence_class") != "hard"
                    or incoming_dependency.get("evidence_class") != "hard"
                    or obligation_id
                    not in _string_set(
                        active_dependency.get("covers_obligation_ids")
                    )
                    or obligation_id
                    not in _string_set(
                        incoming_dependency.get("covers_obligation_ids")
                    )
                    or _exact_active_fields(
                        label="conditional-owner",
                        identity=dependency_id,
                        active=active_dependency,
                        incoming=incoming_dependency,
                        fields=(
                            "kind",
                            "evidence_class",
                            "command",
                            "args",
                            "cwd_token",
                            "expected",
                            "assertion_scope",
                        ),
                    )
                ):
                    valid = False
                    break
            if not valid:
                break
            replacement_check_ids.update(dependencies)
            route_id = str(active_check.get("native_route_id") or "")
            if route_id:
                removed_route_ids.add(route_id)
        if valid:
            reorganizations[obligation_id] = {
                "kind": "conditional-depth-wrapper-to-independent-hard-owner",
                "removed_check_ids": sorted(removed_check_ids),
                "replacement_check_ids": sorted(replacement_check_ids),
                "removed_route_ids": sorted(removed_route_ids),
                "preserved_closure_profile_ids": sorted(active_closure_ids),
            }
    return reorganizations


def _current_semantic_downgrade_reasons(
    incoming: Mapping[str, Any], active: Mapping[str, Any]
) -> list[str]:
    """Return losses between two confirmed-current authorities."""

    reasons: list[str] = []
    incoming_compiled = incoming.get("compiled", {})
    active_compiled = active.get("compiled", {})
    incoming_manifest = incoming.get("manifest", {})
    active_manifest = active.get("manifest", {})
    if not all(
        isinstance(value, dict)
        for value in (incoming_compiled, active_compiled, incoming_manifest, active_manifest)
    ):
        return ["v2-authority-unavailable"]

    incoming_obligations = _indexed_rows(incoming_compiled, "obligations", "obligation_id")
    active_obligations = _indexed_rows(active_compiled, "obligations", "obligation_id")
    incoming_checks = _indexed_rows(incoming_manifest, "checks", "check_id", "id")
    active_checks = _indexed_rows(active_manifest, "checks", "check_id", "id")
    conditional_reorganizations = _conditional_depth_wrapper_reorganizations(
        incoming, active
    )
    reorganized_obligation_ids = set(conditional_reorganizations)
    reorganized_check_ids = {
        check_id
        for row in conditional_reorganizations.values()
        for check_id in row["removed_check_ids"]
    }
    reorganized_route_ids = {
        route_id
        for row in conditional_reorganizations.values()
        for route_id in row["removed_route_ids"]
    }
    for obligation_id, active_row in active_obligations.items():
        incoming_row = incoming_obligations.get(obligation_id)
        if incoming_row is None:
            reasons.append(f"obligation:{obligation_id}:missing")
            continue
        if bool(active_row.get("required")) and not bool(incoming_row.get("required")):
            reasons.append(f"obligation:{obligation_id}:required-weakened")
        reasons.extend(
            _exact_active_fields(
                label="obligation",
                identity=obligation_id,
                active=active_row,
                incoming=incoming_row,
                fields=("invariant_id",),
            )
        )
        for field in ("owner_step_ids", "required_check_ids", "evidence_classes"):
            missing = _string_set(active_row.get(field)) - _string_set(incoming_row.get(field))
            if field == "required_check_ids" and obligation_id in conditional_reorganizations:
                missing -= set(
                    conditional_reorganizations[obligation_id]["removed_check_ids"]
                )
            if missing:
                reasons.append(f"obligation:{obligation_id}:lost-{field}:{sorted(missing)}")

    for check_id, active_row in active_checks.items():
        incoming_row = incoming_checks.get(check_id)
        if incoming_row is None:
            if check_id in reorganized_check_ids:
                continue
            reasons.append(f"check:{check_id}:missing")
            continue
        reasons.extend(
            _exact_active_fields(
                label="check",
                identity=check_id,
                active=active_row,
                incoming=incoming_row,
                fields=(
                    "kind",
                    "evidence_class",
                    "command",
                    "args",
                    "cwd_token",
                    "expected",
                    "assertion_scope",
                ),
            )
        )
        missing_coverage = _string_set(active_row.get("covers_obligation_ids")) - _string_set(
            incoming_row.get("covers_obligation_ids")
        )
        if missing_coverage:
            reasons.append(f"check:{check_id}:lost-coverage:{sorted(missing_coverage)}")
        active_timeout = active_row.get("timeout_seconds")
        incoming_timeout = incoming_row.get("timeout_seconds")
        if isinstance(active_timeout, (int, float)) and (
            not isinstance(incoming_timeout, (int, float)) or incoming_timeout < active_timeout
        ):
            reasons.append(f"check:{check_id}:timeout-weakened")

    incoming_closures = _indexed_rows(incoming_compiled, "closure_profiles", "profile_id")
    active_closures = _indexed_rows(active_compiled, "closure_profiles", "profile_id")
    for profile_id, active_row in active_closures.items():
        incoming_row = incoming_closures.get(profile_id)
        if incoming_row is None:
            reasons.append(f"closure:{profile_id}:missing")
            continue
        missing = _string_set(active_row.get("required_obligation_ids")) - _string_set(
            incoming_row.get("required_obligation_ids")
        )
        if missing:
            reasons.append(f"closure:{profile_id}:lost-obligations:{sorted(missing)}")

    incoming_depth = incoming_compiled.get("depth_profile", {})
    active_depth = active_compiled.get("depth_profile", {})
    if isinstance(active_depth, dict) and active_depth:
        if not isinstance(incoming_depth, dict) or not incoming_depth:
            reasons.append("depth-profile:missing")
        else:
            reasons.extend(
                _exact_active_fields(
                    label="depth-profile",
                    identity=str(active_depth.get("profile_id") or "active"),
                    active=active_depth,
                    incoming=incoming_depth,
                    fields=(
                        "target_skill_id",
                        "integration_mode",
                        "native_owner_id",
                        "skillguard_adds_domain_route",
                        "enforcement_level",
                    ),
                )
            )
            for field in (
                "native_route_ids",
                "required_closure_profiles",
            ):
                missing = _string_set(active_depth.get(field)) - _string_set(incoming_depth.get(field))
                if field == "native_route_ids":
                    missing -= reorganized_route_ids
                if missing:
                    reasons.append(f"depth-profile:lost-{field}:{sorted(missing)}")
            active_native_check_ids = _string_set(active_depth.get("native_check_ids"))
            incoming_native_check_ids = _string_set(incoming_depth.get("native_check_ids"))
            if active_native_check_ids and not incoming_native_check_ids:
                reasons.append("depth-profile:native-check-authority-missing")
            active_native_coverage, active_native_evidence, active_unresolved = (
                _native_check_coverage(active_checks, active_native_check_ids)
            )
            incoming_native_coverage, incoming_native_evidence, incoming_unresolved = (
                _native_check_coverage(incoming_checks, incoming_native_check_ids)
            )
            if active_unresolved:
                reasons.append(
                    "depth-profile:active-native-check-unresolved:"
                    f"{sorted(active_unresolved)}"
                )
            if incoming_unresolved:
                reasons.append(
                    "depth-profile:incoming-native-check-unresolved:"
                    f"{sorted(incoming_unresolved)}"
                )
            missing_native_coverage = (
                active_native_coverage
                - incoming_native_coverage
                - reorganized_obligation_ids
            )
            if missing_native_coverage:
                reasons.append(
                    "depth-profile:lost-native-obligation-coverage:"
                    f"{sorted(missing_native_coverage)}"
                )
            for obligation_id in sorted(
                active_native_coverage & incoming_native_coverage
            ):
                missing_evidence_classes = active_native_evidence.get(
                    obligation_id, set()
                ) - incoming_native_evidence.get(obligation_id, set())
                if missing_evidence_classes:
                    reasons.append(
                        "depth-profile:lost-native-evidence-class:"
                        f"{obligation_id}:{sorted(missing_evidence_classes)}"
                    )
            incoming_dimensions = _indexed_rows(incoming_depth, "dimensions", "dimension_id")
            active_dimensions = _indexed_rows(active_depth, "dimensions", "dimension_id")
            for dimension_id, active_row in active_dimensions.items():
                incoming_row = incoming_dimensions.get(dimension_id)
                if incoming_row is None:
                    remaining_obligations = _string_set(
                        active_row.get("obligation_ids")
                    ) - reorganized_obligation_ids
                    if not remaining_obligations and not _string_set(
                        active_row.get("important_obligation_ids")
                    ):
                        continue
                    reasons.append(f"depth:{dimension_id}:missing")
                    continue
                if bool(active_row.get("required")) and not bool(incoming_row.get("required")):
                    reasons.append(f"depth:{dimension_id}:required-weakened")
                if bool(active_row.get("claim_blocker")) and not bool(
                    incoming_row.get("claim_blocker")
                ):
                    reasons.append(f"depth:{dimension_id}:claim-blocker-weakened")
                if active_row.get("allow_shared_evidence") is False and incoming_row.get(
                    "allow_shared_evidence"
                ) is not False:
                    reasons.append(f"depth:{dimension_id}:shared-evidence-weakened")
                active_minimum = active_row.get("minimum_coverage")
                incoming_minimum = incoming_row.get("minimum_coverage")
                if isinstance(active_minimum, (int, float)) and (
                    not isinstance(incoming_minimum, (int, float))
                    or incoming_minimum < active_minimum
                ):
                    reasons.append(f"depth:{dimension_id}:minimum-coverage-weakened")
                for field in ("obligation_ids", "important_obligation_ids"):
                    missing = _string_set(active_row.get(field)) - _string_set(incoming_row.get(field))
                    if field == "obligation_ids":
                        missing -= reorganized_obligation_ids
                    if missing:
                        reasons.append(f"depth:{dimension_id}:lost-{field}:{sorted(missing)}")
                active_classes = _string_set(active_row.get("accepted_evidence_classes"))
                incoming_classes = _string_set(incoming_row.get("accepted_evidence_classes"))
                if active_classes and (not incoming_classes or not incoming_classes.issubset(active_classes)):
                    reasons.append(f"depth:{dimension_id}:evidence-class-weakened")
            incoming_calibration = incoming_depth.get("calibration", {})
            active_calibration = active_depth.get("calibration", {})
            if isinstance(active_calibration, dict):
                if not isinstance(incoming_calibration, dict):
                    reasons.append("depth-calibration:missing")
                else:
                    for field in (
                        "positive_fixture_ids",
                        "shallow_fixture_ids",
                        "positive_check_ids",
                        "shallow_check_ids",
                    ):
                        missing = _string_set(active_calibration.get(field)) - _string_set(
                            incoming_calibration.get(field)
                        )
                        if missing:
                            reasons.append(f"depth-calibration:lost-{field}:{sorted(missing)}")
    return reasons


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(character in "0123456789abcdefABCDEF" for character in text)


def _authority_contract_hash(authority: Mapping[str, Any]) -> str:
    compiled = authority.get("compiled", {})
    manifest = authority.get("manifest", {})
    if not isinstance(compiled, dict) or not isinstance(manifest, dict):
        return ""
    hashes = {
        str(compiled.get("contract_hash") or ""),
        str(manifest.get("contract_hash") or ""),
    }
    return next(iter(hashes)) if len(hashes) == 1 and "" not in hashes else ""


def _validation_input_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "schema_version",
        "skill_id",
        "status",
        "ok",
        "source_tree_digest",
        "contract_hash",
        "manifest_hash",
        "contract_source_sha256",
        "compiled_contract_sha256",
        "check_manifest_sha256",
        "compiler_sha256",
        "generator_sha256",
        "generator_check_hash",
    )
    return {field: receipt.get(field) for field in fields}


def _skillguard_source_validation_issues(
    *,
    skill_id: str,
    receipt: Mapping[str, Any],
    authority: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
) -> list[str]:
    issues: list[str] = []
    if receipt.get("schema_version") != SKILLGUARD_SOURCE_VALIDATION_SCHEMA:
        issues.append("validation-schema-mismatch")
    if receipt.get("skill_id") != skill_id:
        issues.append("validation-skill-mismatch")
    if receipt.get("status") != "current" or receipt.get("ok") is not True:
        issues.append("validation-not-current")
    if not bool(authority.get("current_shape")):
        issues.append("incoming-authority-shape-not-current")
    if authority.get("issues"):
        issues.append("incoming-authority-has-residuals")
    if receipt.get("source_tree_digest") != source_manifest.get("digest"):
        issues.append("validation-source-tree-digest-mismatch")
    contract_hash = _authority_contract_hash(authority)
    if not contract_hash or receipt.get("contract_hash") != contract_hash:
        issues.append("validation-contract-hash-mismatch")
    files = source_manifest.get("files", [])
    file_hashes = {
        str(row.get("path") or ""): str(row.get("sha256") or "")
        for row in files
        if isinstance(row, dict)
    }
    expected_file_hashes = {
        "contract_source_sha256": file_hashes.get(".skillguard/contract-source.json", ""),
        "compiled_contract_sha256": file_hashes.get(".skillguard/compiled-contract.json", ""),
        "check_manifest_sha256": file_hashes.get(".skillguard/check-manifest.json", ""),
    }
    for field, expected in expected_file_hashes.items():
        if not expected or receipt.get(field) != expected:
            issues.append(f"validation-{field}-mismatch")
    for field in (
        "manifest_hash",
        "compiler_sha256",
        "generator_sha256",
        "generator_check_hash",
    ):
        if not _is_sha256(receipt.get(field)):
            issues.append(f"validation-{field}-invalid")
    expected_input_hash = _canonical_hash(_validation_input_payload(receipt))
    if receipt.get("validation_input_hash") != expected_input_hash:
        issues.append("validation-input-hash-mismatch")
    receipt_body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if receipt.get("receipt_hash") != _canonical_hash(receipt_body):
        issues.append("validation-receipt-hash-mismatch")
    return sorted(set(issues))


def _skillguard_downgrade_reasons(
    incoming: Mapping[str, Any],
    active: Mapping[str, Any],
    *,
    active_confirmed_current: bool,
) -> list[str]:
    if int(incoming.get("generation") or 0) != 2 or not bool(
        incoming.get("current_shape")
    ):
        return ["incoming-authority-not-current"]
    if not active_confirmed_current:
        return []
    if int(active.get("generation") or 0) != 2 or not bool(active.get("current_shape")):
        return ["active-current-confirmation-inconsistent"]
    return _current_semantic_downgrade_reasons(incoming, active)


def _skillguard_authority_snapshot(authority: Mapping[str, Any]) -> dict[str, Any]:
    source = authority.get("source", {})
    compiled = authority.get("compiled", {})
    manifest = authority.get("manifest", {})
    return {
        "generation": int(authority.get("generation") or 0),
        "check_count": int(authority.get("check_count") or 0),
        "current_shape": bool(authority.get("current_shape")),
        "former_runtime_residuals": list(authority.get("former_runtime_residuals") or []),
        "source": {
            "schema_version": source.get("schema_version"),
            "skill_id": source.get("skill_id"),
            "depth_profile": source.get("depth_profile", {}),
        }
        if isinstance(source, dict)
        else {},
        "compiled": {
            "schema_version": compiled.get("schema_version"),
            "skill_id": compiled.get("skill_id"),
            "contract_hash": compiled.get("contract_hash"),
            "obligations": compiled.get("obligations", []),
            "checks": compiled.get("checks", []),
            "closure_profiles": compiled.get("closure_profiles", []),
            "depth_profile": compiled.get("depth_profile", {}),
        }
        if isinstance(compiled, dict)
        else {},
        "manifest": {
            "schema_version": manifest.get("schema_version"),
            "skill_id": manifest.get("skill_id"),
            "contract_hash": manifest.get("contract_hash"),
            "checks": manifest.get("checks", []),
        }
        if isinstance(manifest, dict)
        else {},
    }


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _assert_under(path: Path, root: Path) -> None:
    path.resolve().relative_to(root.resolve())


def _cleanup_staging_root(stages_root: Path) -> list[str]:
    """Remove stage copies left by terminal, pre-journal, or recovered transactions."""

    removed: list[str] = []
    if not stages_root.exists():
        return removed
    for path in sorted(stages_root.iterdir(), key=lambda item: item.name):
        _assert_under(path, stages_root)
        _remove_path(path)
        removed.append(path.name)
    return removed


def _recover_incomplete(control_root: Path, codex_home: Path) -> list[str]:
    recovered: list[str] = []
    transaction_root = control_root / "transactions"
    if not transaction_root.exists():
        return recovered
    for journal_path in sorted(transaction_root.glob("*.json")):
        try:
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(journal.get("status") or "") in {"committed", "rolled_back", "recovered"}:
            continue
        for item in reversed(journal.get("operations", [])):
            if not isinstance(item, dict):
                continue
            active = Path(str(item.get("active_path") or ""))
            backup = Path(str(item.get("backup_path") or ""))
            _assert_under(active, codex_home)
            _assert_under(backup, control_root)
            if backup.exists():
                _remove_path(active)
                active.parent.mkdir(parents=True, exist_ok=True)
                os.replace(backup, active)
            elif not bool(item.get("had_active")):
                _remove_path(active)
        journal["status"] = "recovered"
        journal["recovered_at"] = utc_now_iso()
        transaction_id = str(journal.get("transaction_id") or journal_path.stem)
        stage_path = Path(
            str(journal.get("stage_root") or control_root / "staging" / transaction_id)
        )
        _assert_under(stage_path, control_root / "staging")
        _remove_path(stage_path)
        backup_root = Path(
            str(journal.get("backup_root") or control_root / "backups" / transaction_id)
        )
        _assert_under(backup_root, control_root / "backups")
        _remove_path(backup_root)
        journal["stage_cleanup"] = {
            "ok": not stage_path.exists(),
            "path": str(stage_path),
            "reason": "incomplete-transaction-recovery",
        }
        journal["failed_backup_cleanup"] = {
            "ok": not backup_root.exists(),
            "path": str(backup_root),
            "preserved_for_recovery": False,
        }
        _atomic_json(journal_path, journal)
        recovered.append(transaction_id)
    return recovered


def _backup_retention_receipt(
    *,
    control_root: Path,
    current_transaction_id: str,
    current_backup_root: Path,
    current_created_at: str,
    limit: int,
) -> dict[str, Any]:
    """Retain a bounded set of committed rollback trees and receipt every prune."""

    retention_limit = max(1, int(limit))
    transactions_root = control_root / "transactions"
    backups_root = control_root / "backups"
    candidates: list[dict[str, Any]] = []
    for journal_path in sorted(transactions_root.glob("*.json")):
        try:
            journal = _json_object(journal_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if journal.get("status") != "committed":
            continue
        transaction_id = str(journal.get("transaction_id") or journal_path.stem)
        backup_root = Path(str(journal.get("backup_root") or backups_root / transaction_id))
        try:
            _assert_under(backup_root, backups_root)
        except ValueError:
            continue
        if backup_root.exists():
            candidates.append(
                {
                    "transaction_id": transaction_id,
                    "backup_root": backup_root,
                    "order": str(journal.get("committed_at") or journal.get("created_at") or transaction_id),
                }
            )
    if not any(row["transaction_id"] == current_transaction_id for row in candidates):
        candidates.append(
            {
                "transaction_id": current_transaction_id,
                "backup_root": current_backup_root,
                "order": current_created_at,
            }
        )
    candidates.sort(key=lambda row: (str(row["order"]), str(row["transaction_id"])))
    current_rows = [
        row for row in candidates if str(row["transaction_id"]) == current_transaction_id
    ]
    previous_rows = [
        row for row in candidates if str(row["transaction_id"]) != current_transaction_id
    ]
    previous_limit = max(0, retention_limit - 1)
    retained_previous = previous_rows[-previous_limit:] if previous_limit else []
    retained_rows = retained_previous + current_rows[-1:]
    retained_ids = {str(row["transaction_id"]) for row in retained_rows}
    pruned: list[dict[str, Any]] = []
    for row in candidates:
        transaction_id = str(row["transaction_id"])
        if transaction_id in retained_ids:
            continue
        backup_root = Path(row["backup_root"])
        manifest = tree_manifest(backup_root)
        _remove_path(backup_root)
        pruned.append(
            {
                "transaction_id": transaction_id,
                "backup_root": str(backup_root),
                "backup_manifest": manifest,
                "deleted": not backup_root.exists(),
            }
        )
    retained = []
    for row in retained_rows:
        backup_root = Path(row["backup_root"])
        retained.append(
            {
                "transaction_id": str(row["transaction_id"]),
                "backup_root": str(backup_root),
                "backup_manifest": tree_manifest(backup_root),
            }
        )
    surviving_committed = [row for row in retained if Path(row["backup_root"]).exists()]
    return {
        "policy": "committed-backup-count",
        "limit": retention_limit,
        "generated_at": utc_now_iso(),
        "retained": retained,
        "pruned": pruned,
        "retained_count": len(surviving_committed),
        "pruned_count": len(pruned),
        "bounded": len(surviving_committed) <= retention_limit,
    }


def _install_receipt_payload(journal: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": journal.get("schema_version"),
        "transaction_id": journal.get("transaction_id"),
        "repo_root": journal.get("repo_root"),
        "source_manifests": journal.get("source_manifests", {}),
        "staged_manifests": journal.get("staged_manifests", {}),
        "installed_manifests": journal.get("installed_manifests", {}),
        "retired_post_manifests": journal.get("retired_post_manifests", {}),
        "operations": journal.get("operations", []),
        "backup_retention": journal.get("backup_retention", {}),
        "skillguard_authority_receipts": journal.get("skillguard_authority_receipts", {}),
        "recovered_transactions": journal.get("recovered_transactions", []),
    }


def _snapshot_authority_is_current(authority: Mapping[str, Any]) -> bool:
    source = authority.get("source", {})
    manifest = authority.get("manifest", {})
    compiled = authority.get("compiled", {})
    residuals = list(authority.get("former_runtime_residuals") or [])
    skill_id = str(
        compiled.get("skill_id") if isinstance(compiled, dict) else ""
    )
    return bool(
        authority.get("current_shape")
        and isinstance(source, dict)
        and isinstance(manifest, dict)
        and isinstance(compiled, dict)
        and _current_authority_shape(
            skill_id=skill_id,
            source=source,
            manifest=manifest,
            compiled=compiled,
            residuals=residuals,
        )
    )


def replay_install_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Replay a persisted receipt without needing the deleted staging tree."""

    issues: list[str] = []
    payload = receipt.get("receipt_payload")
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "issues": ["missing-receipt-payload"],
            "expected_receipt_hash": "",
            "actual_receipt_hash": str(receipt.get("receipt_hash") or ""),
        }
    expected_hash = _canonical_hash(payload)
    actual_hash = str(receipt.get("receipt_hash") or "")
    if expected_hash != actual_hash:
        issues.append("receipt-hash-mismatch")
    source = payload.get("source_manifests", {})
    staged = payload.get("staged_manifests", {})
    installed = payload.get("installed_manifests", {})
    if not all(isinstance(value, dict) for value in (source, staged, installed)):
        issues.append("manifest-map-invalid")
        source, staged, installed = {}, {}, {}
    if set(source) != set(staged) or set(staged) != set(installed):
        issues.append("manifest-key-set-mismatch")
    for key in sorted(set(source) & set(staged) & set(installed)):
        digests = {
            str(source[key].get("digest") or "") if isinstance(source[key], dict) else "",
            str(staged[key].get("digest") or "") if isinstance(staged[key], dict) else "",
            str(installed[key].get("digest") or "") if isinstance(installed[key], dict) else "",
        }
        if len(digests) != 1 or "" in digests:
            issues.append(f"manifest-parity-mismatch:{key}")
    operation_rows = payload.get("operations", [])
    if not isinstance(operation_rows, list):
        issues.append("operations-invalid")
        operation_rows = []
    for row in operation_rows:
        if not isinstance(row, dict):
            issues.append("operation-invalid")
            continue
        key = f"{row.get('kind')}:{row.get('id')}"
        post_manifest = row.get("post_manifest")
        if not isinstance(post_manifest, dict):
            issues.append(f"post-manifest-missing:{key}")
            continue
        if row.get("action") == "replace" and installed.get(key) != post_manifest:
            issues.append(f"installed-post-manifest-mismatch:{key}")
        if row.get("action") == "retire" and int(post_manifest.get("file_count") or 0) != 0:
            issues.append(f"retired-post-manifest-not-empty:{key}")
    retention = payload.get("backup_retention", {})
    if not isinstance(retention, dict) or not bool(retention.get("bounded")):
        issues.append("backup-retention-unbounded")
    authority_receipts = payload.get("skillguard_authority_receipts", {})
    if not isinstance(authority_receipts, dict):
        issues.append("skillguard-authority-receipts-invalid")
        authority_receipts = {}
    for skill_id, authority_receipt in authority_receipts.items():
        if not isinstance(authority_receipt, dict):
            issues.append(f"skillguard-authority-receipt-invalid:{skill_id}")
            continue
        incoming_authority = authority_receipt.get("incoming", {})
        active_authority = authority_receipt.get("active", {})
        if not isinstance(incoming_authority, dict) or not isinstance(active_authority, dict):
            issues.append(f"skillguard-authority-snapshot-invalid:{skill_id}")
            continue
        if authority_receipt.get("policy_id") != SKILLGUARD_WHOLE_TREE_POLICY_ID:
            issues.append(f"skillguard-authority-policy-mismatch:{skill_id}")
        former_fields = {
            "migration_policy_id",
            "migration_proof",
            "predecessor_contract_hash",
            "successor_contract_hash",
            "retirement_receipt",
            "renewal_receipt",
        }
        if former_fields & set(authority_receipt):
            issues.append(f"skillguard-former-authority-field:{skill_id}")
        active_confirmation = authority_receipt.get("active_confirmation", {})
        validation_receipt = authority_receipt.get("incoming_validation", {})
        if not isinstance(active_confirmation, dict) or not isinstance(
            validation_receipt, dict
        ):
            issues.append(f"skillguard-currentness-binding-invalid:{skill_id}")
            continue
        active_confirmed_current = bool(active_confirmation.get("confirmed_current"))
        expected_decision = (
            "validated-current-replaces-current"
            if active_confirmed_current
            else "validated-current-replaces-non-current"
        )
        if authority_receipt.get("decision") != expected_decision:
            issues.append(f"skillguard-authority-decision-mismatch:{skill_id}")
        if bool(authority_receipt.get("semantic_comparison_performed")) != (
            active_confirmed_current
        ):
            issues.append(f"skillguard-semantic-comparison-boundary:{skill_id}")
        if not _snapshot_authority_is_current(incoming_authority):
            issues.append(f"skillguard-incoming-authority-not-current:{skill_id}")
        source_manifest = source.get(f"skill:{skill_id}", {})
        if not isinstance(source_manifest, dict):
            issues.append(f"skillguard-source-manifest-missing:{skill_id}")
            source_manifest = {}
        validation_issues = _skillguard_source_validation_issues(
            skill_id=str(skill_id),
            receipt=validation_receipt,
            authority=incoming_authority,
            source_manifest=source_manifest,
        )
        issues.extend(
            f"skillguard-validation-replay:{skill_id}:{item}"
            for item in validation_issues
        )
        downgrade_reasons = _skillguard_downgrade_reasons(
            incoming_authority,
            active_authority,
            active_confirmed_current=active_confirmed_current,
        )
        semantic_reorganizations = (
            _conditional_depth_wrapper_reorganizations(
                incoming_authority, active_authority
            )
            if active_confirmed_current
            else {}
        )
        if authority_receipt.get("semantic_reorganizations", {}) != semantic_reorganizations:
            issues.append(f"skillguard-semantic-reorganization-replay:{skill_id}")
        stored_reasons = authority_receipt.get("downgrade_reasons", [])
        if stored_reasons != downgrade_reasons:
            issues.append(f"skillguard-downgrade-decision-replay:{skill_id}")
        if downgrade_reasons:
            issues.append(f"skillguard-downgrade-replay:{skill_id}:{downgrade_reasons}")
    return {
        "ok": not issues,
        "issues": issues,
        "expected_receipt_hash": expected_hash,
        "actual_receipt_hash": actual_hash,
        "managed_manifest_keys": sorted(installed),
    }


def _confirmed_current_active_authority(
    *,
    control_root: Path,
    skill_id: str,
    active_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    transactions_root = control_root / "transactions"
    candidates: list[tuple[str, Path, dict[str, Any]]] = []
    for path in transactions_root.glob("*.json"):
        try:
            journal = _json_object(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if (
            journal.get("status") != "committed"
            or int(journal.get("schema_version") or 0) != INSTALL_SCHEMA_VERSION
        ):
            continue
        order = str(journal.get("committed_at") or journal.get("created_at") or path.stem)
        candidates.append((order, path, journal))
    for _, _, journal in sorted(candidates, key=lambda row: row[0], reverse=True):
        replay = replay_install_receipt(journal)
        if not replay.get("ok"):
            continue
        payload = journal.get("receipt_payload", {})
        if not isinstance(payload, dict):
            continue
        installed = payload.get("installed_manifests", {})
        receipts = payload.get("skillguard_authority_receipts", {})
        if not isinstance(installed, dict) or not isinstance(receipts, dict):
            continue
        key = f"skill:{skill_id}"
        installed_manifest = installed.get(key, {})
        authority_receipt = receipts.get(skill_id, {})
        if not isinstance(installed_manifest, dict) or not isinstance(authority_receipt, dict):
            continue
        incoming = authority_receipt.get("incoming", {})
        validation = authority_receipt.get("incoming_validation", {})
        if (
            installed_manifest.get("digest") != active_manifest.get("digest")
            or authority_receipt.get("policy_id") != SKILLGUARD_WHOLE_TREE_POLICY_ID
            or not isinstance(incoming, dict)
            or not _snapshot_authority_is_current(incoming)
            or not isinstance(validation, dict)
            or validation.get("source_tree_digest") != installed_manifest.get("digest")
        ):
            continue
        return {
            "confirmed_current": True,
            "transaction_id": str(journal.get("transaction_id") or ""),
            "receipt_hash": str(journal.get("receipt_hash") or ""),
            "installed_manifest_digest": str(installed_manifest.get("digest") or ""),
            "source_validation_receipt_hash": str(validation.get("receipt_hash") or ""),
        }
    return {
        "confirmed_current": False,
        "transaction_id": "",
        "receipt_hash": "",
        "installed_manifest_digest": str(active_manifest.get("digest") or ""),
        "source_validation_receipt_hash": "",
    }


def install_managed_runtime(
    *,
    repo_root: Path,
    codex_home: Path,
    global_skill_name: str,
    global_skill_files: Mapping[str, str],
    skill_sources: Mapping[str, Path],
    skillguard_validation_receipts: Mapping[str, Mapping[str, Any]],
    automation_payloads: Mapping[str, Mapping[str, Any]],
    automation_renderer: Callable[[Mapping[str, Any]], str],
    retired_skill_ids: tuple[str, ...],
    retired_automation_ids: tuple[str, ...],
    fail_after_activation: int | None = None,
    backup_retention: int = COMMITTED_BACKUP_RETENTION,
) -> dict[str, Any]:
    """Stage, compare, activate, verify, and rollback all managed trees together."""

    repo_root = Path(repo_root).resolve()
    codex_home = Path(codex_home).resolve()
    codex_home.mkdir(parents=True, exist_ok=True)
    control_root = codex_home / CONTROL_ROOT_NAME
    stages_root = control_root / "staging"
    backups_root = control_root / "backups"
    transactions_root = control_root / "transactions"
    lock_path = control_root / "install.lock"
    for path in (stages_root, backups_root, transactions_root):
        path.mkdir(parents=True, exist_ok=True)
    stage_root: Path | None = None
    backup_root: Path | None = None
    journal_path: Path | None = None
    journal: dict[str, Any] | None = None
    transaction_committed = False
    try:
        lock_path.mkdir()
    except FileExistsError as exc:
        raise RuntimeError(f"Another Chaos Brain installation owns {lock_path}") from exc
    try:
        recovered = _recover_incomplete(control_root, codex_home)
        orphan_stages_removed = _cleanup_staging_root(stages_root)
        transaction_id = f"install-{int(time.time() * 1000)}-{uuid4().hex[:8]}"
        stage_root = stages_root / transaction_id
        backup_root = backups_root / transaction_id
        stage_root.mkdir(parents=True)
        backup_root.mkdir(parents=True)

        source_manifests: dict[str, dict[str, Any]] = {}
        staged_manifests: dict[str, dict[str, Any]] = {}
        skillguard_authority_receipts: dict[str, dict[str, Any]] = {}
        managed: list[dict[str, Any]] = []
        if set(skillguard_validation_receipts) != set(skill_sources):
            raise RuntimeError(
                "SkillGuard validation receipt inventory does not match managed Skill sources"
            )

        global_stage = stage_root / "skills" / global_skill_name
        for relative, text in sorted(global_skill_files.items()):
            target = global_stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(text), encoding="utf-8")
        global_manifest = tree_manifest(global_stage)
        source_manifests[f"skill:{global_skill_name}"] = global_manifest
        staged_manifests[f"skill:{global_skill_name}"] = global_manifest
        managed.append(
            {
                "kind": "skill",
                "id": global_skill_name,
                "active": codex_home / "skills" / global_skill_name,
                "stage": global_stage,
            }
        )

        for skill_id, source in sorted(skill_sources.items()):
            source = Path(source).resolve()
            before = tree_manifest(source)
            stage = stage_root / "skills" / skill_id
            _copytree(source, stage)
            after_source = tree_manifest(source)
            staged = tree_manifest(stage)
            if before["digest"] != after_source["digest"]:
                raise RuntimeError(f"Concurrent source drift while staging skill {skill_id}")
            if before["digest"] != staged["digest"]:
                raise RuntimeError(f"Source/stage manifest mismatch for skill {skill_id}")
            incoming_authority = _skillguard_authority(stage)
            incoming_generation = int(incoming_authority["generation"])
            incoming_checks = int(incoming_authority["check_count"])
            validation_receipt = skillguard_validation_receipts.get(skill_id, {})
            if not isinstance(validation_receipt, Mapping):
                validation_receipt = {}
            validation_issues = _skillguard_source_validation_issues(
                skill_id=str(skill_id),
                receipt=validation_receipt,
                authority=incoming_authority,
                source_manifest=before,
            )
            if incoming_generation != 2 or validation_issues:
                raise RuntimeError(
                    f"Skill {skill_id} lacks current validated SkillGuard authority: "
                    f"{validation_issues or incoming_authority.get('issues', [])}"
                )
            active = codex_home / "skills" / skill_id
            active_manifest = tree_manifest(active) if active.exists() else {
                "file_count": 0,
                "byte_count": 0,
                "files": [],
                "digest": _canonical_hash([]),
            }
            active_confirmation = _confirmed_current_active_authority(
                control_root=control_root,
                skill_id=str(skill_id),
                active_manifest=active_manifest,
            )
            active_confirmed_current = bool(
                active_confirmation.get("confirmed_current")
            )
            active_authority = (
                _skillguard_authority(active)
                if active_confirmed_current
                else {
                    "generation": 0,
                    "check_count": 0,
                    "current_shape": False,
                    "former_runtime_residuals": [],
                    "issues": [],
                }
            )
            active_generation = int(active_authority["generation"])
            active_checks = int(active_authority["check_count"])
            downgrade_reasons = _skillguard_downgrade_reasons(
                incoming_authority,
                active_authority,
                active_confirmed_current=active_confirmed_current,
            )
            if downgrade_reasons:
                raise RuntimeError(
                    f"SkillGuard downgrade blocked for {skill_id}: incoming={incoming_generation}/{incoming_checks} "
                    f"active={active_generation}/{active_checks}; reasons={downgrade_reasons}"
                )
            skillguard_authority_receipts[skill_id] = {
                "policy_id": SKILLGUARD_WHOLE_TREE_POLICY_ID,
                "decision": (
                    "validated-current-replaces-current"
                    if active_confirmed_current
                    else "validated-current-replaces-non-current"
                ),
                "semantic_comparison_performed": active_confirmed_current,
                "active_confirmation": active_confirmation,
                "incoming_validation": dict(validation_receipt),
                "active": _skillguard_authority_snapshot(active_authority),
                "incoming": _skillguard_authority_snapshot(incoming_authority),
                "semantic_reorganizations": (
                    _conditional_depth_wrapper_reorganizations(
                        incoming_authority, active_authority
                    )
                    if active_confirmed_current
                    else {}
                ),
                "downgrade_reasons": [],
            }
            key = f"skill:{skill_id}"
            source_manifests[key] = before
            staged_manifests[key] = staged
            managed.append({"kind": "skill", "id": skill_id, "active": active, "stage": stage})

        for automation_id, payload in sorted(automation_payloads.items()):
            stage = stage_root / "automations" / automation_id
            stage.mkdir(parents=True)
            (stage / "automation.toml").write_text(automation_renderer(payload), encoding="utf-8")
            manifest = tree_manifest(stage)
            key = f"automation:{automation_id}"
            source_manifests[key] = manifest
            staged_manifests[key] = manifest
            managed.append(
                {
                    "kind": "automation",
                    "id": automation_id,
                    "active": codex_home / "automations" / automation_id,
                    "stage": stage,
                }
            )

        operations: list[dict[str, Any]] = []
        for item in managed:
            active = Path(item["active"])
            backup = backup_root / str(item["kind"]) / str(item["id"])
            operations.append(
                {
                    "kind": item["kind"],
                    "id": item["id"],
                    "action": "replace",
                    "active_path": str(active),
                    "stage_path": str(item["stage"]),
                    "backup_path": str(backup),
                    "had_active": active.exists(),
                    "pre_manifest": tree_manifest(active) if active.exists() else {},
                }
            )
        for kind, retired_ids in (("skill", retired_skill_ids), ("automation", retired_automation_ids)):
            for retired_id in retired_ids:
                active = codex_home / ("skills" if kind == "skill" else "automations") / retired_id
                backup = backup_root / "retired" / kind / retired_id
                operations.append(
                    {
                        "kind": kind,
                        "id": retired_id,
                        "action": "retire",
                        "active_path": str(active),
                        "stage_path": "",
                        "backup_path": str(backup),
                        "had_active": active.exists(),
                        "pre_manifest": tree_manifest(active) if active.exists() else {},
                    }
                )

        journal_path = transactions_root / f"{transaction_id}.json"
        journal = {
            "schema_version": INSTALL_SCHEMA_VERSION,
            "transaction_id": transaction_id,
            "status": "prepared",
            "created_at": utc_now_iso(),
            "repo_root": str(repo_root),
            "stage_root": str(stage_root),
            "backup_root": str(backup_root),
            "source_manifests": source_manifests,
            "staged_manifests": staged_manifests,
            "installed_manifests": {},
            "retired_post_manifests": {},
            "skillguard_authority_receipts": skillguard_authority_receipts,
            "operations": operations,
            "activated_count": 0,
            "recovered_transactions": recovered,
            "orphan_stages_removed": orphan_stages_removed,
        }
        _atomic_json(journal_path, journal)

        activated = 0
        try:
            installed_manifests: dict[str, dict[str, Any]] = {}
            retired_post_manifests: dict[str, dict[str, Any]] = {}
            journal["status"] = "activating"
            _atomic_json(journal_path, journal)
            for operation in operations:
                active = Path(operation["active_path"])
                backup = Path(operation["backup_path"])
                active.parent.mkdir(parents=True, exist_ok=True)
                backup.parent.mkdir(parents=True, exist_ok=True)
                if active.exists():
                    os.replace(active, backup)
                if operation["action"] == "replace":
                    os.replace(Path(operation["stage_path"]), active)
                    expected = staged_manifests[f"{operation['kind']}:{operation['id']}"]
                    installed = tree_manifest(active)
                    if installed["digest"] != expected["digest"]:
                        raise RuntimeError(f"Post-activation parity failed for {operation['kind']} {operation['id']}")
                    installed_manifests[f"{operation['kind']}:{operation['id']}"] = installed
                    operation["post_manifest"] = installed
                else:
                    retired = tree_manifest(active)
                    if int(retired.get("file_count") or 0):
                        raise RuntimeError(
                            f"Post-retirement absence failed for {operation['kind']} {operation['id']}"
                        )
                    retired_post_manifests[f"{operation['kind']}:{operation['id']}"] = retired
                    operation["post_manifest"] = retired
                activated += 1
                journal["activated_count"] = activated
                journal["installed_manifests"] = installed_manifests
                journal["retired_post_manifests"] = retired_post_manifests
                journal["operations"] = operations
                _atomic_json(journal_path, journal)
                if fail_after_activation is not None and activated >= fail_after_activation:
                    raise RuntimeError("Injected installation failure")

            managed_keys = set(source_manifests)
            if managed_keys != set(staged_manifests) or managed_keys != set(installed_manifests):
                raise RuntimeError("Source/stage/installed manifest key sets do not match")
            for key in sorted(managed_keys):
                digests = {
                    str(source_manifests[key].get("digest") or ""),
                    str(staged_manifests[key].get("digest") or ""),
                    str(installed_manifests[key].get("digest") or ""),
                }
                if len(digests) != 1 or "" in digests:
                    raise RuntimeError(f"Source/stage/installed manifest parity failed for {key}")

            journal["status"] = "verifying"
            journal["installed_manifests"] = installed_manifests
            journal["retired_post_manifests"] = retired_post_manifests
            _atomic_json(journal_path, journal)
            retention_receipt = _backup_retention_receipt(
                control_root=control_root,
                current_transaction_id=transaction_id,
                current_backup_root=backup_root,
                current_created_at=str(journal["created_at"]),
                limit=backup_retention,
            )
            if not retention_receipt["bounded"]:
                raise RuntimeError("Committed backup retention did not converge")
            journal["backup_retention"] = retention_receipt
            journal["receipt_payload"] = _install_receipt_payload(journal)
            journal["receipt_hash"] = _canonical_hash(journal["receipt_payload"])
            replay = replay_install_receipt(journal)
            if not replay["ok"]:
                raise RuntimeError(f"Install receipt replay failed: {replay['issues']}")
            journal["status"] = "committed"
            journal["committed_at"] = utc_now_iso()
            _atomic_json(journal_path, journal)
            transaction_committed = True
        except Exception:
            rollback_issues: list[str] = []
            for operation in reversed(operations):
                try:
                    active = Path(operation["active_path"])
                    backup = Path(operation["backup_path"])
                    if backup.exists():
                        _remove_path(active)
                        active.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(backup, active)
                    elif not bool(operation["had_active"]):
                        _remove_path(active)
                except OSError as rollback_error:
                    rollback_issues.append(
                        f"{operation.get('kind')}:{operation.get('id')}:{rollback_error}"
                    )
            journal["status"] = "rollback_failed" if rollback_issues else "rolled_back"
            journal["rolled_back_at"] = utc_now_iso()
            journal["rollback_issues"] = rollback_issues
            journal["rollback_manifests"] = {
                f"{operation['kind']}:{operation['id']}": tree_manifest(
                    Path(operation["active_path"])
                )
                for operation in operations
            }
            journal.pop("receipt_hash", None)
            journal.pop("receipt_payload", None)
            _atomic_json(journal_path, journal)
            raise

        _remove_path(stage_root)
        journal["stage_cleanup"] = {
            "ok": not stage_root.exists(),
            "path": str(stage_root),
            "reason": "committed-transaction-finally",
        }
        _atomic_json(journal_path, journal)
        return {
            "ok": True,
            "schema_version": INSTALL_SCHEMA_VERSION,
            "transaction_id": transaction_id,
            "journal_path": str(journal_path),
            "backup_root": str(backup_root),
            "receipt_hash": journal["receipt_hash"],
            "receipt_payload": journal["receipt_payload"],
            "source_manifests": source_manifests,
            "staged_manifests": staged_manifests,
            "installed_manifests": journal["installed_manifests"],
            "retired_post_manifests": journal["retired_post_manifests"],
            "backup_retention": journal["backup_retention"],
            "skillguard_authority_receipts": journal["skillguard_authority_receipts"],
            "retired_skill_ids": list(retired_skill_ids),
            "retired_automation_ids": list(retired_automation_ids),
            "recovered_transactions": recovered,
            "orphan_stages_removed": orphan_stages_removed,
            "operations": operations,
        }
    finally:
        if stage_root is not None:
            try:
                _assert_under(stage_root, stages_root)
                _remove_path(stage_root)
            except (OSError, ValueError):
                pass
        if backup_root is not None and not transaction_committed:
            should_remove_backup = journal is None or journal.get("status") == "rolled_back"
            if should_remove_backup:
                try:
                    _assert_under(backup_root, backups_root)
                    _remove_path(backup_root)
                except (OSError, ValueError):
                    pass
        if journal is not None and journal_path is not None and journal_path.exists():
            try:
                journal["stage_cleanup"] = {
                    "ok": stage_root is None or not stage_root.exists(),
                    "path": str(stage_root or ""),
                    "reason": "transaction-finally",
                }
                if backup_root is not None and not transaction_committed:
                    journal["failed_backup_cleanup"] = {
                        "ok": not backup_root.exists() if journal.get("status") == "rolled_back" else False,
                        "path": str(backup_root),
                        "preserved_for_recovery": journal.get("status") != "rolled_back",
                    }
                _atomic_json(journal_path, journal)
            except (OSError, ValueError):
                pass
        try:
            lock_path.rmdir()
        except OSError:
            pass


def latest_install_receipt(codex_home: Path) -> dict[str, Any]:
    transaction_root = Path(codex_home) / CONTROL_ROOT_NAME / "transactions"
    if not transaction_root.exists():
        return {}
    for path in sorted(transaction_root.glob("*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("status") == "committed":
            return {**payload, "journal_path": str(path)}
    return {}
