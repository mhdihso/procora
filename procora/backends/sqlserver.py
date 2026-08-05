"""Microsoft SQL Server backend using pyodbc."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..backend import Backend, ConnectionFactory, managed_cursor, read_result_sets
from ..errors import (
    ConfigurationError,
    DriverNotInstalledError,
    ProcedureExecutionError,
    ProcedureNotFoundError,
    UnsupportedParameterError,
)
from ..models import BackendCapabilities, ParameterMode, ProcedureInfo, ProcedureParameter
from ..result import ProcedureResult

_METADATA_SQL = """
SELECT
    procedure_object.object_id,
    procedure_schema.name,
    procedure_object.name,
    procedure_parameter.parameter_id,
    procedure_parameter.name,
    parameter_type.name,
    type_schema.name,
    procedure_parameter.max_length,
    procedure_parameter.precision,
    procedure_parameter.scale,
    procedure_parameter.is_output,
    procedure_parameter.is_cursor_ref,
    parameter_type.is_table_type
FROM sys.procedures AS procedure_object
JOIN sys.schemas AS procedure_schema
    ON procedure_schema.schema_id = procedure_object.schema_id
LEFT JOIN sys.parameters AS procedure_parameter
    ON procedure_parameter.object_id = procedure_object.object_id
LEFT JOIN sys.types AS parameter_type
    ON parameter_type.user_type_id = procedure_parameter.user_type_id
LEFT JOIN sys.schemas AS type_schema
    ON type_schema.schema_id = parameter_type.schema_id
WHERE procedure_schema.name = ? AND procedure_object.name = ?
ORDER BY procedure_parameter.parameter_id;
"""

_LIST_SQL = """
SELECT procedure_schema.name, procedure_object.name
FROM sys.procedures AS procedure_object
JOIN sys.schemas AS procedure_schema
    ON procedure_schema.schema_id = procedure_object.schema_id
