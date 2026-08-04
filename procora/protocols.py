"""Structural DB-API types used by custom connection factories and backends."""

from __future__ import annotations

from typing import Any, Protocol


class CursorProtocol(Protocol):
    """Minimum cursor behavior consumed by Procora's portable core."""

    description: Any

    def execute(self, operation: str, *parameters: Any) -> Any: ...

    def fetchone(self) -> Any: ...

    def fetchall(self) -> Any: ...

    def nextset(self) -> bool | None: ...

    def close(self) -> None: ...


class ConnectionProtocol(Protocol):
    """Minimum connection behavior expected by Procora."""

    autocommit: Any

    def cursor(self) -> CursorProtocol: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...
