#!/usr/bin/env python3
"""Run one current installed SkillGuard V2 contract against its canonical repository.

The installed target is an immutable deployment projection, not a second source
repository.  Its already-compiled current contract is therefore consumed
directly after installation-currentness replay instead of being recompiled
outside the canonical repository boundary.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stdout
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any, Iterator, Mapping


_PYTHONPATH_PRESENT_ENV = "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_PRESENT"
_PYTHONPATH_VALUE_ENV = "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_VALUE"
_SUPERVISION_DYNAMIC_ENV_KEYS = (
    "KHAOS_BRAIN_AUTOMATION_RECEIPT",
    "KHAOS_BRAIN_AUTOMATION_RUN_ID",
    "KHAOS_BRAIN_AUTOMATION_RECEIPT_HASH",
    "KHAOS_BRAIN_SCHEDULED_PRODUCTION_IDENTITY",
    "KHAOS_BRAIN_ALLOW_AUTOMATION_FIXTURE",
    "KHAOS_BRAIN_UPDATE_FINALIZATION_RECEIPT",
    "KHAOS_BRAIN_UPDATE_FINALIZATION_RECEIPT_HASH",
)


def _load_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"current JSON object required: {path}")
    return payload


@contextmanager
def _installation_identity_environment() -> Iterator[None]:
    """Replay installation identity without the formal FlowGuard injection."""

    presence = os.environ.get(_PYTHONPATH_PRESENT_ENV)
    if presence not in {"0", "1"}:
        yield
        return
    previous_present = "PYTHONPATH" in os.environ
    previous_value = os.environ.get("PYTHONPATH", "")
    if presence == "1":
        os.environ["PYTHONPATH"] = os.environ.get(_PYTHONPATH_VALUE_ENV, "")
    else:
        os.environ.pop("PYTHONPATH", None)
    try:
        yield
    finally:
        if previous_present:
            os.environ["PYTHONPATH"] = previous_value
        else:
            os.environ.pop("PYTHONPATH", None)


@contextmanager
def _supervision_dynamic_environment(
    values: Mapping[str, object],
) -> Iterator[None]:
    """Expose only this run's mutable evidence to the frozen supervisor."""

    unknown = set(values) - set(_SUPERVISION_DYNAMIC_ENV_KEYS)
    if unknown:
        raise ValueError(
            "unsupported dynamic supervision environment keys: "
            + ",".join(sorted(unknown))
        )
    previous = {
        key: (key in os.environ, os.environ.get(key, ""))
        for key in _SUPERVISION_DYNAMIC_ENV_KEYS
    }
    for key in _SUPERVISION_DYNAMIC_ENV_KEYS:
        if key in values:
            os.environ[key] = str(values[key])
        else:
            os.environ.pop(key, None)
    try:
        yield
    finally:
        for key, (present, value) in previous.items():
            if present:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)


def _active_skillguard_root(codex_home: Path) -> Path:
    configured = os.environ.get("KHAOS_BRAIN_SKILLGUARD_VALIDATION_ROOT", "").strip()
    return (
        Path(configured).resolve()
        if configured
        else (codex_home / "skills" / "skillguard").resolve()
    )


def _active_skillguard_router_root(
    codex_home: Path, skillguard_root: Path
) -> Path:
    configured = os.environ.get(
        "KHAOS_BRAIN_SKILLGUARD_VALIDATION_ROOT", ""
    ).strip()
    return (
        (skillguard_root.parent / "skillguard-global-router").resolve()
        if configured
        else (codex_home / "skills" / "skillguard-global-router").resolve()
    )


