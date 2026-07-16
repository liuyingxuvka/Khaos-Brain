"""Resolve the one SkillGuard registry that is active for a Codex home."""

from __future__ import annotations

from pathlib import Path
import re


def discover_active_registry(codex_home: Path) -> Path:
    """Return only the registry projected by this Codex home's AGENTS file.

    Registries in unrelated repositories are historical or external state and
    cannot authorize routes—or block retirement—for this installation.
    """

    codex_home = Path(codex_home).resolve()
    agents = codex_home / "AGENTS.md"
    if agents.is_file():
        text = agents.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"^\s*-\s*registry_path:\s*(.+?)\s*$", text, re.MULTILINE)
        if match:
            raw = Path(match.group(1).strip())
            return raw if raw.is_absolute() else Path.home() / raw
    return codex_home / ".skillguard" / "global-router" / "global_registry.json"
