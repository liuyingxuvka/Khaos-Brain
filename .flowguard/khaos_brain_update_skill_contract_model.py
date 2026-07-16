"""FlowGuard route/obligation binding for the Khaos Brain update Skill.

The parent convergence model owns executable update state and side effects.
This child owns only the target Skill's two-route topology: authorization emits
a non-terminal declared-check receipt and no closure; legal no-op completion or
composed finalization emits the sole ``enforced`` closure before native restore.
"""

from __future__ import annotations

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))

from kb_skill_contract_model_common import (  # noqa: E402
    build_contract_model,
    run_current_model_checks,
)


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


def export_contract_model():
    return build_contract_model(
        "khaos-brain-update",
        "Keep all retained automations paused while target-owned update checks are "
        "reconciled; stage exact restoration, obtain the sole enforced closure, "
        "then let the native updater apply, read back, install-check, and mark CURRENT.",
    )


if __name__ == "__main__":
    raise SystemExit(run_current_model_checks(export_contract_model()))
