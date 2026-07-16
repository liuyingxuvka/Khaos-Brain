"""Sole final aggregate owner for the LogicGuard-native Khaos Brain cutover."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_chaos_brain_readiness import (  # noqa: E402
    _write_json,
    build_report as build_base_report,
)
from local_kb.config import default_codex_home  # noqa: E402
from local_kb.install import latest_upgrade_attempt  # noqa: E402
from local_kb.transactional_install import tree_manifest  # noqa: E402


DEFAULT_RECEIPT_ROOT = (
    REPO_ROOT / ".local" / "verification" / "khaos-logicguard-native"
)
DEFAULT_RECEIPT = DEFAULT_RECEIPT_ROOT / "readiness.json"
DEFAULT_EVIDENCE_ROOT = DEFAULT_RECEIPT_ROOT / "evidence"

REQUIRED_CHECKS = (
    "flowguard_models",
    "flowguard_meshes",
    "logicguard_authority_cutover_model",
    "logicguard_field_lifecycle",
    "logicguard_model_mesh",
    "logicguard_code_structure",
    "logicguard_model_test_contract",
    "logicguard_test_mesh",
    "logicguard_runtime",
    "logicguard_openspec",
    "skillguard_source_install_parity",
    "retired_architect_absence",
    "current_runtime_only",
    "retrieval_quality",
    "full_regression",
    "install_health",
    "model_code_test_alignment",
)

_VALIDATION_TOOLCHAINS = (
    (
        "skillguard_validation_toolchain",
        "KHAOS_BRAIN_SKILLGUARD_VALIDATION_ROOT",
        "KHAOS_BRAIN_SKILLGUARD_VALIDATION_DIGEST",
        False,
    ),
    (
        "flowguard_validation_toolchain",
        "KHAOS_BRAIN_FLOWGUARD_VALIDATION_ROOT",
        "KHAOS_BRAIN_FLOWGUARD_VALIDATION_DIGEST",
        True,
    ),
    (
        "logicguard_validation_toolchain",
        "KHAOS_BRAIN_LOGICGUARD_VALIDATION_ROOT",
        "KHAOS_BRAIN_LOGICGUARD_VALIDATION_DIGEST",
        True,
    ),
)
_INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV = (
    "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_PRESENT"
)
_INSTALLATION_IDENTITY_PYTHONPATH_VALUE_ENV = (
    "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_VALUE"
)


def _configure_completed_install_toolchains(codex_home: Path) -> dict[str, Any]:
    """Bind standalone readiness to the successful install's frozen tools.

    The installer already freezes one immutable SkillGuard, FlowGuard, and
    LogicGuard identity.  A later standalone final-owner invocation must use
    those same bytes instead of resolving whichever packages happen to be on
    the ambient Python path.
    """

    production_pythonpath_present = "PYTHONPATH" in os.environ
    production_pythonpath = os.environ.get("PYTHONPATH", "")
    os.environ[_INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV] = (
        "1" if production_pythonpath_present else "0"
    )
    os.environ[_INSTALLATION_IDENTITY_PYTHONPATH_VALUE_ENV] = production_pythonpath

    attempt = latest_upgrade_attempt(codex_home)
    if not (
        attempt.get("status") == "completed"
        and attempt.get("phase") == "post_install_check_passed"
    ):
        raise RuntimeError(
            "LogicGuard-native readiness requires one completed current Khaos "
            "Brain install attempt with frozen validation toolchains"
        )

    python_roots: list[str] = []
    bindings: dict[str, Any] = {}
    for field, root_env, digest_env, add_to_python_path in _VALIDATION_TOOLCHAINS:
        receipt = attempt.get(field)
        if not isinstance(receipt, dict):
            raise RuntimeError(f"Completed install attempt is missing {field}")
        root = Path(str(receipt.get("snapshot_root") or "")).resolve()
        expected = str((receipt.get("manifest") or {}).get("digest") or "")
        actual = tree_manifest(root) if root.is_dir() else {}
        actual_digest = str(actual.get("digest") or "")
        if not expected or actual_digest != expected:
            raise RuntimeError(
                f"Completed install toolchain is missing or stale: {field}"
            )
        os.environ[root_env] = str(root)
        os.environ[digest_env] = expected
        if add_to_python_path:
            parent = str(root.parent)
            python_roots.append(parent)
            if parent not in sys.path:
                sys.path.insert(0, parent)
        bindings[field] = {
            "root": str(root),
            "digest": expected,
            "file_count": int(actual.get("file_count") or 0),
        }

    existing_python_path = [
        item for item in os.environ.get("PYTHONPATH", "").split(os.pathsep) if item
    ]
    os.environ["PYTHONPATH"] = os.pathsep.join(
        list(dict.fromkeys([*python_roots, *existing_python_path]))
    )
    return {
        "attempt_id": str(attempt.get("attempt_id") or ""),
        "attempt_updated_at": str(attempt.get("updated_at") or ""),
        "scheduled_production_pythonpath_present": production_pythonpath_present,
        "toolchains": bindings,
    }


def build_report(
    repo_root: Path,
    codex_home: Path,
    *,
    evidence_root: Path = DEFAULT_EVIDENCE_ROOT,
) -> dict[str, Any]:
    base = build_base_report(
        repo_root,
        codex_home,
        pre_restore=False,
        evidence_root=evidence_root,
    )
    checks = base.get("checks") if isinstance(base.get("checks"), dict) else {}
    missing = [name for name in REQUIRED_CHECKS if name not in checks]
    failed = [
        name
        for name in REQUIRED_CHECKS
        if name in checks and checks[name].get("ok") is not True
    ]
    logicguard_runtime = checks.get("logicguard_runtime", {})
    runtime_payload = (
        logicguard_runtime.get("json_payload")
        if isinstance(logicguard_runtime, dict)
        else None
    )
    runtime_generation = ""
    zero_legacy = False
    if isinstance(runtime_payload, dict):
        runtime_generation = str(runtime_payload.get("generation_id") or "")
        authority = runtime_payload.get("authority")
        zero_legacy = bool(
            isinstance(authority, dict)
            and authority.get("zero_legacy_projection_residuals") is True
        )
    issues = [*(f"missing-check:{name}" for name in missing)]
    issues.extend(f"failed-check:{name}" for name in failed)
    if not runtime_generation:
        issues.append("logicguard-runtime-has-no-exact-generation")
    if not zero_legacy:
        issues.append("logicguard-runtime-did-not-prove-zero-legacy-residuals")

    payload: dict[str, Any] = {
        **base,
        "schema_version": "khaos-brain.logicguard-native-readiness.v1",
        "check": "khaos-brain-logicguard-native-aggregate-readiness",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": base.get("ok") is True and not issues,
        "required_checks": list(REQUIRED_CHECKS),
        "missing_required_checks": missing,
        "failed_required_checks": failed,
        "logicguard_generation_id": runtime_generation,
        "zero_legacy_projection_residuals": zero_legacy,
        "issues": issues,
        "claim_boundary": (
            "This is the sole frozen-snapshot aggregate execution owner for the "
            "LogicGuard-native Khaos Brain cutover. It proves current dependency, "
            "model/mesh/projection/index authority, Sleep/Dream regressions, migration "
            "residuals, runtime performance, FlowGuard/OpenSpec structure, SkillGuard "
            "source-install parity, installation health, and one repository-wide test "
            "execution or exact current immutable owner receipt. It does not establish "
            "factual truth, publish a release, or certify future AI behavior."
        ),
    }
    identity_body = json.dumps(
        {
            "evidence_manifest": payload.get("evidence_manifest"),
            "logicguard_generation_id": runtime_generation,
            "required_checks": list(REQUIRED_CHECKS),
            "ok": payload["ok"],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    payload["receipt_id"] = (
        "khaos-logicguard-native-readiness:"
        + hashlib.sha256(identity_body).hexdigest()
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--codex-home", type=Path, default=default_codex_home())
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--no-write-receipt", action="store_true")
    args = parser.parse_args()
    toolchain_binding = _configure_completed_install_toolchains(args.codex_home)
    report = build_report(
        args.repo_root,
        args.codex_home,
        evidence_root=args.evidence_root,
    )
    report["validation_toolchain_binding"] = toolchain_binding
    if not args.no_write_receipt:
        _write_json(args.receipt, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "Khaos Brain LogicGuard-native readiness:",
            "PASS" if report["ok"] else "FAIL",
        )
        for issue in report["issues"]:
            print(f"- {issue}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
