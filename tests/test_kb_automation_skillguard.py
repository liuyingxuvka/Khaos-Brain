from __future__ import annotations

import json
import hashlib
import importlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from local_kb.automation_contracts import (
    AUTOMATION_COMPLETION_CONTRACTS,
    SKILLGUARD_COMPLETION_MARKER,
    SKILLGUARD_PARTIAL_MARKER,
    check_id,
    evidence_test_node_ids,
    expected_obligation_ids,
    obligation_id,
)
from local_kb.install import REPO_AUTOMATION_SPECS
from local_kb.automation_runtime import (
    build_native_receipt,
    build_fixture_payload,
    evaluate_native_payload,
    validate_native_receipt,
    write_native_receipt,
)
from scripts.build_kb_automation_skillguard_contracts import build_contract_source
from scripts.check_kb_automation_skillguard_depth import build_report
from scripts.check_kb_skillguard import (
    _InstalledSupervisionSession,
    _SUPERVISION_DYNAMIC_ENV_KEYS,
    _ScheduledProductionIdentity,
    _build_and_write_target_native_terminal,
    _build_current_scheduled_production_identity,
    _execute_supervision,
    _execute_skill_assurance,
    _installed_projection_parity,
    _native_output_witness,
    _project_adoption_audit,
    _report_claim_boundary,
    _run_capability_regression,
    _supervision_packet,
    _supervision_target_authority,
)
from scripts import check_chaos_brain_readiness as readiness
from scripts import run_installed_skillguard_supervision as supervision_worker
from scripts.run_kb_guarded_automation import run_guarded_automation
from scripts.run_installed_skillguard_supervision import (
    _active_skillguard_router_root,
    _materialize_installed_control_projection,
    _materialize_skillguard_runtime_projection,
    _prevent_runtime_projection_bytecode_mutation,
    _supervision_dynamic_environment,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _source(skill_id: str) -> dict:
    return _load_json(
        REPO_ROOT
        / ".agents"
        / "skills"
        / skill_id
        / ".skillguard"
        / "contract-source.json"
    )


def _scheduled_identity(run_id: str = "scheduled-run") -> dict:
    return {
        "scheduler_or_trigger_id": "test-trigger",
        "scheduled_execution_id": run_id,
        "installation_receipt_id": "install-1",
        "installation_receipt_hash": "A" * 64,
        "installation_receipt_root_ref": {
            "path_token": "active_skill_root",
            "relative_path": ".sg-runtime/installation",
        },
        "installed_runtime_fingerprint": "B" * 64,
    }


def test_project_adoption_audit_uses_one_canonical_portable_projection() -> None:
    cli = Path(__file__)

    def audit_projection(command: list[str], **_kwargs) -> dict:
        projection_root = Path(command[-1])
        assert projection_root.name == "Khaos-Brain"
        assert (projection_root / "AGENTS.md").read_bytes() == (
            REPO_ROOT / "AGENTS.md"
        ).read_bytes()
        assert (
            projection_root
            / ".agents/skills/khaos-brain-update/SKILL.md"
        ).is_file()
        return {"ok": True, "status": "pass", "exit_code": 0}

    with patch(
        "scripts.check_kb_skillguard._run_json",
        side_effect=audit_projection,
    ):
        report = _project_adoption_audit(cli)

    assert report["ok"]
    projection = report["validation_projection"]
    assert projection["canonical_project_id"] == "Khaos-Brain"
    assert projection["source_stable"]
    assert projection["source_surface_digest"] == projection["projected_surface_digest"]


def test_frozen_skillguard_root_selects_its_same_bundle_router(
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / ".codex"
    frozen_skillguard = tmp_path / "frozen" / "skillguard"
    with patch.dict(
        os.environ,
        {"KHAOS_BRAIN_SKILLGUARD_VALIDATION_ROOT": str(frozen_skillguard)},
    ):
        selected = _active_skillguard_router_root(
            codex_home, frozen_skillguard
        )

    assert selected == frozen_skillguard.parent / "skillguard-global-router"


def test_installed_control_projection_uses_exact_installed_bytes_under_repository(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    target_root = (
        repository_root
        / ".local"
        / ("deep-scheduled-run-segment-" * 4)
        / "target"
    )
    installed_root = tmp_path / ".codex" / "skills" / "example-skill"
    relative_paths = (
        ".skillguard/contract-source.json",
        ".skillguard/compiled-contract.json",
        ".skillguard/check-manifest.json",
        "SKILL.md",
        "agents/openai.yaml",
    )
    for index, relative in enumerate(relative_paths):
        path = installed_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"installed-{index}\n".encode("utf-8"))
    repository_root.mkdir(parents=True, exist_ok=True)

    first_root, first_receipt = _materialize_installed_control_projection(
        installed_root,
        target_root,
        repository_root,
        skill_id="example-skill",
        relative_paths=relative_paths,
    )
    second_root, second_receipt = _materialize_installed_control_projection(
        installed_root,
        target_root,
        repository_root,
        skill_id="example-skill",
        relative_paths=relative_paths,
    )

    first_root.relative_to(repository_root)
    assert first_root == second_root
    assert first_receipt == second_receipt
    assert first_receipt["source_kind"] == "exact-installed-current-bytes"
    assert first_receipt["projection_scope"] == "repository-local-content-addressed"
    assert first_root.parent == repository_root / ".local" / "installed-skillguard-control"
    for relative in relative_paths:
        assert (first_root / relative).read_bytes() == (installed_root / relative).read_bytes()


def test_skillguard_runtime_projection_excludes_receipts_and_caches(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    target_root = (
        repository_root
        / ".local"
        / ("deep-scheduled-run-segment-" * 4)
        / "target"
    )
    skillguard_root = tmp_path / "installed" / "skillguard"
    router_root = tmp_path / "installed" / "skillguard-global-router"
    required_files = {
        skillguard_root / "scripts/skillguard_v2/runtime_fingerprint.py": b"runtime\n",
        router_root / "SKILL.md": b"router\n",
        router_root / ".skillguard/contract-source.json": b"{}\n",
        router_root / ".skillguard/compiled-contract.json": b"{}\n",
        router_root / ".skillguard/check-manifest.json": b"{}\n",
    }
    for path, payload in required_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    (skillguard_root / ".sg-runtime/installation/HEAD.json").parent.mkdir(
        parents=True
    )
    (skillguard_root / ".sg-runtime/installation/HEAD.json").write_text(
        "runtime-state\n", encoding="utf-8"
    )
    (skillguard_root / "scripts/skillguard_v2/__pycache__").mkdir()
    (skillguard_root / "scripts/skillguard_v2/__pycache__/runtime.pyc").write_bytes(
        b"cache"
    )
    repository_root.mkdir(parents=True)

    runtime_root, receipt = _materialize_skillguard_runtime_projection(
        skillguard_root,
        router_root,
        target_root,
        repository_root,
    )

    runtime_root.relative_to(repository_root)
    assert receipt["source_kind"] == "frozen-current-runtime-without-runtime-state"
    assert receipt["projection_scope"] == "repository-local-content-addressed"
    assert runtime_root.parent.parent == repository_root / ".local" / "skillguard-runtime-projections"
    assert not (runtime_root / ".sg-runtime").exists()
    assert not list(runtime_root.rglob("*.pyc"))
    assert (runtime_root.parent / "skillguard-global-router/SKILL.md").read_bytes() == b"router\n"


def test_skillguard_runtime_projection_reuses_verified_windows_race_winner(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    target_root = repository_root / ".local" / "target"
    skillguard_root = tmp_path / "installed" / "skillguard"
    router_root = tmp_path / "installed" / "skillguard-global-router"
    required_files = {
        skillguard_root / "scripts/skillguard_v2/runtime_fingerprint.py": b"runtime\n",
        router_root / "SKILL.md": b"router\n",
        router_root / ".skillguard/contract-source.json": b"{}\n",
        router_root / ".skillguard/compiled-contract.json": b"{}\n",
        router_root / ".skillguard/check-manifest.json": b"{}\n",
    }
    for path, payload in required_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    repository_root.mkdir(parents=True)
    original_rename = Path.rename

    def publish_race_winner(source: Path, target: Path) -> Path:
        if source.name == "current":
            shutil.copytree(source, target)
            raise PermissionError(5, "simulated Windows publication race")
        return original_rename(source, target)

    with patch("pathlib.Path.rename", new=publish_race_winner):
        runtime_root, receipt = _materialize_skillguard_runtime_projection(
            skillguard_root,
            router_root,
            target_root,
            repository_root,
        )

    assert runtime_root.is_dir()
    assert receipt["source_kind"] == "frozen-current-runtime-without-runtime-state"
    assert (
        runtime_root / "scripts/skillguard_v2/runtime_fingerprint.py"
    ).read_bytes() == b"runtime\n"


def test_skillguard_runtime_projection_stays_cache_free_after_import(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    target_root = repository_root / ".local" / "target"
    skillguard_root = tmp_path / "installed" / "skillguard"
    router_root = tmp_path / "installed" / "skillguard-global-router"
    required_files = {
        skillguard_root / "scripts/skillguard_v2/runtime_fingerprint.py": b"runtime\n",
        skillguard_root / "scripts/projection_bytecode_probe.py": b"VALUE = 1\n",
        router_root / "SKILL.md": b"router\n",
        router_root / ".skillguard/contract-source.json": b"{}\n",
        router_root / ".skillguard/compiled-contract.json": b"{}\n",
        router_root / ".skillguard/check-manifest.json": b"{}\n",
    }
    for path, payload in required_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    repository_root.mkdir(parents=True)
    runtime_root, first_receipt = _materialize_skillguard_runtime_projection(
        skillguard_root,
        router_root,
        target_root,
        repository_root,
    )

    previous_dont_write = sys.dont_write_bytecode
    previous_env = os.environ.get("PYTHONDONTWRITEBYTECODE")
    scripts_root = runtime_root / "scripts"
    sys.path.insert(0, str(scripts_root))
    try:
        _prevent_runtime_projection_bytecode_mutation()
        importlib.invalidate_caches()
        probe = importlib.import_module("projection_bytecode_probe")
        assert probe.VALUE == 1
        assert not list(runtime_root.rglob("*.pyc"))
        second_root, second_receipt = _materialize_skillguard_runtime_projection(
            skillguard_root,
            router_root,
            target_root,
            repository_root,
        )
        assert second_root == runtime_root
        assert second_receipt["projection_hash"] == first_receipt["projection_hash"]
    finally:
        sys.path.remove(str(scripts_root))
        sys.modules.pop("projection_bytecode_probe", None)
        sys.dont_write_bytecode = previous_dont_write
        if previous_env is None:
            os.environ.pop("PYTHONDONTWRITEBYTECODE", None)
        else:
            os.environ["PYTHONDONTWRITEBYTECODE"] = previous_env


def test_frozen_supervision_injects_only_current_run_evidence() -> None:
    receipt_key = "KHAOS_BRAIN_AUTOMATION_RECEIPT"
    run_key = "KHAOS_BRAIN_AUTOMATION_RUN_ID"
    with patch.dict(
        os.environ,
        {
            receipt_key: "stale-receipt.json",
            run_key: "stale-run",
            "UNRELATED_SUPERVISION_SECRET": "preserved",
        },
        clear=False,
    ):
        with _supervision_dynamic_environment(
            {receipt_key: "current-receipt.json"}
        ):
            assert os.environ[receipt_key] == "current-receipt.json"
            assert run_key not in os.environ
            assert os.environ["UNRELATED_SUPERVISION_SECRET"] == "preserved"
        assert os.environ[receipt_key] == "stale-receipt.json"
        assert os.environ[run_key] == "stale-run"

    with pytest.raises(ValueError, match="unsupported dynamic"):
        with _supervision_dynamic_environment({"UNDECLARED_SECRET": "blocked"}):
            pass


def test_frozen_session_protocol_filters_dynamic_environment(
    tmp_path: Path,
) -> None:
    packet_path = tmp_path / "packet.json"
    packet_path.write_text("{}\n", encoding="utf-8")
    target_root = tmp_path / "target"
    captured: dict[str, object] = {}
    session = object.__new__(_InstalledSupervisionSession)

    def request(payload: dict, *, timeout: float) -> dict:
        captured.update(payload=payload, timeout=timeout)
        return {"ok": True}

    session.request = request
    result = session.run_packet(
        packet_path,
        target_root=target_root,
        environment={
            **{
                key: f"value-{index}"
                for index, key in enumerate(_SUPERVISION_DYNAMIC_ENV_KEYS)
            },
            "UNDECLARED_SECRET": "must-not-cross",
        },
    )

    assert result["exit_code"] == 0
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["dynamic_environment"] == {
        key: f"value-{index}"
        for index, key in enumerate(_SUPERVISION_DYNAMIC_ENV_KEYS)
    }
    assert captured["timeout"] == 2400


def test_session_bootstrap_reports_the_worker_failure_detail(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    skill_root = tmp_path / ".codex" / "skills" / "kb-dream-pass"
    codex_home = tmp_path / ".codex"
    repository_root.mkdir()
    skill_root.mkdir(parents=True)
    worker = repository_root / "scripts" / "run_installed_skillguard_supervision.py"
    worker.parent.mkdir()
    worker.write_text("# fixture\n", encoding="utf-8")
    fake_process = SimpleNamespace()
    ready = {
        "ok": False,
        "stage": "replay-skillguard-installation-currentness",
        "error": "ValueError: installation_projection_component_hash_mismatch",
    }

    with patch(
        "scripts.check_kb_skillguard.subprocess.Popen",
        return_value=fake_process,
    ), patch.object(
        _InstalledSupervisionSession,
        "_read_protocol",
        return_value=ready,
    ), patch.object(
        _InstalledSupervisionSession,
        "close",
    ), pytest.raises(
        RuntimeError,
        match="installation_projection_component_hash_mismatch",
    ):
        _InstalledSupervisionSession.start(
            skill_root=skill_root,
            codex_home=codex_home,
            repository_root=repository_root,
            session_root=repository_root / ".local" / "session",
            scheduler_or_trigger_id="fixture-trigger",
            scheduled_execution_id="fixture-run",
        )


def test_supervision_worker_preserves_constructor_failure_stage(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_init(self, **kwargs) -> None:
        del kwargs
        self.stage = "replay-skillguard-installation-currentness"
        raise ValueError("installation_projection_component_hash_mismatch")

    monkeypatch.setattr(
        supervision_worker._FrozenInstalledSupervisionRuntime,
        "__init__",
        fail_init,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_installed_skillguard_supervision.py",
            "fixture-skill",
            "--session",
            "--target-root",
            "fixture-target",
            "--repository-root",
            "fixture-repository",
            "--codex-home",
            "fixture-home",
        ],
    )

    assert supervision_worker.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["stage"] == "replay-skillguard-installation-currentness"
    assert "installation_projection_component_hash_mismatch" in payload["error"]


def test_skillguard_runtime_projection_rejects_tampered_behavior(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    target_root = repository_root / ".local" / "target"
    skillguard_root = tmp_path / "installed" / "skillguard"
    router_root = tmp_path / "installed" / "skillguard-global-router"
    required_files = {
        skillguard_root / "scripts/skillguard_v2/runtime_fingerprint.py": b"runtime\n",
        router_root / "SKILL.md": b"router\n",
        router_root / ".skillguard/contract-source.json": b"{}\n",
        router_root / ".skillguard/compiled-contract.json": b"{}\n",
        router_root / ".skillguard/check-manifest.json": b"{}\n",
    }
    for path, payload in required_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    repository_root.mkdir(parents=True)
    runtime_root, _ = _materialize_skillguard_runtime_projection(
        skillguard_root,
        router_root,
        target_root,
        repository_root,
    )
    (runtime_root / "scripts/skillguard_v2/runtime_fingerprint.py").write_bytes(
        b"tampered\n"
    )

    with pytest.raises(ValueError, match="byte mismatch"):
        _materialize_skillguard_runtime_projection(
            skillguard_root,
            router_root,
            target_root,
            repository_root,
        )


def _full_regression_receipt(root: Path, skill_id: str) -> Path:
    node_ids = sorted(
        set(
            evidence_test_node_ids(skill_id, repo_root=REPO_ROOT).values()
        )
    )
    cases: list[str] = []
    for node_id in node_ids:
        path, *parts = node_id.split("::")
        module = path.removesuffix(".py").replace("/", ".")
        name = parts[-1]
        class_suffix = ".".join(parts[:-1])
        classname = module + ("." + class_suffix if class_suffix else "")
        cases.append(f'<testcase classname="{classname}" name="{name}" />')
    junit_path = root / "full-regression.junit.xml"
    junit_path.write_text(
        "<?xml version=\"1.0\"?><testsuite>" + "".join(cases) + "</testsuite>",
        encoding="utf-8",
    )
    source = readiness._source_snapshot(REPO_ROOT)
    verifier = readiness._verifier_fingerprint()
    environment = readiness._environment_contract(REPO_ROOT)
    command = [sys.executable, "-m", "pytest", "-q", "tests"]
    identity = readiness._command_identity(
        command,
        source_digest=str(source["digest"]),
        verifier_digest=str(verifier["digest"]),
        environment_contract=environment,
    )
    receipt = {
        "schema_version": "khaos-brain.validation-evidence.v1",
        "receipt_id": f"validation:full_regression:{identity}",
        "name": "full_regression",
        "identity_fingerprint": identity,
        "command": command,
        "input_fingerprints": {
            "source": source["digest"],
            "verifier": verifier["digest"],
        },
        "terminal_status": "passed",
        "timed_out": False,
        "exit_code": 0,
        "ok": True,
        "proof_artifact_ref": {
            "path": str(junit_path.resolve()),
            "present": True,
            "sha256": hashlib.sha256(junit_path.read_bytes()).hexdigest(),
        },
        "junit": readiness._junit_summary(junit_path, REPO_ROOT),
    }
    receipt_path = root / "full_regression.receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return receipt_path


def test_source_capability_consumes_full_junit_without_nested_pytest() -> None:
    skill_id = "kb-sleep-maintenance"
    with tempfile.TemporaryDirectory() as tmp:
        receipt_path = _full_regression_receipt(Path(tmp), skill_id)
        capability = _run_capability_regression(
            skill_id,
            capability_receipt_path=receipt_path,
        )
        with patch(
            "scripts.check_kb_skillguard._execute_supervision",
            side_effect=AssertionError("source-only must not start production supervision"),
        ):
            assurance = _execute_skill_assurance(
                skill_id,
                REPO_ROOT / ".agents" / "skills" / skill_id,
                Path(tmp) / ".codex",
                "source",
                capability_receipt_path=receipt_path,
            )

    assert capability["ok"], capability
    assert capability["execution"] == "consumed"
    assert assurance["ok"], assurance
    assert assurance["scheduled_production_supervision"]["status"] == "not_applicable"


def test_installed_assurance_invokes_real_guarded_entrypoint_not_fixture_supervision() -> None:
    skill_id = "kb-sleep-maintenance"
    with tempfile.TemporaryDirectory() as tmp:
        receipt_path = _full_regression_receipt(Path(tmp), skill_id)
        expected_result = {
            "ok": True,
            "exit_code": 0,
            "skill_id": skill_id,
            "guarded_result_path": str(Path(tmp) / "guarded-result.json"),
            "status": "completed",
        }
        with patch(
            "scripts.check_kb_skillguard._run_json",
            return_value=expected_result,
        ) as run_json, patch(
            "scripts.check_kb_skillguard._execute_supervision",
            side_effect=AssertionError("installed aggregate must use the guarded entrypoint"),
        ):
            assurance = _execute_skill_assurance(
                skill_id,
                REPO_ROOT / ".agents" / "skills" / skill_id,
                Path(tmp) / ".codex",
                "installed",
                capability_receipt_path=receipt_path,
            )

    assert assurance["ok"], assurance
    command = run_json.call_args.args[0]
    assert "scripts" in command[1]
    assert command[1].endswith("run_kb_guarded_automation.py")
    assert "--skill" in command
    assert "--json" in command


def test_supervision_authority_comes_from_exact_root_not_surface_label(
    tmp_path: Path,
) -> None:
    skill_id = "kb-sleep-maintenance"
    codex_home = tmp_path / ".codex"
    installed_root = codex_home / "skills" / skill_id
    installed_root.mkdir(parents=True)

    assert (
        _supervision_target_authority(skill_id, installed_root, codex_home)
        == "installed"
    )
    assert (
        _supervision_target_authority(
            skill_id,
            REPO_ROOT / ".agents" / "skills" / skill_id,
            codex_home,
        )
        == "source"
    )


def test_supervision_authority_rejects_unknown_or_ambiguous_root(
    tmp_path: Path,
) -> None:
    skill_id = "kb-sleep-maintenance"
    unknown_root = tmp_path / "unknown" / skill_id
    unknown_root.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="exactly one current managed root"):
        _supervision_target_authority(
            skill_id,
            unknown_root,
            tmp_path / ".codex",
        )


@pytest.mark.parametrize(
    ("source_only", "execute_checks", "required", "boundary_marker"),
    (
        (True, False, "current source compiler/depth", "No installed-tree parity"),
        (True, True, "capability JUnit", "does not compare installed trees"),
        (False, False, "complete tree-parity", "No capability execution"),
        (False, True, "one real guarded execution", "does not certify future runs"),
    ),
)
def test_skillguard_report_claim_boundary_matches_executed_scope(
    source_only: bool,
    execute_checks: bool,
    required: str,
    boundary_marker: str,
) -> None:
    claim = _report_claim_boundary(
        source_only=source_only,
        execute_checks=execute_checks,
    )
    normalized_claim = claim.casefold()
    assert required.casefold() in normalized_claim
    assert boundary_marker.casefold() in normalized_claim


@pytest.mark.parametrize("skill_id", tuple(AUTOMATION_COMPLETION_CONTRACTS))
def test_all_automation_contracts_are_deep_and_current(skill_id: str) -> None:
    source = _source(skill_id)
    assert source == build_contract_source(skill_id)
    assert len(expected_obligation_ids(skill_id)) >= 8
    assert source["depth_profile"]["enforcement_level"] == "enforced"
    assert source["depth_profile"]["required_closure_profiles"] == ["enforced"]
    assert [row["profile_id"] for row in source["closure_profiles"]] == [
        "enforced"
    ]
    assert set(
        source["closure_profiles"][-1]["required_obligation_ids"]
    ) == set(expected_obligation_ids(skill_id))
    report = build_report(skill_id, "positive")
    assert report["ok"], report
    assert report["observed_status"] == "deep-pass"


@pytest.mark.parametrize("skill_id", tuple(AUTOMATION_COMPLETION_CONTRACTS))
def test_shallow_automation_contract_is_rejected(skill_id: str) -> None:
    report = build_report(skill_id, "shallow")
    assert report["ok"], report
    assert report["observed_status"] == "shallow-blocked"
    assert report["findings"] == []
    assert report["failed_obligation_ids"]


def test_organization_automation_native_checks_bind_full_automation_regressions() -> None:
    for skill_id in (
        "kb-organization-contribute",
        "kb-organization-maintenance",
    ):
        source = _source(skill_id)
        assert "tests/test_org_automation.py" in source["implementation_paths"]
        for kind in ("intake-runtime", "native-runtime", "terminal-runtime"):
            native = next(
                row
                for row in source["checks"]
                if row["check_id"] == check_id(skill_id, kind)
            )
            assert "scripts/check_kb_automation_run_receipt.py" in native["args"]


def test_all_scheduled_prompts_require_terminal_skillguard_closure() -> None:
    prompts = {
        str(row["skill_name"]): str(row["prompt"])
        for row in REPO_AUTOMATION_SPECS
    }
    assert set(AUTOMATION_COMPLETION_CONTRACTS).issubset(prompts)
    for skill_id in AUTOMATION_COMPLETION_CONTRACTS:
        assert SKILLGUARD_COMPLETION_MARKER in prompts[skill_id]
        assert SKILLGUARD_PARTIAL_MARKER in prompts[skill_id]
        assert "scripts/run_kb_guarded_automation.py" in prompts[skill_id]
        assert "Fixture or capability evidence cannot close a scheduled run" in prompts[skill_id]
        assert "installed runtime fingerprint" in prompts[skill_id]
    update_prompt = prompts["khaos-brain-update"]
    for reason in (
        "no-update",
        "waiting-for-user",
        "ui-running",
        "already-upgrading",
        "failed-awaiting-user",
        "concurrent-update",
    ):
        assert reason in update_prompt


@pytest.mark.parametrize("skill_id", tuple(AUTOMATION_COMPLETION_CONTRACTS))
def test_positive_native_run_receipt_covers_every_domain_phase(skill_id: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "native-receipt.json"
        run_id = f"positive-{skill_id}"
        receipt = build_native_receipt(
            skill_id,
            run_id=run_id,
            command=["fixture", "positive", skill_id],
            native_payload=build_fixture_payload(skill_id, shallow=False, run_id=run_id),
            exit_code=0,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            fixture="positive",
        )
        write_native_receipt(path, receipt)
        for phase in ("intake", "execute", "verify", "all"):
            report = validate_native_receipt(
                path,
                skill_id=skill_id,
                phase=phase,
                expected_run_id=run_id,
                expected_receipt_hash=str(receipt["receipt_hash"]),
                allow_fixture=True,
            )
            assert report["ok"], report


@pytest.mark.parametrize("skill_id", tuple(AUTOMATION_COMPLETION_CONTRACTS))
def test_partial_native_run_receipt_cannot_reach_terminal_closure(skill_id: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "native-receipt.json"
        run_id = f"shallow-{skill_id}"
        receipt = build_native_receipt(
            skill_id,
            run_id=run_id,
            command=["fixture", "shallow", skill_id],
            native_payload=build_fixture_payload(skill_id, shallow=True, run_id=run_id),
            exit_code=0,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            fixture="shallow",
        )
        write_native_receipt(path, receipt)
        report = validate_native_receipt(
            path,
            skill_id=skill_id,
            phase="all",
            expected_run_id=run_id,
            expected_receipt_hash=str(receipt["receipt_hash"]),
            allow_fixture=True,
        )
        assert not report["ok"]
        assert "native-terminal-not-successful" in report["issues"]


def test_guarded_runner_does_not_return_success_before_skillguard_closure() -> None:
    skill_id = "kb-organization-contribute"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo_root = root / "repo"
        codex_home = root / ".codex"
        repo_root.mkdir()
        (codex_home / "skills" / skill_id).mkdir(parents=True)
        def completed_for(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            run_id = command[command.index("--run-id") + 1]
            payload = build_fixture_payload(skill_id, shallow=False, run_id=run_id)
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )
        with patch(
            "scripts.run_kb_guarded_automation.run_with_timeout_cleanup",
            side_effect=completed_for,
        ), patch(
            "scripts.run_kb_guarded_automation._build_current_scheduled_production_identity",
            return_value=_scheduled_identity(),
        ), patch(
            "scripts.run_kb_guarded_automation._execute_supervision",
            return_value={"ok": False, "validation": {"depth_passed": False}},
        ):
            result = run_guarded_automation(
                skill_id,
                repo_root=repo_root,
                codex_home=codex_home,
            )
        assert not result["ok"]
        assert result["status"] == "skillguard-blocked"
        assert Path(result["native_receipt_path"]).is_file()


def test_guarded_runner_reports_installed_identity_failure_as_guard_block() -> None:
    skill_id = "kb-organization-contribute"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo_root = root / "repo"
        codex_home = root / ".codex"
        repo_root.mkdir()
        (codex_home / "skills" / skill_id).mkdir(parents=True)

        def completed_for(
            command: list[str], **_: object
        ) -> subprocess.CompletedProcess[str]:
            run_id = command[command.index("--run-id") + 1]
            payload = build_fixture_payload(skill_id, shallow=False, run_id=run_id)
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )

        with patch(
            "scripts.run_kb_guarded_automation.run_with_timeout_cleanup",
            side_effect=completed_for,
        ) as native_run, patch(
            "scripts.run_kb_guarded_automation._build_current_scheduled_production_identity",
            side_effect=RuntimeError("installation receipt stale"),
        ):
            result = run_guarded_automation(
                skill_id,
                repo_root=repo_root,
                codex_home=codex_home,
            )

        assert not result["ok"]
        assert result["status"] == "scheduled-production-identity-blocked"
        assert "installation receipt stale" in result["issues"][0]
        assert Path(result["guarded_result_path"]).is_file()
        native_run.assert_not_called()


def test_contract_manifest_declares_exact_runtime_and_target_fixture_checks() -> None:
    for skill_id in AUTOMATION_COMPLETION_CONTRACTS:
        source = _source(skill_id)
        expected_checks = {
            check_id(skill_id, kind)
            for kind in (
                "intake-runtime",
                "native-runtime",
                "terminal-runtime",
                "depth-positive",
                "depth-shallow",
            )
        }
        if skill_id == "khaos-brain-update":
            expected_checks.add(check_id(skill_id, "finalization-runtime"))
            expected_checks.add(check_id(skill_id, "branch-terminal-runtime"))
        assert {row["check_id"] for row in source["checks"]} == expected_checks


def test_supervisor_packet_uses_only_current_execution_depth_fields() -> None:
    scheduled_identity = {
        "scheduler_or_trigger_id": "kb-sleep",
        "scheduled_execution_id": "run-1",
        "installation_receipt_id": "install-1",
        "installation_receipt_hash": "B" * 64,
        "installation_receipt_root_ref": {
            "path_token": "active_skill_root",
            "relative_path": ".sg-runtime/installation",
        },
        "installed_runtime_fingerprint": "C" * 64,
    }
    packet = _supervision_packet(
        "kb-sleep-maintenance",
        stage="complete",
        native_run_id="run-1",
        native_receipt_hash="A" * 64,
        native_receipt_path=Path("native-receipt.json"),
        scheduled_production_identity=scheduled_identity,
    )
    assert packet["execution_depth"] == {
        "observations": [],
        "run_started": True,
        "boundary_only": False,
        "evidence_domain": "scheduled_production",
        "scheduled_production_identity": scheduled_identity,
    }


def test_scheduled_identity_comes_from_installed_skillguard_six_field_builder(
    tmp_path: Path,
) -> None:
    identity = {
        "scheduler_or_trigger_id": "kb-sleep",
        "scheduled_execution_id": "run-1",
        "installation_receipt_id": "install-1",
        "installation_receipt_hash": "A" * 64,
        "installation_receipt_root_ref": {
            "path_token": "active_skill_root",
            "relative_path": ".sg-runtime/installation",
        },
        "installed_runtime_fingerprint": "B" * 64,
    }
    verified_context = object()
    loader_calls: list[tuple[Path, Path | None, Path]] = []
    builder_contexts: list[object] = []
    verifier_calls: list[tuple[dict, Path, object]] = []
    observed_pythonpaths: list[str | None] = []

    def load_context(
        receipt_root: Path,
        *,
        canonical_skill_root: Path | None,
        codex_home: Path,
    ) -> object:
        observed_pythonpaths.append(os.environ.get("PYTHONPATH"))
        loader_calls.append((receipt_root, canonical_skill_root, codex_home))
        return verified_context

    def build(**kwargs: object) -> dict:
        observed_pythonpaths.append(os.environ.get("PYTHONPATH"))
        builder_contexts.append(kwargs["verified_context"])
        return dict(identity)

    def verify(
        value: dict,
        *,
        active_skill_root: Path,
        verified_context: object,
    ) -> None:
        observed_pythonpaths.append(os.environ.get("PYTHONPATH"))
        verifier_calls.append((dict(value), active_skill_root, verified_context))

    module = SimpleNamespace(
        DEFAULT_INSTALLATION_RECEIPT_RELATIVE_PATH=".sg-runtime/installation",
        load_verified_installation_context=load_context,
        build_scheduled_production_identity=build,
        verify_scheduled_production_installation_identity=verify,
    )
    with patch.dict(
        os.environ,
        {
            "PYTHONPATH": "C:\\formal-flowguard-snapshot",
            "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_PRESENT": "0",
            "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_VALUE": "",
        },
    ), patch(
        "scripts.check_kb_skillguard._installed_skillguard_module",
        return_value=module,
    ):
        observed = _build_current_scheduled_production_identity(
            tmp_path,
            scheduler_or_trigger_id="kb-sleep",
            scheduled_execution_id="run-1",
        )
        assert os.environ["PYTHONPATH"] == "C:\\formal-flowguard-snapshot"

    assert observed == identity
    active_root = (tmp_path / "skills" / "skillguard").resolve()
    assert loader_calls == [
        (
            active_root / ".sg-runtime" / "installation",
            None,
            tmp_path,
        )
    ]
    assert builder_contexts == [verified_context]
    assert observed_pythonpaths == [None, None, None]
    assert verifier_calls == [
        (identity, active_root, verified_context)
    ]


def test_scheduled_identity_can_start_one_frozen_supervision_session(
    tmp_path: Path,
) -> None:
    identity = _scheduled_identity("run-frozen-1")
    snapshot = {
        "schema_version": "khaos-brain.scheduled-supervision-start-snapshot.v1",
        "authority_frozen_before_native": True,
    }
    session = SimpleNamespace(identity=identity, snapshot=snapshot)
    skill_root = tmp_path / ".codex" / "skills" / "kb-dream-pass"
    repository_root = tmp_path / "repo"
    session_root = repository_root / ".local" / "session"

    with patch(
        "scripts.check_kb_skillguard._InstalledSupervisionSession.start",
        return_value=session,
    ) as start:
        observed = _build_current_scheduled_production_identity(
            tmp_path / ".codex",
            scheduler_or_trigger_id="kb-dream",
            scheduled_execution_id="run-frozen-1",
            scheduled_skill_root=skill_root,
            repository_root=repository_root,
            session_root=session_root,
        )

    assert isinstance(observed, _ScheduledProductionIdentity)
    assert dict(observed) == identity
    assert observed._supervision_session is session
    start.assert_called_once_with(
        skill_root=skill_root,
        codex_home=tmp_path / ".codex",
        repository_root=repository_root,
        session_root=session_root,
        scheduler_or_trigger_id="kb-dream",
        scheduled_execution_id="run-frozen-1",
    )


def test_scheduled_identity_rejects_builder_without_portable_receipt_root(
    tmp_path: Path,
) -> None:
    incomplete = {
        "scheduler_or_trigger_id": "kb-sleep",
        "scheduled_execution_id": "run-1",
        "installation_receipt_id": "install-1",
        "installation_receipt_hash": "A" * 64,
        "installed_runtime_fingerprint": "B" * 64,
    }
    verified_context = object()
    module = SimpleNamespace(
        DEFAULT_INSTALLATION_RECEIPT_RELATIVE_PATH=".sg-runtime/installation",
        load_verified_installation_context=lambda *_args, **_kwargs: verified_context,
        build_scheduled_production_identity=lambda **_: incomplete,
        verify_scheduled_production_installation_identity=lambda *_args, **_kwargs: None,
    )
    with patch(
        "scripts.check_kb_skillguard._installed_skillguard_module",
        return_value=module,
    ), pytest.raises(RuntimeError, match="six-field"):
        _build_current_scheduled_production_identity(
            tmp_path,
            scheduler_or_trigger_id="kb-sleep",
            scheduled_execution_id="run-1",
        )


def test_installed_projection_parity_uses_official_skillguard_owner(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    receipt = {"status": "current", "receipt_id": "sha256:" + "A" * 64}

    def verify(
        canonical_repository_root: Path,
        target_identity: dict,
        installed_target_root: Path,
        *,
        portfolio_projection_hash: str,
    ) -> dict:
        captured.update(
            canonical_repository_root=canonical_repository_root,
            target_identity=target_identity,
            installed_target_root=installed_target_root,
            portfolio_projection_hash=portfolio_projection_hash,
        )
        return dict(receipt)

    module = SimpleNamespace(
        verify_installed_content_parity=verify,
        validate_installed_parity_receipt=lambda *_args, **_kwargs: [],
        replay_installed_content_parity_currentness=lambda *_args, **_kwargs: [],
    )
    source = REPO_ROOT / ".agents" / "skills" / "kb-sleep-maintenance"
    installed = tmp_path / "skills" / "kb-sleep-maintenance"
    with patch(
        "scripts.check_kb_skillguard._installed_skillguard_module",
        return_value=module,
    ):
        result = _installed_projection_parity(
            tmp_path,
            skill_id="kb-sleep-maintenance",
            source_skill_root=source,
            installed_skill_root=installed,
        )

    assert result["ok"] is True
    assert captured["canonical_repository_root"] == REPO_ROOT
    assert captured["installed_target_root"] == installed
    target = captured["target_identity"]
    assert target == {
        "skill_id": "kb-sleep-maintenance",
        "target_kind": "single_skill",
        "member_identities": [
            {
                "member_skill_id": "kb-sleep-maintenance",
                "skill_path": ".agents/skills/kb-sleep-maintenance",
            }
        ],
        "skill_paths": [".agents/skills/kb-sleep-maintenance"],
    }
    assert str(captured["portfolio_projection_hash"]).startswith("sha256:")


@pytest.mark.parametrize(
    ("supervision_stage", "branch_id", "profile"),
    (
        ("no-op", "no-update", "enforced"),
        ("no-op", "waiting-for-user", "enforced"),
        ("no-op", "ui-running", "enforced"),
        ("authorization", "prepared-update", "enforced"),
    ),
)
def test_update_supervision_stages_nonterminal_or_closes_enforced(
    tmp_path: Path,
    supervision_stage: str,
    branch_id: str,
    profile: str,
) -> None:
    skill_id = "khaos-brain-update"
    codex_home = tmp_path / ".codex"
    skill_root = codex_home / "skills" / skill_id
    supervisor = (
        codex_home
        / "skills"
        / "skillguard"
        / "scripts"
        / "skillguard_supervise.py"
    )
    supervisor.parent.mkdir(parents=True)
    supervisor.write_text("# fixture\n", encoding="utf-8")
    run_root = tmp_path / "unassigned-run-root"
    (skill_root / ".skillguard").mkdir(parents=True)
    (skill_root / ".skillguard" / "compiled-contract.json").write_text(
        json.dumps(
            {
                "steps": [],
                "depth_profile": {
                    "required_closure_profiles": ["enforced"],
                    "native_check_ids": [
                        check_id(skill_id, kind)
                        for kind in (
                            "intake-runtime",
                            "native-runtime",
                            "terminal-runtime",
                            "branch-terminal-runtime",
                            "depth-positive",
                            "depth-shallow",
                        )
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    native_run_id = "scheduled-update-1"
    native = build_native_receipt(
        skill_id,
        run_id=native_run_id,
        command=["fixture-native-update"],
        native_payload=build_fixture_payload(skill_id, run_id=native_run_id),
        exit_code=0,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
    )
    native_path = write_native_receipt(tmp_path / "native.json", native)
    expected_ids = {
        obligation_id(skill_id, str(row["suffix"]))
        for row in AUTOMATION_COMPLETION_CONTRACTS[skill_id]["obligations"]
        if str(row.get("phase") or "") in {"intake", "execute", "verify"}
    }
    depth = {
        "receipt_id": "depth-1",
        "receipt_hash": "D" * 64,
        "status": "EXECUTION_DEPTH_PASS",
        "uncovered_obligation_ids": [],
        "declared_check_results": [
            {
                "check_id": check_id(skill_id, kind),
                "disposition": "passed",
                "current": True,
            }
            for kind in (
                "intake-runtime",
                "native-runtime",
                "terminal-runtime",
                "branch-terminal-runtime",
                "depth-positive",
                "depth-shallow",
            )
        ],
        "unresolved_check_ids": [],
        "provider_runtime_audit": {"status": "passed"},
    }
    stage_report = {
        "status": "staged",
        "supervision_mode": "stage_depth",
        "run_id": "skillguard-run-1",
        "run_root": str(run_root),
        "closures": [],
        "executed_steps": [],
        "target_execution_depth_receipt": depth,
    }
    close_report = {
        "status": "passed",
        "supervision_mode": "close",
        "run_id": "skillguard-run-1",
        "run_root": str(run_root),
        "executed_steps": [],
        "target_execution_depth_receipt": depth,
        "closures": [
            {
                "profile": profile,
                "closure_receipt_id": "closure-1",
                "verification": {"ok": True},
            }
        ],
    }
    packets: list[dict] = []
    commands: list[list[str]] = []

    def run_json(command: list[str], **_: object) -> dict:
        target_root = Path(command[command.index("--target-root") + 1])
        actual_run_root = target_root / ".skillguard" / "runs" / "run-1"
        actual_run_root.mkdir(parents=True, exist_ok=True)
        stage_report["run_root"] = str(actual_run_root)
        close_report["run_root"] = str(actual_run_root)
        closures_root = actual_run_root / "closures"
        closures_root.mkdir(exist_ok=True)
        (closures_root / "closure-1.json").write_text(
            json.dumps(
                {
                    "status": "closed",
                    "profile": profile,
                    "consumed_receipt_ids": ["depth-1"],
                }
            ),
            encoding="utf-8",
        )
        commands.append(command)
        packet = _load_json(Path(command[3]))
        packets.append(packet)
        return {
            "ok": True,
            "exit_code": 0,
            "report": stage_report if len(packets) == 1 else close_report,
        }

    identity = {
        "scheduler_or_trigger_id": "khaos-brain-system-update",
        "scheduled_execution_id": native_run_id,
        "installation_receipt_id": "install-1",
        "installation_receipt_hash": "A" * 64,
        "installation_receipt_root_ref": {
            "path_token": "active_skill_root",
            "relative_path": ".sg-runtime/installation",
        },
        "installed_runtime_fingerprint": "B" * 64,
    }
    terminal = {
        "receipt": {
            "receipt_id": "native-noop-1",
            "depth_receipt_id": "depth-1",
            "depth_receipt_hash": "D" * 64,
            "target_obligation_ids": sorted(expected_ids),
        },
        "receipt_ref": {
            "path_token": "run_root",
            "relative_path": "native-terminal/receipts/native-noop-1.json",
        },
    }
    with patch(
        "scripts.check_kb_skillguard._build_current_scheduled_production_identity",
        return_value=identity,
    ), patch(
        "scripts.check_kb_skillguard._build_and_write_target_native_terminal",
        return_value=terminal,
    ) as terminal_builder, patch(
        "scripts.check_kb_skillguard._run_json",
        side_effect=run_json,
    ), patch(
        "scripts.check_kb_skillguard.validate_native_receipt",
        return_value={
            "ok": True,
            "issues": [],
            "selected_obligation_ids": sorted(expected_ids),
        },
    ):
        result = _execute_supervision(
            skill_id,
            skill_root,
            codex_home,
            f"scheduled-guarded-{native_run_id}",
            native_receipt_path=native_path,
            expected_native_run_id=native_run_id,
            expected_native_receipt_hash=str(native["receipt_hash"]),
            expected_native_receipt_path=native_path,
            supervision_stage=supervision_stage,
            native_terminal_branch_id=branch_id,
        )

    assert result["ok"], result
    assert result["target_authority"] == "installed"
    assert Path(commands[0][1]).name == "run_installed_skillguard_supervision.py"
    assert commands[0][-2:] == ["--codex-home", str(codex_home)]
    assert Path(result["target_root"]) == Path(
        commands[0][commands[0].index("--target-root") + 1]
    )
    if supervision_stage == "authorization":
        assert [packet["supervision_mode"] for packet in packets] == [
            "stage_depth"
        ]
        assert packets[0]["profiles"] == []
        terminal_builder.assert_not_called()
        assert result["validation"]["non_terminal_authorization"] is True
        assert result["validation"]["overall_complete"] is False
        assert result["validation"]["closure_emitted"] is False
    else:
        assert "target_obligation_ids" not in depth
        assert [packet["supervision_mode"] for packet in packets] == [
            "stage_depth",
            "close",
        ]
        assert packets[0]["request"] == packets[1]["request"]
        assert packets[0]["profiles"] == []
        assert packets[1]["profiles"] == [profile]
        assert packets[1]["native_terminal"]["expected_branch_id"] == branch_id
        assert terminal_builder.call_args.kwargs["profile"] == profile
        assert terminal_builder.call_args.kwargs["branch_id"] == branch_id
        assert result["validation"]["native_obligation_source"] == (
            "target-native-terminal"
        )
        assert result["validation"]["native_target_obligations"] == sorted(
            expected_ids
        )
        expected_applicable = set(expected_obligation_ids(skill_id)) - {
            "obligation:khaos-brain-update:staged-restoration-authorization"
        }
        assert result["validation"]["applicable_obligations"] == sorted(
            expected_applicable
        )
        assert result["validation"]["complete_obligation_set"] is True
        assert result["validation"]["two_stage_terminal"] == {
            "same_run_id": True,
            "same_run_root": True,
            "exact_depth_receipt_reused": True,
            "close_did_not_rerun_target_steps": True,
            "terminal_bound_exact_depth": True,
            "close_consumed_staged_depth": True,
        }


def test_target_terminal_builder_consumes_run_snapshot_and_native_artifact(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    native_path = tmp_path / "native.json"
    native_path.write_bytes(b'{"receipt_hash":"logical-native-hash"}\n')
    calls: list[dict] = []

    def builder(_run_root: Path, contract: dict, **kwargs: object) -> dict:
        calls.append({"run_root": _run_root, "contract": contract, **kwargs})
        return {
            "schema_version": "skillguard.native_noop_receipt.v1",
            "receipt_id": "native-noop-1",
            "receipt_hash": "terminal-hash",
            "depth_receipt_id": "depth-1",
            "depth_receipt_hash": "depth-hash",
        }

    def writer(_run_root: Path, receipt: dict) -> dict:
        assert _run_root == run_root
        return {
            "receipt": receipt,
            "receipt_ref": {
                "path_token": "run_root",
                "relative_path": "native-terminal/receipts/native-noop-1.json",
            },
        }

    terminal_module = SimpleNamespace(
        build_target_native_terminal_receipt=builder,
        write_target_native_terminal_receipt=writer,
    )
    run_store_module = SimpleNamespace(
        load_contract_snapshot=lambda _: {"contract_hash": "snapshot-hash"}
    )
    verified_context = object()
    installation_module = SimpleNamespace(
        DEFAULT_INSTALLATION_RECEIPT_RELATIVE_PATH=".sg-runtime/installation",
        load_verified_installation_context=lambda *_args, **_kwargs: verified_context,
    )

    def module_for(_home: Path, name: str):
        if name == "skillguard_v2.native_terminal":
            return terminal_module
        if name == "skillguard_v2.installation_receipt":
            return installation_module
        return run_store_module

    with patch(
        "scripts.check_kb_skillguard._installed_skillguard_module",
        side_effect=module_for,
    ):
        result = _build_and_write_target_native_terminal(
            tmp_path / ".codex",
            run_root=run_root,
            profile="enforced",
            branch_id="no-update",
            native_receipt_path=native_path,
            native_receipt_hash="logical-native-hash",
            finalization_receipt_hash="",
            stage="no-op",
        )

    assert result["receipt_ref"]["path_token"] == "run_root"
    assert calls[0]["contract"] == {"contract_hash": "snapshot-hash"}
    assert calls[0]["native_check_id"] == (
        "check:khaos-brain-update:branch-terminal-runtime"
    )
    assert calls[0]["native_route_id"] == "route:khaos-brain-update:authorize"
    artifact_ref = result["native_artifact_ref"]
    assert (run_root / artifact_ref["relative_path"]).read_bytes() == native_path.read_bytes()


def test_supervision_rejects_installation_identity_drift_after_native_start(
    tmp_path: Path,
) -> None:
    skill_id = "kb-organization-contribute"
    codex_home = tmp_path / ".codex"
    skill_root = codex_home / "skills" / skill_id
    supervisor = (
        codex_home
        / "skills"
        / "skillguard"
        / "scripts"
        / "skillguard_supervise.py"
    )
    supervisor.parent.mkdir(parents=True)
    supervisor.write_text("# fixture\n", encoding="utf-8")
    skill_root.mkdir(parents=True)
    run_id = "scheduled-org-1"
    native = build_native_receipt(
        skill_id,
        run_id=run_id,
        command=["fixture-native-org"],
        native_payload=build_fixture_payload(skill_id, run_id=run_id),
        exit_code=0,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
    )
    native_path = write_native_receipt(tmp_path / "native-org.json", native)
    before = _scheduled_identity(run_id)
    after = {
        **before,
        "installation_receipt_hash": "C" * 64,
    }
    with patch(
        "scripts.check_kb_skillguard._build_current_scheduled_production_identity",
        return_value=after,
    ), pytest.raises(RuntimeError, match="changed between native start"):
        _execute_supervision(
            skill_id,
            skill_root,
            codex_home,
            "installed",
            native_receipt_path=native_path,
            expected_native_run_id=run_id,
            expected_native_receipt_hash=str(native["receipt_hash"]),
            scheduled_production_identity=before,
        )


def test_supervision_reuses_start_frozen_identity_without_live_recheck(
    tmp_path: Path,
) -> None:
    skill_id = "kb-organization-contribute"
    codex_home = tmp_path / ".codex"
    skill_root = codex_home / "skills" / skill_id
    supervisor = (
        codex_home
        / "skills"
        / "skillguard"
        / "scripts"
        / "skillguard_supervise.py"
    )
    supervisor.parent.mkdir(parents=True)
    supervisor.write_text("# fixture\n", encoding="utf-8")
    skill_root.mkdir(parents=True)
    run_id = "scheduled-org-frozen-1"
    native = build_native_receipt(
        skill_id,
        run_id=run_id,
        command=["fixture-native-org"],
        native_payload=build_fixture_payload(skill_id, run_id=run_id),
        exit_code=0,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
    )
    native_path = write_native_receipt(tmp_path / "native-org-frozen.json", native)
    identity = _scheduled_identity(run_id)
    session = object.__new__(_InstalledSupervisionSession)
    session.identity = dict(identity)
    session.snapshot = {
        "schema_version": "khaos-brain.scheduled-supervision-start-snapshot.v1",
        "authority_frozen_before_native": True,
    }
    session._closed = True
    session._stderr_handle = SimpleNamespace(close=lambda: None)
    frozen_identity = _ScheduledProductionIdentity(identity, session)

    with patch(
        "scripts.check_kb_skillguard._build_current_scheduled_production_identity",
        side_effect=AssertionError("live currentness must not be reloaded"),
    ) as live_builder, patch(
        "scripts.check_kb_skillguard._supervision_packet",
        side_effect=RuntimeError("reached-packet-with-frozen-session"),
    ), pytest.raises(RuntimeError, match="reached-packet-with-frozen-session"):
        _execute_supervision(
            skill_id,
            skill_root,
            codex_home,
            "installed",
            native_receipt_path=native_path,
            expected_native_run_id=run_id,
            expected_native_receipt_hash=str(native["receipt_hash"]),
            scheduled_production_identity=frozen_identity,
        )

    live_builder.assert_not_called()


def test_update_functions_are_mutually_composable_for_final_supervision() -> None:
    compiled = _load_json(
        REPO_ROOT
        / ".agents"
        / "skills"
        / "khaos-brain-update"
        / ".skillguard"
        / "compiled-contract.json"
    )
    functions = {
        row["function_id"]: row
        for row in compiled["functions"]
    }
    authorize = "function:khaos-brain-update:authorize"
    finalize = "function:khaos-brain-update:finalize"
    assert set(functions[authorize]["composable_with"]) == {finalize}
    assert set(functions[finalize]["composable_with"]) == {authorize}


def test_native_output_witness_is_pre_materialized_and_hash_bound(tmp_path: Path) -> None:
    receipt = tmp_path / "native-receipt.json"
    receipt.write_text('{"ok":true}\n', encoding="utf-8")
    witness = _native_output_witness(
        artifact_id="artifact:test:native-receipt",
        run_id="run-test",
        receipt_hash="ABC123",
        receipt_path=receipt,
        executor_id="native-owner",
    )
    assert witness["witness_kind"] == "native_output"
    assert witness["output"] == {"receipt_hash": "ABC123"}
    assert witness["witness_id"].startswith("native-output-")
    assert witness["input_fingerprint"]
    assert witness["output_fingerprint"]


def test_contribution_runtime_rejects_push_before_check_or_unreleased_lane() -> None:
    skill_id = "kb-organization-contribute"
    payload = build_fixture_payload(skill_id, shallow=False)
    payload["requested_actions"] = {"prepare_branch": True, "commit": True, "push": True}
    payload["outbox"]["pending_count"] = 1
    payload["branch"] = {
        "attempted": True,
        "ok": True,
        "organization_check": {"ok": False, "auto_merge_eligible": True},
        "restore_base": {"ok": False},
        "push": {"pushed": False},
        "pull_request": {"attempted": False, "ok": True},
    }
    payload["lock_release"] = {"ok": False}

    report = evaluate_native_payload(skill_id, payload, exit_code=0)

    assert not report["ok"], report
    evidence = report["evidence"]
    assert not evidence[obligation_id(skill_id, "branch-pr-auto-merge")]["ok"]
    assert not evidence[obligation_id(skill_id, "lane-failure-recovery")]["ok"]


def test_maintenance_runtime_rejects_forged_exact_apply_skill_blocker_and_missing_label() -> None:
    skill_id = "kb-organization-maintenance"
    payload = build_fixture_payload(skill_id, shallow=False)
    cleanup = payload["report"]["cleanup"]
    cleanup["review"]["selected_action_ids"] = ["action-a"]
    cleanup["apply"] = {
        "attempted": True,
        "ok": True,
        "applied_action_ids": [],
    }
    cleanup["exact_selected_apply"] = {
        "complete": True,
        "exact": True,
        "selected_action_ids": ["action-a"],
        "applied_action_ids": [],
    }
    cleanup["skill_safety_checkpoint"]["blocking_decision_ids"] = ["fork-required"]
    cleanup["github_merge_readiness"] = {
        "complete": True,
        "eligible": True,
        "label": "org-kb:auto-merge",
    }
    payload["maintenance_branch"] = {
        "ok": True,
        "push": {
            "pull_request": {
                "attempted": True,
                "ok": True,
                "labels": [],
            }
        },
    }
    payload["lock_release"] = {"ok": False}

    report = evaluate_native_payload(skill_id, payload, exit_code=0)

    assert not report["ok"], report
    evidence = report["evidence"]
    assert not evidence[obligation_id(skill_id, "skill-safety-version")]["ok"]
    assert not evidence[obligation_id(skill_id, "exact-selected-apply")]["ok"]
    assert not evidence[obligation_id(skill_id, "postapply-merge-readiness")]["ok"]
    assert not evidence[obligation_id(skill_id, "postflight-terminal")]["ok"]


def test_contribution_runtime_requires_github_pr_and_actual_label_after_push() -> None:
    skill_id = "kb-organization-contribute"
    payload = build_fixture_payload(skill_id, shallow=False)
    payload["source"] = {"repo_url": "https://github.com/example/org-kb.git"}
    payload["requested_actions"] = {"prepare_branch": True, "commit": True, "push": True}
    payload["outbox"]["pending_count"] = 1
    payload["branch"] = {
        "attempted": True,
        "ok": True,
        "organization_check": {"ok": True, "auto_merge_eligible": True},
        "restore_base": {"ok": True},
        "push": {"pushed": True},
        "pull_request": {"attempted": False, "ok": True, "labels": []},
    }

    report = evaluate_native_payload(skill_id, payload, exit_code=0)

    assert not report["ok"], report
    assert not report["evidence"][obligation_id(skill_id, "branch-pr-auto-merge")]["ok"]


def test_maintenance_runtime_cross_checks_proposal_counts_and_github_label_receipt() -> None:
    skill_id = "kb-organization-maintenance"
    payload = build_fixture_payload(skill_id, shallow=False)
    payload["source"] = {"repo_url": "https://github.com/example/org-kb.git"}
    cleanup = payload["report"]["cleanup"]
    cleanup["proposal_counts"] = {
        "merge-cards": 1,
        "split-card": 1,
        "skill-bundle-fork-required": 1,
    }
    cleanup["card_decision_checkpoint"].update(
        {"complete": True, "card_count": 1, "decision_count": 0, "decision_ids": [], "decisions": []}
    )
    cleanup["merge_split_checkpoint"]["merge_decision_ids"] = []
    cleanup["merge_split_checkpoint"]["split_decision_ids"] = []
    cleanup["skill_safety_checkpoint"].update(
        {"passed": True, "decision_ids": [], "blocking_decision_ids": []}
    )
    cleanup["github_merge_readiness"] = {
        "complete": True,
        "eligible": True,
        "label": "org-kb:auto-merge",
    }
    payload["maintenance_branch"] = {
        "ok": True,
        "push": {
            "pushed": True,
            "pull_request": {"attempted": False, "ok": True, "labels": []},
        },
    }

    report = evaluate_native_payload(skill_id, payload, exit_code=0)

    assert not report["ok"], report
    evidence = report["evidence"]
    assert not evidence[obligation_id(skill_id, "card-decision-coverage")]["ok"]
    assert not evidence[obligation_id(skill_id, "merge-split-decisions")]["ok"]
    assert not evidence[obligation_id(skill_id, "skill-safety-version")]["ok"]
    assert not evidence[obligation_id(skill_id, "postapply-merge-readiness")]["ok"]


def test_update_runtime_rejects_arbitrary_noop_reason_without_system_gate() -> None:
    skill_id = "khaos-brain-update"
    payload = {
        "ok": True,
        "status": "no-op",
        "reason": "trust-me-no-update",
        "system_check": {},
    }

    report = evaluate_native_payload(skill_id, payload, exit_code=0)

    assert not report["ok"], report
    assert report["terminal_status"] == "failed"


def test_update_runtime_rejects_rolled_back_or_mismatched_transactions() -> None:
    skill_id = "khaos-brain-update"
    payload = build_fixture_payload(skill_id, shallow=False)
    payload["install"]["paused_install_transaction"].update({"ok": False})
    payload["install"]["install_transaction"].update({"ok": False, "status": "rolled_back"})
    payload["install"]["history_migration"] = {"ok": False, "status": "current"}
    payload["install_check"]["install_transaction"]["transaction_id"] = "different-transaction"

    report = evaluate_native_payload(skill_id, payload, exit_code=0)

    assert not report["ok"], report
    evidence = report["evidence"]
    assert not evidence[obligation_id(skill_id, "preserve-state-rollback")]["ok"]
    assert not evidence[obligation_id(skill_id, "migration-debt-settlement")]["ok"]
    assert not evidence[obligation_id(skill_id, "transaction-retirement")]["ok"]
    assert not evidence[obligation_id(skill_id, "aggregate-hard-gates")]["ok"]


def test_native_receipt_rejects_fake_command_and_payload_run_id_mismatch() -> None:
    skill_id = "kb-sleep-maintenance"
    run_id = "scheduled-run"
    payload = build_fixture_payload(skill_id, run_id="different-run")
    receipt = build_native_receipt(
        skill_id,
        run_id=run_id,
        command=["fake", "not-the-native-entrypoint.py", "--run-id", run_id, "--json"],
        native_payload=payload,
        exit_code=0,
        started_at="2026-01-01T00:00:00+00:00",
    )
    assert receipt["terminal_status"] == "failed"
    assert any("native-run-id-mismatch" in item for item in receipt["evaluation_issues"])
    assert any("native-entrypoint-mismatch" in item for item in receipt["evaluation_issues"])


def test_fixture_receipt_cannot_be_used_as_a_scheduled_receipt() -> None:
    skill_id = "kb-dream-pass"
    run_id = "fixture-positive-kb-dream-pass"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "native-receipt.json"
        receipt = build_native_receipt(
            skill_id,
            run_id=run_id,
            command=["fixture", "positive", skill_id],
            native_payload=build_fixture_payload(skill_id, run_id=run_id),
            exit_code=0,
            started_at="2026-01-01T00:00:00+00:00",
            fixture="positive",
        )
        write_native_receipt(path, receipt)
        report = validate_native_receipt(
            path,
            skill_id=skill_id,
            expected_run_id=run_id,
            expected_receipt_hash=receipt["receipt_hash"],
        )
    assert not report["ok"]
    assert "fixture-receipt-not-allowed-for-scheduled-run" in report["issues"]


def test_sleep_receipt_rejects_impossible_range_and_fake_backlog_convergence() -> None:
    skill_id = "kb-sleep-maintenance"
    payload = build_fixture_payload(skill_id, run_id="sleep-run")
    payload.update(
        {
            "input_watermark": 0,
            "output_watermark": 10,
            "consumed_range": {"inclusive_start": 999, "exclusive_end": -5},
            "opening_actionable_backlog": 0,
            "newly_admitted": 100,
            "terminally_disposed": 0,
            "explicitly_parked": 0,
            "closing_actionable_backlog": 0,
            "backlog_delta": -100,
            "disposition_ids": [],
            "lifecycle_review": {"ok": False},
        }
    )
    report = evaluate_native_payload(
        skill_id,
        payload,
        exit_code=0,
        expected_run_id="sleep-run",
    )
    assert not report["ok"]
    assert not report["evidence"][obligation_id(skill_id, "lane-delta-intake")]["ok"]
    assert not report["evidence"][obligation_id(skill_id, "observation-disposition")]["ok"]
    assert not report["evidence"][obligation_id(skill_id, "candidate-outcomes")]["ok"]


def test_dream_receipt_rejects_empty_fake_execution_and_unreleased_lane() -> None:
    skill_id = "kb-dream-pass"
    payload = build_fixture_payload(skill_id, run_id="dream-run")
    payload.update(
        {
            "opportunity_count": 0,
            "executable_opportunity_count": 0,
            "valuable_opportunity_count": 0,
            "evaluated_fingerprints": [],
            "evidence_deltas": [],
            "selected_experiment_count": 0,
            "experiments": [],
            "emitted_handoff_ids": [],
            "final_run_state": "completed",
            "lock_release": {"ok": True, "released": False},
        }
    )
    report = evaluate_native_payload(
        skill_id,
        payload,
        exit_code=0,
        expected_run_id="dream-run",
    )
    assert not report["ok"]
    assert not report["evidence"][obligation_id(skill_id, "no-delta-closure")]["ok"]
    assert not report["evidence"][obligation_id(skill_id, "terminal-receipt")]["ok"]


def test_dream_maintenance_lane_skip_is_not_success() -> None:
    skill_id = "kb-dream-pass"
    payload = {
        "run_id": "dream-lane-contention",
        "status": "skipped",
        "reason": "maintenance-lane-active",
        "lane_guard": {
            "lane": "kb-dream",
            "blocked": True,
            "blocking_lanes": ["kb-sleep"],
        },
        "terminal_gate": {
            "gate_id": "maintenance-lane",
            "evaluated": True,
            "applicable": False,
            "reason": "maintenance-lane-active",
        },
    }

    report = evaluate_native_payload(
        skill_id,
        payload,
        exit_code=0,
        expected_run_id="dream-lane-contention",
    )

    assert not report["ok"], report
    assert report["terminal_status"] == "failed"
    assert all(
        row["ok"] is False for row in report["evidence"].values()
    )


def test_contribution_receipt_rejects_count_forgery_and_unreleased_lane() -> None:
    skill_id = "kb-organization-contribute"
    payload = build_fixture_payload(skill_id, run_id="contribute-run")
    payload["outbox"]["created_count"] = 0
    payload["outbox"]["privacy_checkpoint"].update(
        {"reviewed_count": -1, "blocked_sensitive_count": -1}
    )
    payload["lock_release"] = {"ok": True, "released": False}
    report = evaluate_native_payload(
        skill_id,
        payload,
        exit_code=0,
        expected_run_id="contribute-run",
    )
    assert not report["ok"]
    assert not report["evidence"][obligation_id(skill_id, "privacy-shareability")]["ok"]
    assert not report["evidence"][obligation_id(skill_id, "content-hash-dedup")]["ok"]
    assert not report["evidence"][obligation_id(skill_id, "lane-failure-recovery")]["ok"]


def test_maintenance_receipt_rejects_duplicate_apply_and_duplicate_card_identity() -> None:
    skill_id = "kb-organization-maintenance"
    payload = build_fixture_payload(skill_id, run_id="maintenance-run")
    cleanup = payload["report"]["cleanup"]
    cleanup["apply"]["applied_action_ids"] = ["fixture-action", "fixture-action"]
    cleanup["exact_selected_apply"]["applied_action_ids"] = [
        "fixture-action",
        "fixture-action",
    ]
    duplicate = dict(cleanup["card_decision_checkpoint"]["decisions"][0])
    duplicate["decision_id"] = "second-decision"
    cleanup["card_decision_checkpoint"].update(
        {
            "card_count": 2,
            "decision_count": 2,
            "decision_ids": ["fixture-card-decision", "second-decision"],
            "decisions": [cleanup["card_decision_checkpoint"]["decisions"][0], duplicate],
        }
    )
    cleanup["merge_split_checkpoint"]["reviewed_card_count"] = 2
    payload["report"]["main_active_count"] = 2
    payload["maintenance_branch"].pop("restore_base")
    report = evaluate_native_payload(
        skill_id,
        payload,
        exit_code=0,
        expected_run_id="maintenance-run",
    )
    assert not report["ok"]
    assert not report["evidence"][obligation_id(skill_id, "card-decision-coverage")]["ok"]
    assert not report["evidence"][obligation_id(skill_id, "exact-selected-apply")]["ok"]
    assert not report["evidence"][obligation_id(skill_id, "postapply-merge-readiness")]["ok"]


def test_update_receipt_rejects_broad_retirement_and_state_snapshot_mismatch() -> None:
    skill_id = "khaos-brain-update"
    payload = build_fixture_payload(skill_id, run_id="update-run")
    payload["install"]["retired_skill_ids"].append("kb-architect-pass-personal")
    payload["install"]["automations"][0]["status"] = "PAUSED"
    report = evaluate_native_payload(
        skill_id,
        payload,
        exit_code=0,
        expected_run_id="update-run",
    )
    assert not report["ok"]
    assert not report["evidence"][obligation_id(skill_id, "transaction-retirement")]["ok"]
    assert not report["evidence"][obligation_id(skill_id, "restore-or-stay-paused")]["ok"]
