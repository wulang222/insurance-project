"""Load, validate, hash, and render versioned prompt files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PromptDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    role: str = Field(min_length=1)
    policy: list[str] = Field(default_factory=list)
    task: str = Field(min_length=1)
    input_contract: dict[str, Any]
    output_contract: dict[str, Any]
    examples: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def prompt_hash(self) -> str:
        canonical = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RenderedPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_id: str
    prompt_version: str
    prompt_hash: str
    text: str


class PromptRegistry:
    """In-memory immutable registry sourced from versioned JSON files."""

    def __init__(self, prompts: list[PromptDefinition]) -> None:
        definitions: dict[tuple[str, str], PromptDefinition] = {}
        for prompt in prompts:
            key = (prompt.id, prompt.version)
            if key in definitions:
                raise ValueError(f"duplicate prompt definition: {prompt.id}@{prompt.version}")
            definitions[key] = prompt
        self._definitions = definitions

    @classmethod
    def from_directory(cls, directory: str | Path) -> "PromptRegistry":
        root = Path(directory)
        prompts = [
            PromptDefinition.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(root.rglob("*.json"))
        ]
        if not prompts:
            raise ValueError(f"no prompt definitions found under {root}")
        return cls(prompts)

    @classmethod
    def default(cls) -> "PromptRegistry":
        return cls.from_directory(Path(__file__).resolve().parent)

    def get(self, name: str, version: str) -> PromptDefinition:
        try:
            return self._definitions[(name, version)]
        except KeyError as exc:
            raise KeyError(f"unknown prompt: {name}@{version}") from exc

    def render(
        self,
        name: str,
        version: str,
        variables: dict[str, Any],
    ) -> RenderedPrompt:
        definition = self.get(name, version)
        missing = set(definition.input_contract.get("required", [])) - variables.keys()
        if missing:
            raise ValueError(
                f"missing prompt variables for {name}@{version}: {sorted(missing)}"
            )
        try:
            task = definition.task.format_map(variables)
        except KeyError as exc:
            raise ValueError(f"missing prompt variable: {exc.args[0]}") from exc
        policy = "\n".join(f"- {item}" for item in definition.policy)
        examples = json.dumps(definition.examples, ensure_ascii=False, indent=2)
        text = (
            f"【角色】\n{definition.role}\n\n"
            f"【政策】\n{policy or '- 无'}\n\n"
            f"【任务】\n{task}\n\n"
            f"【输出契约】\n"
            f"{json.dumps(definition.output_contract, ensure_ascii=False)}\n\n"
            f"【示例】\n{examples}"
        )
        return RenderedPrompt(
            prompt_id=definition.id,
            prompt_version=definition.version,
            prompt_hash=definition.prompt_hash,
            text=text,
        )
