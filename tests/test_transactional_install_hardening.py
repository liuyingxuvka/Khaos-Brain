from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from local_kb.transactional_install import (
    COMMITTED_BACKUP_RETENTION,
    CONTROL_ROOT_NAME,
    install_managed_runtime,
    replay_install_receipt,
    tree_manifest,
)
from scripts.check_kb_automation_skillguard_depth import build_report


SKILL_ID = "kb-sleep-maintenance"
CHECK_ID = "check:kb-sleep-maintenance:native"
OBLIGATION_A = "obligation:kb-sleep-maintenance:complete-native-route"
OBLIGATION_B = "obligation:kb-sleep-maintenance:failure-closure"
REPO_ROOT = Path(__file__).resolve().parents[1]
AUTOMATION_SKILL_IDS = (
    "kb-sleep-maintenance",
    "kb-dream-pass",
    "kb-organization-contribute",
    "kb-organization-maintenance",
    "khaos-brain-update",
)
def _write_contract_skill(
    root: Path,
    *,
    marker: str = "fixture",
    obligations: tuple[str, ...] = (OBLIGATION_A,),
    check_args: tuple[str, ...] = ("scripts/check.py", "--all"),
    closure_obligations: tuple[str, ...] | None = None,
    depth_obligations: tuple[str, ...] | None = None,
    minimum_coverage: float = 1.0,
    check_count: int = 1,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(f"# {marker}\n", encoding="utf-8")
    contract_hash = hashlib.sha256(
        json.dumps(
            {
                "marker": marker,
                "obligations": obligations,
                "check_args": check_args,
                "closure": closure_obligations,
                "depth": depth_obligations,
                "minimum_coverage": minimum_coverage,
                "check_count": check_count,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest().upper()
    control = root / ".skillguard"
    control.mkdir()
    closure = closure_obligations if closure_obligations is not None else obligations
    depth = depth_obligations if depth_obligations is not None else obligations
    contract_source = {
        "schema_version": "skillguard.contract_source.v2",
        "skill_id": SKILL_ID,
    }
    check_ids = [CHECK_ID, *(f"{CHECK_ID}:extra-{index}" for index in range(1, check_count))]
    manifest = {
        "schema_version": "skillguard.check_manifest.v2",
        "skill_id": SKILL_ID,
        "contract_hash": contract_hash,
        "checks": [
            {
                "check_id": check_id,
                "kind": "command",
                "evidence_class": "hard",
                "covers_obligation_ids": list(obligations),
                "command": "python",
                "args": list(check_args),
                "cwd_token": "repository_root",
                "expected": {"exit_code": 0},
                "timeout_seconds": 120,
            }
            for check_id in check_ids
        ],
    }
    compiled = {
        "schema_version": "skillguard.compiled_contract.v2",
        "skill_id": SKILL_ID,
        "contract_hash": contract_hash,
        "obligations": [
            {
                "obligation_id": obligation_id,
                "invariant_id": obligation_id.replace("obligation:", "invariant:"),
                "required": True,
                "owner_step_ids": ["step:execute"],
                "required_check_ids": [CHECK_ID],
                "evidence_classes": ["hard"],
            }
            for obligation_id in obligations
        ],
        "closure_profiles": [
            {
                "profile_id": "enforced",
                "required_obligation_ids": list(closure),
            }
        ],
        "depth_profile": {
            "schema_version": "skillguard.depth_profile.v2",
            "profile_id": "profile:fixture-declared-check-supervision",
            "target_skill_id": SKILL_ID,
            "integration_mode": "native-integrated",
            "native_owner_id": SKILL_ID,
            "native_route_ids": [f"route:{SKILL_ID}:run"],
            "native_check_ids": check_ids,
            "skillguard_adds_domain_route": False,
            "enforcement_level": "enforced",
            "required_closure_profiles": ["enforced"],
            "provider_runtime": {
                "provider_id": "skillguard-local-provider",
                "required_runtime_contract_id": (
                    "skillguard-declared-check-supervision-current"
                ),
                "required_capability_ids": [
                    "declared-check-inventory.v1",
                    "declared-check-receipt-reconciliation.v1",
                    "installation-receipt-binding.v1",
                    "installation-currentness-replay.v1",
                    "provider-runtime-enrollment.v1",
                    "single-flight-check-execution.v1",
                ],
                "required_enrollment_status": "enrolled",
                "readiness_check_ids": check_ids,
            },
            "claim_boundary": "Exact current receipts for fixture-declared checks only.",
        },
    }
    compiled["checks"] = copy.deepcopy(manifest["checks"])
    contract_source["depth_profile"] = copy.deepcopy(compiled["depth_profile"])
    for filename, payload in (
        ("contract-source.json", contract_source),
        ("check-manifest.json", manifest),
        ("compiled-contract.json", compiled),
    ):
        (control / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
    return root


def _mutate_compiled_contract(root: Path, mutator) -> None:
    path = root / ".skillguard" / "compiled-contract.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutator(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _set_native_check_ids(root: Path, check_ids: tuple[str, ...]) -> None:
    for filename in ("contract-source.json", "compiled-contract.json"):
        path = root / ".skillguard" / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["depth_profile"]["native_check_ids"] = list(check_ids)
        payload["depth_profile"]["provider_runtime"][
            "readiness_check_ids"
        ] = list(check_ids)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )


def _split_native_check_coverage(root: Path) -> None:
    path = root / ".skillguard" / "check-manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["checks"][0]["covers_obligation_ids"] = [OBLIGATION_A]
    payload["checks"][1]["covers_obligation_ids"] = [OBLIGATION_B]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _configure_declared_check_removal(root: Path, *, incoming: bool) -> None:
    wrapper_id = f"{CHECK_ID}:extra-1"
    manifest_path = root / ".skillguard" / "check-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    wrapper = next(row for row in manifest["checks"] if row["check_id"] == wrapper_id)
    wrapper["evidence_domain_id"] = "target:fixture:conditional-finalization"
    wrapper["depends_on_check_ids"] = [CHECK_ID]
    wrapper["native_route_id"] = f"route:{SKILL_ID}:finalize"
    if incoming:
        manifest["checks"] = [
            row for row in manifest["checks"] if row["check_id"] != wrapper_id
        ]
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    for filename in ("contract-source.json", "compiled-contract.json"):
        path = root / ".skillguard" / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        depth = payload["depth_profile"]
        depth["native_route_ids"] = [f"route:{SKILL_ID}:run"]
        depth["native_check_ids"] = [CHECK_ID, *((() if incoming else (wrapper_id,)))]
        depth["provider_runtime"]["readiness_check_ids"] = list(
            depth["native_check_ids"]
        )
        if filename == "compiled-contract.json":
            payload["checks"] = copy.deepcopy(manifest["checks"])
            obligation = payload["obligations"][0]
            obligation["conditional"] = True
            obligation["required_check_ids"] = [
                CHECK_ID,
                *((() if incoming else (wrapper_id,))),
            ]
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )


def _renderer(payload: dict[str, object]) -> str:
    return f'id = "{payload["id"]}"\nstatus = "ACTIVE"\n'


def _validation_receipt(skill_root: Path, skill_id: str = SKILL_ID) -> dict[str, object]:
    control = skill_root / ".skillguard"
    compiled = json.loads((control / "compiled-contract.json").read_text(encoding="utf-8"))
    manifest = json.loads((control / "check-manifest.json").read_text(encoding="utf-8"))
    source_manifest = tree_manifest(skill_root)
    receipt: dict[str, object] = {
        "schema_version": "chaos_brain.skillguard_source_validation.v1",
        "skill_id": skill_id,
        "status": "current",
        "ok": True,
        "source_tree_digest": source_manifest["digest"],
        "contract_hash": compiled["contract_hash"],
        "manifest_hash": hashlib.sha256(
            (control / "check-manifest.json").read_bytes()
        ).hexdigest(),
        "contract_source_sha256": hashlib.sha256(
            (control / "contract-source.json").read_bytes()
        ).hexdigest(),
        "compiled_contract_sha256": hashlib.sha256(
            (control / "compiled-contract.json").read_bytes()
        ).hexdigest(),
        "check_manifest_sha256": hashlib.sha256(
            (control / "check-manifest.json").read_bytes()
        ).hexdigest(),
        "compiler_sha256": "1" * 64,
        "generator_sha256": "2" * 64,
        "generator_check_hash": "3" * 64,
    }
    receipt["validation_input_hash"] = _canonical_hash(receipt)
    receipt["receipt_hash"] = _canonical_hash(receipt)
    return receipt


def _install(
    repo_root: Path,
    codex_home: Path,
    source: Path,
    *,
    fail_after_activation: int | None = None,
    validation_receipt: dict[str, object] | None = None,
) -> dict[str, object]:
    return install_managed_runtime(
        repo_root=repo_root,
        codex_home=codex_home,
        global_skill_name="predictive-kb-preflight",
        global_skill_files={"SKILL.md": "# global\n"},
        skill_sources={SKILL_ID: source},
        skillguard_validation_receipts={
            SKILL_ID: (
                validation_receipt
                if validation_receipt is not None
                else _validation_receipt(source)
            )
        },
        automation_payloads={"kb-sleep": {"id": "kb-sleep"}},
        automation_renderer=_renderer,
        retired_skill_ids=("kb-architect-pass",),
        retired_automation_ids=("kb-architect",),
        fail_after_activation=fail_after_activation,
    )


def _canonical_hash(payload: object) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class TransactionalInstallHardeningTests(unittest.TestCase):
    def test_receipt_persists_replayable_source_stage_and_installed_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            source = _write_contract_skill(root / "source")

            result = _install(repo_root, codex_home, source)
            journal = json.loads(Path(result["journal_path"]).read_text(encoding="utf-8"))

            source_manifests = journal["source_manifests"]
            staged_manifests = journal["staged_manifests"]
            installed_manifests = journal["installed_manifests"]
            self.assertEqual(set(source_manifests), set(staged_manifests))
            self.assertEqual(set(staged_manifests), set(installed_manifests))
            for key in source_manifests:
                self.assertEqual(source_manifests[key], staged_manifests[key])
                self.assertEqual(staged_manifests[key], installed_manifests[key])
                self.assertTrue(installed_manifests[key]["files"])
            for operation in journal["operations"]:
                self.assertIn("post_manifest", operation)
                if operation["action"] == "replace":
                    key = f"{operation['kind']}:{operation['id']}"
                    self.assertEqual(installed_manifests[key], operation["post_manifest"])

            self.assertEqual(journal["receipt_payload"], result["receipt_payload"])
            self.assertEqual(_canonical_hash(journal["receipt_payload"]), journal["receipt_hash"])
            authority_receipt = journal["skillguard_authority_receipts"][SKILL_ID]
            self.assertEqual(
                "validated-current-replaces-non-current",
                authority_receipt["decision"],
            )
            self.assertEqual(
                "skillguard.managed-whole-tree-currentness.v1",
                authority_receipt["policy_id"],
            )
            self.assertEqual(
                source_manifests[f"skill:{SKILL_ID}"]["digest"],
                authority_receipt["incoming_validation"]["source_tree_digest"],
            )
            self.assertEqual([], authority_receipt["downgrade_reasons"])
            self.assertTrue(replay_install_receipt(journal)["ok"])

            tampered = copy.deepcopy(journal)
            key = sorted(tampered["receipt_payload"]["installed_manifests"])[0]
            tampered["receipt_payload"]["installed_manifests"][key]["digest"] = "tampered"
            replay = replay_install_receipt(tampered)
            self.assertFalse(replay["ok"])
            self.assertIn("receipt-hash-mismatch", replay["issues"])
            self.assertIn(f"manifest-parity-mismatch:{key}", replay["issues"])

            decision_tampered = copy.deepcopy(journal)
            decision_tampered["receipt_payload"]["skillguard_authority_receipts"][
                SKILL_ID
            ]["decision"] = "caller-authored-current"
            decision_tampered["receipt_hash"] = _canonical_hash(
                decision_tampered["receipt_payload"]
            )
            replay = replay_install_receipt(decision_tampered)
            self.assertFalse(replay["ok"])
            self.assertIn(
                f"skillguard-authority-decision-mismatch:{SKILL_ID}",
                replay["issues"],
            )

    def test_same_check_count_cannot_hide_obligation_or_check_loss(self) -> None:
        cases = (
            (
                "obligation",
                {"obligations": (OBLIGATION_B,)},
                "obligation:",
            ),
            (
                "check",
                {"check_args": ("scripts/check.py", "--shallow")},
                "changed-args",
            ),
        )
        for label, incoming_kwargs, expected_reason in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo_root = root / "repo"
                codex_home = root / ".codex"
                repo_root.mkdir()
                baseline = _write_contract_skill(
                    root / "baseline",
                    marker="baseline",
                )
                _install(repo_root, codex_home, baseline)
                active = codex_home / "skills" / SKILL_ID
                source = _write_contract_skill(
                    root / "source",
                    marker="incoming",
                    **incoming_kwargs,
                )

                with self.assertRaisesRegex(RuntimeError, "SkillGuard downgrade blocked") as caught:
                    _install(repo_root, codex_home, source)

                self.assertIn(expected_reason, str(caught.exception))
                self.assertIn("baseline", (active / "SKILL.md").read_text(encoding="utf-8"))
                self.assertFalse(any((codex_home / CONTROL_ROOT_NAME / "staging").iterdir()))

    def test_non_current_enforced_closure_or_profile_is_blocked_before_install(self) -> None:
        for label in ("closure", "profile"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo_root = root / "repo"
                codex_home = root / ".codex"
                repo_root.mkdir()
                source = _write_contract_skill(
                    root / "source",
                    obligations=(OBLIGATION_A, OBLIGATION_B),
                    closure_obligations=(
                        (OBLIGATION_A,)
                        if label == "closure"
                        else (OBLIGATION_A, OBLIGATION_B)
                    ),
                )
                if label == "profile":
                    for filename in (
                        "contract-source.json",
                        "compiled-contract.json",
                    ):
                        path = source / ".skillguard" / filename
                        payload = json.loads(path.read_text(encoding="utf-8"))
                        payload["depth_profile"]["enforcement_level"] = "advisory"
                        path.write_text(
                            json.dumps(payload, indent=2, sort_keys=True),
                            encoding="utf-8",
                        )
                with self.assertRaisesRegex(
                    RuntimeError, "lacks current validated SkillGuard authority"
                ):
                    _install(repo_root, codex_home, source)

    def test_native_check_reorganization_is_allowed_when_semantic_coverage_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            baseline = _write_contract_skill(
                root / "baseline",
                marker="baseline",
                obligations=(OBLIGATION_A, OBLIGATION_B),
                check_count=2,
            )
            _install(repo_root, codex_home, baseline)
            source = _write_contract_skill(
                root / "source",
                marker="incoming",
                obligations=(OBLIGATION_A, OBLIGATION_B),
                check_count=2,
            )
            _set_native_check_ids(source, (CHECK_ID,))

            result = _install(repo_root, codex_home, source)

            authority = result["skillguard_authority_receipts"][SKILL_ID]
            self.assertEqual("validated-current-replaces-current", authority["decision"])
            self.assertTrue(authority["semantic_comparison_performed"])
            self.assertEqual([], authority["downgrade_reasons"])
            self.assertIn(
                "incoming",
                (codex_home / "skills" / SKILL_ID / "SKILL.md").read_text(
                    encoding="utf-8"
                ),
            )

    def test_native_check_reorganization_is_blocked_when_obligation_coverage_is_lost(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            baseline = _write_contract_skill(
                root / "baseline",
                marker="baseline",
                obligations=(OBLIGATION_A, OBLIGATION_B),
                check_count=2,
            )
            source = _write_contract_skill(
                root / "source",
                marker="incoming",
                obligations=(OBLIGATION_A, OBLIGATION_B),
                check_count=2,
            )
            _split_native_check_coverage(baseline)
            _split_native_check_coverage(source)
            _install(repo_root, codex_home, baseline)
            _set_native_check_ids(source, (CHECK_ID,))

            with self.assertRaisesRegex(
                RuntimeError, "lost-native-obligation-coverage"
            ):
                _install(repo_root, codex_home, source)

            self.assertIn(
                "baseline",
                (codex_home / "skills" / SKILL_ID / "SKILL.md").read_text(
                    encoding="utf-8"
                ),
            )

    def test_declared_check_removal_is_blocked_even_with_overlapping_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            baseline = _write_contract_skill(
                root / "baseline", marker="baseline", check_count=2
            )
            source = _write_contract_skill(
                root / "source", marker="incoming", check_count=2
            )
            _configure_declared_check_removal(baseline, incoming=False)
            _configure_declared_check_removal(source, incoming=True)
            _install(repo_root, codex_home, baseline)

            with self.assertRaisesRegex(
                RuntimeError, "SkillGuard downgrade blocked"
            ):
                _install(repo_root, codex_home, source)

    def test_declared_check_removal_and_owner_change_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            baseline = _write_contract_skill(
                root / "baseline", marker="baseline", check_count=2
            )
            source = _write_contract_skill(
                root / "source", marker="incoming", check_count=2
            )
            _configure_declared_check_removal(baseline, incoming=False)
            _configure_declared_check_removal(source, incoming=True)
            manifest_path = source / ".skillguard" / "check-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["checks"][0]["args"] = ["scripts/check.py", "--shallow"]
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
            )
            _install(repo_root, codex_home, baseline)

            with self.assertRaisesRegex(RuntimeError, "SkillGuard downgrade blocked"):
                _install(repo_root, codex_home, source)

    def test_validated_current_automations_replace_non_current_managed_trees_whole(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            skill_sources: dict[str, Path] = {}
            validations: dict[str, dict[str, object]] = {}
            for skill_id in AUTOMATION_SKILL_IDS:
                source = REPO_ROOT / ".agents" / "skills" / skill_id
                skill_sources[skill_id] = source
                validations[skill_id] = _validation_receipt(source, skill_id)
                active = codex_home / "skills" / skill_id
                active.mkdir(parents=True)
                (active / "SKILL.md").write_text("# opaque old managed tree\n", encoding="utf-8")
                (active / "FORMER_RUNTIME_SENTINEL.txt").write_text(
                    "old-only", encoding="utf-8"
                )

            result = install_managed_runtime(
                repo_root=repo_root,
                codex_home=codex_home,
                global_skill_name="predictive-kb-preflight",
                global_skill_files={"SKILL.md": "# global\n"},
                skill_sources=skill_sources,
                skillguard_validation_receipts=validations,
                automation_payloads={"kb-sleep": {"id": "kb-sleep"}},
                automation_renderer=_renderer,
                retired_skill_ids=("kb-architect-pass",),
                retired_automation_ids=("kb-architect",),
            )

            for skill_id in AUTOMATION_SKILL_IDS:
                authority = result["skillguard_authority_receipts"][skill_id]
                self.assertEqual(
                    "validated-current-replaces-non-current", authority["decision"]
                )
                self.assertFalse(authority["semantic_comparison_performed"])
                self.assertFalse(
                    authority["active_confirmation"]["confirmed_current"]
                )
                self.assertEqual([], authority["downgrade_reasons"])
                self.assertNotIn("migration_policy_id", authority)
                self.assertNotIn("migration_proof", authority)
                installed = codex_home / "skills" / skill_id
                self.assertFalse((installed / "FORMER_RUNTIME_SENTINEL.txt").exists())
                self.assertEqual(
                    tree_manifest(skill_sources[skill_id])["digest"],
                    tree_manifest(installed)["digest"],
                )
            journal = json.loads(Path(result["journal_path"]).read_text(encoding="utf-8"))
            self.assertTrue(replay_install_receipt(journal)["ok"])

    def test_unvalidated_or_validation_stale_incoming_is_blocked_before_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            source = _write_contract_skill(root / "source")
            with self.assertRaisesRegex(RuntimeError, "inventory does not match"):
                install_managed_runtime(
                    repo_root=repo_root,
                    codex_home=codex_home,
                    global_skill_name="predictive-kb-preflight",
                    global_skill_files={"SKILL.md": "# global\n"},
                    skill_sources={SKILL_ID: source},
                    skillguard_validation_receipts={},
                    automation_payloads={"kb-sleep": {"id": "kb-sleep"}},
                    automation_renderer=_renderer,
                    retired_skill_ids=("kb-architect-pass",),
                    retired_automation_ids=("kb-architect",),
                )
            stale_validation = _validation_receipt(source)
            (source / "SKILL.md").write_text("# changed after validation\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "validation-source-tree-digest-mismatch"):
                _install(
                    repo_root,
                    codex_home,
                    source,
                    validation_receipt=stale_validation,
                )
            self.assertFalse((codex_home / "skills" / SKILL_ID).exists())
    def test_target_specific_shallow_runtime_fails_exactly_one_declared_gap(self) -> None:
        report = build_report(SKILL_ID, "shallow")

        self.assertTrue(report["ok"], report)
        self.assertEqual("shallow-blocked", report["observed_status"])
        self.assertEqual(report["findings"], [])
        self.assertEqual(
            set(report["failed_obligation_ids"]),
            {
                "obligation:kb-sleep-maintenance:atomic-model-generation",
                "obligation:kb-sleep-maintenance:index-watermark-commit",
            },
        )

    def test_stage_and_failed_backup_roots_are_cleaned_before_and_after_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            invalid_source = root / "invalid-source"
            invalid_source.mkdir()
            (invalid_source / "SKILL.md").write_text("# invalid\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "lacks current validated SkillGuard"):
                _install(
                    repo_root,
                    codex_home,
                    invalid_source,
                    validation_receipt={},
                )

            control = codex_home / CONTROL_ROOT_NAME
            self.assertEqual([], list((control / "staging").iterdir()))
            self.assertEqual([], list((control / "backups").iterdir()))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            source = _write_contract_skill(root / "source")
            active_global = codex_home / "skills" / "predictive-kb-preflight"
            active_global.mkdir(parents=True)
            (active_global / "old.txt").write_text("old-good", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "Injected installation failure"):
                _install(repo_root, codex_home, source, fail_after_activation=1)

            control = codex_home / CONTROL_ROOT_NAME
            self.assertEqual("old-good", (active_global / "old.txt").read_text(encoding="utf-8"))
            self.assertEqual([], list((control / "staging").iterdir()))
            self.assertEqual([], list((control / "backups").iterdir()))
            journal_paths = list((control / "transactions").glob("*.json"))
            self.assertEqual(1, len(journal_paths))
            journal = json.loads(journal_paths[0].read_text(encoding="utf-8"))
            self.assertEqual("rolled_back", journal["status"])
            self.assertTrue(journal["stage_cleanup"]["ok"])
            self.assertTrue(journal["failed_backup_cleanup"]["ok"])

    def test_incomplete_journal_recovers_active_tree_and_removes_its_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            source = _write_contract_skill(root / "source")
            control = codex_home / CONTROL_ROOT_NAME
            transaction_id = "interrupted-fixture"
            active = codex_home / "skills" / "recover-me"
            backup = control / "backups" / transaction_id / "skill" / "recover-me"
            stage = control / "staging" / transaction_id
            active.mkdir(parents=True)
            backup.mkdir(parents=True)
            stage.mkdir(parents=True)
            (active / "value.txt").write_text("partial-new", encoding="utf-8")
            (backup / "value.txt").write_text("old-good", encoding="utf-8")
            (stage / "orphan.txt").write_text("stage-copy", encoding="utf-8")
            journal_path = control / "transactions" / f"{transaction_id}.json"
            journal_path.parent.mkdir(parents=True)
            journal_path.write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "transaction_id": transaction_id,
                        "status": "activating",
                        "stage_root": str(stage),
                        "operations": [
                            {
                                "active_path": str(active),
                                "backup_path": str(backup),
                                "had_active": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = _install(repo_root, codex_home, source)

            self.assertEqual("old-good", (active / "value.txt").read_text(encoding="utf-8"))
            self.assertFalse(stage.exists())
            self.assertFalse((control / "backups" / transaction_id).exists())
            self.assertIn(transaction_id, result["recovered_transactions"])
            recovered = json.loads(journal_path.read_text(encoding="utf-8"))
            self.assertEqual("recovered", recovered["status"])
            self.assertTrue(recovered["stage_cleanup"]["ok"])
            self.assertTrue(recovered["failed_backup_cleanup"]["ok"])

    def test_repeated_commits_keep_bounded_backups_with_hashed_retention_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            codex_home = root / ".codex"
            repo_root.mkdir()
            source = _write_contract_skill(root / "source", marker="version-0")
            results = []
            for index in range(COMMITTED_BACKUP_RETENTION + 4):
                (source / "SKILL.md").write_text(f"# version-{index}\n", encoding="utf-8")
                results.append(_install(repo_root, codex_home, source))

            control = codex_home / CONTROL_ROOT_NAME
            backup_roots = list((control / "backups").iterdir())
            self.assertLessEqual(len(backup_roots), COMMITTED_BACKUP_RETENTION)
            self.assertTrue(Path(results[-1]["backup_root"]).exists())
            journals = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (control / "transactions").glob("*.json")
            ]
            self.assertEqual(COMMITTED_BACKUP_RETENTION + 4, len(journals))
            self.assertTrue(all(journal["status"] == "committed" for journal in journals))
            self.assertTrue(any(journal["backup_retention"]["pruned_count"] for journal in journals))

            latest = json.loads(Path(results[-1]["journal_path"]).read_text(encoding="utf-8"))
            retention = latest["backup_retention"]
            self.assertTrue(retention["bounded"])
            self.assertEqual(COMMITTED_BACKUP_RETENTION, retention["limit"])
            self.assertLessEqual(retention["retained_count"], retention["limit"])
            self.assertTrue(replay_install_receipt(latest)["ok"])

            tampered = copy.deepcopy(latest)
            tampered["receipt_payload"]["backup_retention"]["limit"] += 1
            replay = replay_install_receipt(tampered)
            self.assertFalse(replay["ok"])
            self.assertIn("receipt-hash-mismatch", replay["issues"])


if __name__ == "__main__":
    unittest.main()
