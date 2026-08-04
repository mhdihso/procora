"""Database-neutral public API."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from threading import RLock
from typing import Any

from .backend import Backend, ConnectionFactory, ConnectionReleaser
from .errors import (
    DatabaseConnectionError,
    ProcedureExecutionError,
    ProcedureParameterError,
    ProcoraError,
)
from .models import ProcedureInfo, ProcedureParameter
from .result import ProcedureResult

_NOT_PREPARED = object()


def _procedure_parts(name: str, schema: str | None) -> tuple[str | None, str]:
    if not isinstance(name, str) or not name.strip():
        raise ProcedureParameterError("procedure name cannot be empty")
    if schema is not None:
        if not isinstance(schema, str) or not schema.strip():
            raise ProcedureParameterError("schema cannot be empty")
        return schema.strip(), name.strip()
    parts = name.split(".")
    if len(parts) == 1:
        return None, parts[0].strip()
    if len(parts) == 2 and all(part.strip() for part in parts):
        return parts[0].strip(), parts[1].strip()
    raise ProcedureParameterError(
        "Use 'Procedure', 'schema.Procedure', or pass schema= for names containing dots"
    )


class Procedure:
    """A lazy callable procedure proxy."""

    def __init__(self, database: Database, name: str, schema: str | None = None) -> None:
        self._database = database
        self.name = name
        self.schema = schema

    def inspect(self, *, refresh: bool = False) -> ProcedureInfo:
        return self._database.inspect(self.name, schema=self.schema, refresh=refresh)

    def __call__(
        self,
        parameters: Mapping[str, Any] | None = None,
        *,
        refresh_metadata: bool = False,
        **keyword_parameters: Any,
    ) -> ProcedureResult:
        return self._database.call(
            self.name,
            parameters,
            schema=self.schema,
            refresh=refresh_metadata,
            **keyword_parameters,
        )


class _ProcedureNamespace:
    def __init__(self, database: Database, schema: str | None = None) -> None:
        self._database = database
        self._schema = schema

    def __getattr__(self, name: str) -> Procedure:
        return Procedure(self._database, name, self._schema)


class _SchemaNamespace:
    def __init__(self, database: Database) -> None:
        self._database = database

    def __getattr__(self, schema: str) -> _ProcedureNamespace:
        return _ProcedureNamespace(self._database, schema)


class Database:
    """Call stored procedures through a selected database backend."""

    def __init__(
        self,
        backend: Backend,
        connection_factory: ConnectionFactory,
        *,
        autocommit: bool = True,
        query_timeout: int = 0,
        connection_releaser: ConnectionReleaser | None = None,
    ) -> None:
        if query_timeout < 0:
            raise ValueError("query_timeout cannot be negative")
        self.backend = backend
        self._connection_factory = connection_factory
        self.autocommit = autocommit
        self.query_timeout = query_timeout
        self._connection_releaser = connection_releaser
        self._metadata_cache: dict[tuple[str, str], ProcedureInfo] = {}
        self._cache_lock = RLock()
        self.procedures = _ProcedureNamespace(self)
        self.schemas = _SchemaNamespace(self)

    def _connect(self) -> tuple[Any, Any]:
        connection = None
        prepared_state = _NOT_PREPARED
        try:
            connection = self._connection_factory()
            if connection is None:
                raise DatabaseConnectionError("connection_factory returned None")
            prepared_state = self.backend.prepare_connection(connection, self.query_timeout)
            return connection, prepared_state
        except ProcoraError:
            if connection is not None:
                with suppress(Exception):
                    self._release(connection, prepared_state)
            raise
        except Exception as exc:
            if connection is not None:
                with suppress(Exception):
                    self._release(connection, prepared_state)
            raise DatabaseConnectionError(
                f"Could not connect using the {self.backend.name} backend: {exc}"
            ) from exc

    def _release(self, connection: Any, prepared_state: Any = _NOT_PREPARED) -> None:
        reset_error = None
        try:
            if prepared_state is not _NOT_PREPARED:
                self.backend.reset_connection(connection, prepared_state)
        except Exception as exc:
            reset_error = exc
        finally:
            if self._connection_releaser is None:
                connection.close()
            else:
                self._connection_releaser(connection)
        if reset_error is not None:
            raise reset_error

    def procedure(self, name: str, *, schema: str | None = None) -> Procedure:
        return Procedure(self, name, schema)

    def invalidate_metadata(self, name: str, *, schema: str | None = None) -> bool:
        """Remove one procedure from the metadata cache."""
        schema_name, procedure_name = _procedure_parts(name, schema)
        cache_key = (schema_name or "", procedure_name)
        with self._cache_lock:
            return self._metadata_cache.pop(cache_key, None) is not None

    def clear_metadata_cache(self) -> int:
        """Clear all discovered metadata and return the number of removed entries."""
        with self._cache_lock:
            count = len(self._metadata_cache)
            self._metadata_cache.clear()
            return count

    def _cached_info(
        self,
        cache_key: tuple[str, str],
        *,
        refresh: bool,
    ) -> ProcedureInfo | None:
        if refresh:
            return None
        with self._cache_lock:
            return self._metadata_cache.get(cache_key)

    def _discover_and_cache(
        self,
        connection: Any,
        schema_name: str | None,
        procedure_name: str,
        cache_key: tuple[str, str],
    ) -> ProcedureInfo:
        try:
            info = self.backend.discover(connection, procedure_name, schema_name)
        except ProcoraError:
            raise
        except Exception as exc:
            label = f"{schema_name}.{procedure_name}" if schema_name else procedure_name
            raise ProcedureExecutionError(
                f"Could not inspect {label} using {self.backend.name}: {exc}"
            ) from exc
        with self._cache_lock:
            self._metadata_cache[cache_key] = info
        return info

    def inspect(
        self,
        name: str,
        *,
        schema: str | None = None,
        refresh: bool = False,
    ) -> ProcedureInfo:
        schema_name, procedure_name = _procedure_parts(name, schema)
        cache_key = (schema_name or "", procedure_name)
        cached = self._cached_info(cache_key, refresh=refresh)
        if cached is not None:
            return cached

        connection = None
        prepared_state = _NOT_PREPARED
        try:
            connection, prepared_state = self._connect()
            return self._discover_and_cache(
                connection,
                schema_name,
                procedure_name,
                cache_key,
            )
        finally:
            if connection is not None:
                self._rollback(connection)
                with suppress(Exception):
                    self._release(connection, prepared_state)

    def call(
        self,
        name: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        schema: str | None = None,
        refresh: bool = False,
        **keyword_parameters: Any,
    ) -> ProcedureResult:
        if parameters is not None and keyword_parameters:
            raise ProcedureParameterError(
                "Pass parameters as a mapping or keyword arguments, not both"
            )
        supplied = parameters if parameters is not None else keyword_parameters
        if not isinstance(supplied, Mapping):
            raise ProcedureParameterError("parameters must be a mapping")
        schema_name, procedure_name = _procedure_parts(name, schema)
        cache_key = (schema_name or "", procedure_name)
        info = self._cached_info(cache_key, refresh=refresh)

        connection = None
        prepared_state = _NOT_PREPARED
        try:
            connection, prepared_state = self._connect()
            if info is None:
                info = self._discover_and_cache(
                    connection,
                    schema_name,
                    procedure_name,
                    cache_key,
                )
            normalized = self._normalize_parameters(info, supplied)
            result = self.backend.execute(connection, info, normalized)
            if not self._is_autocommit(connection):
                connection.commit()
            return result
        except ProcoraError:
            self._rollback(connection)
            raise
        except Exception as exc:
            self._rollback(connection)
            raise ProcedureExecutionError(
                f"Execution failed for {info.qualified_name} on {self.backend.name}: {exc}"
            ) from exc
        finally:
            if connection is not None:
                with suppress(Exception):
                    self._release(connection, prepared_state)

    @staticmethod
    def _normalize_parameters(info: ProcedureInfo, supplied: Mapping[str, Any]) -> dict[int, Any]:
        if not isinstance(supplied, Mapping):
            raise ProcedureParameterError("parameters must be a mapping")
        exact = {parameter.python_name: parameter for parameter in info.parameters}
        folded: dict[str, list[ProcedureParameter]] = {}
        for parameter in info.parameters:
            folded.setdefault(parameter.python_name.casefold(), []).append(parameter)

        normalized: dict[int, Any] = {}
        for raw_name, value in supplied.items():
            if not isinstance(raw_name, str):
                raise ProcedureParameterError("parameter names must be strings")
            name = raw_name.removeprefix("@")
            parameter = exact.get(name)
            if parameter is None:
                candidates = folded.get(name.casefold(), [])
                if len(candidates) > 1:
                    raise ProcedureParameterError(
                        f"Parameter {raw_name!r} is case-ambiguous; use exact database casing"
                    )
                parameter = candidates[0] if candidates else None
            if parameter is None:
                available = ", ".join(item.python_name for item in info.parameters) or "none"
                message = (
                    f"Unknown parameter {raw_name!r}; available for "
                    f"{info.qualified_name}: {available}"
                )
                raise ProcedureParameterError(message)
            if not parameter.mode.accepts_input:
                raise ProcedureParameterError(
                    f"Parameter {parameter.python_name!r} is OUT-only and cannot receive "
                    "an input value"
                )
            if parameter.position in normalized:
                raise ProcedureParameterError(f"Parameter was supplied more than once: {raw_name}")
            normalized[parameter.position] = value
        return normalized

    def list_procedures(self) -> list[str]:
        connection = None
        prepared_state = _NOT_PREPARED
        try:
            connection, prepared_state = self._connect()
            return self.backend.list_procedures(connection)
        except ProcoraError:
            raise
        except Exception as exc:
            raise ProcedureExecutionError(
                f"Could not list procedures using {self.backend.name}: {exc}"
            ) from exc
        finally:
            if connection is not None:
                self._rollback(connection)
                with suppress(Exception):
                    self._release(connection, prepared_state)

    def ping(self) -> bool:
        connection = None
        prepared_state = _NOT_PREPARED
        try:
            connection, prepared_state = self._connect()
            return self.backend.ping(connection)
        except ProcoraError:
            raise
        except Exception as exc:
            raise DatabaseConnectionError(
                f"{self.backend.name} health check failed: {exc}"
            ) from exc
        finally:
            if connection is not None:
                self._rollback(connection)
                with suppress(Exception):
                    self._release(connection, prepared_state)

    def _is_autocommit(self, connection: Any) -> bool:
        value = getattr(connection, "autocommit", self.autocommit)
        return bool(value() if callable(value) else value)

    def _rollback(self, connection: Any) -> None:
        if connection is None:
            return
        try:
            if not self._is_autocommit(connection):
                connection.rollback()
        except Exception:
            pass
