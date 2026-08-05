import pytest

from procora import (
    ConfigurationError,
    ProcedureExecutionError,
    ProcedureInfo,
    ProcedureNotFoundError,
    ProcedureParameter,
    UnsupportedParameterError,
)
from procora.backends.sqlserver import SQLServerBackend, _connection_string

from .fakes import FakeConnection, FakeCursor


def metadata_rows():
    return [
        (42, "dbo", "GetUsers", 1, "@UserId", "int", "sys", 4, 10, 0, False, False, False),
        (
            42,
            "dbo",
            "GetUsers",
            2,
            "@Status",
            "nvarchar",
            "sys",
            -1,
            0,
            0,
            True,
            False,
            False,
        ),
    ]


def test_sqlserver_discovers_executes_and_decodes_every_response():
    backend = SQLServerBackend()
    metadata_cursor = FakeCursor([([], metadata_rows())])
    procedure = backend.discover(FakeConnection(metadata_cursor), "GetUsers", "dbo")
    assert procedure.parameters[1].python_name == "Status"

    marker = ["__procora_return_value", "__procora_output_0"]
    cursor = FakeCursor([(["Id", "Name"], [(1, "Ada")]), (marker, [(0, "success")])])
    result = backend.execute(FakeConnection(cursor), procedure, {1: 1})
    assert result.rows == [{"Id": 1, "Name": "Ada"}]
    assert result.output == {"Status": "success"}
    assert result.return_value == 0
    sql, bindings = cursor.executions[0]
    assert "EXEC @__procora_return = [dbo].[GetUsers]" in sql
    assert "NOCOUNT" not in sql
    assert "@UserId = ?" in sql
    assert bindings == (1,)


def test_sqlserver_output_can_receive_initial_value_and_values_stay_bound():
    backend = SQLServerBackend()
    procedure = backend.discover(
        FakeConnection(FakeCursor([([], metadata_rows())])), "GetUsers", "dbo"
    )
    hostile = "value'); DROP TABLE x;--"
    cursor = FakeCursor([(["__procora_return_value", "__procora_output_0"], [(0, "changed")])])
    backend.execute(FakeConnection(cursor), procedure, {1: 7, 2: hostile})
    sql, bindings = cursor.executions[0]
    assert hostile not in sql
    assert bindings == (hostile, 7)


def test_sqlserver_requires_its_private_output_marker():
    backend = SQLServerBackend()
    procedure = backend.discover(
        FakeConnection(FakeCursor([([], metadata_rows())])), "GetUsers", "dbo"
    )
    with pytest.raises(ProcedureExecutionError, match="output marker"):
        backend.execute(FakeConnection(FakeCursor([(["value"], [(1,)])])), procedure, {1: 1})


def test_sqlserver_rejects_table_valued_parameters_explicitly():
    procedure = ProcedureInfo(
        "sqlserver",
        "dbo",
        "BulkInsert",
        (
            ProcedureParameter(
                1,
                "@Rows",
                "RowType",
                backend_data={"is_table_type": True},
            ),
        ),
    )
    with pytest.raises(UnsupportedParameterError, match="Table-valued"):
        SQLServerBackend._build_call(procedure, {1: [(1,)]})


def test_sqlserver_query_timeout_is_restored():
    backend = SQLServerBackend()
    connection = FakeConnection()
    connection.timeout = 30
    state = backend.prepare_connection(connection, 5)
    assert connection.timeout == 5
    backend.reset_connection(connection, state)
    assert connection.timeout == 30


@pytest.mark.parametrize("resolved_schema", ["sales", "dbo"])
def test_sqlserver_resolves_default_schema_then_dbo(resolved_schema):
    cursor = FakeCursor([(["schema"], [(resolved_schema,)])])
    schema = SQLServerBackend().resolve_schema(FakeConnection(cursor), "Calculate", None)
    assert schema == resolved_schema
    assert "SCHEMA_NAME()" in cursor.executions[0][0]
    assert "N'dbo'" in cursor.executions[0][0]
    assert cursor.executions[0][1] == ("Calculate",)


