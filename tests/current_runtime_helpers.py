from __future__ import annotations

from pathlib import Path
from typing import Any

from local_kb.maintenance_migration import migrate_legacy_card_generation
from local_kb.logicguard_models import authority_generation_pointer_path
from local_kb.maintenance_standard import (
    CURRENT_HISTORY_SCHEMA_VERSION,
    CURRENT_MAINTENANCE_STANDARD_VERSION,
    write_maintenance_state,
)
from local_kb.model_maintenance import publish_sleep_model_generation


def activate_current_kb_runtime(repo_root: Path) -> None:
    """Commit the only supported runtime authority for retrieval tests."""

    card_roots = [repo_root / "kb" / scope for scope in ("public", "private", "candidates")]
    has_cards = any(root.exists() and any(root.rglob("*.yaml")) for root in card_roots)
    if authority_generation_pointer_path(repo_root).exists():
        authority = publish_sleep_model_generation(
            repo_root,
            reason="test-current-runtime-refresh",
        )
    elif has_cards:
        authority = migrate_legacy_card_generation(repo_root)
    else:
        authority = publish_sleep_model_generation(repo_root, reason="test-current-runtime-empty")
    if not authority.get("ok"):
        raise RuntimeError(f"Unable to activate model-native test runtime: {authority}")

    write_maintenance_state(
        repo_root,
        {
            "maintenance_standard_version": CURRENT_MAINTENANCE_STANDARD_VERSION,
            "history_schema_version": CURRENT_HISTORY_SCHEMA_VERSION,
            "phase": "committed",
            "committed": True,
            "migration_id": "test-current-runtime",
        },
    )


def consolidate_current_history(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Run consolidation only after the test repository has current authority."""

    repo_root_value = kwargs.get("repo_root")
    if repo_root_value is None and args:
        repo_root_value = args[0]
    if repo_root_value is None:
        raise TypeError("repo_root is required")
    repo_root = Path(repo_root_value)
    activate_current_kb_runtime(repo_root)
    from local_kb.consolidate import consolidate_history

    return consolidate_history(*args, **kwargs)
