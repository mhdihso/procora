from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from procora import (
    Backend,
    Database,
    DatabaseConnectionError,
    ParameterMode,
    ProcedureInfo,
    ProcedureParameter,
    ProcedureParameterError,
    ProcedureResult,
    ResultSet,
    connect,
    get_backend,
)

from .fakes import ConnectionQueue, FakeConnection


class RecordingBackend(Backend):
    name = "recording"

    def __init__(self) -> None:
        self.executions: list[tuple[ProcedureInfo, Mapping[int, Any]]] = []

    def create_connection_factory(self, **kwargs):
        raise AssertionError("custom connection factory expected")

    def discover(self, connection, name, schema):
        return ProcedureInfo(
            self.name,
            schema or "public",
            name,
            (
                ProcedureParameter(1, "Input", "integer"),
                ProcedureParameter(2, "Output", "text", ParameterMode.OUT),
            ),
        )

    def execute(self, connection, procedure, supplied):
        self.executions.append((procedure, supplied))
        return ProcedureResult(
            procedure,
            (ResultSet(("value",), ({"value": supplied[1]},)),),
            {"Output": "done"},
        )

    def list_procedures(self, connection):
        return ["public.One"]

    def ping(self, connection):
        return True


def test_database_neutral_api_cache_namespaces_and_results():
    backend = RecordingBackend()
    queue = ConnectionQueue(FakeConnection(), FakeConnection(), FakeConnection())
    database = Database(backend, queue)

    result = database.procedures.DoWork(Input=7)
    second = database.procedures.DoWork(Input=8)

    assert result.rows == [{"value": 7}]
    assert result.first == {"value": 7}
    assert result.scalar == 7
    assert result.output == {"Output": "done"}
    assert second.scalar == 8
    assert queue.calls == 3  # one discovery and two executions
    assert backend.executions[0][1] == {1: 7}


def test_mapping_parameters_are_case_friendly_and_reject_duplicates():
    backend = RecordingBackend()
    database = Database(backend, ConnectionQueue(FakeConnection(), FakeConnection()))
    assert database.call("Work", {"@input": 2}).scalar == 2

    database = Database(backend, ConnectionQueue(FakeConnection()))
    with pytest.raises(ProcedureParameterError, match="more than once"):
        database.call("Work", {"Input": 1, "@input": 2})


def test_unknown_parameter_is_rejected_before_execution_connection():
    backend = RecordingBackend()
    queue = ConnectionQueue(FakeConnection())
    database = Database(backend, queue)
    with pytest.raises(ProcedureParameterError, match="Unknown parameter"):
        database.call("Work", Missing=1)
    assert queue.calls == 1


def test_non_autocommit_success_commits_and_failure_rolls_back():
    backend = RecordingBackend()
    discovery = FakeConnection()
    execution = FakeConnection(autocommit=False)
    database = Database(backend, ConnectionQueue(discovery, execution), autocommit=False)
    database.call("Work", Input=1)
    assert execution.commits == 1

    class FailingBackend(RecordingBackend):
        def execute(self, connection, procedure, supplied):
            raise RuntimeError("failure")

    discovery = FakeConnection()
    execution = FakeConnection(autocommit=False)
    database = Database(FailingBackend(), ConnectionQueue(discovery, execution), autocommit=False)
    with pytest.raises(Exception, match="Execution failed"):
        database.call("Work", Input=1)
    assert execution.rollbacks == 1


def test_connect_accepts_aliases_and_custom_backend():
    assert get_backend("mssql").name == "sqlserver"
    assert get_backend("postgres").name == "postgresql"
    assert get_backend("mariadb").name == "mysql"
    backend = RecordingBackend()
    database = connect(backend, connection_factory=lambda: FakeConnection())
    assert database.backend is backend


def test_connection_releaser_supports_pools():
    backend = RecordingBackend()
    connections = [FakeConnection(), FakeConnection()]
    released = []
    database = connect(
        backend,
        connection_factory=lambda: connections.pop(0),
        connection_releaser=released.append,
    )
    database.call("Work", Input=1)
    assert len(released) == 2
    assert all(not connection.closed for connection in released)


def test_pooled_read_operations_rollback_before_release():
    backend = RecordingBackend()
    connections = [FakeConnection(autocommit=False) for _ in range(3)]
    released = []
    database = connect(
        backend,
        connection_factory=lambda: connections[len(released)],
        connection_releaser=released.append,
        autocommit=False,
    )

    database.inspect("Work")
    database.list_procedures()
    assert database.ping() is True

    assert released == connections
    assert [connection.rollbacks for connection in released] == [1, 1, 1]


def test_timeout_setup_failure_releases_created_connection():
    class TimeoutBackend(RecordingBackend):
        def set_query_timeout(self, connection, seconds):
            raise RuntimeError("timeout setup failed")

    connection = FakeConnection()
    released = []
    database = Database(
        TimeoutBackend(),
        lambda: connection,
        query_timeout=5,
        connection_releaser=released.append,
    )

    with pytest.raises(DatabaseConnectionError, match="timeout setup failed"):
        database.ping()
    assert released == [connection]


def test_none_from_connection_factory_is_rejected():
    database = Database(RecordingBackend(), lambda: None)
    with pytest.raises(DatabaseConnectionError, match="returned None"):
        database.ping()


def test_result_json_helper():
    procedure = ProcedureInfo("test", "public", "json_proc")
    result = ProcedureResult(
        procedure,
        (ResultSet(("payload",), ({"payload": '{"ok": true}'},)),),
    )
    assert result.json() == {"ok": True}
