"""Long-term profile memory write tool."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from shared.memory import UserMemoryStore


class SaveProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1)
    profile: dict[str, Any]
    interaction: dict[str, Any] | None = None


class SaveProfileResult(BaseModel):
    saved: bool


class ProfileMemoryRepository:
    def __init__(self, store: Any) -> None:
        self.memory = UserMemoryStore(store)

    async def save(
        self,
        user_id: str,
        profile: dict[str, Any],
        interaction: dict[str, Any] | None,
    ) -> SaveProfileResult:
        await self.memory.save_user_profile(user_id, dict(profile))
        if interaction:
            await self.memory.save_interaction(user_id, dict(interaction))
        return SaveProfileResult(saved=True)