def _prevent_runtime_projection_bytecode_mutation() -> None:
    """Keep the content-addressed SkillGuard projection byte-for-byte immutable."""

    # The projection is imported in this process and some supervised checks may
    # start child Python processes.  Disable bytecode writes for both surfaces;
    # otherwise the first successful import creates ``__pycache__`` inside the
    # projection and the next exact-inventory verification correctly blocks.
    sys.dont_write_bytecode = True
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _materialize_installed_control_projection(
    installed_skill_root: Path,
    target_root: Path,
    repository_root: Path,
    *,
    skill_id: str,
    relative_paths: tuple[str, ...],
) -> tuple[Path, dict[str, object]]:
    """Project exact installed control bytes under the repository run root."""

    installed = installed_skill_root.resolve(strict=True)
    repository = repository_root.resolve(strict=True)
    target = target_root.resolve()
    target.relative_to(repository)
    if not skill_id or Path(skill_id).name != skill_id:
        raise ValueError("current installed skill id must be one path segment")

    files: list[tuple[str, bytes]] = []
    for raw_relative in relative_paths:
        relative = Path(raw_relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"installed control path must be relative: {raw_relative}")
        source = installed / relative
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"exact installed control file is unavailable: {source}")
        source.resolve(strict=True).relative_to(installed)
        files.append((relative.as_posix(), source.read_bytes()))

    fingerprint_payload = b"".join(
        relative.encode("utf-8")
        + b"\0"
        + str(len(payload)).encode("ascii")
        + b"\0"
        + payload
        for relative, payload in files
    )
    projection_hash = _sha256_bytes(fingerprint_payload)
    parent = repository / ".local" / "installed-skillguard-control"
    projection = parent / f"{skill_id}-{projection_hash[:24].lower()}"
    expected_hashes = {
        relative: _sha256_bytes(payload) for relative, payload in files
    }

    def verify_projection(root: Path) -> None:
        actual_files = sorted(
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        )
        if actual_files != sorted(expected_hashes):
            raise ValueError("installed control projection file inventory mismatch")
        for relative, expected_hash in expected_hashes.items():
            candidate = root / relative
            if candidate.is_symlink() or _sha256_bytes(candidate.read_bytes()) != expected_hash:
                raise ValueError(
                    f"installed control projection byte mismatch: {relative}"
                )

    parent.mkdir(parents=True, exist_ok=True)
    if projection.exists():
        verify_projection(projection)
    else:
        with TemporaryDirectory(prefix=".projection-", dir=parent) as temporary:
            temporary_root = Path(temporary) / "current"
            temporary_root.mkdir()
            for relative, payload in files:
                destination = temporary_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(payload)
            verify_projection(temporary_root)
            temporary_root.rename(projection)
    verify_projection(projection)
    return projection, {
        "schema_version": "khaos-brain.installed-skillguard-control-projection.v1",
        "skill_id": skill_id,
        "projection_hash": projection_hash,
        "file_hashes": expected_hashes,
        "projection_root": str(projection),
        "projection_scope": "repository-local-content-addressed",
        "source_kind": "exact-installed-current-bytes",
    }


