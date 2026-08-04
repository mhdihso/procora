import pytest

from procora import (
    ConfigurationError,
    ProcedureInfo,
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
