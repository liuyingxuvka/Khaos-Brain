from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from local_kb.automation_contracts import (
    AGGREGATE_SKILLGUARD_TIMEOUT_SECONDS,
    PRE_RESTORE_ASSURANCE_TIMEOUT_SECONDS,
    STANDARD_NATIVE_TIMEOUT_SECONDS,
    STANDARD_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS,
    UPDATE_NATIVE_TIMEOUT_SECONDS,
    UPDATE_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS,
)
from local_kb.process_control import run_with_timeout_cleanup


def test_timeout_hierarchy_preserves_cleanup_margin() -> None:
    assert STANDARD_NATIVE_TIMEOUT_SECONDS < STANDARD_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS
    assert UPDATE_NATIVE_TIMEOUT_SECONDS < UPDATE_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS
    assert STANDARD_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS < AGGREGATE_SKILLGUARD_TIMEOUT_SECONDS
    assert UPDATE_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS < AGGREGATE_SKILLGUARD_TIMEOUT_SECONDS
    assert AGGREGATE_SKILLGUARD_TIMEOUT_SECONDS < PRE_RESTORE_ASSURANCE_TIMEOUT_SECONDS


def test_timeout_terminates_the_complete_descendant_tree(tmp_path: Path) -> None:
    child_pid_path = tmp_path / "child.json"
    parent = (
        "import json,subprocess,sys,time; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        f"open({str(child_pid_path)!r},'w',encoding='utf-8').write(json.dumps({{'pid':child.pid}})); "
        "time.sleep(60)"
    )
    try:
        run_with_timeout_cleanup(
            [sys.executable, "-c", parent],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        cleanup = dict(getattr(exc, "cleanup_receipt", {}) or {})
    else:
        raise AssertionError("timeout fixture unexpectedly completed")

    assert child_pid_path.is_file()
    assert json.loads(child_pid_path.read_text(encoding="utf-8"))["pid"] in cleanup[
        "captured_process_ids"
    ]
    assert cleanup["remaining_process_count"] == 0
    assert cleanup["cleanup_confirmed"] is True