def _materialize_skillguard_runtime_projection(
    skillguard_root: Path,
    global_router_root: Path,
    target_root: Path,
    repository_root: Path,
) -> tuple[Path, dict[str, object]]:
    """Copy only frozen current behavior bytes, never runtime state or caches."""

    repository = repository_root.resolve(strict=True)
    target = target_root.resolve()
    target.relative_to(repository)
    members = (
        ("skillguard", skillguard_root.resolve(strict=True)),
        ("skillguard-global-router", global_router_root.resolve(strict=True)),
    )
    files: list[tuple[str, bytes]] = []
    for member_id, member_root in members:
        for source in sorted(
            (path for path in member_root.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(member_root).as_posix(),
        ):
            relative = source.relative_to(member_root)
            if (
                ".sg-runtime" in relative.parts
                or "__pycache__" in relative.parts
                or source.suffix.lower() in {".pyc", ".pyo"}
            ):
                continue
            if source.is_symlink():
                raise ValueError(
                    f"SkillGuard runtime behavior file must not be a symlink: {source}"
                )
            source.resolve(strict=True).relative_to(member_root)
            files.append(
                (f"{member_id}/{relative.as_posix()}", source.read_bytes())
            )
    required = {
        "skillguard/scripts/skillguard_v2/runtime_fingerprint.py",
        "skillguard-global-router/SKILL.md",
        "skillguard-global-router/.skillguard/contract-source.json",
        "skillguard-global-router/.skillguard/compiled-contract.json",
        "skillguard-global-router/.skillguard/check-manifest.json",
    }
    observed = {relative for relative, _ in files}
    if not required.issubset(observed):
        raise ValueError(
            "frozen SkillGuard runtime behavior projection is incomplete: "
            + ",".join(sorted(required - observed))
        )
    fingerprint_payload = b"".join(
        relative.encode("utf-8")
        + b"\0"
        + str(len(payload)).encode("ascii")
        + b"\0"
        + payload
        for relative, payload in files
    )
    projection_hash = _sha256_bytes(fingerprint_payload)
    # Keep the complete runtime projection at one short repository-local root.
    # Scheduled run roots can already be deep on Windows; nesting the full
    # SkillGuard inventory below them would make correctness path-length
    # dependent.  Content addressing plus byte verification keeps this shared
    # projection immutable and safe for all run consumers.
    parent = repository / ".local" / "skillguard-runtime-projections"
    bundle_root = parent / projection_hash[:24].lower()
    expected_hashes = {
        relative: _sha256_bytes(payload) for relative, payload in files
    }

    def verify_bundle(root: Path) -> None:
        actual_files = sorted(
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        )
        if actual_files != sorted(expected_hashes):
            raise ValueError("SkillGuard runtime projection file inventory mismatch")
        for relative, expected_hash in expected_hashes.items():
            candidate = root / relative
            if candidate.is_symlink() or _sha256_bytes(candidate.read_bytes()) != expected_hash:
                raise ValueError(
                    f"SkillGuard runtime projection byte mismatch: {relative}"
                )

    parent.mkdir(parents=True, exist_ok=True)
    if bundle_root.exists():
        verify_bundle(bundle_root)
    else:
        with TemporaryDirectory(prefix=".runtime-", dir=parent) as temporary:
            temporary_root = Path(temporary) / "current"
            temporary_root.mkdir()
            for relative, payload in files:
                destination = temporary_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(payload)
            verify_bundle(temporary_root)
            try:
                temporary_root.rename(bundle_root)
            except (FileExistsError, PermissionError):
                # Windows can report an atomic directory-publication race as
                # PermissionError rather than FileExistsError.  Reuse only an
                # exact immutable winner; every other permission failure stays
                # visible.
                if not bundle_root.exists():
                    raise
                verify_bundle(bundle_root)
    verify_bundle(bundle_root)
    runtime_root = bundle_root / "skillguard"
    return runtime_root, {
        "schema_version": "khaos-brain.skillguard-runtime-projection.v1",
        "projection_hash": projection_hash,
        "file_hashes": expected_hashes,
        "runtime_root": str(runtime_root),
        "projection_scope": "repository-local-content-addressed",
        "source_kind": "frozen-current-runtime-without-runtime-state",
    }


class _FrozenInstalledSupervisionRuntime:
    """One start-verified runtime retained for one scheduled execution.

    ``VerifiedInstallationContext`` is intentionally sealed and cannot be
    reconstructed from caller-authored JSON.  Keeping this small worker alive
    across the native Sleep/Dream/update command preserves that official seal
    and the exact imported behavior bytes without requiring the global
    SkillGuard source installation to remain unchanged until the native command
    ends.  Khaos upgrades supply an officially installed isolated validation
    home; ordinary already-installed use may supply the real current Codex home.
    """

    def __init__(
        self,
        *,
        skill_root: Path,
        target_root: Path,
        repository_root: Path,
        codex_home: Path,
        scheduler_or_trigger_id: str = "",
        scheduled_execution_id: str = "",
    ) -> None:
        self.stage = "resolve-roots"
        self.codex_home = codex_home.resolve(strict=True)
        self.skill_root = skill_root.resolve(strict=True)
        self.repository_root = repository_root.resolve(strict=True)
        self.target_root = target_root.resolve()
        self.target_root.relative_to(self.repository_root)
        expected_parent = (self.codex_home / "skills").resolve(strict=True)
        if self.skill_root.parent != expected_parent:
            raise ValueError(
                "installed skill root must be an exact current Codex skill"
            )

        self.stage = "load-installed-contract-pair"
        initial_compiled = _load_object(
            self.skill_root / ".skillguard" / "compiled-contract.json"
        )
        self.skill_id = str(initial_compiled.get("skill_id") or "")
        if not self.skill_id:
            raise ValueError("installed compiled contract has no skill id")

        self.stage = "materialize-current-skillguard-runtime"
        _prevent_runtime_projection_bytecode_mutation()
        self.validation_runtime_root = _active_skillguard_root(self.codex_home)
        self.validation_router_root = _active_skillguard_router_root(
            self.codex_home, self.validation_runtime_root
        )
        self.validation_codex_home = self.validation_runtime_root.parent.parent
        if self.validation_codex_home.name != ".codex":
            raise ValueError(
                "SkillGuard validation runtime must belong to an exact .codex home"
            )
        self.validation_codex_home = self.validation_codex_home.resolve(strict=True)
        self.runtime_root, self.runtime_projection_receipt = (
            _materialize_skillguard_runtime_projection(
                self.validation_runtime_root,
                self.validation_router_root,
                self.target_root,
                self.repository_root,
            )
        )
        scripts_root = (self.runtime_root / "scripts").resolve(strict=True)
        if str(scripts_root) not in sys.path:
            sys.path.insert(0, str(scripts_root))
        importlib.invalidate_caches()
        self.supervisor_module = importlib.import_module(
            "skillguard_v2.supervisor"
        )
        self.installation_module = importlib.import_module(
            "skillguard_v2.installation_receipt"
        )
        self.authority_module = importlib.import_module(
            "skillguard_v2.runtime_authority"
        )
        self.runtime_fingerprint_module = importlib.import_module(
            "skillguard_v2.runtime_fingerprint"
        )
        self.terminal_module = importlib.import_module(
            "skillguard_v2.native_terminal"
        )
        self.run_store_module = importlib.import_module(
            "skillguard_v2.run_store"
        )
        for module in (
            self.supervisor_module,
            self.installation_module,
            self.authority_module,
            self.runtime_fingerprint_module,
            self.terminal_module,
            self.run_store_module,
        ):
            Path(str(module.__file__)).resolve(strict=True).relative_to(
                scripts_root
            )

        self.stage = "validate-installed-authority"
        installed_authority = self.authority_module.resolve_runtime_authority(
            self.skill_root
        )
        if not (
            installed_authority.ok
            and installed_authority.authority
            == self.authority_module.AUTHORITY_CURRENT
            and installed_authority.skill_id == self.skill_id
        ):
            raise ValueError(
                "installed SkillGuard authority is not exact current V2"
            )

        self.stage = "materialize-installed-control-projection"
        self.control_projection_root, self.control_projection_receipt = (
            _materialize_installed_control_projection(
                self.skill_root,
                self.target_root,
                self.repository_root,
                skill_id=self.skill_id,
                relative_paths=(
                    str(self.authority_module.CURRENT_CONTRACT_SOURCE_PATH),
                    str(self.authority_module.CURRENT_COMPILED_CONTRACT_PATH),
                    str(self.authority_module.CURRENT_CHECK_MANIFEST_PATH),
                    "SKILL.md",
                    "agents/openai.yaml",
                ),
            )
        )
        self.stage = "validate-control-projection-authority"
        projection_authority = self.authority_module.resolve_runtime_authority(
            self.control_projection_root
        )
        if not (
            projection_authority.ok
            and projection_authority.authority
            == self.authority_module.AUTHORITY_CURRENT
            and projection_authority.skill_id == self.skill_id
        ):
            raise ValueError(
                "installed control projection is not exact current V2"
            )
        self.compiled = _load_object(
            self.control_projection_root
            / ".skillguard"
            / "compiled-contract.json"
        )
        self.manifest = _load_object(
            self.control_projection_root
            / ".skillguard"
            / "check-manifest.json"
        )
        if str(self.compiled.get("skill_id") or "") != self.skill_id:
            raise ValueError("installed control projection skill id changed")

        self.stage = "replay-skillguard-installation-currentness"
        receipt_relative = str(
            self.installation_module.DEFAULT_INSTALLATION_RECEIPT_RELATIVE_PATH
        )
        self.active_skillguard_root = self.validation_runtime_root.resolve(strict=True)
        with _installation_identity_environment():
            self.verified_context = (
                self.installation_module.load_verified_installation_context(
                    self.active_skillguard_root / receipt_relative,
                    canonical_skill_root=None,
                    codex_home=self.validation_codex_home,
                )
            )

        self.stage = "bind-verified-runtime-identity"
        installed_runtime_identity = (
            self.verified_context.current_snapshot.get(
                "installed_runtime_fingerprint"
            )
        )
        self.guard_runtime_identity = (
            self.runtime_fingerprint_module.guard_runtime_fingerprint(
                self.runtime_root
            )
        )
        if not isinstance(installed_runtime_identity, dict):
            raise ValueError(
                "verified installed runtime fingerprint is unavailable"
            )
        if self.guard_runtime_identity != installed_runtime_identity:
            raise ValueError(
                "frozen SkillGuard behavior projection does not match installed currentness"
            )

        self.scheduled_identity: dict[str, Any] = {}
        if scheduler_or_trigger_id or scheduled_execution_id:
            if not scheduler_or_trigger_id or not scheduled_execution_id:
                raise ValueError(
                    "scheduled supervision requires trigger and execution ids together"
                )
            self.stage = "build-start-scheduled-production-identity"
            with _installation_identity_environment():
                identity = (
                    self.installation_module.build_scheduled_production_identity(
                        scheduler_or_trigger_id=scheduler_or_trigger_id,
                        scheduled_execution_id=scheduled_execution_id,
                        active_skill_root=self.active_skillguard_root,
                        verified_context=self.verified_context,
                    )
                )
                self.installation_module.verify_scheduled_production_installation_identity(
                    identity,
                    active_skill_root=self.active_skillguard_root,
                    verified_context=self.verified_context,
                )
            self.scheduled_identity = dict(identity)
        self.stage = "ready"

    def portable_snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": (
                "khaos-brain.scheduled-supervision-start-snapshot.v1"
            ),
            "skill_id": self.skill_id,
            "scheduled_production_identity": dict(self.scheduled_identity),
            "verified_installation_context": (
                self.verified_context.portable_identity()
            ),
            "runtime_projection_hash": str(
                self.runtime_projection_receipt.get("projection_hash") or ""
            ),
            "runtime_projection_file_count": len(
                self.runtime_projection_receipt.get("file_hashes", {})
            ),
            "control_projection_hash": str(
                self.control_projection_receipt.get("projection_hash") or ""
            ),
            "control_projection_file_count": len(
                self.control_projection_receipt.get("file_hashes", {})
            ),
            "runtime_fingerprint": str(
                self.guard_runtime_identity.get("source_hash") or ""
            ),
            "authority_frozen_before_native": True,
        }

    def supervise(
        self,
        *,
        packet: Mapping[str, Any],
        target_root: Path,
        dynamic_environment: Mapping[str, object] | None = None,
    ) -> dict[str, Any]:
        self.stage = "execute-stable-supervisor"
        resolved_target = target_root.resolve()
        resolved_target.relative_to(self.repository_root)
        resolved_target.mkdir(parents=True, exist_ok=True)
        with _supervision_dynamic_environment(dynamic_environment or {}):
            return self.supervisor_module.supervise_contract_run(
                self.control_projection_root,
                resolved_target,
                self.repository_root,
                dict(packet),
                compiled_contract=self.compiled,
                check_manifest=self.manifest,
                guard_runtime_identity=self.guard_runtime_identity,
                verified_installation_context=self.verified_context,
            )

    def build_terminal(self, request: Mapping[str, Any]) -> dict[str, Any]:
        self.stage = "build-target-native-terminal"
        run_root = Path(str(request.get("run_root") or "")).resolve(strict=True)
        run_root.relative_to(self.repository_root)
        native_receipt_path = Path(
            str(request.get("native_receipt_path") or "")
        ).resolve(strict=True)
        native_receipt_path.relative_to(self.repository_root)
        native_receipt_hash = str(
            request.get("native_receipt_hash") or ""
        )
        native_bytes = native_receipt_path.read_bytes()
        artifact_relative = (
            Path("native-terminal")
            / "artifacts"
            / f"native-receipt-{native_receipt_hash[:24].lower()}.json"
        )
        artifact_path = run_root / artifact_relative
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        if artifact_path.exists():
            if artifact_path.read_bytes() != native_bytes:
                raise RuntimeError("native terminal artifact collision")
        else:
            artifact_path.write_bytes(native_bytes)
        contract = self.run_store_module.load_contract_snapshot(run_root)
        built = self.terminal_module.build_target_native_terminal_receipt(
            run_root,
            contract,
            profile=str(request.get("profile") or ""),
            native_route_id="route:khaos-brain-update:authorize",
            branch_id=str(request.get("branch_id") or ""),
            native_check_id=(
                "check:khaos-brain-update:branch-terminal-runtime"
            ),
            native_receipt_artifact_ref={
                "path_token": "run_root",
                "relative_path": artifact_relative.as_posix(),
            },
            observed_state={
                "stage": str(request.get("stage") or ""),
                "branch_id": str(request.get("branch_id") or ""),
                "native_receipt_hash": native_receipt_hash,
                "finalization_receipt_hash": str(
                    request.get("finalization_receipt_hash") or ""
                ),
            },
            verified_installation_context=self.verified_context,
        )
        persisted = self.terminal_module.write_target_native_terminal_receipt(
            run_root,
            built,
        )
        if not isinstance(persisted, Mapping):
            raise RuntimeError(
                "target native terminal writer returned an invalid result"
            )
        receipt = persisted.get("receipt")
        receipt_ref = persisted.get("receipt_ref")
        if not isinstance(receipt, Mapping) or not isinstance(
            receipt_ref, Mapping
        ):
            raise RuntimeError(
                "target native terminal writer omitted receipt or portable ref"
            )
        return {
            "receipt": dict(receipt),
            "receipt_ref": dict(receipt_ref),
            "native_artifact_ref": {
                "path_token": "run_root",
                "relative_path": artifact_relative.as_posix(),
            },
        }


