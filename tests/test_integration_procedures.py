"""Opt-in end-to-end stored-procedure tests for dedicated disposable databases."""

import json
import os

import pytest

from procora import ProcedureExecutionError, connect


def integration_options(variable):
    raw = os.environ.get(variable)
    if not raw:
        pytest.skip(f"{variable} is not configured")
    return json.loads(raw)


@pytest.mark.integration
def test_postgresql_procedure_end_to_end():
    options = integration_options("PROCORA_INTEGRATION_POSTGRESQL_OPTIONS")
    psycopg = pytest.importorskip("psycopg")
    direct_options = dict(options)
    dsn = direct_options.pop("dsn", direct_options.pop("connection_string", ""))
    connection = psycopg.connect(dsn, autocommit=True, **direct_options)
    try:
        connection.execute("DROP SCHEMA IF EXISTS procora_it CASCADE")
        connection.execute("DROP SCHEMA IF EXISTS procora_empty CASCADE")
        connection.execute("CREATE SCHEMA procora_it")
        connection.execute("CREATE SCHEMA procora_empty")
        connection.execute(
            """
            CREATE PROCEDURE procora_it.calculate(
                IN value integer,
                INOUT doubled integer,
                OUT label text
            )
            LANGUAGE plpgsql
            AS $$
            BEGIN
                doubled := value * 2;
                label := 'ok';
            END;
            $$
            """
        )
        connection.execute(
            """
            CREATE PROCEDURE procora_it.with_defaults(
                IN value integer DEFAULT 9,
                INOUT doubled integer DEFAULT 0
            )
            LANGUAGE plpgsql
            AS $$
            BEGIN
                doubled := value * 2;
            END;
            $$
            """
        )
        connection.execute(
            """
            CREATE PROCEDURE procora_it.zero_arguments()
            LANGUAGE plpgsql
            AS $$
            BEGIN
                NULL;
            END;
            $$
            """
        )
        connection.execute(
            """
            CREATE PROCEDURE procora_it.always_fails()
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'intentional procora failure';
            END;
            $$
            """
        )
        connection.execute(
            """
            CREATE PROCEDURE procora_it.changing(IN value integer)
            LANGUAGE plpgsql
            AS $$ BEGIN NULL; END; $$
            """
        )

        database = connect("postgresql", **options)
        assert "procora_it.calculate" in database.list_procedures()
        info = database.inspect("procora_it.calculate")
        assert [parameter.python_name for parameter in info.parameters] == [
            "value",
            "doubled",
            "label",
        ]
        result = database.call("procora_it.calculate", value=7, doubled=0)
        assert result.output == {"doubled": 14, "label": "ok"}
        assert database.call("procora_it.with_defaults").output == {"doubled": 18}
        assert database.call("procora_it.zero_arguments").rows == []

        changing = database.inspect("procora_it.changing")
        assert len(changing.parameters) == 1
        connection.execute("DROP PROCEDURE procora_it.changing(integer)")
        connection.execute(
            """
            CREATE PROCEDURE procora_it.changing(IN value integer, IN extra integer)
            LANGUAGE plpgsql
            AS $$ BEGIN NULL; END; $$
            """
        )
        assert len(database.inspect("procora_it.changing").parameters) == 1
        assert len(database.inspect("procora_it.changing", refresh=True).parameters) == 2

        pooled_connection = psycopg.connect(dsn, autocommit=False, **direct_options)
        pooled_connection.execute("SET search_path TO procora_empty, procora_it")
        pooled_connection.commit()
        available = [pooled_connection]

        def acquire():
            return available.pop()

        def release(value):
            available.append(value)

        pooled_database = connect(
            "postgresql",
            connection_factory=acquire,
            connection_releaser=release,
            connection_discarder=lambda value: value.close(),
            autocommit=False,
        )
        with pytest.raises(ProcedureExecutionError, match="intentional procora failure"):
            pooled_database.call("always_fails")
        assert available == [pooled_connection]
        assert pooled_database.call("zero_arguments").rows == []
        assert available == [pooled_connection]
        pooled_connection.close()
    finally:
        connection.execute("DROP SCHEMA IF EXISTS procora_it CASCADE")
        connection.execute("DROP SCHEMA IF EXISTS procora_empty CASCADE")
        connection.close()


