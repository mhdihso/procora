import pytest

from procora import (
    AmbiguousProcedureError,
    ProcedureParameterError,
    UnsupportedParameterError,
)
from procora.backends.postgresql import PostgreSQLBackend

from .fakes import FakeConnection, FakeCursor


def postgres_metadata():
    return [
        (
            100,
            "public",
            "create_order",
            ["customer_id", "note", "order_id"],
            ["i", "i", "o"],
            ["integer", "text", "bigint"],
            1,
        )
    ]


def test_postgresql_discovers_defaults_calls_named_and_decodes_outputs():
    backend = PostgreSQLBackend()
    procedure = backend.discover(
        FakeConnection(FakeCursor([([], postgres_metadata())])),
        "create_order",
        "public",
    )
    assert procedure.parameters[1].has_default is True

    cursor = FakeCursor([(["order_id"], [(55,)])])
    result = backend.execute(FakeConnection(cursor), procedure, {1: 9})
    assert result.output == {"order_id": 55}
    assert result.return_value is None
    sql, bindings = cursor.executions[0]
    assert sql == 'CALL "public"."create_order"("customer_id" => %s, "order_id" => NULL)'
    assert bindings == ((9,),)


def test_postgresql_without_outputs_preserves_result_sets():
    backend = PostgreSQLBackend()
    row = [(101, "public", "maintenance", [], [], [], 0)]
    procedure = backend.discover(FakeConnection(FakeCursor([([], row)])), "maintenance", "public")
    cursor = FakeCursor([])
    result = backend.execute(FakeConnection(cursor), procedure, {})
    assert result.output == {}


def test_postgresql_rejects_ambiguous_overloads():
    rows = postgres_metadata() * 2
    with pytest.raises(AmbiguousProcedureError, match="overloaded"):
        PostgreSQLBackend().discover(
            FakeConnection(FakeCursor([([], rows)])), "create_order", "public"
        )


def test_postgresql_unnamed_required_parameter_must_be_supplied():
    row = [(101, "public", "work", None, ["i"], ["integer"], 0)]
    procedure = PostgreSQLBackend().discover(
        FakeConnection(FakeCursor([([], row)])), "work", "public"
    )
    with pytest.raises(ProcedureParameterError, match="must be supplied"):
        PostgreSQLBackend._build_call(procedure, {})


def test_postgresql_named_required_parameter_must_be_supplied():
    row = [(101, "public", "work", ["value"], ["i"], ["integer"], 0)]
    procedure = PostgreSQLBackend().discover(
        FakeConnection(FakeCursor([([], row)])), "work", "public"
    )
    with pytest.raises(ProcedureParameterError, match="value must be supplied"):
        PostgreSQLBackend._build_call(procedure, {})


def test_postgresql_trailing_unnamed_default_can_be_omitted():
    row = [(101, "public", "work", None, ["i", "i"], ["integer", "text"], 1)]
    procedure = PostgreSQLBackend().discover(
        FakeConnection(FakeCursor([([], row)])), "work", "public"
    )
    sql, bindings = PostgreSQLBackend._build_call(procedure, {1: 7})
    assert sql == 'CALL "public"."work"(%s)'
    assert bindings == [7]


def test_postgresql_unnamed_default_before_output_is_rejected_clearly():
    row = [
        (
            101,
            "public",
            "work",
            None,
            ["i", "i", "o"],
            ["integer", "text", "text"],
            1,
        )
    ]
    procedure = PostgreSQLBackend().discover(
        FakeConnection(FakeCursor([([], row)])), "work", "public"
    )
    with pytest.raises(ProcedureParameterError, match="cannot be omitted"):
        PostgreSQLBackend._build_call(procedure, {1: 7})


def test_postgresql_variadic_parameters_are_rejected():
    row = [(101, "public", "work", ["values"], ["v"], ["integer[]"], 0)]
    with pytest.raises(UnsupportedParameterError, match="Variadic"):
        PostgreSQLBackend().discover(FakeConnection(FakeCursor([([], row)])), "work", "public")


def test_postgresql_outputs_prefer_discovered_column_names():
    row = [
        (
            101,
            "public",
            "work",
            ["first", "second"],
            ["o", "o"],
            ["text", "text"],
            0,
        )
    ]
    backend = PostgreSQLBackend()
    procedure = backend.discover(FakeConnection(FakeCursor([([], row)])), "work", "public")
    result = backend.execute(
        FakeConnection(FakeCursor([(["second", "first"], [("two", "one")])])),
        procedure,
        {},
    )
    assert result.output == {"first": "one", "second": "two"}


def test_postgresql_transaction_timeout_is_local_to_the_operation():
    cursor = FakeCursor([])
    state = PostgreSQLBackend().prepare_connection(FakeConnection(cursor, autocommit=False), 12)
    assert state is None
    assert cursor.executions == [
        (
            "SELECT pg_catalog.set_config('statement_timeout', %s, %s)",
            (("12000", True),),
        )
    ]


def test_postgresql_autocommit_timeout_restores_previous_session_value():
    prepare_cursor = FakeCursor([(["current_setting"], [("5s",)])])
    reset_cursor = FakeCursor([])
    connection = FakeConnection(prepare_cursor, reset_cursor, autocommit=True)
    backend = PostgreSQLBackend()

    state = backend.prepare_connection(connection, 12)
    backend.reset_connection(connection, state)

    assert state == "5s"
    assert prepare_cursor.executions == [
        ("SELECT current_setting('statement_timeout')", ()),
        (
            "SELECT pg_catalog.set_config('statement_timeout', %s, %s)",
            (("12000", False),),
        ),
    ]
    assert reset_cursor.executions == [
        (
            "SELECT pg_catalog.set_config('statement_timeout', %s, false)",
            (("5s",),),
        )
    ]
