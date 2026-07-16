from __future__ import annotations

import pytest

from scripts.check_retired_kb_architect import (
    REPO_ROOT,
    _active_architect_marker_matches,
    _active_text_violations,
)


@pytest.mark.parametrize(
    "active_surface",
    (
        "class ArchitectRollupBlock:",
        "class ArchitectOutletBlock:",
        'Event("architect_collect_sleep")',
        'Event("architect_ready_for_patch")',
        "architect_summary_status: str = 'none'",
        "architect_patch_debt = True",
        "def architect_complete_requires_sources(...):",
        '"architect_execution_outlet_gap"',
        "REQUIRED_ARCHITECT_REPORTS = ()",
        "bad_architect_summary_without_sources",
        "Architect-owned report aggregation",
    ),
)
def test_precise_active_architect_model_surfaces_are_rejected(active_surface: str) -> None:
    assert _active_architect_marker_matches(active_surface)


@pytest.mark.parametrize(
    "retirement_evidence",
    (
        "architect_present: bool = False",
        "architect_removed = True",
        "architect_retired_tombstone = 'verified'",
        "kb/history/architecture/maintenance_rollup.json",
        "Retired Architect provenance is retained for audit.",
        "ArchitectureDecisionRecord",
    ),
)
def test_historical_retirement_evidence_is_not_rejected(retirement_evidence: str) -> None:
    assert _active_architect_marker_matches(retirement_evidence) == ()


def test_current_models_have_only_generic_maintenance_runtime_roles() -> None:
    planned = (REPO_ROOT / ".flowguard" / "khaos_brain_planned_maintenance_flow.py").read_text(
        encoding="utf-8"
    )
    governance = (REPO_ROOT / ".flowguard" / "khaos_brain_governance_flow.py").read_text(
        encoding="utf-8"
    )

    assert "from flowguard.explorer import Explorer" in planned
    assert "SystemMaintenanceRollupBlock" in planned
    assert "MaintenanceChangeOutletBlock" in governance
    assert _active_architect_marker_matches(planned) == ()
    assert _active_architect_marker_matches(governance) == ()
    assert _active_text_violations() == []
