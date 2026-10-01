"""Lazily connected MySQL client owned by the application lifespan."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MySQLClient:
    host: str
    port: int
    user: str
    password: str = field(repr=False)
    database: str
    _connections: list[Any] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def from_env(cls) -> "MySQLClient":
        return cls(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "insurance"),
        )

    def connect(self) -> Any:
        """Create a tracked connection only when a tool actually needs it."""

        import pymysql

        connection = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset="utf8mb4",
            connect_timeout=5,
        )
        self._connections.append(connection)
        return connection

    async def aclose(self) -> None:
        for connection in self._connections:
            try:
                connection.close()
            except Exception:
                pass
        self._connections.clear()
