from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import check_chaos_brain_readiness as readiness


def test_readiness_planner_changes_launch_no_native_owner() -> None:
    assert readiness._SOURCE_COMPONENT_OWNER_EDGES["readiness_planner"] == frozenset()
    assert (
        readiness._classify_watched_source(
            Path("tests/test_chaos_brain_readiness_projection.py")
        )
        == "readiness_planner"
    )


def test_reused_receipt_projection_omits_oversized_json_payload(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    current_dir = tmp_path / "current"
    source_dir.mkdir()
    proof_path = source_dir / "proof.txt"
    proof_path.write_text("passed\n", encoding="utf-8")
    source_receipt = {
        "schema_version": readiness.EVIDENCE_SCHEMA,
        "receipt_id": "validation:flowguard_meshes:identity",
        "name": "flowguard_meshes",
        "execution": "executed",
        "identity_fingerprint": "identity",
        "inventory_revision": "old-inventory",
        "terminal_status": "passed",
        "timed_out": False,
        "cleanup_confirmed": True,
        "exit_code": 0,
        "ok": True,
        "json_payload": {"large": "x" * 1_100_000},
        "proof_artifact_ref": readiness._proof_ref(proof_path),
    }
    source_path = source_dir / "flowguard_meshes.receipt.json"
    source_path.write_text(
        json.dumps(source_receipt, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()

    projected = readiness._materialize_owner_reuse(
        {
            "receipt": source_receipt,
            "receipt_path": source_path,
            "receipt_sha256": source_hash,
            "current_manifest_path": source_dir / "current.json",
        },
        owner_name="flowguard_meshes",
        evidence_dir=current_dir,
        inventory_revision="new-inventory",
    )

    projected_path = Path(projected["receipt_path"])
    stored = json.loads(projected_path.read_text(encoding="utf-8"))
    assert projected["execution"] == "reused"
    assert stored["execution"] == "executed"
    assert stored["json_payload"] is None
    assert stored["json_payload_projection"]["status"] == "omitted-oversize"
    assert stored["compacted_from"]["receipt_sha256"] == source_hash
    assert projected_path.stat().st_size < 50_000
