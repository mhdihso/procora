"""Backend protocol and shared DB-API result helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from typing import Any

from .models import BackendCapabilities, ProcedureInfo
from .protocols import ConnectionProtocol
from .result import ProcedureResult, ResultSet

ConnectionFactory = Callable[[], ConnectionProtocol]
ConnectionReleaser = Callable[[ConnectionProtocol], None]
ConnectionDiscarder = Callable[[ConnectionProtocol], None]


@contextmanager
def managed_cursor(cursor: Any) -> Iterator[Any]:
    """Close a cursor without allowing cleanup to mask an active error."""
    try:
        yield cursor
    except BaseException:
        with suppress(Exception):
            cursor.close()
        raise
    else:
        cursor.close()


def unique_columns(description: Any) -> tuple[str, ...]:
    allocated: set[str] = set()
    counters: dict[str, int] = {}
    columns: list[str] = []
    for index, item in enumerate(description, start=1):
        base = str(item[0] or f"column_{index}")
        candidate = base
        suffix = counters.get(base, 1)
        while candidate in allocated:
            suffix += 1
            candidate = f"{base}_{suffix}"
        counters[base] = suffix
        allocated.add(candidate)
        columns.append(candidate)
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
    capabilities = BackendCapabilities()

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
        with managed_cursor(connection.cursor()) as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            return bool(row and row[0] == 1)

    def resolve_schema(
        self,
        connection: Any,
        name: str,
        schema: str | None,
    ) -> str | None:
        """Resolve an unqualified call to a stable metadata-cache namespace.

        Backends whose default schema depends on connection state should override this
        method. Returning ``None`` retains a shared unqualified namespace, which is
        appropriate only when the backend's default is stable across all connections.
        """
        _ = (connection, name)
        return schema

    def set_query_timeout(self, connection: Any, seconds: int) -> None:
        """Apply a query timeout when the driver supports it."""
        _ = (connection, seconds)

    def prepare_connection(self, connection: Any, query_timeout: int) -> Any:
        """Apply temporary per-operation settings and return restoration state."""
        if query_timeout:
            self.set_query_timeout(connection, query_timeout)
        return None

    def reset_connection(self, connection: Any, state: Any) -> None:
        """Restore settings changed by :meth:`prepare_connection`."""
        _ = (connection, state)
