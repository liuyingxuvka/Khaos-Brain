"""FlowGuard route/obligation binding for the Khaos Brain update Skill.

The parent convergence model owns executable update state and side effects.
This child owns the target Skill's explicit-manual topology: an authorized run
must proceed through update, validation, exact restoration, final installed
health, CURRENT state, and cleanup before its own terminal can succeed.
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
        "Require an explicit current-conversation request, keep all four retained automations paused during mutation, "
        "then let the native updater apply the exact captured state, read it back, run the final installed-health check, "
        "mark CURRENT, clean its snapshot, and emit its own terminal receipt.",
    )


if __name__ == "__main__":
    raise SystemExit(run_current_model_checks(export_contract_model()))
