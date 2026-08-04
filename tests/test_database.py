from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from procora import (
    Backend,
    ConfigurationError,
    Database,
    DatabaseConnectionError,
    ParameterMode,
    ProcedureDiscoveryError,
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
        self.discoveries: list[tuple[str, str | None]] = []

    def create_connection_factory(self, **kwargs):
        raise AssertionError("custom connection factory expected")

    def discover(self, connection, name, schema):
        self.discoveries.append((name, schema))
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
    queue = ConnectionQueue(FakeConnection(), FakeConnection())
    database = Database(backend, queue)

    result = database.procedures.DoWork(Input=7)
    second = database.procedures.DoWork(Input=8)

    assert result.rows == [{"value": 7}]
    assert result.first == {"value": 7}
    assert result.scalar == 7
    assert result.output == {"Output": "done"}
    assert second.scalar == 8
    assert queue.calls == 2  # discovery shares the first execution connection
    assert backend.executions[0][1] == {1: 7}


def test_metadata_cache_can_be_invalidated_or_cleared():
    backend = RecordingBackend()
    database = Database(
        backend,
        ConnectionQueue(FakeConnection(), FakeConnection(), FakeConnection()),
    )

    database.call("public.Work", Input=1)
    assert backend.discoveries == [("Work", "public")]
    assert database.invalidate_metadata("public.Work") is True
    assert database.invalidate_metadata("public.Work") is False

    database.call("public.Work", Input=2)
    assert len(backend.discoveries) == 2
    assert database.clear_metadata_cache() == 1
    assert database.clear_metadata_cache() == 0

    database.call("public.Work", Input=3)
    assert len(backend.discoveries) == 3


def test_mapping_parameters_are_case_friendly_and_reject_duplicates():
    backend = RecordingBackend()
    database = Database(backend, ConnectionQueue(FakeConnection()))
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


def test_pure_out_parameter_rejects_input_before_execution():
    backend = RecordingBackend()
    queue = ConnectionQueue(FakeConnection())
    database = Database(backend, queue)
    with pytest.raises(ProcedureParameterError, match="OUT-only"):
        database.call("Work", Output="not allowed")
    assert queue.calls == 1


def test_procedure_proxy_accepts_mapping_for_reserved_parameter_names():
    class ReservedBackend(RecordingBackend):
        def discover(self, connection, name, schema):
            return ProcedureInfo(
                self.name,
                schema or "public",
                name,
                (
                    ProcedureParameter(1, "schema", "text"),
                    ProcedureParameter(2, "refresh", "text"),
                ),
            )

        def execute(self, connection, procedure, supplied):
            return ProcedureResult(
                procedure,
                (ResultSet(("values",), ({"values": tuple(supplied.values())},)),),
            )

    database = Database(
        ReservedBackend(),
        ConnectionQueue(FakeConnection()),
    )
    result = database.procedure("Work")({"schema": "sales", "refresh": "yes"})
    assert result.scalar == ("sales", "yes")


def test_non_autocommit_success_commits_and_failure_rolls_back():
    backend = RecordingBackend()
    execution = FakeConnection(autocommit=False)
    database = Database(backend, ConnectionQueue(execution), autocommit=False)
    database.call("Work", Input=1)
    assert execution.commits == 1

    class FailingBackend(RecordingBackend):
        def execute(self, connection, procedure, supplied):
            raise RuntimeError("failure")

    execution = FakeConnection(autocommit=False)
    database = Database(FailingBackend(), ConnectionQueue(execution), autocommit=False)
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


def test_builtin_backends_advertise_portable_capabilities():
    sqlserver = get_backend("sqlserver").capabilities
    postgresql = get_backend("postgresql").capabilities
    mysql = get_backend("mysql").capabilities

    assert sqlserver.supports_return_value is True
    assert sqlserver.timeout_kind == "driver"
    assert sqlserver.metadata_defaults_are_reliable is False
    assert postgresql.supports_overloads is True
    assert postgresql.timeout_kind == "statement"
    assert mysql.supports_per_borrow_timeout is False
    assert mysql.timeout_kind == "socket"
    assert all(item.buffers_results for item in (sqlserver, postgresql, mysql))


def test_mysql_custom_factory_rejects_an_unenforceable_query_timeout():
    with pytest.raises(
        ConfigurationError,
        match="configure the timeout in the pool",
    ):
        connect(
            "mysql",
            connection_factory=lambda: FakeConnection(),
            query_timeout=5,
        )


def test_connection_releaser_supports_pools():
    backend = RecordingBackend()
    connections = [FakeConnection()]
    released = []
    database = connect(
        backend,
        connection_factory=lambda: connections.pop(0),
        connection_releaser=released.append,
    )
    database.call("Work", Input=1)
    assert len(released) == 1
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


def test_temporary_connection_state_is_reset_before_pool_release():
    events = []

    class StatefulBackend(RecordingBackend):
        def prepare_connection(self, connection, query_timeout):
            events.append(("prepare", query_timeout))
            return "original-state"

        def reset_connection(self, connection, state):
            events.append(("reset", state))

    connection = FakeConnection()
    database = Database(
        StatefulBackend(),
        lambda: connection,
        query_timeout=5,
        connection_releaser=lambda value: events.append(("release", value)),
    )
    assert database.ping() is True
    assert events == [
        ("prepare", 5),
        ("reset", "original-state"),
        ("release", connection),
    ]


def test_none_from_connection_factory_is_rejected():
    database = Database(RecordingBackend(), lambda: None)
    with pytest.raises(DatabaseConnectionError, match="returned None"):
        database.ping()


def test_unexpected_metadata_failure_has_a_discovery_error():
    class BrokenDiscoveryBackend(RecordingBackend):
        def discover(self, connection, name, schema):
            raise RuntimeError("catalog unavailable")

    database = Database(BrokenDiscoveryBackend(), lambda: FakeConnection())
    with pytest.raises(ProcedureDiscoveryError, match="catalog unavailable") as raised:
        database.inspect("Work")
    assert isinstance(raised.value.__cause__, RuntimeError)


def test_release_failure_is_observable_without_replacing_success():
    def fail_release(connection):
        raise RuntimeError("pool release failed")

    database = Database(
        RecordingBackend(),
        lambda: FakeConnection(),
        connection_releaser=fail_release,
    )
    with pytest.warns(RuntimeWarning, match="pool release failed"):
        result = database.call("Work", Input=1)
    assert result.scalar == 1


def test_cleanup_errors_can_be_routed_to_a_callback():
    cleanup_errors = []

    class BrokenResetBackend(RecordingBackend):
        def prepare_connection(self, connection, query_timeout):
            return "state"

        def reset_connection(self, connection, state):
            raise RuntimeError("reset failed")

    connection = FakeConnection()
    released = []
    database = Database(
        BrokenResetBackend(),
        lambda: connection,
        connection_releaser=released.append,
        on_cleanup_error=cleanup_errors.append,
    )
    assert database.ping() is True
    assert released == [connection]
    assert len(cleanup_errors) == 1
    assert str(cleanup_errors[0]) == "reset failed"


def test_result_json_helper():
    procedure = ProcedureInfo("test", "public", "json_proc")
    result = ProcedureResult(
        procedure,
        (ResultSet(("payload",), ({"payload": '{"ok": true}'},)),),
    )
    assert result.json() == {"ok": True}


def test_result_and_metadata_mappings_are_read_only():
    parameter = ProcedureParameter(1, "value", "integer", backend_data={"oid": 23})
    procedure = ProcedureInfo(
        "test",
        "public",
        "immutable",
        (parameter,),
        backend_data={"source": "catalog"},
    )
    result = ProcedureResult(
        procedure,
        (ResultSet(("value",), ({"value": 1},)),),
        {"status": "ok"},
    )

    with pytest.raises(TypeError):
        result.output["status"] = "changed"
    with pytest.raises(TypeError):
        result.result_sets[0].rows[0]["value"] = 2
    with pytest.raises(TypeError):
        parameter.backend_data["oid"] = 24
    with pytest.raises(TypeError):
        procedure.backend_data["source"] = "changed"


def test_first_and_scalar_do_not_copy_the_entire_result_set(monkeypatch):
    procedure = ProcedureInfo("test", "public", "large_result")
    result = ProcedureResult(
        procedure,
        (ResultSet(("value",), tuple({"value": index} for index in range(1_000))),),
    )

    def fail_if_copied(self):
        raise AssertionError("as_list copied the complete result set")

    monkeypatch.setattr(ResultSet, "as_list", fail_if_copied)
    assert result.first == {"value": 0}
    assert result.scalar == 0
