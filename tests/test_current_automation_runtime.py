from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_kb.install import (
    AUTOMATION_MODEL_ENV_VAR,
    AUTOMATION_REASONING_EFFORT_ENV_VAR,
    resolve_automation_runtime,
)


def _clear_runtime_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(AUTOMATION_MODEL_ENV_VAR, raising=False)
    monkeypatch.delenv(AUTOMATION_REASONING_EFFORT_ENV_VAR, raising=False)


def test_current_provider_metadata_selects_highest_version_and_deepest_effort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_runtime_overrides(monkeypatch)
    (tmp_path / "models_cache.json").write_text(
        json.dumps(
            {
                "models": [
                    {
                        "slug": "gpt-5.5",
                        "supported_reasoning_levels": [{"effort": "high"}],
                    },
                    {
                        "slug": "gpt-5.6-sol",
                        "supported_reasoning_levels": [
                            {"effort": "medium"},
                            {"effort": "xhigh"},
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    runtime = resolve_automation_runtime(tmp_path)

    assert runtime["model"] == "gpt-5.6-sol"
    assert runtime["reasoning_effort"] == "xhigh"


def test_missing_current_model_authority_is_visible_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_runtime_overrides(monkeypatch)

    with pytest.raises(RuntimeError, match="cannot be resolved"):
        resolve_automation_runtime(tmp_path)


def test_stale_configured_model_is_not_used_as_an_alternate_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_runtime_overrides(monkeypatch)
    (tmp_path / "config.toml").write_text(
        'model = "gpt-retired"\nmodel_reasoning_effort = "high"\n',
        encoding="utf-8",
    )
    (tmp_path / "models_cache.json").write_text(
        json.dumps(
            {
                "models": [
                    {
                        "slug": "vendor-current",
                        "supported_reasoning_levels": [{"effort": "high"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="not present in current provider metadata"):
        resolve_automation_runtime(tmp_path)
