import pytest

from procora import ProcedureInfo, UnsupportedParameterError
from procora.backends.mysql import MySQLBackend

from .fakes import FakeConnection, FakeCursor


def mysql_metadata():
    return [
        ("shop", "create_order", 1, "IN", "customer_id", "int", "int"),
        ("shop", "create_order", 2, "OUT", "order_id", "bigint", "bigint"),
    ]


def test_mysql_discovers_uses_callproc_and_returns_outputs_and_sets():
    backend = MySQLBackend()
    procedure = backend.discover(
        FakeConnection(FakeCursor([([], mysql_metadata())])), "create_order", "shop"
    )
    stored = FakeCursor([(["message"], [("created",)])])
    cursor = FakeCursor(callproc_result=(9, 55), stored=[stored])
    result = backend.execute(FakeConnection(cursor), procedure, {1: 9})
    assert result.rows == [{"message": "created"}]
    assert result.output == {"order_id": 55}
    assert cursor.callprocs == [("shop.create_order", (9, None))]
    assert stored.closed


def test_mysql_accepts_the_new_stored_results_property_form():
    stored = FakeCursor([(["value"], [(1,)])])

    class PropertyCursor:
        stored_results = [stored]

    result_sets = MySQLBackend._stored_result_sets(PropertyCursor())
    assert result_sets[0].as_list() == [{"value": 1}]
    assert stored.closed


def test_mysql_discovers_a_zero_parameter_procedure_from_routines():
    class SequentialCursor(FakeCursor):
        def execute(self, sql, *bindings):
            if self.executions:
                self.index += 1
            return super().execute(sql, *bindings)

    cursor = SequentialCursor([([], []), (["schema", "name"], [("shop", "cleanup")])])
    procedure = MySQLBackend().discover(FakeConnection(cursor), "cleanup", "shop")
    assert procedure.qualified_name == "shop.cleanup"
    assert procedure.parameters == ()


def test_mysql_timeout_is_applied_when_the_connection_is_created(monkeypatch):
    captured = {}

    def fake_connect(**options):
        captured.update(options)
        return FakeConnection()

    monkeypatch.setattr("mysql.connector.connect", fake_connect)
    factory = MySQLBackend().create_connection_factory(
        autocommit=True,
        connect_timeout=5,
        query_timeout=15,
        options={"host": "localhost"},
    )
    factory()
    assert captured["connection_timeout"] == 5
    assert captured["read_timeout"] == 15
    assert captured["write_timeout"] == 15


@pytest.mark.parametrize(
    ("schema", "name"),
    [
        ("special-schema", "work"),
        ("shop", "special procedure"),
        ("shop", "name.with.dot"),
        ("shop", "`quoted`"),
    ],
)
def test_mysql_callproc_identifier_limitations_are_explicit(schema, name):
    procedure = ProcedureInfo("mysql", schema, name)
    with pytest.raises(UnsupportedParameterError, match="callproc"):
        MySQLBackend().execute(FakeConnection(FakeCursor()), procedure, {})
