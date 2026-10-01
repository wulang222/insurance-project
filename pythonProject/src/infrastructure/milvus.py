"""Lifespan-owned Milvus client with lazy network connection."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MilvusClient:
    host: str
    port: str
    uri: str
    token: str = field(repr=False)
    user: str
    password: str = field(repr=False)
    alias: str = "harness_milvus"
    _connected: bool = field(default=False, init=False, repr=False)

    @classmethod
    def from_env(cls) -> "MilvusClient":
        return cls(
            host=os.getenv("MILVUS_HOST", "localhost"),
            port=os.getenv("MILVUS_PORT", "19530"),
            uri=os.getenv("MILVUS_URI", ""),
            token=os.getenv("MILVUS_TOKEN", ""),
            user=os.getenv("MILVUS_USER", ""),
            password=os.getenv("MILVUS_PASSWORD", ""),
        )

    def connect(self) -> Any:
        from pymilvus import connections

        if not self._connected:
            if self.uri:
                connections.connect(alias=self.alias, uri=self.uri, token=self.token)
            else:
                connections.connect(
                    alias=self.alias,
                    host=self.host,
                    port=self.port,
                    user=self.user or None,
                    password=self.password or None,
                )
            self._connected = True
        return connections

    async def aclose(self) -> None:
        if not self._connected:
            return
        from pymilvus import connections

        connections.disconnect(self.alias)
        self._connected = False
