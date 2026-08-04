"""MySQL procedure backend using MySQL Connector/Python."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from warnings import catch_warnings, filterwarnings

from ..backend import Backend, ConnectionFactory, managed_cursor, unique_columns
from ..errors import (
    DriverNotInstalledError,
    ProcedureNotFoundError,
    ProcedureParameterError,
    UnsupportedParameterError,
)
from ..models import ParameterMode, ProcedureInfo, ProcedureParameter
from ..result import ProcedureResult, ResultSet

_METADATA_SQL = """
SELECT
    SPECIFIC_SCHEMA,
    SPECIFIC_NAME,
    ORDINAL_POSITION,
    PARAMETER_MODE,
    PARAMETER_NAME,
    DTD_IDENTIFIER,
    DATA_TYPE
FROM information_schema.parameters
WHERE ROUTINE_TYPE = 'PROCEDURE'
  AND SPECIFIC_SCHEMA = %s
  AND SPECIFIC_NAME = %s
ORDER BY ORDINAL_POSITION;
"""

_EXISTS_SQL = """
SELECT ROUTINE_SCHEMA, ROUTINE_NAME
FROM information_schema.routines
WHERE ROUTINE_TYPE = 'PROCEDURE'
  AND ROUTINE_SCHEMA = %s
  AND ROUTINE_NAME = %s;
"""

_LIST_SQL = """
SELECT ROUTINE_SCHEMA, ROUTINE_NAME
FROM information_schema.routines
WHERE ROUTINE_TYPE = 'PROCEDURE'
  AND ROUTINE_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME;
"""

_CALLPROC_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _validate_callproc_identifier(value: str, kind: str) -> None:
    if not _CALLPROC_IDENTIFIER.fullmatch(value):
        raise UnsupportedParameterError(
            f"MySQL {kind} {value!r} cannot be represented safely by Connector/Python callproc()"
        )


class MySQLBackend(Backend):
    name = "mysql"
    aliases = ("mariadb",)
    supports_per_borrow_query_timeout = False

    def create_connection_factory(
        self,
        *,
        autocommit: bool,
        connect_timeout: int,
        query_timeout: int,
        options: Mapping[str, Any],
    ) -> ConnectionFactory:
        values = dict(options)
        values.setdefault("connection_timeout", connect_timeout)
        values.setdefault("autocommit", autocommit)
        if query_timeout:
            values.setdefault("read_timeout", query_timeout)
            values.setdefault("write_timeout", query_timeout)

        def factory() -> Any:
            try:
                import mysql.connector
            except ImportError as exc:
                raise DriverNotInstalledError(
                    "Install MySQL support with: pip install 'procora[mysql]'"
                ) from exc
            return mysql.connector.connect(**values)

        return factory

    def set_query_timeout(self, connection: Any, seconds: int) -> None:
        # Connector/Python's C extension only accepts these at connect time.
        _ = (connection, seconds)

    def discover(self, connection: Any, name: str, schema: str | None) -> ProcedureInfo:
        with managed_cursor(connection.cursor()) as cursor:
            if schema is None:
                cursor.execute("SELECT DATABASE()")
                row = cursor.fetchone()
                schema = row[0] if row else None
            if not schema:
                raise ProcedureParameterError(
                    "MySQL needs a selected database or an explicit schema"
                )
            cursor.execute(_METADATA_SQL, (schema, name))
            rows = cursor.fetchall()
            if not rows:
                cursor.execute(_EXISTS_SQL, (schema, name))
                exists = cursor.fetchone()
                if not exists:
                    raise ProcedureNotFoundError(f"MySQL procedure does not exist: {schema}.{name}")
                return ProcedureInfo(self.name, str(schema), name)
        mode_map = {
            "IN": ParameterMode.IN,
            "OUT": ParameterMode.OUT,
            "INOUT": ParameterMode.INOUT,
        }
        parameters = tuple(
            ProcedureParameter(
                position=int(row[2]),
                name=str(row[4] or ""),
                native_type=str(row[5] or row[6]),
                mode=mode_map[str(row[3]).upper()],
                backend_data={"data_type": str(row[6])},
            )
            for row in rows
        )
        return ProcedureInfo(
            backend=self.name,
            schema=str(rows[0][0]),
            name=str(rows[0][1]),
            parameters=parameters,
        )

    def execute(
        self,
        connection: Any,
        procedure: ProcedureInfo,
        supplied: Mapping[int, Any],
    ) -> ProcedureResult:
        _validate_callproc_identifier(procedure.schema, "schema")
        _validate_callproc_identifier(procedure.name, "procedure")
        arguments = []
        for parameter in procedure.parameters:
            if parameter.mode is ParameterMode.OUT and parameter.position in supplied:
                raise ProcedureParameterError(
                    f"MySQL parameter {parameter.python_name} is OUT-only"
                )
            if parameter.position in supplied:
                arguments.append(supplied[parameter.position])
            elif parameter.mode is ParameterMode.OUT:
                arguments.append(None)
            else:
                raise ProcedureParameterError(
                    f"MySQL parameter {parameter.python_name} must be supplied"
                )
        with managed_cursor(connection.cursor()) as cursor:
            # Connector/Python's callproc() accepts a database-qualified name but
            # internally derives session-variable names from the unquoted routine.
            qualified = f"{procedure.schema}.{procedure.name}"
            returned = cursor.callproc(qualified, tuple(arguments))
            result_sets = self._stored_result_sets(cursor)
        output = {
            parameter.python_name: returned[parameter.position - 1]
            for parameter in procedure.output_parameters
        }
        return ProcedureResult(procedure, result_sets, output)

    @staticmethod
    def _stored_result_sets(cursor: Any) -> tuple[ResultSet, ...]:
        result_sets = []
        stored_results = cursor.stored_results
        if callable(stored_results):
            with catch_warnings():
                filterwarnings(
                    "ignore",
                    message="Call to deprecated function stored_results.*",
                    category=DeprecationWarning,
                )
                stored_results = stored_results()
        for stored in stored_results:
            with managed_cursor(stored):
                columns = unique_columns(stored.description)
                rows = tuple(dict(zip(columns, row, strict=False)) for row in stored.fetchall())
                result_sets.append(ResultSet(columns, rows))
        return tuple(result_sets)

    def list_procedures(self, connection: Any) -> list[str]:
        with managed_cursor(connection.cursor()) as cursor:
            cursor.execute(_LIST_SQL)
            return [f"{row[0]}.{row[1]}" for row in cursor.fetchall()]