@pytest.mark.integration
def test_mysql_procedure_end_to_end():
    options = integration_options("PROCORA_INTEGRATION_MYSQL_OPTIONS")
    connector = pytest.importorskip("mysql.connector")
    connection = connector.connect(**options)
    cursor = connection.cursor()
    try:
        cursor.execute("DROP PROCEDURE IF EXISTS procora_it_calculate")
        cursor.execute(
            """
            CREATE PROCEDURE procora_it_calculate(
                IN value INT,
                INOUT doubled INT,
                OUT label VARCHAR(20)
            )
            BEGIN
                SET doubled = value * 2;
                SET label = 'ok';
                SELECT value AS input_value, doubled AS doubled_value;
                SELECT 'second' AS result_name;
            END
            """
        )
        cursor.execute("DROP PROCEDURE IF EXISTS procora_it_zero_arguments")
        cursor.execute(
            """
            CREATE PROCEDURE procora_it_zero_arguments()
            BEGIN
                SELECT 1 AS duplicate_name, 2 AS duplicate_name;
            END
            """
        )
        cursor.execute("DROP PROCEDURE IF EXISTS procora_it_always_fails")
        cursor.execute(
            """
            CREATE PROCEDURE procora_it_always_fails()
            BEGIN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'intentional procora failure';
            END
            """
        )

        database = connect("mysql", **options)
        schema = options["database"]
        qualified = f"{schema}.procora_it_calculate"
        assert qualified in database.list_procedures()
        result = database.call(qualified, value=7, doubled=0)
        assert result.rows == [{"input_value": 7, "doubled_value": 14}]
        assert result.result_sets[1].as_list() == [{"result_name": "second"}]
        assert result.output == {"doubled": 14, "label": "ok"}
        duplicate = database.call(f"{schema}.procora_it_zero_arguments")
        assert duplicate.rows == [{"duplicate_name": 1, "duplicate_name_2": 2}]

        pooled_connection = connector.connect(**options)
        pooled_connection.autocommit = False
        available = [pooled_connection]

        def acquire():
            return available.pop()

        def release(value):
            available.append(value)

        pooled_database = connect(
            "mysql",
            connection_factory=acquire,
            connection_releaser=release,
            connection_discarder=lambda value: value.close(),
            autocommit=False,
        )
        with pytest.raises(ProcedureExecutionError, match="intentional procora failure"):
            pooled_database.call(f"{schema}.procora_it_always_fails")
        assert available == [pooled_connection]
        assert pooled_database.call(f"{schema}.procora_it_zero_arguments").scalar == 1
        assert available == [pooled_connection]
        pooled_connection.close()
    finally:
        cursor.execute("DROP PROCEDURE IF EXISTS procora_it_calculate")
        cursor.execute("DROP PROCEDURE IF EXISTS procora_it_zero_arguments")
        cursor.execute("DROP PROCEDURE IF EXISTS procora_it_always_fails")
        cursor.close()
        connection.close()


@pytest.mark.integration
def test_sqlserver_procedure_end_to_end():
    options = integration_options("PROCORA_INTEGRATION_SQLSERVER_OPTIONS")
    pyodbc = pytest.importorskip("pyodbc")
    from procora.backends.sqlserver import _connection_string

    connection = pyodbc.connect(_connection_string(options), autocommit=True)
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE OR ALTER PROCEDURE dbo.procora_it_calculate
                @value int,
                @doubled int OUTPUT
            AS
            BEGIN
                SET @doubled = @value * 2;
                SELECT @value AS input_value, @doubled AS doubled_value;
                SELECT @value AS duplicate_name, @doubled AS duplicate_name;
                RETURN 7;
            END
            """
        )
        cursor.execute(
            """
            CREATE OR ALTER PROCEDURE dbo.procora_it_defaults
                @value int = 9
            AS
            BEGIN
                SELECT @value AS default_value;
            END
            """
        )
        cursor.execute(
            """
            CREATE OR ALTER PROCEDURE dbo.procora_it_zero_arguments
            AS
            BEGIN
                SELECT CAST(12.34 AS decimal(10, 2)) AS decimal_value,
                       CAST(0x010203 AS varbinary(max)) AS binary_value,
                       CAST('2026-08-04T12:34:56' AS datetime2) AS datetime_value,
                       N'{"ok":true}' AS json_value;
            END
            """
        )
        cursor.execute(
            """
            CREATE OR ALTER PROCEDURE dbo.procora_it_always_fails
            AS
            BEGIN
                THROW 50000, 'intentional procora failure', 1;
            END
            """
        )

        database = connect("sqlserver", **options)
        result = database.call("dbo.procora_it_calculate", value=7, doubled=0)
        assert result.rows == [{"input_value": 7, "doubled_value": 14}]
        assert result.result_sets[1].as_list() == [
            {"duplicate_name": 7, "duplicate_name_2": 14}
        ]
        assert result.output == {"doubled": 14}
        assert result.return_value == 7
        assert database.call("dbo.procora_it_defaults").scalar == 9
        native = database.call("dbo.procora_it_zero_arguments").first
        assert native is not None
        assert str(native["decimal_value"]) == "12.34"
        assert bytes(native["binary_value"]) == b"\x01\x02\x03"
        assert native["datetime_value"].isoformat() == "2026-08-04T12:34:56"
        assert native["json_value"] == '{"ok":true}'

        pooled_connection = pyodbc.connect(_connection_string(options), autocommit=False)
        pooled_connection.timeout = 17
        available = [pooled_connection]

        def acquire():
            return available.pop()

        def release(value):
            available.append(value)

        pooled_database = connect(
            "sqlserver",
            connection_factory=acquire,
            connection_releaser=release,
            connection_discarder=lambda value: value.close(),
            autocommit=False,
            query_timeout=3,
        )
        with pytest.raises(ProcedureExecutionError, match="intentional procora failure"):
            pooled_database.call("dbo.procora_it_always_fails")
        assert available == [pooled_connection]
        assert pooled_connection.timeout == 17
        assert pooled_database.call("dbo.procora_it_zero_arguments").first == native
        assert available == [pooled_connection]
        assert pooled_connection.timeout == 17
        pooled_connection.close()
    finally:
        cursor.execute("DROP PROCEDURE IF EXISTS dbo.procora_it_calculate")
        cursor.execute("DROP PROCEDURE IF EXISTS dbo.procora_it_defaults")
        cursor.execute("DROP PROCEDURE IF EXISTS dbo.procora_it_zero_arguments")
        cursor.execute("DROP PROCEDURE IF EXISTS dbo.procora_it_always_fails")
        cursor.close()
        connection.close()
