"""PostgreSQL procedure backend using psycopg 3."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..backend import Backend, ConnectionFactory, read_result_sets
from ..errors import (
    AmbiguousProcedureError,
    DriverNotInstalledError,
    ProcedureNotFoundError,
    ProcedureParameterError,
)
from ..models import ParameterMode, ProcedureInfo, ProcedureParameter
from ..result import ProcedureResult

_METADATA_SQL = """
SELECT
    procedure_object.oid,
    procedure_schema.nspname,
    procedure_object.proname,
    procedure_object.proargnames,
    procedure_object.proargmodes,
    ARRAY(
        SELECT format_type(argument_type, NULL)
        FROM unnest(
            COALESCE(procedure_object.proallargtypes, procedure_object.proargtypes::oid[])
        ) WITH ORDINALITY AS argument(argument_type, argument_order)
        ORDER BY argument_order
    ) AS argument_types,
    procedure_object.pronargdefaults
FROM pg_catalog.pg_proc AS procedure_object
JOIN pg_catalog.pg_namespace AS procedure_schema
    ON procedure_schema.oid = procedure_object.pronamespace
WHERE procedure_object.prokind = 'p'
  AND procedure_schema.nspname = %s
  AND procedure_object.proname = %s
ORDER BY procedure_object.oid;
"""

_LIST_SQL = """
SELECT procedure_schema.nspname, procedure_object.proname
FROM pg_catalog.pg_proc AS procedure_object
JOIN pg_catalog.pg_namespace AS procedure_schema
    ON procedure_schema.oid = procedure_object.pronamespace
WHERE procedure_object.prokind = 'p'
  AND procedure_schema.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY procedure_schema.nspname, procedure_object.proname;
"""


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


class PostgreSQLBackend(Backend):
    name = "postgresql"
    aliases = ("postgres", "psql")

    def create_connection_factory(
        self,
        *,
        autocommit: bool,
        connect_timeout: int,
        query_timeout: int,
        options: Mapping[str, Any],
    ) -> ConnectionFactory:
        _ = query_timeout
        values = dict(options)
        dsn = values.pop("dsn", values.pop("connection_string", ""))
        values.setdefault("connect_timeout", connect_timeout)

        def factory() -> Any:
            try:
                import psycopg
            except ImportError as exc:
                raise DriverNotInstalledError(
                    "Install PostgreSQL support with: pip install 'procora[postgresql]'"
                ) from exc
            if dsn:
                return psycopg.connect(dsn, autocommit=autocommit, **values)
            return psycopg.connect(autocommit=autocommit, **values)

        return factory

    def set_query_timeout(self, connection: Any, seconds: int) -> None:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "SELECT pg_catalog.set_config('statement_timeout', %s, false)",
                (str(seconds * 1000),),
            )
        finally:
            cursor.close()

    def discover(self, connection: Any, name: str, schema: str | None) -> ProcedureInfo:
        cursor = connection.cursor()
        try:
            if schema is None:
                cursor.execute("SELECT current_schema()")
                schema = cursor.fetchone()[0]
            cursor.execute(_METADATA_SQL, (schema, name))
            rows = cursor.fetchall()
        finally:
            cursor.close()
        if not rows:
            raise ProcedureNotFoundError(f"PostgreSQL procedure does not exist: {schema}.{name}")
        if len(rows) > 1:
            raise AmbiguousProcedureError(
                f"PostgreSQL procedure is overloaded: {schema}.{name}; "
                "use a custom backend or uniquely named wrapper procedure"
            )
        row = rows[0]
        names = list(row[3] or [])
        modes = list(row[4] or [])
        types = list(row[5] or [])
        if not modes:
            modes = ["i"] * len(types)
        if len(names) < len(types):
            names.extend([""] * (len(types) - len(names)))
        mode_map = {
            "i": ParameterMode.IN,
            "o": ParameterMode.OUT,
            "b": ParameterMode.INOUT,
            "v": ParameterMode.IN,
            "t": ParameterMode.OUT,
        }
        input_positions = [index for index, mode in enumerate(modes) if mode in {"i", "b", "v"}]
        default_count = int(row[6] or 0)
        default_indexes = set(input_positions[-default_count:]) if default_count else set()
        parameters = tuple(
            ProcedureParameter(
                position=index + 1,
                name=str(names[index] or ""),
                native_type=str(types[index]),
                mode=mode_map[modes[index]],
                has_default=index in default_indexes,
                backend_data={"postgres_mode": modes[index]},
            )
            for index in range(len(types))
        )
        return ProcedureInfo(
            backend=self.name,
            schema=str(row[1]),
            name=str(row[2]),
            parameters=parameters,
            identity=int(row[0]),
        )

    def execute(
        self,
        connection: Any,
        procedure: ProcedureInfo,
        supplied: Mapping[int, Any],
    ) -> ProcedureResult:
        sql, bindings = self._build_call(procedure, supplied)
        cursor = connection.cursor()
        try:
            cursor.execute(sql, tuple(bindings))
            result_sets = read_result_sets(cursor)
        finally:
            cursor.close()
        outputs = procedure.output_parameters
        if not outputs:
            return ProcedureResult(procedure, result_sets)
        if not result_sets or not result_sets[0].rows:
            raise ProcedureParameterError("PostgreSQL did not return its output-parameter row")
        values = tuple(result_sets[0].rows[0].values())
        output = {parameter.python_name: values[index] for index, parameter in enumerate(outputs)}
        return ProcedureResult(procedure, result_sets[1:], output)

    @staticmethod
    def _build_call(
        procedure: ProcedureInfo,
        supplied: Mapping[int, Any],
    ) -> tuple[str, list[Any]]:
        all_named = all(parameter.name for parameter in procedure.parameters)
        arguments: list[str] = []
        bindings: list[Any] = []
        if all_named:
            for parameter in procedure.parameters:
                label = _quote(parameter.name)
                if parameter.mode is ParameterMode.OUT:
                    arguments.append(f"{label} => NULL")
                elif parameter.position in supplied:
                    arguments.append(f"{label} => %s")
                    bindings.append(supplied[parameter.position])
                elif not parameter.has_default:
                    # Omitting it lets PostgreSQL produce its precise missing-argument error.
                    continue
        else:
            for parameter in procedure.parameters:
                if parameter.mode is ParameterMode.OUT:
                    arguments.append("NULL")
                elif parameter.position in supplied:
                    arguments.append("%s")
                    bindings.append(supplied[parameter.position])
                else:
                    raise ProcedureParameterError(
                        f"Unnamed PostgreSQL parameter {parameter.position} must be supplied"
                    )
        qualified = f"{_quote(procedure.schema)}.{_quote(procedure.name)}"
        return f"CALL {qualified}({', '.join(arguments)})", bindings

    def list_procedures(self, connection: Any) -> list[str]:
        cursor = connection.cursor()
        try:
            cursor.execute(_LIST_SQL)
            return [f"{row[0]}.{row[1]}" for row in cursor.fetchall()]
        finally:
            cursor.close()
