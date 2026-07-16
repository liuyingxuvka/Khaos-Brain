"""Run current SkillGuard and source/install parity checks for KB Skills."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from collections import Counter
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


_INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV = (
    "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_PRESENT"
)
_INSTALLATION_IDENTITY_PYTHONPATH_VALUE_ENV = (
    "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_VALUE"
)


@contextmanager
def _installation_identity_environment():
    """Hide only the formal FlowGuard PYTHONPATH injection from install replay."""

    presence = os.environ.get(_INSTALLATION_IDENTITY_PYTHONPATH_PRESENT_ENV)
    if presence not in {"0", "1"}:
        yield
        return
    previous_present = "PYTHONPATH" in os.environ
    previous_value = os.environ.get("PYTHONPATH", "")
    if presence == "1":
        os.environ["PYTHONPATH"] = os.environ.get(
            _INSTALLATION_IDENTITY_PYTHONPATH_VALUE_ENV, ""
        )
    else:
        os.environ.pop("PYTHONPATH", None)
    try:
        yield
    finally:
        if previous_present:
            os.environ["PYTHONPATH"] = previous_value
        else:
            os.environ.pop("PYTHONPATH", None)

from local_kb.automation_contracts import (  # noqa: E402
    AUTOMATION_COMPLETION_CONTRACTS,
    STANDARD_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS,
    UPDATE_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS,
    check_id,
    evidence_test_node_ids,
    step_id,
)
from local_kb.codex_registry import discover_active_registry  # noqa: E402
from local_kb.automation_runtime import (  # noqa: E402
    build_update_finalization_receipt,
    content_hash,
    validate_native_receipt,
    validate_update_finalization_receipt,
    write_fixture_receipt,
    write_native_receipt,
)
from local_kb.install import MAINTENANCE_SKILL_NAMES, REPO_AUTOMATION_SPECS  # noqa: E402
from local_kb.transactional_install import tree_manifest  # noqa: E402
from local_kb.process_control import (  # noqa: E402
    run_with_timeout_cleanup,
    terminate_process_tree,
)
from scripts.check_kb_automation_skillguard_depth import _closure_findings  # noqa: E402


V2_FILES = (
    ".skillguard/contract-source.json",
    ".skillguard/compiled-contract.json",
    ".skillguard/check-manifest.json",
)

_SUPERVISION_SURFACE_CODES = {
    "source": "src",
    "source-shallow-calibration": "src-sh",
    "installed": "ins",
    "installed-shallow-calibration": "ins-sh",
}
_SUPERVISION_SKILL_CODES = {
    "kb-sleep-maintenance": "sleep",
    "kb-dream-pass": "dream",
    "kb-organization-contribute": "org-c",
    "kb-organization-maintenance": "org-m",
    "khaos-brain-update": "update",
}

_SCHEDULED_PRODUCTION_IDENTITY_FIELDS = frozenset(
    {
        "scheduler_or_trigger_id",
        "scheduled_execution_id",
        "installation_receipt_id",
        "installation_receipt_hash",
        "installation_receipt_root_ref",
        "installed_runtime_fingerprint",
    }
)

_SUPERVISION_DYNAMIC_ENV_KEYS = (
    "KHAOS_BRAIN_AUTOMATION_RECEIPT",
    "KHAOS_BRAIN_AUTOMATION_RUN_ID",
    "KHAOS_BRAIN_AUTOMATION_RECEIPT_HASH",
    "KHAOS_BRAIN_SCHEDULED_PRODUCTION_IDENTITY",
    "KHAOS_BRAIN_ALLOW_AUTOMATION_FIXTURE",
    "KHAOS_BRAIN_UPDATE_FINALIZATION_RECEIPT",
    "KHAOS_BRAIN_UPDATE_FINALIZATION_RECEIPT_HASH",
)


def _run_json(
    command: list[str],
    *,
    timeout: int = 1800,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        completed = run_with_timeout_cleanup(
            command,
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        cleanup = dict(getattr(exc, "cleanup_receipt", {}) or {})
        return {
            "ok": False,
            "error": "command timed out",
            "stdout": str(exc.stdout or "")[-2000:],
            "stderr": str(exc.stderr or "")[-2000:],
            "exit_code": 124,
            "timeout_cleanup": cleanup,
            "cleanup_confirmed": cleanup.get("cleanup_confirmed") is True,
        }
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {
            "ok": False,
            "error": "command did not emit JSON",
            "stdout": completed.stdout[-2000:],
            "stderr": completed.stderr[-2000:],
        }
    payload["exit_code"] = completed.returncode
    return payload


class _ScheduledProductionIdentity(dict[str, Any]):
    """Portable identity carrying a non-serializable start-frozen session."""

    def __init__(
        self,
        payload: Mapping[str, Any],
        session: "_InstalledSupervisionSession",
    ) -> None:
        super().__init__(payload)
        self._supervision_session = session

    def __del__(self) -> None:
        try:
            session = getattr(self, "_supervision_session", None)
            session_type = globals().get("_InstalledSupervisionSession")
            if session_type is not None and isinstance(session, session_type):
                session.close(force=True)
        except Exception:
            # Interpreter teardown may clear module globals in any order.  A
            # best-effort finalizer must never manufacture a shutdown error;
            # the explicit guarded-result path remains the lifecycle owner.
            pass


class _InstalledSupervisionSession:
    """Own one persistent official SkillGuard worker for one native run."""

    def __init__(
        self,
        *,
        process: subprocess.Popen[str],
        stderr_handle: Any,
        stderr_path: Path,
        identity: Mapping[str, Any],
        snapshot: Mapping[str, Any],
    ) -> None:
        self.process = process
        self._stderr_handle = stderr_handle
        self.stderr_path = stderr_path
        self.identity = dict(identity)
        self.snapshot = dict(snapshot)
        self._request_lock = threading.Lock()
        self._closed = False
        self.cleanup_receipt: dict[str, Any] = {}

    @classmethod
    def start(
        cls,
        *,
        skill_root: Path,
        codex_home: Path,
        repository_root: Path,
        session_root: Path,
        scheduler_or_trigger_id: str,
        scheduled_execution_id: str,
    ) -> "_InstalledSupervisionSession":
        worker = (
            repository_root
            / "scripts"
            / "run_installed_skillguard_supervision.py"
        ).resolve(strict=True)
        resolved_session_root = session_root.resolve()
        resolved_session_root.relative_to(repository_root.resolve(strict=True))
        resolved_session_root.mkdir(parents=True, exist_ok=True)
        target_root = resolved_session_root / "bootstrap-target"
        target_root.mkdir(parents=True, exist_ok=True)
        stderr_path = resolved_session_root / "worker-stderr.log"
        stderr_handle = stderr_path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        )
        command = [
            sys.executable,
            str(worker),
            str(skill_root.resolve(strict=True)),
            "--session",
            "--target-root",
            str(target_root),
            "--repository-root",
            str(repository_root.resolve(strict=True)),
            "--codex-home",
            str(codex_home.resolve(strict=True)),
            "--scheduler-or-trigger-id",
            scheduler_or_trigger_id,
            "--scheduled-execution-id",
            scheduled_execution_id,
        ]
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(codex_home.resolve(strict=True))
        environment["KHAOS_BRAIN_ASSURANCE_ACTIVE"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        for key in _SUPERVISION_DYNAMIC_ENV_KEYS:
            environment.pop(key, None)
        popen_options: dict[str, Any] = {
            "cwd": repository_root,
            "env": environment,
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": stderr_handle,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
        }
        if os.name == "nt":
            popen_options["creationflags"] = getattr(
                subprocess,
                "CREATE_NEW_PROCESS_GROUP",
                0,
            )
        else:
            popen_options["start_new_session"] = True
        process = subprocess.Popen(command, **popen_options)
        provisional = cls(
            process=process,
            stderr_handle=stderr_handle,
            stderr_path=stderr_path,
            identity={},
            snapshot={},
        )
        try:
            ready = provisional._read_protocol(timeout=300)
            identity = ready.get("scheduled_production_identity")
            snapshot = ready.get("scheduled_supervision_snapshot")
            if (
                ready.get("ok") is not True
                or ready.get("status") != "session-ready"
                or not isinstance(identity, Mapping)
                or set(identity) != set(_SCHEDULED_PRODUCTION_IDENTITY_FIELDS)
                or not isinstance(snapshot, Mapping)
                or snapshot.get("authority_frozen_before_native") is not True
            ):
                detail = {
                    key: ready.get(key)
                    for key in ("status", "stage", "error")
                    if ready.get(key) not in (None, "")
                }
                raise RuntimeError(
                    "start-frozen SkillGuard supervision session did not become ready: "
                    + json.dumps(detail, ensure_ascii=True, sort_keys=True)
                )
            provisional.identity = dict(identity)
            provisional.snapshot = dict(snapshot)
            return provisional
        except Exception:
            provisional.close(force=True)
            raise

    def _stderr_tail(self) -> str:
        try:
            self._stderr_handle.flush()
            return self.stderr_path.read_text(
                encoding="utf-8",
                errors="replace",
            )[-3000:]
        except OSError:
            return ""

    def _read_protocol(self, *, timeout: float) -> dict[str, Any]:
        if self.process.stdout is None:
            raise RuntimeError("SkillGuard session stdout is unavailable")
        rows: queue.Queue[str] = queue.Queue(maxsize=1)

        def read_one() -> None:
            rows.put(self.process.stdout.readline())

        reader = threading.Thread(target=read_one, daemon=True)
        reader.start()
        try:
            line = rows.get(timeout=timeout)
        except queue.Empty as exc:
            self.cleanup_receipt = terminate_process_tree(self.process)
            self._closed = True
            raise TimeoutError(
                "SkillGuard supervision session timed out; "
                f"cleanup={json.dumps(self.cleanup_receipt, sort_keys=True)}"
            ) from exc
        if not line:
            raise RuntimeError(
                "SkillGuard supervision session exited without a response; "
                f"exit_code={self.process.poll()} stderr={self._stderr_tail()}"
            )
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "SkillGuard supervision session emitted invalid JSON; "
                f"line={line[-1000:]} stderr={self._stderr_tail()}"
            ) from exc
        if not isinstance(payload, dict):
            raise RuntimeError(
                "SkillGuard supervision session response must be an object"
            )
        return payload

    def request(
        self,
        payload: Mapping[str, Any],
        *,
        timeout: float = 2400,
    ) -> dict[str, Any]:
        with self._request_lock:
            if self._closed or self.process.poll() is not None:
                raise RuntimeError(
                    "start-frozen SkillGuard supervision session is not available"
                )
            if self.process.stdin is None:
                raise RuntimeError("SkillGuard session stdin is unavailable")
            self.process.stdin.write(
                json.dumps(
                    dict(payload),
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            )
            self.process.stdin.flush()
            return self._read_protocol(timeout=timeout)

    def run_packet(
        self,
        packet_path: Path,
        *,
        target_root: Path,
        environment: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        dynamic_environment = {
            key: str(environment[key])
            for key in _SUPERVISION_DYNAMIC_ENV_KEYS
            if environment is not None and key in environment
        }
        payload = self.request(
            {
                "operation": "supervise",
                "packet_path": str(packet_path.resolve(strict=True)),
                "target_root": str(target_root.resolve()),
                "dynamic_environment": dynamic_environment,
            },
            timeout=2400,
        )
        payload["exit_code"] = 0 if payload.get("ok") is True else 1
        return payload

    def build_terminal(self, **kwargs: Any) -> dict[str, Any]:
        payload = self.request(
            {"operation": "build-terminal", **kwargs},
            timeout=300,
        )
        result = payload.get("result")
        if payload.get("ok") is not True or not isinstance(result, Mapping):
            raise RuntimeError(
                "start-frozen SkillGuard terminal construction failed: "
                f"{payload.get('error') or payload}"
            )
        return dict(result)

    def close(self, *, force: bool = False) -> None:
        if self._closed:
            try:
                self._stderr_handle.close()
            except OSError:
                pass
            return
        try:
            if self.process.poll() is None and not force:
                response = self.request(
                    {"operation": "close"},
                    timeout=30,
                )
                if response.get("ok") is not True:
                    force = True
            if self.process.poll() is None and not force:
                try:
                    self.process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    force = True
            if force and self.process.poll() is None:
                self.cleanup_receipt = terminate_process_tree(self.process)
        finally:
            self._closed = True
            for stream in (self.process.stdin, self.process.stdout):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
            try:
                self._stderr_handle.close()
            except OSError:
                pass


def _close_scheduled_supervision_session(
    identity: Mapping[str, Any] | None,
) -> None:
    session = getattr(identity, "_supervision_session", None)
    if isinstance(session, _InstalledSupervisionSession):
        session.close()


def _scheduled_supervision_snapshot(
    identity: Mapping[str, Any] | None,
) -> dict[str, Any]:
    session = getattr(identity, "_supervision_session", None)
    return (
        dict(session.snapshot)
        if isinstance(session, _InstalledSupervisionSession)
        else {}
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _installed_skillguard_module(codex_home: Path, module_name: str):
    configured = os.environ.get(
        "KHAOS_BRAIN_SKILLGUARD_VALIDATION_ROOT", ""
    ).strip()
    skillguard_root = (
        Path(configured).resolve()
        if configured
        else (codex_home / "skills" / "skillguard").resolve()
    )
    scripts_root = (skillguard_root / "scripts").resolve()
    if not scripts_root.is_dir():
        raise RuntimeError("installed SkillGuard scripts root is missing")
    root_text = str(scripts_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    importlib.invalidate_caches()
    module = importlib.import_module(module_name)
    module_path = Path(str(getattr(module, "__file__", ""))).resolve()
    try:
        module_path.relative_to(scripts_root)
    except ValueError as exc:
        raise RuntimeError(
            f"SkillGuard module resolved outside the active installed runtime: {module_name}"
        ) from exc
    return module


def _load_current_verified_installation_context(
    codex_home: Path,
) -> tuple[object, Path]:
    """Replay the active installation receipt and retain its sealed context.

    The portable six-field scheduled identity is evidence that can be stored in
    receipts.  SkillGuard's verified installation context is intentionally an
    in-process, non-forgeable authority object.  Producers that construct a
    target-native terminal must receive both; retaining only the portable
    projection is not enough to authorize terminal issuance.
    """

    module = _installed_skillguard_module(
        codex_home,
        "skillguard_v2.installation_receipt",
    )
    context_loader = getattr(module, "load_verified_installation_context", None)
    receipt_relative_path = getattr(
        module, "DEFAULT_INSTALLATION_RECEIPT_RELATIVE_PATH", ""
    )
    if not callable(context_loader) or not str(receipt_relative_path):
        raise RuntimeError(
            "installed SkillGuard lacks the verified installation context API"
        )
    active_skill_root = (codex_home / "skills" / "skillguard").resolve()
    with _installation_identity_environment():
        verified_context = context_loader(
            active_skill_root / str(receipt_relative_path),
            canonical_skill_root=None,
            codex_home=codex_home,
        )
    return verified_context, active_skill_root


def _build_current_scheduled_production_identity(
    codex_home: Path,
    *,
    scheduler_or_trigger_id: str,
    scheduled_execution_id: str,
    scheduled_skill_root: Path | None = None,
    repository_root: Path | None = None,
    session_root: Path | None = None,
) -> dict[str, Any]:
    session_inputs = (
        scheduled_skill_root,
        repository_root,
        session_root,
    )
    if any(value is not None for value in session_inputs):
        if not all(value is not None for value in session_inputs):
            raise RuntimeError(
                "start-frozen supervision requires skill, repository, and session roots"
            )
        session = _InstalledSupervisionSession.start(
            skill_root=Path(scheduled_skill_root),
            codex_home=codex_home,
            repository_root=Path(repository_root),
            session_root=Path(session_root),
            scheduler_or_trigger_id=scheduler_or_trigger_id,
            scheduled_execution_id=scheduled_execution_id,
        )
        identity = session.identity
        if set(identity) != set(_SCHEDULED_PRODUCTION_IDENTITY_FIELDS):
            session.close(force=True)
            raise RuntimeError(
                "scheduled-production identity does not have the exact six-field contract"
            )
        return _ScheduledProductionIdentity(identity, session)

    module = _installed_skillguard_module(
        codex_home,
        "skillguard_v2.installation_receipt",
    )
    builder = getattr(module, "build_scheduled_production_identity", None)
    verifier = getattr(
        module,
        "verify_scheduled_production_installation_identity",
        None,
    )
    if (
        not callable(builder)
        or not callable(verifier)
    ):
        raise RuntimeError(
            "installed SkillGuard lacks the scheduled-production installation identity API"
        )
    verified_context, active_skill_root = _load_current_verified_installation_context(
        codex_home
    )
    with _installation_identity_environment():
        identity = builder(
            scheduler_or_trigger_id=scheduler_or_trigger_id,
            scheduled_execution_id=scheduled_execution_id,
            active_skill_root=active_skill_root,
            verified_context=verified_context,
        )
        if not isinstance(identity, Mapping) or set(identity) != set(
            _SCHEDULED_PRODUCTION_IDENTITY_FIELDS
        ):
            raise RuntimeError(
                "scheduled-production identity does not have the exact six-field contract"
            )
        root_ref = identity.get("installation_receipt_root_ref")
        if (
            not isinstance(root_ref, Mapping)
            or root_ref.get("path_token") != "active_skill_root"
            or not str(root_ref.get("relative_path") or "")
        ):
            raise RuntimeError("scheduled-production installation receipt root ref is invalid")
        verifier(
            identity,
            active_skill_root=active_skill_root,
            verified_context=verified_context,
        )
    return dict(identity)


def _installed_projection_parity(
    codex_home: Path,
    *,
    skill_id: str,
    source_skill_root: Path,
    installed_skill_root: Path,
) -> dict[str, Any]:
    """Use SkillGuard's compiler-owned installation projection, not repo recompilation."""

    module = _installed_skillguard_module(
        codex_home,
        "skillguard_v2.installed_parity",
    )
    verifier = getattr(module, "verify_installed_content_parity", None)
    validator = getattr(module, "validate_installed_parity_receipt", None)
    replay = getattr(module, "replay_installed_content_parity_currentness", None)
    if not callable(verifier) or not callable(validator) or not callable(replay):
        return {
            "ok": False,
            "status": "blocked",
            "blockers": ["installed_parity_api_unavailable"],
        }
    skill_path = source_skill_root.resolve().relative_to(REPO_ROOT).as_posix()
    target_identity = {
        "skill_id": skill_id,
        "target_kind": "single_skill",
        "member_identities": [
            {"member_skill_id": skill_id, "skill_path": skill_path}
        ],
        "skill_paths": [skill_path],
    }
    portfolio_projection_hash = "sha256:" + hashlib.sha256(
        json.dumps(
            target_identity,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    receipt = verifier(
        REPO_ROOT,
        target_identity,
        installed_skill_root,
        portfolio_projection_hash=portfolio_projection_hash,
    )
    findings = list(
        validator(
            receipt,
            portfolio_projection_hash=portfolio_projection_hash,
        )
    )
    replay_findings = list(
        replay(
            receipt,
            canonical_repository_root=REPO_ROOT,
            target_identity=target_identity,
            installed_target_root=installed_skill_root,
            portfolio_projection_hash=portfolio_projection_hash,
        )
    )
    return {
        "ok": (
            isinstance(receipt, Mapping)
            and receipt.get("status") == "current"
            and not findings
            and not replay_findings
        ),
        "status": receipt.get("status") if isinstance(receipt, Mapping) else "blocked",
        "target_identity": target_identity,
        "portfolio_projection_hash": portfolio_projection_hash,
        "receipt": dict(receipt) if isinstance(receipt, Mapping) else {},
        "validation_findings": findings,
        "currentness_findings": replay_findings,
        "claim_boundary": (
            "Official SkillGuard installation-projection parity only; repository-only "
            "models, tests, notes, reports, and runtime outputs remain source-owned."
        ),
    }


def _build_and_write_target_native_terminal(
    codex_home: Path,
    *,
    run_root: Path,
    profile: str,
    branch_id: str,
    native_receipt_path: Path,
    native_receipt_hash: str,
    finalization_receipt_hash: str,
    stage: str,
    supervision_session: _InstalledSupervisionSession | None = None,
) -> dict[str, Any]:
    if supervision_session is not None:
        return supervision_session.build_terminal(
            run_root=str(run_root.resolve()),
            profile=profile,
            branch_id=branch_id,
            native_receipt_path=str(native_receipt_path.resolve(strict=True)),
            native_receipt_hash=native_receipt_hash,
            finalization_receipt_hash=finalization_receipt_hash,
            stage=stage,
        )

    terminal_module = _installed_skillguard_module(
        codex_home,
        "skillguard_v2.native_terminal",
    )
    run_store_module = _installed_skillguard_module(
        codex_home,
        "skillguard_v2.run_store",
    )
    builder = getattr(terminal_module, "build_target_native_terminal_receipt", None)
    writer = getattr(terminal_module, "write_target_native_terminal_receipt", None)
    load_contract_snapshot = getattr(run_store_module, "load_contract_snapshot", None)
    if not callable(builder) or not callable(writer) or not callable(load_contract_snapshot):
        raise RuntimeError(
            "installed SkillGuard lacks the target-owned native terminal producer API"
        )
    run_root = run_root.resolve()
    native_bytes = native_receipt_path.resolve().read_bytes()
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
    contract = load_contract_snapshot(run_root)
    verified_installation_context, _ = (
        _load_current_verified_installation_context(codex_home)
    )
    with _installation_identity_environment():
        built = builder(
            run_root,
            contract,
            profile=profile,
            native_route_id="route:khaos-brain-update:authorize",
            branch_id=branch_id,
            native_check_id="check:khaos-brain-update:branch-terminal-runtime",
            native_receipt_artifact_ref={
                "path_token": "run_root",
                "relative_path": artifact_relative.as_posix(),
            },
            observed_state={
                "stage": stage,
                "branch_id": branch_id,
                "native_receipt_hash": native_receipt_hash,
                "finalization_receipt_hash": finalization_receipt_hash,
            },
            verified_installation_context=verified_installation_context,
        )
    persisted = writer(run_root, built)
    if not isinstance(persisted, Mapping):
        raise RuntimeError("target native terminal writer returned an invalid result")
    receipt = persisted.get("receipt")
    receipt_ref = persisted.get("receipt_ref")
    if not isinstance(receipt, Mapping) or not isinstance(receipt_ref, Mapping):
        raise RuntimeError("target native terminal writer omitted receipt or portable ref")
    return {
        "receipt": dict(receipt),
        "receipt_ref": dict(receipt_ref),
        "native_artifact_ref": {
            "path_token": "run_root",
            "relative_path": artifact_relative.as_posix(),
        },
    }


def _automation_prompt(skill_id: str) -> str:
    return next(
        str(item.get("prompt") or "")
        for item in REPO_AUTOMATION_SPECS
        if str(item.get("skill_name") or "") == skill_id
    )


def _skill_surface(skill_root: Path, skill_id: str) -> dict[str, Any]:
    control = skill_root / ".skillguard"
    skill_path = skill_root / "SKILL.md"
    return {
        "skill_text": (
            skill_path.read_text(encoding="utf-8", errors="replace")
            if skill_path.is_file()
            else ""
        ),
        "automation_prompt": _automation_prompt(skill_id),
        "contract_source": _load_json(control / "contract-source.json"),
        "compiled_contract": _load_json(control / "compiled-contract.json"),
        "check_manifest": _load_json(control / "check-manifest.json"),
    }


def _supervision_scope(skill_id: str, stage: str) -> dict[str, Any]:
    if skill_id != "khaos-brain-update":
        if stage not in {"complete", "finalization"}:
            raise ValueError(f"unsupported supervision stage for {skill_id}: {stage}")
        return {
            "stage": "complete",
            "route_ids": [f"route:{skill_id}:run"],
            "compose": False,
            "profile": "enforced",
            "included_phases": {"intake", "execute", "verify"},
        }
    if stage == "authorization":
        return {
            "stage": stage,
            "route_ids": ["route:khaos-brain-update:authorize"],
            "compose": False,
            "profile": "enforced",
            "included_phases": {"intake", "execute", "verify"},
        }
    if stage == "no-op":
        return {
            "stage": stage,
            "route_ids": ["route:khaos-brain-update:authorize"],
            "compose": False,
            "profile": "enforced",
            "included_phases": {"intake", "execute", "verify"},
        }
    if stage in {"complete", "finalization"}:
        return {
            "stage": "finalization",
            "route_ids": [
                "route:khaos-brain-update:authorize",
                "route:khaos-brain-update:finalize",
            ],
            "compose": True,
            "profile": "enforced",
            "included_phases": {"intake", "execute", "verify", "finalize"},
        }
    raise ValueError(f"unsupported supervision stage for {skill_id}: {stage}")


def _native_output_witness(
    *,
    artifact_id: str,
    run_id: str,
    receipt_hash: str,
    receipt_path: Path,
    executor_id: str,
) -> dict[str, Any]:
    witness_input = {
        "run_id": run_id,
        "receipt_path": str(Path(receipt_path).resolve()),
    }
    witness_output = {"receipt_hash": receipt_hash}
    witness_identity = {
        "artifact_id": artifact_id,
        "run_id": run_id,
        "receipt_hash": receipt_hash,
        "receipt_path": witness_input["receipt_path"],
        "executor_id": executor_id,
    }
    return {
        # Pre-materialize the exact native-output witness because the current
        # official supervisor recognizes native_output as an artifact kind but
        # its generic action-witness constructor intentionally accepts only
        # interactive tool/API kinds. The supervisor still validates the four
        # required immutable witness fields and records their canonical hash.
        "witness_id": f"native-output-{content_hash(witness_identity)[:24].lower()}",
        "witness_kind": "native_output",
        "target_id": artifact_id,
        "executor_id": executor_id,
        "input": witness_input,
        "output": witness_output,
        "input_fingerprint": content_hash(witness_input),
        "output_fingerprint": content_hash(witness_output),
        "limitations": [
            "This witness binds only the exact immutable receipt; target behavior is proven by the declared native checks."
        ],
    }


def _supervision_packet(
    skill_id: str,
    *,
    stage: str,
    native_run_id: str,
    native_receipt_hash: str,
    native_receipt_path: Path,
    finalization_receipt_hash: str = "",
    finalization_receipt_path: Path | None = None,
    supervision_mode: str = "close",
    scheduled_production_identity: Mapping[str, Any] | None = None,
    request_text: str = "",
    native_terminal_receipt_ref: Mapping[str, Any] | None = None,
    expected_native_route_id: str = "",
    expected_native_branch_id: str = "",
) -> dict[str, Any]:
    spec = AUTOMATION_COMPLETION_CONTRACTS[skill_id]
    scope = _supervision_scope(skill_id, stage)
    native_artifact_id = f"artifact:{skill_id}:native-receipt"
    steps: dict[str, Any] = {
        step_id(skill_id, "execute"): {
            "artifact_witnesses": {
                native_artifact_id: _native_output_witness(
                    artifact_id=native_artifact_id,
                    run_id=native_run_id,
                    receipt_hash=native_receipt_hash,
                    receipt_path=native_receipt_path,
                    executor_id=str(spec["entrypoint_path"]),
                )
            }
        }
    }
    if scope["stage"] == "finalization":
        if not finalization_receipt_hash or finalization_receipt_path is None:
            raise ValueError("finalization supervision requires the exact finalization receipt")
        final_artifact_id = "artifact:khaos-brain-update:finalization-receipt"
        steps[step_id(skill_id, "finalize")] = {
            "artifact_witnesses": {
                final_artifact_id: _native_output_witness(
                    artifact_id=final_artifact_id,
                    run_id=native_run_id,
                    receipt_hash=finalization_receipt_hash,
                    receipt_path=finalization_receipt_path,
                    executor_id="scripts/run_kb_guarded_automation.py",
                )
            }
        }
    packet: dict[str, Any] = {
        "supervision_mode": supervision_mode,
        "request": {
            "route_ids": list(scope["route_ids"]),
            "compose": bool(scope["compose"]),
            "request": request_text
            or f"current {scope['stage']} supervision for {native_run_id}",
            "intent": (
                "authorize exact native update work without claiming completion"
                if scope["stage"] == "authorization"
                else "execute every target-owned automation obligation and reject partial completion"
            ),
            "claim_scope": str(scope["profile"]),
            "target_input_paths": ["automation-input.json"],
        },
        "profiles": (
            [] if supervision_mode == "stage_depth" else [str(scope["profile"])]
        ),
        "steps": steps,
        "execution_depth": {
            "observations": [],
            "run_started": True,
            "boundary_only": False,
        },
    }
    if scheduled_production_identity is not None:
        packet["execution_depth"].update(
            {
                "evidence_domain": "scheduled_production",
                "scheduled_production_identity": dict(
                    scheduled_production_identity
                ),
            }
        )
    if native_terminal_receipt_ref is not None:
        packet["native_terminal"] = {
            "receipt_ref": dict(native_terminal_receipt_ref),
            "expected_route_id": expected_native_route_id,
            "expected_branch_id": expected_native_branch_id,
        }
    return packet


def _supervision_target_authority(
    skill_id: str,
    skill_root: Path,
    codex_home: Path,
) -> str:
    """Bind supervision authority to one exact managed root, never a display label."""

    resolved_skill_root = Path(skill_root).resolve(strict=True)
    if not resolved_skill_root.is_dir():
        raise RuntimeError(
            f"SkillGuard supervision target is not a directory: {resolved_skill_root}"
        )
    expected_roots = {
        "source": (REPO_ROOT / ".agents" / "skills" / skill_id).resolve(),
        "installed": (Path(codex_home) / "skills" / skill_id).resolve(),
    }
    matches = [
        authority
        for authority, expected_root in expected_roots.items()
        if resolved_skill_root == expected_root
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "SkillGuard supervision target must be exactly one current managed root; "
            f"skill_id={skill_id} actual={resolved_skill_root} "
            f"source={expected_roots['source']} installed={expected_roots['installed']}"
        )
    return matches[0]


def _execute_supervision(
    skill_id: str,
    skill_root: Path,
    codex_home: Path,
    surface_kind: str,
    *,
    native_receipt_path: Path | None = None,
    expected_native_run_id: str = "",
    expected_native_receipt_hash: str = "",
    expected_native_receipt_path: Path | None = None,
    update_finalization_receipt_path: Path | None = None,
    expected_update_finalization_receipt_hash: str = "",
    supervision_stage: str = "complete",
    expect_blocked: bool = False,
    scheduler_or_trigger_id: str = "",
    native_terminal_branch_id: str = "",
    scheduled_production_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    target_authority = _supervision_target_authority(
        skill_id,
        skill_root,
        codex_home,
    )
    installed_target = target_authority == "installed"
    validation_root = os.environ.get(
        "KHAOS_BRAIN_SKILLGUARD_VALIDATION_ROOT", ""
    ).strip()
    supervisor = (
        (Path(validation_root).resolve() if validation_root else codex_home / "skills" / "skillguard")
        / "scripts"
        / "skillguard_supervise.py"
    )
    if not supervisor.is_file():
        return {"ok": False, "error": "official current SkillGuard supervisor missing"}
    installed_supervisor = REPO_ROOT / "scripts" / "run_installed_skillguard_supervision.py"
    if installed_target and not installed_supervisor.is_file():
        return {
            "ok": False,
            "error": "current installed SkillGuard supervision adapter missing",
        }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_parent = (
        REPO_ROOT
        / ".local"
        / "sg"
        / _SUPERVISION_SURFACE_CODES.get(surface_kind, "other")
        / _SUPERVISION_SKILL_CODES.get(skill_id, skill_id[:12])
        / stamp
    )
    run_parent.mkdir(parents=True, exist_ok=True)
    packet_path = run_parent / "packet.json"
    target_root = run_parent / "target"
    generated_fixture = native_receipt_path is None
    if native_receipt_path is None:
        native_receipt_path = write_fixture_receipt(
            REPO_ROOT,
            skill_id,
            shallow=expect_blocked,
            run_id=(
                f"sg-{_SUPERVISION_SURFACE_CODES.get(surface_kind, 'other')}-"
                f"{_SUPERVISION_SKILL_CODES.get(skill_id, skill_id[:12])}-{stamp}"
            ),
        )
    resolved_receipt_path = Path(native_receipt_path).resolve()
    if (
        expected_native_receipt_path is not None
        and resolved_receipt_path != Path(expected_native_receipt_path).resolve()
    ):
        return {
            "ok": False,
            "error": "native receipt path changed before supervision",
            "expected_path": str(Path(expected_native_receipt_path).resolve()),
            "actual_path": str(resolved_receipt_path),
        }
    native_receipt = _load_json(resolved_receipt_path)
    observed_run_id = str(native_receipt.get("run_id") or "")
    observed_receipt_hash = str(native_receipt.get("receipt_hash") or "")
    native_run_id = expected_native_run_id or observed_run_id
    native_receipt_hash = expected_native_receipt_hash or observed_receipt_hash
    if observed_run_id != native_run_id or observed_receipt_hash != native_receipt_hash:
        return {
            "ok": False,
            "error": "native receipt identity changed before supervision",
            "expected_run_id": native_run_id,
            "actual_run_id": observed_run_id,
            "expected_receipt_hash": native_receipt_hash,
            "actual_receipt_hash": observed_receipt_hash,
        }
    scheduled_identity: dict[str, Any] | None = None
    supervision_session = getattr(
        scheduled_production_identity,
        "_supervision_session",
        None,
    )
    if supervision_session is not None and not isinstance(
        supervision_session,
        _InstalledSupervisionSession,
    ):
        raise RuntimeError("scheduled supervision session type is invalid")
    if not generated_fixture:
        current_identity = (
            dict(supervision_session.identity)
            if isinstance(
                supervision_session,
                _InstalledSupervisionSession,
            )
            else _build_current_scheduled_production_identity(
                codex_home,
                scheduler_or_trigger_id=(
                    scheduler_or_trigger_id
                    or str(
                        AUTOMATION_COMPLETION_CONTRACTS[skill_id][
                            "automation_id"
                        ]
                    )
                ),
                scheduled_execution_id=native_run_id,
            )
        )
        if (
            scheduled_production_identity is not None
            and dict(scheduled_production_identity) != current_identity
        ):
            raise RuntimeError(
                "scheduled-production identity changed between native start and SkillGuard supervision"
            )
        scheduled_identity = current_identity
    scope = _supervision_scope(skill_id, supervision_stage)
    if (
        generated_fixture
        and skill_id == "khaos-brain-update"
        and scope["stage"] == "finalization"
        and update_finalization_receipt_path is None
    ):
        fixture_states = {
            "kb-sleep": "ACTIVE",
            "kb-dream": "ACTIVE",
            "kb-org-contribute": "ACTIVE",
            "kb-org-maintenance": "ACTIVE",
            "khaos-brain-system-update": "ACTIVE",
        }
        fixture_user_paused = {key: False for key in fixture_states}
        fixture_plan_body = {
            "schema_version": "khaos-brain.automation-restoration-plan.v1",
            "states": fixture_states,
            "user_paused": fixture_user_paused,
            "source_states": {key: "PAUSED" for key in fixture_states},
            "source_user_paused": fixture_user_paused,
            "source_hashes": {
                key: content_hash(["fixture-source", key]) for key in fixture_states
            },
            "target_hashes": {
                key: content_hash(["fixture-target", key]) for key in fixture_states
            },
        }
        fixture_plan = {
            **fixture_plan_body,
            "ok": True,
            "issues": [],
            "plan_hash": content_hash(fixture_plan_body),
        }
        fixture_finalization = build_update_finalization_receipt(
            run_id=native_run_id,
            native_receipt_hash=native_receipt_hash,
            authorization_declared_check_receipt={
                "ok": True,
                "fixture": "authorization-declared-check-receipt",
                "validation": {
                    "non_terminal_authorization": True,
                    "overall_complete": False,
                    "closure_emitted": False,
                    "declared_checks_current": True,
                    "depth_receipt_id": "fixture-depth-receipt",
                    "depth_receipt_hash": "fixture-depth-receipt-hash",
                },
                "claim_boundary": "Calibration only.",
            },
            snapshot={
                "snapshot_hash": f"fixture-snapshot-{native_run_id}",
                "states": fixture_states,
                "user_paused": fixture_user_paused,
            },
            restoration_plan=fixture_plan,
            deferred_install_check={"ok": True, "fixture": "deferred-installed-state-current"},
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        update_finalization_receipt_path = write_native_receipt(
            run_parent / "update-finalization-receipt.json",
            fixture_finalization,
        )
        expected_update_finalization_receipt_hash = str(
            fixture_finalization.get("receipt_hash") or ""
        )
    finalization_validation: dict[str, Any] = {}
    finalization_receipt_hash = ""
    resolved_finalization_path: Path | None = None
    if update_finalization_receipt_path is not None:
        resolved_finalization_path = Path(update_finalization_receipt_path).resolve()
        finalization_validation = validate_update_finalization_receipt(
            resolved_finalization_path,
            expected_run_id=native_run_id,
            expected_native_receipt_hash=native_receipt_hash,
            expected_receipt_hash=expected_update_finalization_receipt_hash,
        )
        if finalization_validation.get("ok") is not True:
            return {
                "ok": False,
                "error": "update finalization receipt failed before SkillGuard supervision",
                "update_finalization_receipt_validation": finalization_validation,
            }
        finalization_receipt_hash = str(finalization_validation.get("receipt_hash") or "")
    target_root.mkdir(parents=True, exist_ok=True)
    target_input = {
        "schema_version": "khaos-brain.skillguard-supervision-input.v1",
        "skill_id": skill_id,
        "stage": str(scope["stage"]),
        "native_run_id": native_run_id,
        "native_receipt_hash": native_receipt_hash,
        "update_finalization_receipt_hash": finalization_receipt_hash,
    }
    (target_root / "automation-input.json").write_text(
        json.dumps(target_input, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(codex_home.resolve())
    environment["KHAOS_BRAIN_ASSURANCE_ACTIVE"] = "1"
    environment["KHAOS_BRAIN_AUTOMATION_RECEIPT"] = str(resolved_receipt_path)
    environment["KHAOS_BRAIN_AUTOMATION_RUN_ID"] = native_run_id
    environment["KHAOS_BRAIN_AUTOMATION_RECEIPT_HASH"] = native_receipt_hash
    if scheduled_identity is not None:
        environment["KHAOS_BRAIN_SCHEDULED_PRODUCTION_IDENTITY"] = json.dumps(
            scheduled_identity,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    else:
        environment.pop("KHAOS_BRAIN_SCHEDULED_PRODUCTION_IDENTITY", None)
    if generated_fixture:
        environment["KHAOS_BRAIN_ALLOW_AUTOMATION_FIXTURE"] = "1"
    else:
        environment.pop("KHAOS_BRAIN_ALLOW_AUTOMATION_FIXTURE", None)
    if resolved_finalization_path is not None:
        environment["KHAOS_BRAIN_UPDATE_FINALIZATION_RECEIPT"] = str(resolved_finalization_path)
        environment["KHAOS_BRAIN_UPDATE_FINALIZATION_RECEIPT_HASH"] = finalization_receipt_hash
    else:
        environment.pop("KHAOS_BRAIN_UPDATE_FINALIZATION_RECEIPT", None)
        environment.pop("KHAOS_BRAIN_UPDATE_FINALIZATION_RECEIPT_HASH", None)
    stable_request = (
        f"current {scope['stage']} scheduled automation supervision "
        f"skill_id={skill_id} scheduled_execution_id={native_run_id} "
        f"native_receipt_hash={native_receipt_hash} "
        f"update_finalization_receipt_hash={finalization_receipt_hash or 'none'}"
    )

    def run_packet(path: Path, packet_value: Mapping[str, Any]) -> dict[str, Any]:
        path.write_text(
            json.dumps(
                dict(packet_value),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        command = [
            sys.executable,
            str(
                installed_supervisor
                if installed_target
                else supervisor
            ),
            str(skill_root),
            str(path),
            "--target-root",
            str(target_root),
            "--repository-root",
            str(REPO_ROOT),
        ]
        if installed_target:
            command.extend(["--codex-home", str(codex_home)])
        if installed_target and isinstance(
            supervision_session,
            _InstalledSupervisionSession,
        ):
            return supervision_session.run_packet(
                path,
                target_root=target_root,
                environment=environment,
            )
        return _run_json(
            command,
            timeout=2400,
            environment=environment,
        )

    stage_payload: dict[str, Any] = {}
    stage_report: dict[str, Any] = {}
    terminal_result: dict[str, Any] = {}
    two_stage_validation: dict[str, Any] = {}
    if skill_id == "khaos-brain-update" and not generated_fixture:
        if native_terminal_branch_id not in {
            "no-update",
            "waiting-for-user",
            "ui-running",
            "prepared-update",
        }:
            raise RuntimeError(
                f"unsupported update native terminal branch: {native_terminal_branch_id}"
            )
        stage_packet = _supervision_packet(
            skill_id,
            stage=str(scope["stage"]),
            native_run_id=native_run_id,
            native_receipt_hash=native_receipt_hash,
            native_receipt_path=resolved_receipt_path,
            finalization_receipt_hash=finalization_receipt_hash,
            finalization_receipt_path=resolved_finalization_path,
            supervision_mode="stage_depth",
            scheduled_production_identity=scheduled_identity,
            request_text=stable_request,
        )
        stage_path = run_parent / "packet-stage-depth.json"
        stage_payload = run_packet(stage_path, stage_packet)
        stage_report = (
            dict(stage_payload.get("report", {}))
            if isinstance(stage_payload.get("report"), Mapping)
            else {}
        )
        stage_depth = (
            dict(stage_report.get("target_execution_depth_receipt", {}))
            if isinstance(stage_report.get("target_execution_depth_receipt"), Mapping)
            else {}
        )
        if not (
            stage_payload.get("ok") is True
            and stage_payload.get("exit_code") == 0
            and stage_report.get("status") == "staged"
            and stage_report.get("supervision_mode") == "stage_depth"
            and not stage_report.get("closures")
            and stage_depth.get("status") == "EXECUTION_DEPTH_PASS"
        ):
            raise RuntimeError(
                "SkillGuard stage_depth did not produce one non-terminal EXECUTION_DEPTH_PASS"
            )
        if str(scope["stage"]) == "authorization":
            declared_results = [
                row
                for row in stage_depth.get("declared_check_results", [])
                if isinstance(row, Mapping)
            ]
            authorization_native_validation = validate_native_receipt(
                resolved_receipt_path,
                skill_id=skill_id,
                phase="all",
                expected_run_id=native_run_id,
                expected_receipt_hash=native_receipt_hash,
                allow_fixture=False,
            )
            authorization_ok = bool(
                authorization_native_validation.get("ok") is True
                and declared_results
                and not stage_depth.get("unresolved_check_ids")
                and all(
                    row.get("disposition") == "passed"
                    and row.get("current") is True
                    for row in declared_results
                )
                and isinstance(stage_depth.get("provider_runtime_audit"), Mapping)
                and stage_depth["provider_runtime_audit"].get("status") == "passed"
            )
            return {
                "ok": authorization_ok,
                "status": (
                    "declared-check-authorization-staged"
                    if authorization_ok
                    else "declared-check-authorization-blocked"
                ),
                "surface": surface_kind,
                "target_authority": target_authority,
                "skill_root": str(skill_root),
                "packet_path": str(stage_path),
                "target_root": str(target_root),
                "native_receipt_path": str(resolved_receipt_path),
                "native_receipt_validation": authorization_native_validation,
                "validation": {
                    "profile": "enforced",
                    "stage": "authorization",
                    "non_terminal_authorization": True,
                    "overall_complete": False,
                    "closure_emitted": False,
                    "declared_checks_current": authorization_ok,
                    "depth_status": stage_depth.get("status"),
                    "depth_receipt_id": str(stage_depth.get("receipt_id") or ""),
                    "depth_receipt_hash": str(stage_depth.get("receipt_hash") or ""),
                    "scheduled_production_identity": scheduled_identity or {},
                },
                "stage_depth": stage_payload,
                "target_native_terminal": {},
                "supervisor": stage_payload,
            }
        stage_run_root = Path(str(stage_report.get("run_root") or "")).resolve()
        try:
            stage_run_root.relative_to(
                (target_root / ".skillguard" / "runs").resolve()
            )
        except ValueError as exc:
            raise RuntimeError("SkillGuard staged run root escaped the current target") from exc
        terminal_result = _build_and_write_target_native_terminal(
            codex_home,
            run_root=stage_run_root,
            profile=str(scope["profile"]),
            branch_id=native_terminal_branch_id,
            native_receipt_path=resolved_receipt_path,
            native_receipt_hash=native_receipt_hash,
            finalization_receipt_hash=finalization_receipt_hash,
            stage=str(scope["stage"]),
            supervision_session=(
                supervision_session
                if isinstance(
                    supervision_session,
                    _InstalledSupervisionSession,
                )
                else None
            ),
        )
        packet = _supervision_packet(
            skill_id,
            stage=str(scope["stage"]),
            native_run_id=native_run_id,
            native_receipt_hash=native_receipt_hash,
            native_receipt_path=resolved_receipt_path,
            finalization_receipt_hash=finalization_receipt_hash,
            finalization_receipt_path=resolved_finalization_path,
            supervision_mode="close",
            scheduled_production_identity=scheduled_identity,
            request_text=stable_request,
            native_terminal_receipt_ref=terminal_result["receipt_ref"],
            expected_native_route_id="route:khaos-brain-update:authorize",
            expected_native_branch_id=native_terminal_branch_id,
        )
        packet_path = run_parent / "packet-close.json"
        payload = run_packet(packet_path, packet)
        close_report = (
            dict(payload.get("report", {}))
            if isinstance(payload.get("report"), Mapping)
            else {}
        )
        close_depth = (
            dict(close_report.get("target_execution_depth_receipt", {}))
            if isinstance(close_report.get("target_execution_depth_receipt"), Mapping)
            else {}
        )
        close_closure_rows = [
            row
            for row in close_report.get("closures", [])
            if isinstance(row, Mapping)
            and row.get("profile") == str(scope["profile"])
        ]
        close_closure_record = (
            _load_json(
                stage_run_root
                / "closures"
                / f"{close_closure_rows[0].get('closure_receipt_id', '')}.json"
            )
            if len(close_closure_rows) == 1
            else {}
        )
        terminal_receipt = terminal_result["receipt"]
        two_stage_validation = {
            "same_run_id": close_report.get("run_id") == stage_report.get("run_id"),
            "same_run_root": close_report.get("run_root") == stage_report.get("run_root"),
            "exact_depth_receipt_reused": bool(
                stage_depth.get("receipt_id")
                and stage_depth.get("receipt_id") == close_depth.get("receipt_id")
                and stage_depth.get("receipt_hash") == close_depth.get("receipt_hash")
            ),
            "close_did_not_rerun_target_steps": not close_report.get("executed_steps"),
            "terminal_bound_exact_depth": bool(
                terminal_receipt.get("depth_receipt_id") == stage_depth.get("receipt_id")
                and terminal_receipt.get("depth_receipt_hash") == stage_depth.get("receipt_hash")
            ),
            "close_consumed_staged_depth": bool(
                stage_depth.get("receipt_id")
                and stage_depth.get("receipt_id")
                in {
                    str(item)
                    for item in close_closure_record.get("consumed_receipt_ids", [])
                }
            ),
        }
        if not all(two_stage_validation.values()):
            raise RuntimeError(
                "SkillGuard close did not resume the exact staged run/depth without rerunning target checks"
            )
    else:
        packet = _supervision_packet(
            skill_id,
            stage=str(scope["stage"]),
            native_run_id=native_run_id,
            native_receipt_hash=native_receipt_hash,
            native_receipt_path=resolved_receipt_path,
            finalization_receipt_hash=finalization_receipt_hash,
            finalization_receipt_path=resolved_finalization_path,
            scheduled_production_identity=scheduled_identity,
            request_text=stable_request,
        )
        payload = run_packet(packet_path, packet)
    native_validation = validate_native_receipt(
        resolved_receipt_path,
        skill_id=skill_id,
        phase="all",
        expected_run_id=native_run_id,
        expected_receipt_hash=native_receipt_hash,
        allow_fixture=generated_fixture,
    )
    if expect_blocked:
        native_issues = [str(item) for item in native_validation.get("issues", [])]
        supervisor_error = str(payload.get("error") or "")
        expected_native_failure = (
            "native-terminal-not-successful" in native_issues
            and any(item.startswith("phase-obligations-failed:") for item in native_issues)
            and not any(
                marker in item
                for item in native_issues
                for marker in (
                    "hash-mismatch",
                    "not-current",
                    "run-id-mismatch",
                    "command-",
                    "schema-mismatch",
                )
            )
        )
        expected_supervisor_failure = (
            supervisor_error.startswith("step_check_failed:")
            and skill_id in supervisor_error
            and f"check:{skill_id}:" in supervisor_error
        )
        blocked = (
            native_validation.get("ok") is not True
            and payload.get("ok") is not True
            and payload.get("exit_code") != 0
            and expected_native_failure
            and expected_supervisor_failure
        )
        return {
            "ok": blocked,
            "surface": surface_kind,
            "target_authority": target_authority,
            "skill_root": str(skill_root),
            "native_receipt_path": str(resolved_receipt_path),
            "native_receipt_validation": native_validation,
            "expected_native_shallow_failure": expected_native_failure,
            "expected_supervisor_shallow_failure": expected_supervisor_failure,
            "packet_path": str(packet_path),
            "target_root": str(target_root),
            "observed_status": "shallow-blocked" if blocked else "calibration-miss",
            "supervisor": payload,
        }
    report = payload.get("report", {}) if isinstance(payload.get("report"), dict) else {}
    evidence_report = stage_report or report
    depth = (
        report.get("target_execution_depth_receipt", {})
        if isinstance(report.get("target_execution_depth_receipt"), dict)
        else {}
    )
    expected_profile = str(scope["profile"])
    closures = [
        row
        for row in report.get("closures", [])
        if isinstance(row, dict) and row.get("profile") == expected_profile
    ]
    declared_check_results = [
        row
        for row in depth.get("declared_check_results", [])
        if isinstance(row, dict)
    ]
    expected_ids = {
        f"obligation:{skill_id}:{row['suffix']}"
        for row in AUTOMATION_COMPLETION_CONTRACTS[skill_id]["obligations"]
    }
    check_records = []
    for row in evidence_report.get("executed_steps", []):
        if not isinstance(row, dict):
            continue
        for record_id in row.get("check_record_ids", []):
            record_path = Path(str(report.get("run_root") or "")) / "checks" / f"{record_id}.json"
            record = _load_json(record_path)
            if record:
                check_records.append(record)
    actual_check_ids = [str(row.get("check_id") or "") for row in check_records]
    check_counts = Counter(actual_check_ids)
    frozen_control = (
        payload.get("installed_control_projection", {})
        if isinstance(payload.get("installed_control_projection"), Mapping)
        else {}
    )
    frozen_control_root = str(frozen_control.get("projection_root") or "")
    compiled_skill_root = (
        Path(frozen_control_root).resolve(strict=True)
        if installed_target
        and isinstance(
            supervision_session,
            _InstalledSupervisionSession,
        )
        and frozen_control_root
        else skill_root
    )
    compiled_contract = _load_json(
        compiled_skill_root / ".skillguard" / "compiled-contract.json"
    )
    selected_route_ids = set(str(item) for item in scope["route_ids"])
    selected_steps = [
        row
        for row in compiled_contract.get("steps", [])
        if isinstance(row, dict)
        and str(row.get("route_id") or "") in selected_route_ids
        and not str(row.get("terminal_kind") or "")
    ]
    expected_check_ids = {
        str(item)
        for row in selected_steps
        for item in (
            row.get("binding", {}).get("check_ids", [])
            if isinstance(row.get("binding"), dict)
            else []
        )
    }
    expected_artifact_ids = {
        str(item)
        for row in selected_steps
        for item in (
            row.get("binding", {}).get("output_artifact_ids", [])
            if isinstance(row.get("binding"), dict)
            else []
        )
    }
    run_root = Path(str(report.get("run_root") or ""))
    artifact_records = [
        _load_json(path)
        for path in sorted((run_root / "artifacts").glob("artifact-record-*.json"))
    ] if run_root else []
    actual_artifact_ids = {
        str(row.get("artifact_id") or "")
        for row in artifact_records
        if row
    }
    artifact_records_current = bool(
        actual_artifact_ids == expected_artifact_ids
        and len(artifact_records) == len(expected_artifact_ids)
        and all(
            row.get("status") == "passed"
            and bool(str(row.get("fingerprint") or ""))
            and bool(str(row.get("witness_fingerprint") or ""))
            for row in artifact_records
        )
    )
    packet_witness_hashes = {
        str(artifact_id): str(
            witness.get("output", {}).get("receipt_hash", "")
            if isinstance(witness.get("output"), dict)
            else ""
        )
        for raw_step in packet.get("steps", {}).values()
        if isinstance(raw_step, dict)
        for artifact_id, witness in raw_step.get("artifact_witnesses", {}).items()
        if isinstance(witness, dict)
    }
    expected_witness_hashes = {
        f"artifact:{skill_id}:native-receipt": native_receipt_hash,
    }
    if scope["stage"] == "finalization":
        expected_witness_hashes[
            "artifact:khaos-brain-update:finalization-receipt"
        ] = finalization_receipt_hash
    packet_artifacts_bound_to_exact_receipts = (
        packet_witness_hashes == expected_witness_hashes
    )
    closure_record = {}
    if closures:
        closure_record = _load_json(
            Path(str(report.get("run_root") or ""))
            / "closures"
            / f"{closures[0].get('closure_receipt_id', '')}.json"
        )
    native_obligation_source = "native-receipt"
    native_target_values = native_validation.get("selected_obligation_ids", [])
    if skill_id == "khaos-brain-update" and not generated_fixture:
        native_obligation_source = "target-native-terminal"
        native_target_values = terminal_result.get("receipt", {}).get(
            "target_obligation_ids", []
        )
    native_target_ids = {
        str(item)
        for item in native_target_values
        if str(item)
    }
    depth_uncovered_ids = {
        str(item)
        for item in depth.get("uncovered_obligation_ids", [])
        if str(item)
    }
    depth_calibration_id = f"obligation:{skill_id}:depth-calibration"
    expected_applicable_ids = set(expected_ids)
    if skill_id == "khaos-brain-update" and str(scope["stage"]) == "no-op":
        expected_applicable_ids.discard(
            "obligation:khaos-brain-update:staged-restoration-authorization"
        )
    applicable_ids = set(native_target_ids)
    if depth.get("status") == "EXECUTION_DEPTH_PASS":
        applicable_ids.add(depth_calibration_id)
    unknown_native_ids = native_target_ids - expected_ids
    complete_obligation_set = bool(
        native_validation.get("ok") is True
        and native_target_ids
        and depth_calibration_id in expected_ids
        and not unknown_native_ids
        and depth.get("status") == "EXECUTION_DEPTH_PASS"
        and not depth_uncovered_ids
        and applicable_ids == expected_applicable_ids
    )
    closed_ids = (
        applicable_ids - depth_uncovered_ids
        if depth.get("status") == "EXECUTION_DEPTH_PASS"
        else set()
    )
    depth_profile = (
        compiled_contract.get("depth_profile", {})
        if isinstance(compiled_contract.get("depth_profile"), dict)
        else {}
    )
    depth_required = expected_profile in {
        str(item) for item in depth_profile.get("required_closure_profiles", [])
    }
    depth_consumed = str(depth.get("receipt_id") or "") in {
        str(item) for item in closure_record.get("consumed_receipt_ids", [])
    }
    closure_verified = bool(
        closures
        and closures[0].get("verification", {}).get("ok") is True
        and closure_record.get("status") == "closed"
        and closure_record.get("profile") == expected_profile
        and (depth_consumed if depth_required else True)
    )
    validation = {
        "supervisor_passed": payload.get("ok") is True
        and payload.get("exit_code") == 0
        and report.get("status") == "passed",
        "depth_status": depth.get("status"),
        "depth_required": depth_required,
        "depth_passed": (
            depth.get("status") == "EXECUTION_DEPTH_PASS" if depth_required else None
        ),
        "native_receipt_valid": native_validation.get("ok") is True,
        "profile": expected_profile,
        "stage": str(scope["stage"]),
        "selected_route_ids": sorted(selected_route_ids),
        "requested_profile_closure_verified": closure_verified,
        "closure_consumed_depth_receipt_id": str(depth.get("receipt_id") or "")
        if closure_verified and depth_consumed
        else "",
        "contract_obligations": sorted(expected_ids),
        "expected_obligations": sorted(expected_applicable_ids),
        "nonapplicable_obligations": sorted(expected_ids - expected_applicable_ids),
        "applicable_obligations": sorted(applicable_ids),
        "native_obligation_source": native_obligation_source,
        "native_target_obligations": sorted(native_target_ids),
        "unknown_native_obligations": sorted(unknown_native_ids),
        "closed_obligations": sorted(closed_ids),
        "complete_obligation_set": complete_obligation_set,
        "declared_check_receipts_current": (
            {str(row.get("check_id") or "") for row in declared_check_results}
            == set(depth_profile.get("native_check_ids", []))
            and not depth.get("unresolved_check_ids")
            and all(
                row.get("disposition") == "passed"
                and row.get("current") is True
                for row in declared_check_results
            )
        ),
        "expected_check_ids": sorted(expected_check_ids),
        "actual_check_ids": sorted(actual_check_ids),
        "check_id_counts": dict(sorted(check_counts.items())),
        "all_declared_checks_executed_exactly_once": (
            set(actual_check_ids) == expected_check_ids
            and all(check_counts[item] == 1 for item in expected_check_ids)
        ),
        "expected_artifact_ids": sorted(expected_artifact_ids),
        "actual_artifact_ids": sorted(actual_artifact_ids),
        "artifact_records_current": artifact_records_current,
        "packet_artifacts_bound_to_exact_receipts": packet_artifacts_bound_to_exact_receipts,
        "update_finalization_receipt_valid": (
            finalization_validation.get("ok") is True
            if resolved_finalization_path is not None
            else None
        ),
        "scheduled_production_identity": scheduled_identity or {},
        "scheduled_production_identity_exact_six_fields": (
            set(scheduled_identity or {})
            == set(_SCHEDULED_PRODUCTION_IDENTITY_FIELDS)
            if not generated_fixture
            else None
        ),
        "two_stage_terminal": two_stage_validation,
    }
    ok = all(
        (
            validation["supervisor_passed"],
            validation["depth_passed"] is True if depth_required else True,
            validation["native_receipt_valid"],
            validation["requested_profile_closure_verified"],
            validation["complete_obligation_set"],
            validation["declared_check_receipts_current"],
            validation["all_declared_checks_executed_exactly_once"],
            validation["artifact_records_current"],
            validation["packet_artifacts_bound_to_exact_receipts"],
            (
                validation["scheduled_production_identity_exact_six_fields"] is True
                if not generated_fixture
                else True
            ),
            (all(two_stage_validation.values()) if two_stage_validation else True),
            (
                validation["update_finalization_receipt_valid"] is True
                if resolved_finalization_path is not None
                else True
            ),
        )
    )
    return {
        "ok": ok,
        "surface": surface_kind,
        "target_authority": target_authority,
        "skill_root": str(skill_root),
        "packet_path": str(packet_path),
        "target_root": str(target_root),
        "native_receipt_path": str(resolved_receipt_path),
        "native_receipt_validation": native_validation,
        "update_finalization_receipt_path": str(resolved_finalization_path or ""),
        "update_finalization_receipt_validation": finalization_validation,
        "validation": validation,
        "stage_depth": stage_payload,
        "target_native_terminal": terminal_result,
        "supervisor": payload,
    }


def _run_capability_regression(
    skill_id: str,
    *,
    capability_receipt_path: Path | None,
) -> dict[str, Any]:
    try:
        marker_nodes = evidence_test_node_ids(skill_id, repo_root=REPO_ROOT)
    except (KeyError, ValueError) as exc:
        return {
            "ok": False,
            "skill_id": skill_id,
            "error": f"declared evidence test resolution failed: {exc}",
            "claim_boundary": "No capability claim is allowed without exact collectable evidence nodes.",
        }
    node_ids = sorted(set(marker_nodes.values()))
    if capability_receipt_path is None:
        return {
            "ok": False,
            "skill_id": skill_id,
            "error": "current full-regression capability receipt is required",
            "declared_evidence_markers": marker_nodes,
            "requested_node_ids": node_ids,
            "claim_boundary": (
                "Capability checks consume a current owner-issued full-regression receipt; "
                "this consumer never starts pytest implicitly."
            ),
        }
    receipt_path = Path(capability_receipt_path).resolve()
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "skill_id": skill_id,
            "error": f"capability receipt unreadable: {type(exc).__name__}",
            "receipt_path": str(receipt_path),
        }
    if not isinstance(receipt, dict):
        return {"ok": False, "skill_id": skill_id, "error": "capability receipt is not an object"}
    proof = receipt.get("proof_artifact_ref") if isinstance(receipt.get("proof_artifact_ref"), dict) else {}
    proof_path = Path(str(proof.get("path") or "")).resolve() if proof.get("path") else Path()
    proof_current = bool(
        proof_path.is_file()
        and hashlib.sha256(proof_path.read_bytes()).hexdigest()
        == str(proof.get("sha256") or "")
    )
    from scripts import check_chaos_brain_readiness as readiness

    source = readiness._source_snapshot(REPO_ROOT)
    verifier = readiness._verifier_fingerprint()
    environment_contract = readiness._environment_contract(REPO_ROOT)
    command = [str(item) for item in receipt.get("command", [])]
    expected_identity = readiness._command_identity(
        command,
        source_digest=str(source["digest"]),
        verifier_digest=str(verifier["digest"]),
        environment_contract=environment_contract,
    )
    identity_current = bool(
        receipt.get("identity_fingerprint") == expected_identity
        and receipt.get("receipt_id")
        == f"validation:full_regression:{expected_identity}"
        and receipt.get("input_fingerprints")
        == {"source": source["digest"], "verifier": verifier["digest"]}
    )
    junit = receipt.get("junit") if isinstance(receipt.get("junit"), dict) else {}
    observed_junit = (
        readiness._junit_summary(proof_path, REPO_ROOT) if proof_path.is_file() else {}
    )
    junit_current = bool(junit and observed_junit == junit)
    passed_nodes = {str(item) for item in junit.get("passed_node_ids", [])}
    unsafe_nodes = {
        str(item)
        for key in ("skipped_node_ids", "failed_node_ids", "errored_node_ids")
        for item in junit.get(key, [])
    }

    def covered(node_id: str) -> bool:
        return any(item == node_id or item.startswith(node_id + "[") for item in passed_nodes)

    missing_nodes = [node_id for node_id in node_ids if not covered(node_id)]
    unsafe_declared_nodes = [
        node_id
        for node_id in node_ids
        if any(item == node_id or item.startswith(node_id + "[") for item in unsafe_nodes)
    ]
    exact_nodes_executed = bool(node_ids and not missing_nodes and not unsafe_declared_nodes)
    receipt_terminal = bool(
        receipt.get("schema_version") == "khaos-brain.validation-evidence.v1"
        and receipt.get("name") == "full_regression"
        and receipt.get("terminal_status") == "passed"
        and receipt.get("ok") is True
        and receipt.get("timed_out") is False
        and receipt.get("exit_code") == 0
    )
    return {
        "ok": (
            receipt_terminal
            and identity_current
            and proof_current
            and junit_current
            and exact_nodes_executed
        ),
        "execution": "consumed",
        "receipt_path": str(receipt_path),
        "consumed_receipt_id": str(receipt.get("receipt_id") or ""),
        "receipt_terminal": receipt_terminal,
        "identity_current": identity_current,
        "proof_current": proof_current,
        "junit_current": junit_current,
        "declared_evidence_markers": marker_nodes,
        "requested_node_ids": node_ids,
        "requested_node_count": len(node_ids),
        "missing_node_ids": missing_nodes,
        "unsafe_declared_node_ids": unsafe_declared_nodes,
        "exact_declared_nodes_executed_without_skip": exact_nodes_executed,
        "claim_boundary": (
            "Exact declared version-capability nodes were consumed from one current owner-issued "
            "full-regression receipt without starting pytest again; this is not scheduled-production evidence."
        ),
    }


def _execute_skill_assurance(
    skill_id: str,
    skill_root: Path,
    codex_home: Path,
    surface_kind: str,
    *,
    capability_receipt_path: Path | None,
) -> dict[str, Any]:
    capability = _run_capability_regression(
        skill_id,
        capability_receipt_path=capability_receipt_path,
    )
    if surface_kind == "source":
        return {
            "ok": capability.get("ok") is True,
            "capability_regression": capability,
            "scheduled_production_supervision": {
                "status": "not_applicable",
                "reason": "source-only capability evidence cannot close a scheduled run",
            },
            "claim_boundary": (
                "Source-only assurance proves current compile/depth shape and exact capability JUnit nodes only. "
                "It neither creates a fixture production receipt nor requests a scheduled-production closure."
            ),
        }
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_kb_guarded_automation.py"),
        "--skill",
        skill_id,
        "--repo-root",
        str(REPO_ROOT),
        "--codex-home",
        str(codex_home),
        "--scheduler-or-trigger-id",
        "chaos-brain-aggregate-readiness",
        "--json",
    ]
    environment = os.environ.copy()
    environment["KHAOS_BRAIN_ASSURANCE_ACTIVE"] = "1"
    environment["KHAOS_BRAIN_AUTOMATION_TRIGGER_ID"] = (
        "chaos-brain-aggregate-readiness"
    )
    production = _run_json(
        command,
        timeout=(
            UPDATE_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS
            if skill_id == "khaos-brain-update"
            else STANDARD_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS
        ),
        environment=environment,
    )
    production_ok = bool(
        production.get("ok") is True
        and production.get("exit_code") == 0
        and production.get("skill_id") == skill_id
        and str(production.get("guarded_result_path") or "")
    )
    return {
        "ok": capability.get("ok") is True
        and production_ok,
        "capability_regression": capability,
        "scheduled_production": production,
        "scheduled_production_command": command,
        "claim_boundary": (
            "Reused capability regression plus one real installed guarded automation execution. "
            "Positive/shallow target calibration is consumed inside that run's execution-depth receipt; "
            "no fixture is allowed to stand in for scheduled production."
        ),
    }


def _report_claim_boundary(*, source_only: bool, execute_checks: bool) -> str:
    if source_only and execute_checks:
        return (
            "Current source compiler/depth results and target-specific completion surfaces, plus exact "
            "capability JUnit consumed without starting pytest again. This mode does not compare installed trees, "
            "run scheduled production, or replace migration receipts."
        )
    if source_only:
        return (
            "Current source compiler/depth results and target-specific completion surfaces only. "
            "No installed-tree parity, capability execution, scheduled production, or migration claim is made."
        )
    if execute_checks:
        return (
            "Current canonical source compile, official installed-projection parity, target-specific completion, and complete tree-parity results, "
            "plus exact capability JUnit reuse and one real guarded execution for each installed automation. "
            "Each installed execution requires official target-owned declared-check supervision and the sole current enforced "
            "EXECUTION_DEPTH_PASS; this does not certify future runs or replace migration receipts."
        )
    return (
        "Current canonical source compile, official installed-projection parity, target-specific completion, and complete tree-parity results only. "
        "No capability execution, scheduled-production completion, future-run, or migration claim is made."
    )


def _check_record(check_id: str, ok: bool, details: Any) -> dict[str, Any]:
    return {"id": check_id, "ok": bool(ok), "details": details}


def build_report(
    *,
    codex_home: Path,
    source_only: bool,
    registry_path: Path | None,
    execute_checks: bool = False,
    capability_receipt_path: Path | None = None,
) -> dict[str, Any]:
    codex_home = Path(codex_home).resolve()
    validation_root = os.environ.get(
        "KHAOS_BRAIN_SKILLGUARD_VALIDATION_ROOT", ""
    ).strip()
    skillguard_root = (
        Path(validation_root).resolve()
        if validation_root
        else codex_home / "skills" / "skillguard"
    )
    compiler = skillguard_root / "scripts" / "skillguard_compile.py"
    cli = skillguard_root / "scripts" / "skillguard.py"
    supervisor = skillguard_root / "scripts" / "skillguard_supervise.py"
    checks: list[dict[str, Any]] = []
    checks.append(_check_record("skillguard_v2_compiler_present", compiler.is_file(), str(compiler)))
    if execute_checks:
        checks.append(_check_record("skillguard_v2_supervisor_present", supervisor.is_file(), str(supervisor)))
    skill_reports: dict[str, Any] = {}
    execution_targets: list[tuple[str, Path, str]] = []
    for skill_id in MAINTENANCE_SKILL_NAMES:
        source = REPO_ROOT / ".agents" / "skills" / skill_id
        installed = codex_home / "skills" / skill_id
        source_files = {relative: (source / relative).is_file() for relative in V2_FILES}
        source_compile = (
            _run_json(
                [
                    sys.executable,
                    str(compiler),
                    str(source),
                    "--repository-root",
                    str(REPO_ROOT),
                    "--check",
                ]
            )
            if compiler.is_file()
            else {"ok": False, "error": "compiler missing", "exit_code": 1}
        )
        record: dict[str, Any] = {
            "source": str(source),
            "source_v2_files": source_files,
            "source_compile": source_compile,
        }
        source_completion_findings = _closure_findings(
            skill_id, _skill_surface(source, skill_id)
        )
        record["source_completion_findings"] = source_completion_findings
        source_ok = (
            all(source_files.values())
            and source_compile.get("ok") is True
            and source_compile.get("exit_code") == 0
            and not source_completion_findings
        )
        checks.append(_check_record(f"source_v2:{skill_id}", source_ok, record))
        if not source_only:
            installed_files = {relative: (installed / relative).is_file() for relative in V2_FILES}
            installed_projection = (
                _installed_projection_parity(
                    codex_home,
                    skill_id=skill_id,
                    source_skill_root=source,
                    installed_skill_root=installed,
                )
                if compiler.is_file() and installed.exists()
                else {
                    "ok": False,
                    "status": "blocked",
                    "blockers": ["installed_target_missing"],
                }
            )
            source_manifest = tree_manifest(source)
            installed_manifest = tree_manifest(installed)
            parity = source_manifest["digest"] == installed_manifest["digest"]
            installed_compile = {
                "artifact_type": "skillguard_v2_installed_currentness_projection",
                "status": (
                    "current"
                    if source_compile.get("ok") is True
                    and source_compile.get("exit_code") == 0
                    and installed_projection.get("ok") is True
                    and parity
                    else "blocked"
                ),
                "ok": bool(
                    source_compile.get("ok") is True
                    and source_compile.get("exit_code") == 0
                    and installed_projection.get("ok") is True
                    and parity
                ),
                "exit_code": (
                    0
                    if source_compile.get("ok") is True
                    and source_compile.get("exit_code") == 0
                    and installed_projection.get("ok") is True
                    and parity
                    else 1
                ),
                "contract_hash": source_compile.get("contract_hash", ""),
                "installed_parity_receipt_id": (
                    installed_projection.get("receipt", {}).get("receipt_id", "")
                ),
                "claim_boundary": (
                    "Current canonical repository compile plus official installed-content "
                    "projection parity; the installed directory is not treated as a second "
                    "repository or asked to own repository-only FlowGuard models."
                ),
            }
            installed_completion_findings = _closure_findings(
                skill_id, _skill_surface(installed, skill_id)
            )
            record.update(
                {
                    "installed": str(installed),
                    "installed_v2_files": installed_files,
                    "installed_compile": installed_compile,
                    "installed_projection_parity": installed_projection,
                    "source_manifest": source_manifest,
                    "installed_manifest": installed_manifest,
                    "whole_tree_parity": parity,
                    "installed_completion_findings": installed_completion_findings,
                }
            )
            installed_ok = (
                all(installed_files.values())
                and installed_compile.get("ok") is True
                and installed_compile.get("exit_code") == 0
                and installed_projection.get("ok") is True
                and parity
                and not installed_completion_findings
            )
            checks.append(_check_record(f"installed_v2_parity:{skill_id}", installed_ok, record))
        if execute_checks:
            execution_targets.append(
                (skill_id, source, "source" if source_only else "installed")
            )
        skill_reports[skill_id] = record

    if execute_checks:
        def execute_target(row: tuple[str, Path, str]) -> tuple[str, dict[str, Any]]:
            return (
                row[0],
                _execute_skill_assurance(
                    row[0],
                    row[1],
                    codex_home,
                    row[2],
                    capability_receipt_path=capability_receipt_path,
                ),
            )

        if source_only:
            with ThreadPoolExecutor(max_workers=4) as executor:
                execution_rows = list(executor.map(execute_target, execution_targets))
        else:
            # These are real maintenance runs, not model regressions.  Keep
            # their target-owned locks and side effects ordered; in particular
            # Sleep and Dream must never race each other for the shared lane.
            execution_rows = [execute_target(row) for row in execution_targets]
        for skill_id, execution in execution_rows:
            skill_reports[skill_id]["executed_supervision"] = execution
            checks.append(
                _check_record(
                    (
                        f"executed_capability:{skill_id}"
                        if source_only
                        else f"executed_scheduled_production:{skill_id}"
                    ),
                    execution.get("ok") is True,
                    execution,
                )
            )

    project_adoption = (
        _run_json(
            [
                sys.executable,
                str(cli),
                "project-audit",
                "--root",
                str(REPO_ROOT),
            ]
        )
        if cli.is_file() and (REPO_ROOT / ".skillguard" / "project.json").is_file()
        else {"ok": False, "error": "SkillGuard project adoption manifest or CLI missing", "exit_code": 1}
    )
    project_adoption_ok = (
        project_adoption.get("ok") is True
        and project_adoption.get("status") == "pass"
        and project_adoption.get("exit_code") == 0
    )
    checks.append(
        _check_record(
            "skillguard_project_adoption_current",
            project_adoption_ok,
            project_adoption,
        )
    )

    router: dict[str, Any] = {}
    if not source_only:
        registry = Path(registry_path) if registry_path else discover_active_registry(codex_home)
        if cli.is_file() and registry.is_file():
            router["registry"] = _run_json(
                [
                    sys.executable,
                    str(cli),
                    "check-global-registry",
                    "--registry",
                    str(registry),
                    "--codex-home",
                    str(codex_home),
                    "--output",
                    "-",
                ]
            )
            router["prompt"] = _run_json(
                [
                    sys.executable,
                    str(cli),
                    "check-global-prompt",
                    "--registry",
                    str(registry),
                    "--codex-home",
                    str(codex_home),
                    "--output",
                    "-",
                ]
            )
        else:
            router = {
                "registry": {"ok": False, "error": f"missing registry or CLI: {registry}"},
                "prompt": {"ok": False, "error": f"missing registry or CLI: {registry}"},
            }
        router_ok = all(
            value.get("decision") == "pass" and value.get("exit_code", 0) == 0
            for value in router.values()
        )
        checks.append(_check_record("global_router_current", router_ok, router))

    return {
        "schema_version": 1,
        "check": "kb-skillguard-v2-parity",
        "source_only": source_only,
        "execute_checks": execute_checks,
        "ok": all(item["ok"] for item in checks),
        "skills": skill_reports,
        "project_adoption": project_adoption,
        "router": router,
        "checks": checks,
        "claim_boundary": _report_claim_boundary(
            source_only=source_only,
            execute_checks=execute_checks,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--execute-checks", action="store_true")
    parser.add_argument("--capability-receipt", type=Path)
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--registry", type=Path)
    args = parser.parse_args()
    report = build_report(
        codex_home=args.codex_home,
        source_only=args.source_only,
        registry_path=args.registry,
        execute_checks=args.execute_checks,
        capability_receipt_path=args.capability_receipt,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for item in report["checks"]:
            print(("PASS" if item["ok"] else "FAIL"), item["id"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
