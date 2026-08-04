import pytest

from procora import AmbiguousProcedureError, ProcedureParameterError
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


def test_postgresql_timeout_uses_a_bound_set_config_value():
    cursor = FakeCursor([])
    PostgreSQLBackend().set_query_timeout(FakeConnection(cursor), 12)
    assert cursor.executions == [
        (
            "SELECT pg_catalog.set_config('statement_timeout', %s, false)",
            (("12000",),),
        )
    ]