def _write_protocol(payload: Mapping[str, Any]) -> None:
    print(
        json.dumps(dict(payload), ensure_ascii=True, sort_keys=True),
        flush=True,
    )


def _run_session(
    runtime: _FrozenInstalledSupervisionRuntime,
) -> int:
    _write_protocol(
        {
            "ok": True,
            "status": "session-ready",
            "scheduled_production_identity": runtime.scheduled_identity,
            "scheduled_supervision_snapshot": runtime.portable_snapshot(),
        }
    )
    for raw_line in sys.stdin:
        try:
            request = json.loads(raw_line)
            if not isinstance(request, dict):
                raise ValueError("session request must be a JSON object")
            operation = str(request.get("operation") or "")
            if operation == "close":
                _write_protocol({"ok": True, "status": "session-closed"})
                return 0
            if operation == "supervise":
                packet = _load_object(
                    Path(str(request.get("packet_path") or "")).resolve(
                        strict=True
                    )
                )
                dynamic_environment = request.get("dynamic_environment", {})
                if not isinstance(dynamic_environment, Mapping):
                    raise ValueError(
                        "dynamic supervision environment must be an object"
                    )
                with redirect_stdout(sys.stderr):
                    report = runtime.supervise(
                        packet=packet,
                        target_root=Path(
                            str(request.get("target_root") or "")
                        ),
                        dynamic_environment=dynamic_environment,
                    )
                _write_protocol(
                    {
                        "ok": True,
                        "installed_control_projection": (
                            runtime.control_projection_receipt
                        ),
                        "skillguard_runtime_projection": (
                            runtime.runtime_projection_receipt
                        ),
                        "scheduled_supervision_snapshot": (
                            runtime.portable_snapshot()
                        ),
                        "report": report,
                    }
                )
                continue
            if operation == "build-terminal":
                with redirect_stdout(sys.stderr):
                    result = runtime.build_terminal(request)
                _write_protocol({"ok": True, "result": result})
                continue
            raise ValueError(f"unsupported session operation: {operation}")
        except Exception as exc:
            _write_protocol(
                {
                    "ok": False,
                    "stage": runtime.stage,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_root")
    parser.add_argument("packet", nargs="?")
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--codex-home", required=True)
    parser.add_argument("--session", action="store_true")
    parser.add_argument("--scheduler-or-trigger-id", default="")
    parser.add_argument("--scheduled-execution-id", default="")
    args = parser.parse_args()

    stage = "parse-inputs"
    runtime = _FrozenInstalledSupervisionRuntime.__new__(
        _FrozenInstalledSupervisionRuntime
    )
    runtime.stage = stage
    try:
        _FrozenInstalledSupervisionRuntime.__init__(
            runtime,
            skill_root=Path(args.skill_root),
            target_root=Path(args.target_root),
            repository_root=Path(args.repository_root),
            codex_home=Path(args.codex_home),
            scheduler_or_trigger_id=str(args.scheduler_or_trigger_id),
            scheduled_execution_id=str(args.scheduled_execution_id),
        )
        if args.session:
            return _run_session(runtime)
        if not args.packet:
            raise ValueError("packet is required outside session mode")
        packet = _load_object(Path(args.packet).resolve(strict=True))
        report = runtime.supervise(
            packet=packet,
            target_root=Path(args.target_root),
        )
    except Exception as exc:  # machine boundary: fail closed with one JSON object
        stage = str(getattr(runtime, "stage", stage))
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": stage,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "installed_control_projection": (
                    runtime.control_projection_receipt
                ),
                "skillguard_runtime_projection": (
                    runtime.runtime_projection_receipt
                ),
                "scheduled_supervision_snapshot": (
                    runtime.portable_snapshot()
                ),
                "report": report,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
