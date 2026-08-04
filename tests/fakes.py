from __future__ import annotations

from typing import Any


class FakeCursor:
    def __init__(
        self,
        result_sets: list[tuple[list[str], list[tuple[Any, ...]]]] | None = None,
        *,
        callproc_result: tuple[Any, ...] | None = None,
        stored: list[FakeCursor] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result_sets = result_sets or []
        self.index = 0
        self.callproc_result = callproc_result
        self.stored = stored or []
        self.error = error
        self.executions: list[tuple[str, tuple[Any, ...]]] = []
        self.callprocs: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    @property
    def description(self):
        if self.index >= len(self.result_sets):
            return None
        return [(column,) for column in self.result_sets[self.index][0]]

    def execute(self, sql: str, *bindings: Any):
        self.executions.append((sql, bindings))
        if self.error:
            raise self.error
        return self

    def fetchall(self):
        return self.result_sets[self.index][1]

    def fetchone(self):
        rows = self.result_sets[self.index][1]
        return rows[0] if rows else None

    def nextset(self):
        if self.index + 1 < len(self.result_sets):
            self.index += 1
            return True
        return False

    def callproc(self, name: str, args: tuple[Any, ...]):
        self.callprocs.append((name, args))
        if self.error:
            raise self.error
        return self.callproc_result if self.callproc_result is not None else args

    def stored_results(self):
        return iter(self.stored)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(
        self,
        *cursors: FakeCursor,
        autocommit: bool = True,
    ) -> None:
        self.cursors = list(cursors)
        self.autocommit = autocommit
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.timeout = 0

    def cursor(self):
        if not self.cursors:
            raise AssertionError("No fake cursor remains")
        return self.cursors.pop(0)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class ConnectionQueue:
    def __init__(self, *connections: FakeConnection) -> None:
        self.connections = list(connections)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if not self.connections:
            raise AssertionError("No fake connection remains")
        return self.connections.pop(0)
