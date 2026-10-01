"""Deterministic graph fixtures for durable runtime integration tests."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.store.memory import InMemoryStore
from langgraph.types import interrupt

from harness.runtime import RunManager


class ResumeState(TypedDict, total=False):
    messages: list
    user_id: str
    age: int
    final_answer: str
    handled_by: str


def build_resume_graph(checkpointer: Any):
    async def collect_age(state: ResumeState) -> dict:
        age = state.get("age")
        if age is None:
            payload = interrupt(
                {
                    "type": "missing_profile_fields",
                    "fields": ["age"],
                    "question": "请补充年龄",
                }
            )
            age = int(payload["age"] if isinstance(payload, dict) else payload)
        return {
            "age": age,
            "final_answer": f"user={state.get('user_id', '')};age={age}",
            "handled_by": "profile_agent",
        }

    workflow = StateGraph(ResumeState)
    workflow.add_node("collect_age", collect_age)
    workflow.set_entry_point("collect_age")
    workflow.add_edge("collect_age", END)
    return workflow.compile(checkpointer=checkpointer)


def build_runtime(
    checkpointer: MemorySaver | None = None,
    store: InMemoryStore | None = None,
) -> tuple[RunManager, MemorySaver, InMemoryStore]:
    resolved_checkpointer = checkpointer or MemorySaver()
    resolved_store = store or InMemoryStore()
    graph = build_resume_graph(resolved_checkpointer)
    return (
        RunManager(graph, resolved_store),
        resolved_checkpointer,
        resolved_store,
    )