WHERE procedure_object.is_ms_shipped = 0
ORDER BY procedure_schema.name, procedure_object.name;
"""

_RETURN_COLUMN = "__procora_return_value"
_OUTPUT_PREFIX = "__procora_output_"


def _quote(value: str) -> str:
    return "[" + value.replace("]", "]]") + "]"


def _odbc_value(value: object) -> str:
    return "{" + str(value).replace("}", "}}") + "}"


def _boolean_option(values: dict[str, Any], name: str, default: bool) -> bool:
    value = values.pop(name, default)
    if not isinstance(value, bool):
        raise ConfigurationError(f"SQL Server option {name} must be a boolean")
    return value


def _detect_driver() -> str:
    try:
        import pyodbc
    except ImportError as exc:
        raise DriverNotInstalledError(
            "Install SQL Server support with: pip install 'procora[sqlserver]'"
        ) from exc
    installed = pyodbc.drivers()
    for preferred in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"):
        if preferred in installed:
            return preferred
    available = ", ".join(installed) or "none"
    raise ConfigurationError(
        f"Install Microsoft ODBC Driver 18 or 17 for SQL Server; currently available: {available}"
    )


def _connection_string(options: Mapping[str, Any]) -> str:
    values = dict(options)
    raw = values.pop("connection_string", None)
    if raw is not None:
        if values:
            raise ConfigurationError(
                "connection_string cannot be combined with SQL Server credential fields"
            )
        return str(raw)

    host = values.pop("host", None)
    database = values.pop("database", None)
    username = values.pop("username", values.pop("user", None))
    password = values.pop("password", None)
    raw_port = values.pop("port", 1433)
    try:
        if isinstance(raw_port, bool):
            raise ValueError
        port = int(raw_port)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("SQL Server option port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ConfigurationError("SQL Server option port must be between 1 and 65535")
    driver = values.pop("driver", None) or _detect_driver()
    trusted = _boolean_option(values, "trusted_connection", False)
    encrypt = _boolean_option(values, "encrypt", True)
    trust_certificate = _boolean_option(values, "trust_server_certificate", False)
    application_name = values.pop("application_name", "procora")
    if values:
        raise ConfigurationError(f"Unknown SQL Server options: {', '.join(sorted(values))}")
    if not host or not database:
        raise ConfigurationError("SQL Server requires host and database")
    if not trusted and (not username or password is None):
        raise ConfigurationError("SQL Server requires username/password or trusted_connection=True")
    parts = [
        f"DRIVER={_odbc_value(driver)}",
        f"SERVER={_odbc_value(f'{host},{port}')}",
        f"DATABASE={_odbc_value(database)}",
    ]
    if trusted:
        parts.append("Trusted_Connection=yes")
    else:
        parts.extend([f"UID={_odbc_value(username)}", f"PWD={_odbc_value(password)}"])
    parts.extend(
        [
            f"Encrypt={'yes' if encrypt else 'no'}",
            f"TrustServerCertificate={'yes' if trust_certificate else 'no'}",
            f"APP={_odbc_value(application_name)}",
        ]
    )
    return ";".join(parts) + ";"


def _declaration_type(parameter: ProcedureParameter) -> str:
    data = parameter.backend_data
    if data.get("is_cursor_ref"):
        raise UnsupportedParameterError(
            f"Cursor output parameter {parameter.name} needs a custom adapter"
        )
    if data.get("is_table_type"):
        raise UnsupportedParameterError(
            f"Table-valued parameter {parameter.name} needs a custom adapter"
        )
    type_name = parameter.native_type
    type_schema = str(data["type_schema"])
    base = (
        _quote(type_name)
        if type_schema.casefold() == "sys"
        else f"{_quote(type_schema)}.{_quote(type_name)}"
    )
    normalized = type_name.casefold()
    max_length = int(data["max_length"])
    if normalized in {"varchar", "char", "varbinary", "binary"}:
        length = "max" if max_length == -1 else str(max_length)
        return f"{base}({length})"
    if normalized in {"nvarchar", "nchar"}:
        length = "max" if max_length == -1 else str(max_length // 2)
        return f"{base}({length})"
    if normalized in {"decimal", "numeric"}:
        return f"{base}({data['precision']},{data['scale']})"
    if normalized in {"datetime2", "datetimeoffset", "time"}:
        return f"{base}({data['scale']})"
    return base


class SQLServerBackend(Backend):
    name = "sqlserver"
    aliases = ("mssql", "sql-server")
    capabilities = BackendCapabilities(
        supports_multiple_result_sets=True,
        supports_output_parameters=True,
        supports_return_value=True,
        timeout_kind="driver",
    )

    def create_connection_factory(
        self,
        *,
        autocommit: bool,
        connect_timeout: int,
        query_timeout: int,
        options: Mapping[str, Any],
    ) -> ConnectionFactory:
        _ = query_timeout
        connection_string = _connection_string(options)

        def factory() -> Any:
            try:
                import pyodbc
            except ImportError as exc:
                raise DriverNotInstalledError(
                    "Install SQL Server support with: pip install 'procora[sqlserver]'"
                ) from exc
            return pyodbc.connect(
                connection_string,
                autocommit=autocommit,
                timeout=connect_timeout,
            )

        return factory

    def set_query_timeout(self, connection: Any, seconds: int) -> None:
        connection.timeout = seconds

    def prepare_connection(self, connection: Any, query_timeout: int) -> int | None:
        if not query_timeout:
            return None
        previous = int(connection.timeout)
        connection.timeout = query_timeout
        return previous

    def reset_connection(self, connection: Any, state: Any) -> None:
        if state is not None:
            connection.timeout = int(state)

    def resolve_schema(self, connection: Any, name: str, schema: str | None) -> str:
        _ = (connection, name)
        return schema or "dbo"

    def discover(self, connection: Any, name: str, schema: str | None) -> ProcedureInfo:
        schema = self.resolve_schema(connection, name, schema)
        with managed_cursor(connection.cursor()) as cursor:
            cursor.execute(_METADATA_SQL, schema, name)
            rows = cursor.fetchall()
        if not rows:
            raise ProcedureNotFoundError(f"SQL Server procedure does not exist: {schema}.{name}")
        first = rows[0]
        parameters = []
        for row in rows:
            if row[3] is None:
                continue
            is_output = bool(row[10])
            parameters.append(
                ProcedureParameter(
                    position=int(row[3]),
                    name=str(row[4]),
                    native_type=str(row[5]),
                    mode=ParameterMode.INOUT if is_output else ParameterMode.IN,
                    backend_data={
                        "type_schema": str(row[6]),
                        "max_length": int(row[7]),
                        "precision": int(row[8]),
                        "scale": int(row[9]),
                        "is_cursor_ref": bool(row[11]),
                        "is_table_type": bool(row[12]),
                    },
                )
            )
        return ProcedureInfo(
            backend=self.name,
            schema=str(first[1]),
            name=str(first[2]),
            parameters=tuple(parameters),
            identity=int(first[0]),
        )

    def execute(
        self,
        connection: Any,
        procedure: ProcedureInfo,
        supplied: Mapping[int, Any],
    ) -> ProcedureResult:
        sql, bindings = self._build_call(procedure, supplied)
        with managed_cursor(connection.cursor()) as cursor:
            cursor.execute(sql, *bindings) if bindings else cursor.execute(sql)
            sets = read_result_sets(cursor)
        expected = (_RETURN_COLUMN,) + tuple(
            f"{_OUTPUT_PREFIX}{index}" for index in range(len(procedure.output_parameters))
        )
        if not sets or sets[-1].columns != expected or not sets[-1].rows:
            raise ProcedureExecutionError("SQL Server output marker was not returned")
        marker = sets[-1].rows[0]
        output = {
            parameter.python_name: marker[f"{_OUTPUT_PREFIX}{index}"]
            for index, parameter in enumerate(procedure.output_parameters)
        }
        return ProcedureResult(
            procedure,
            sets[:-1],
            output,
            marker[_RETURN_COLUMN],
        )

    @staticmethod
    def _build_call(
        procedure: ProcedureInfo,
        supplied: Mapping[int, Any],
    ) -> tuple[str, tuple[Any, ...]]:
        statements = ["DECLARE @__procora_return int;"]
        assignments = []
        bindings = []
        outputs = procedure.output_parameters
        output_indexes = {parameter.position: index for index, parameter in enumerate(outputs)}
        for index, parameter in enumerate(outputs):
            variable = f"@__procora_out_{index}"
            statements.append(f"DECLARE {variable} {_declaration_type(parameter)};")
            if parameter.position in supplied:
                statements.append(f"SET {variable} = ?;")
                bindings.append(supplied[parameter.position])
        for parameter in procedure.parameters:
            if parameter.backend_data.get("is_table_type"):
                raise UnsupportedParameterError(
                    f"Table-valued parameter {parameter.name} needs a custom adapter"
                )
            if parameter.mode.returns_output:
                index = output_indexes[parameter.position]
                assignments.append(f"{parameter.name} = @__procora_out_{index} OUTPUT")
            elif parameter.position in supplied:
                assignments.append(f"{parameter.name} = ?")
                bindings.append(supplied[parameter.position])
        qualified = f"{_quote(procedure.schema)}.{_quote(procedure.name)}"
        execute = f"EXEC @__procora_return = {qualified}"
        if assignments:
            execute += "\n    " + ",\n    ".join(assignments)
        statements.append(execute + ";")
        selections = [f"@__procora_return AS [{_RETURN_COLUMN}]"]
        selections.extend(
            f"@__procora_out_{index} AS [{_OUTPUT_PREFIX}{index}]" for index in range(len(outputs))
        )
        statements.append("SELECT " + ", ".join(selections) + ";")
        return "\n".join(statements), tuple(bindings)

    def list_procedures(self, connection: Any) -> list[str]:
        with managed_cursor(connection.cursor()) as cursor:
            cursor.execute(_LIST_SQL)
            return [f"{row[0]}.{row[1]}" for row in cursor.fetchall()]
