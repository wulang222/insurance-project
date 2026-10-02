from __future__ import annotations

import pytest
from pydantic import BaseModel

from harness.errors import PolicyDeniedError
from middleware.model import ModelCallContext, ModelGateway, ModelRequest
from prompts.registry import PromptDefinition, PromptRegistry


class Decision(BaseModel):
    route: str


class Response:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage_metadata = {"input_tokens": 5, "output_tokens": 3}


class SequenceModel:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    async def ainvoke(self, prompt: str) -> Response:
        del prompt
        response = Response(self.responses[self.calls])
        self.calls += 1
        return response


def registry() -> PromptRegistry:
    return PromptRegistry(
        [
            PromptDefinition(
                id="test.route",
                version="v1",
                role="router",
                policy=["json only"],
                task="route {question}",
                input_contract={"required": ["question"]},
                output_contract={"type": "object"},
                examples=[],
            )
        ]
    )


def versioned_registry() -> PromptRegistry:
    return PromptRegistry(
        [
            PromptDefinition(
                id="test.route",
                version=version,
                role="router",
                policy=["json only"],
                task=f"{version} route {{question}}",
                input_contract={"required": ["question"]},
                output_contract={"type": "object"},
                examples=[],
            )
            for version in ("v1", "v2")
        ]
    )


def context(limit: int = 4) -> ModelCallContext:
    return ModelCallContext(request_id="request-1", run_id="run-1", max_model_calls=limit)


@pytest.mark.asyncio
async def test_bad_json_is_repaired_exactly_once() -> None:
    model = SequenceModel(["not json", '{"route":"knowledge_agent"}'])
    gateway = ModelGateway(lambda **_: model, registry())
    result = await gateway.invoke(
        ModelRequest(
            prompt_id="test.route",
            variables={"question": "等待期"},
            strategy="route",
            response_model=Decision,
        ),
        context=context(),
    )
    assert result.data.route == "knowledge_agent"
    assert result.repaired is True
    assert model.calls == 2
    assert gateway.audit_events[-1].prompt_version == "v1"
    assert gateway.audit_events[-1].input_tokens == 10
    assert gateway.audit_events[-1].output_tokens == 6


@pytest.mark.asyncio
async def test_model_budget_ends_run_before_provider_call() -> None:
    model = SequenceModel(["ok"])
    gateway = ModelGateway(lambda **_: model, registry())
    request = ModelRequest(
        prompt_id="test.route",
        variables={"question": "hello"},
        strategy="route",
    )
    await gateway.invoke(request, context=context(limit=1))
    with pytest.raises(PolicyDeniedError, match="budget"):
        await gateway.invoke(request, context=context(limit=1))
    assert model.calls == 1


@pytest.mark.asyncio
async def test_recommendation_uses_primary_then_fallback_on_transient_failure() -> None:
    created: list[str] = []

    class FailingModel:
        async def ainvoke(self, prompt: str) -> Response:
            del prompt
            raise OSError("temporary network failure")

    fallback = SequenceModel(["safe answer"])

    def factory(*, model: str, temperature: float):
        del temperature
        created.append(model)
        return FailingModel() if model == "primary" else fallback

    gateway = ModelGateway(
        factory,
        registry(),
        primary_model="primary",
        fallback_model="fallback",
        max_retries=0,
    )
    result = await gateway.invoke(
        ModelRequest(
            prompt_id="test.route",
            variables={"question": "recommend"},
            strategy="recommend",
        ),
        context=context(),
    )
    assert result.data == "safe answer"
    assert result.fallback_used is True
    assert created == ["primary", "fallback"]


@pytest.mark.asyncio
async def test_replay_context_overrides_prompt_version_and_model_policy() -> None:
    created: list[str] = []
    sequence_model = SequenceModel(['{"route":"knowledge_agent"}'])

    def factory(*, model: str, temperature: float):
        del temperature
        created.append(model)
        return sequence_model

    gateway = ModelGateway(
        factory,
        versioned_registry(),
        primary_model="primary",
        low_cost_model="cheap-model",
    )
    result = await gateway.invoke(
        ModelRequest(
            prompt_id="test.route",
            variables={"question": "等待期"},
            strategy="recommend",
            response_model=Decision,
        ),
        context=ModelCallContext(
            request_id="request-1",
            run_id="replay-1",
            model_policy="cheap",
            prompt_versions={"test": "v2"},
        ),
    )

    assert result.prompt_version == "v2"
    assert result.model_name == "cheap-model"
    assert created == ["cheap-model"]
