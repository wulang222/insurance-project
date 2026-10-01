import os

import pytest

from simple_agent.graph import graph

pytestmark = pytest.mark.anyio

if os.getenv("RUN_EXTERNAL_INTEGRATION_TESTS", "").lower() != "true":
    pytest.skip(
        "Set RUN_EXTERNAL_INTEGRATION_TESTS=true to run provider-backed tests.",
        allow_module_level=True,
    )


async def test_simple_agent_smoke() -> None:
    result = await graph.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "What is 19*3? Use tools if needed and answer with just the number.",
                }
            ]
        }
    )
    output_text = str(result["messages"][-1].content)
    assert "57" in output_text
