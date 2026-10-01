from __future__ import annotations

import json

import pytest

from prompts.registry import PromptRegistry


def test_registry_loads_versions_renders_and_hashes(tmp_path) -> None:
    path = tmp_path / "route.v1.json"
    path.write_text(
        json.dumps(
            {
                "id": "route",
                "version": "v1",
                "role": "router",
                "policy": ["json only"],
                "task": "route {question}",
                "input_contract": {"required": ["question"]},
                "output_contract": {"type": "object"},
                "examples": [],
            }
        ),
        encoding="utf-8",
    )
    registry = PromptRegistry.from_directory(tmp_path)
    rendered = registry.render("route", "v1", {"question": "hello"})

    assert rendered.prompt_version == "v1"
    assert len(rendered.prompt_hash) == 64
    assert "route hello" in rendered.text


def test_registry_rejects_missing_required_variable() -> None:
    registry = PromptRegistry.default()
    with pytest.raises(ValueError, match="missing prompt variables"):
        registry.render("supervisor.route", "v1", {})
