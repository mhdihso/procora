"""Opt-in end-to-end stored-procedure tests for dedicated disposable databases."""

import json
import os

import pytest

from procora import connect


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
        connection.execute("CREATE SCHEMA procora_it")
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
    finally:
        connection.execute("DROP SCHEMA IF EXISTS procora_it CASCADE")
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

        database = connect("mysql", **options)
        schema = options["database"]
        qualified = f"{schema}.procora_it_calculate"
        assert qualified in database.list_procedures()
        result = database.call(qualified, value=7, doubled=0)
        assert result.rows == [{"input_value": 7, "doubled_value": 14}]
        assert result.result_sets[1].as_list() == [{"result_name": "second"}]
        assert result.output == {"doubled": 14, "label": "ok"}
    finally:
        cursor.execute("DROP PROCEDURE IF EXISTS procora_it_calculate")
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
                RETURN 7;
            END
            """
        )

        database = connect("sqlserver", **options)
        result = database.call("dbo.procora_it_calculate", value=7, doubled=0)
        assert result.rows == [{"input_value": 7, "doubled_value": 14}]
        assert result.output == {"doubled": 14}
        assert result.return_value == 7
    finally:
        cursor.execute("DROP PROCEDURE IF EXISTS dbo.procora_it_calculate")
        cursor.close()
        connection.close()
