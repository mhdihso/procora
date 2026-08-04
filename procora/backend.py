"""Backend protocol and shared DB-API result helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from typing import Any

from .models import ProcedureInfo
from .result import ProcedureResult, ResultSet

ConnectionFactory = Callable[[], Any]
ConnectionReleaser = Callable[[Any], None]


def unique_columns(description: Any) -> tuple[str, ...]:
    used: dict[str, int] = {}
    columns: list[str] = []
    for index, item in enumerate(description, start=1):
        original = str(item[0] or f"column_{index}")
        count = used.get(original, 0) + 1
        used[original] = count
        columns.append(original if count == 1 else f"{original}_{count}")
    return tuple(columns)


def read_result_sets(cursor: Any) -> tuple[ResultSet, ...]:
    """Read every DB-API result set exposed by one cursor."""
    result_sets: list[ResultSet] = []
    while True:
        if cursor.description:
            columns = unique_columns(cursor.description)
            rows = tuple(dict(zip(columns, row, strict=False)) for row in cursor.fetchall())
            result_sets.append(ResultSet(columns, rows))
        try:
            has_next = cursor.nextset()
        except (AttributeError, NotImplementedError):
            has_next = False
        if not has_next:
            break
    return tuple(result_sets)


class Backend(ABC):
    """Implement this interface to add another procedure-capable database."""

    name: str
    aliases: tuple[str, ...] = ()

    @abstractmethod
    def create_connection_factory(
        self,
        *,
        autocommit: bool,
        connect_timeout: int,
        query_timeout: int,
        options: Mapping[str, Any],
    ) -> ConnectionFactory:
        """Create a lazy connection factory from driver-specific options."""

    @abstractmethod
    def discover(self, connection: Any, name: str, schema: str | None) -> ProcedureInfo:
        """Read one procedure from live database metadata."""

    @abstractmethod
    def execute(
        self,
        connection: Any,
        procedure: ProcedureInfo,
        supplied: Mapping[int, Any],
    ) -> ProcedureResult:
        """Execute a discovered procedure."""

    @abstractmethod
    def list_procedures(self, connection: Any) -> list[str]:
        """List callable user procedures."""

    def ping(self, connection: Any) -> bool:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            return bool(row and row[0] == 1)
        finally:
            cursor.close()

    def set_query_timeout(self, connection: Any, seconds: int) -> None:
        """Apply a query timeout when the driver supports it."""
        _ = (connection, seconds)