def test_sqlserver_unqualified_missing_procedure_is_explicit():
    cursor = FakeCursor([(["schema"], [])])
    with pytest.raises(ProcedureNotFoundError, match="default schema or dbo"):
        SQLServerBackend().resolve_schema(FakeConnection(cursor), "Missing", None)


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("trusted_connection", "false"),
        ("encrypt", "no"),
        ("trust_server_certificate", 0),
    ],
)
def test_sqlserver_security_options_require_real_booleans(option, value):
    options = {
        "host": "localhost",
        "database": "app",
        "username": "user",
        "password": "secret",
        "driver": "ODBC Driver 18 for SQL Server",
        option: value,
    }
    with pytest.raises(ConfigurationError, match=f"{option} must be a boolean"):
        _connection_string(options)


@pytest.mark.parametrize("port", ["invalid", True, 0, 65536])
def test_sqlserver_port_validation_is_consistent(port):
    with pytest.raises(ConfigurationError, match="port"):
        _connection_string(
            {
                "host": "localhost",
                "database": "app",
                "username": "user",
                "password": "secret",
                "driver": "ODBC Driver 18 for SQL Server",
                "port": port,
            }
        )


def test_sqlserver_connection_factory_builds_and_uses_a_secure_connection_string(
    monkeypatch,
):
    captured = {}
    sentinel = object()

    def fake_connect(connection_string, **options):
        captured["connection_string"] = connection_string
        captured["options"] = options
        return sentinel

    monkeypatch.setattr("pyodbc.connect", fake_connect)
    factory = SQLServerBackend().create_connection_factory(
        autocommit=False,
        connect_timeout=7,
        query_timeout=2,
        options={
            "host": "database.internal",
            "database": "app",
            "username": "user",
            "password": "secret}",
            "driver": "ODBC Driver 18 for SQL Server",
            "encrypt": True,
            "trust_server_certificate": False,
            "application_name": "procora-tests",
        },
    )

    assert factory() is sentinel
    assert "SERVER={database.internal,1433}" in captured["connection_string"]
    assert "PWD={secret}}}" in captured["connection_string"]
    assert "Encrypt=yes" in captured["connection_string"]
    assert "TrustServerCertificate=no" in captured["connection_string"]
    assert captured["options"] == {"autocommit": False, "timeout": 7}


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (
            {"connection_string": "DSN=app", "host": "unexpected"},
            "cannot be combined",
        ),
        (
            {"host": "localhost", "driver": "ODBC Driver 18 for SQL Server"},
            "requires host and database",
        ),
        (
            {
                "host": "localhost",
                "database": "app",
                "driver": "ODBC Driver 18 for SQL Server",
            },
            "requires username/password",
        ),
        (
            {
                "host": "localhost",
                "database": "app",
                "trusted_connection": True,
                "driver": "ODBC Driver 18 for SQL Server",
                "unknown": "value",
            },
            "Unknown SQL Server options",
        ),
    ],
)
def test_sqlserver_connection_configuration_errors_are_explicit(options, message):
    with pytest.raises(ConfigurationError, match=message):
        _connection_string(options)


def test_sqlserver_accepts_a_raw_connection_string_without_other_options():
    assert _connection_string({"connection_string": "DSN=procora"}) == "DSN=procora"


def test_sqlserver_reports_when_no_supported_odbc_driver_is_installed(monkeypatch):
    monkeypatch.setattr("pyodbc.drivers", lambda: ["Unrelated Driver"])
    with pytest.raises(ConfigurationError, match="currently available: Unrelated Driver"):
        _connection_string(
            {
                "host": "localhost",
                "database": "app",
                "username": "user",
                "password": "secret",
            }
        )
