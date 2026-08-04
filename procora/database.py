"""Database-neutral public API."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Mapping
from threading import Event, RLock
from time import monotonic
from typing import Any
from warnings import warn

from .backend import Backend, ConnectionDiscarder, ConnectionFactory, ConnectionReleaser
from .errors import (
    DatabaseConnectionError,
    ProcedureDiscoveryError,
    ProcedureExecutionError,
    ProcedureParameterError,
    ProcoraError,
)
from .models import ProcedureInfo, ProcedureParameter
from .result import ProcedureResult

_NOT_PREPARED = object()
CleanupErrorHandler = Callable[[Exception], None]
DiscoveryClaim = tuple[Event, int, int]


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
        connection_discarder: ConnectionDiscarder | None = None,
        on_cleanup_error: CleanupErrorHandler | None = None,
        metadata_cache_ttl: float | None = None,
        metadata_cache_max_size: int | None = 1024,
    ) -> None:
        if query_timeout < 0:
            raise ValueError("query_timeout cannot be negative")
        if metadata_cache_ttl is not None and metadata_cache_ttl < 0:
            raise ValueError("metadata_cache_ttl cannot be negative")
        if metadata_cache_max_size is not None and metadata_cache_max_size < 0:
            raise ValueError("metadata_cache_max_size cannot be negative")
        self.backend = backend
        self._connection_factory = connection_factory
        self.autocommit = autocommit
        self.query_timeout = query_timeout
        self._connection_releaser = connection_releaser
        self._connection_discarder = connection_discarder
        self._on_cleanup_error = on_cleanup_error
        self.metadata_cache_ttl = metadata_cache_ttl
        self.metadata_cache_max_size = metadata_cache_max_size
        self._metadata_cache: OrderedDict[tuple[str, str], tuple[float, ProcedureInfo]] = (
            OrderedDict()
        )
        self._cache_lock = RLock()
        self._metadata_inflight: dict[tuple[str, str], Event] = {}
        self._cache_generation = 0
        self._cache_key_generations: dict[tuple[str, str], int] = {}
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
                self._release_safely(connection, prepared_state, discard=True)
            raise
        except Exception as exc:
            if connection is not None:
                self._release_safely(connection, prepared_state, discard=True)
            raise DatabaseConnectionError(
                f"Could not connect using the {self.backend.name} backend: {exc}"
            ) from exc

    def _release(
        self,
        connection: Any,
        prepared_state: Any = _NOT_PREPARED,
        *,
        discard: bool = False,
    ) -> None:
        errors = []
        must_discard = discard
        try:
            if prepared_state is not _NOT_PREPARED:
                self.backend.reset_connection(connection, prepared_state)
        except Exception as exc:
            errors.append(exc)
            must_discard = True
        try:
            if must_discard:
                if self._connection_discarder is not None:
                    self._connection_discarder(connection)
                else:
                    connection.close()
            elif self._connection_releaser is None:
                connection.close()
            else:
                self._connection_releaser(connection)
        except Exception as exc:
            errors.append(exc)
        if errors:
            if len(errors) > 1:
                errors[-1].__context__ = errors[0]
            raise errors[-1]

    def _report_cleanup_error(self, error: Exception) -> None:
        if self._on_cleanup_error is not None:
            try:
                self._on_cleanup_error(error)
                return
            except Exception as callback_error:
                error = callback_error
        warn(f"Procora connection cleanup failed: {error}", RuntimeWarning, stacklevel=3)

    def _release_safely(
        self,
        connection: Any,
        prepared_state: Any = _NOT_PREPARED,
        *,
        discard: bool = False,
    ) -> None:
        try:
            self._release(connection, prepared_state, discard=discard)
        except Exception as exc:
            self._report_cleanup_error(exc)

    def procedure(self, name: str, *, schema: str | None = None) -> Procedure:
        return Procedure(self, name, schema)

    def invalidate_metadata(self, name: str, *, schema: str | None = None) -> bool:
        """Remove one procedure from the metadata cache."""
        schema_name, procedure_name = _procedure_parts(name, schema)
        with self._cache_lock:
            if schema_name is not None:
                cache_key = (schema_name, procedure_name)
                removed = self._metadata_cache.pop(cache_key, None) is not None
                self._cache_key_generations[cache_key] = (
                    self._cache_key_generations.get(cache_key, 0) + 1
                )
                return removed
            matching = {
                key
                for key in self._metadata_cache.keys() | self._metadata_inflight.keys()
                if key[1] == procedure_name
            }
            removed = any(key in self._metadata_cache for key in matching)
            for key in matching:
                self._metadata_cache.pop(key, None)
                self._cache_key_generations[key] = (
                    self._cache_key_generations.get(key, 0) + 1
                )
            return removed

    def clear_metadata_cache(self) -> int:
        """Clear all discovered metadata and return the number of removed entries."""
        with self._cache_lock:
            count = len(self._metadata_cache)
            self._metadata_cache.clear()
            self._cache_generation += 1
            self._cache_key_generations.clear()
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
            cached = self._metadata_cache.get(cache_key)
            if cached is None:
                return None
            stored_at, info = cached
            if (
                self.metadata_cache_ttl is not None
                and monotonic() - stored_at >= self.metadata_cache_ttl
            ):
                del self._metadata_cache[cache_key]
                return None
            self._metadata_cache.move_to_end(cache_key)
            return info

    def _metadata_or_claim_discovery(
        self,
        cache_key: tuple[str, str],
        *,
        refresh: bool,
    ) -> tuple[ProcedureInfo | None, DiscoveryClaim | None]:
        while True:
            cached = self._cached_info(cache_key, refresh=refresh)
            if cached is not None:
                return cached, None
            with self._cache_lock:
                pending = self._metadata_inflight.get(cache_key)
                if pending is None:
                    pending = Event()
                    self._metadata_inflight[cache_key] = pending
                    return None, (
                        pending,
                        self._cache_generation,
                        self._cache_key_generations.get(cache_key, 0),
                    )
            pending.wait()
            refresh = False

    def _finish_discovery(
        self,
        cache_key: tuple[str, str],
        claim: DiscoveryClaim | None,
    ) -> None:
        if claim is None:
            return
        pending = claim[0]
        with self._cache_lock:
            if self._metadata_inflight.get(cache_key) is pending:
                del self._metadata_inflight[cache_key]
            pending.set()

    def _discover_and_cache(
        self,
        connection: Any,
        schema_name: str | None,
        procedure_name: str,
        cache_key: tuple[str, str],
        claim: DiscoveryClaim,
    ) -> ProcedureInfo:
        try:
            info = self.backend.discover(connection, procedure_name, schema_name)
        except ProcoraError:
            raise
        except Exception as exc:
            label = f"{schema_name}.{procedure_name}" if schema_name else procedure_name
            raise ProcedureDiscoveryError(
                f"Could not inspect {label} using {self.backend.name}: {exc}"
            ) from exc
        with self._cache_lock:
            if self.metadata_cache_max_size == 0:
                return info
            _, global_generation, key_generation = claim
            if (
                self._cache_generation != global_generation
                or self._cache_key_generations.get(cache_key, 0) != key_generation
            ):
                return info
            self._metadata_cache[cache_key] = (monotonic(), info)
            self._metadata_cache.move_to_end(cache_key)
            if self.metadata_cache_max_size is not None:
                while len(self._metadata_cache) > self.metadata_cache_max_size:
                    self._metadata_cache.popitem(last=False)
        return info

    def _resolve_schema(self, connection: Any, schema: str | None, name: str) -> str | None:
        try:
            return self.backend.resolve_schema(connection, schema)
        except ProcoraError:
            raise
        except Exception as exc:
            label = f"{schema}.{name}" if schema else name
            raise ProcedureDiscoveryError(
                f"Could not resolve the schema for {label} using {self.backend.name}: {exc}"
            ) from exc

    def inspect(
        self,
        name: str,
        *,
        schema: str | None = None,
        refresh: bool = False,
    ) -> ProcedureInfo:
        schema_name, procedure_name = _procedure_parts(name, schema)
        connection = None
        prepared_state = _NOT_PREPARED
        connection_healthy = True
        cache_key: tuple[str, str] | None = None
        claim: DiscoveryClaim | None = None
        try:
            if schema_name is None:
                connection, prepared_state = self._connect()
                schema_name = self._resolve_schema(connection, schema_name, procedure_name)
            cache_key = (schema_name or "", procedure_name)
            cached, claim = self._metadata_or_claim_discovery(
                cache_key,
                refresh=refresh,
            )
            if cached is not None:
                return cached
            if connection is None:
                connection, prepared_state = self._connect()
            assert claim is not None
            return self._discover_and_cache(
                connection,
                schema_name,
                procedure_name,
                cache_key,
                claim,
            )
        finally:
            if cache_key is not None:
                self._finish_discovery(cache_key, claim)
            if connection is not None:
                connection_healthy = self._rollback(connection)
                self._release_safely(
                    connection,
                    prepared_state,
                    discard=not connection_healthy,
                )

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
        procedure_label = f"{schema_name}.{procedure_name}" if schema_name else procedure_name

        connection = None
        prepared_state = _NOT_PREPARED
        connection_healthy = True
        commit_in_progress = False
        cache_key: tuple[str, str] | None = None
        claim: DiscoveryClaim | None = None
        try:
            if schema_name is None:
                connection, prepared_state = self._connect()
                schema_name = self._resolve_schema(connection, schema_name, procedure_name)
                procedure_label = (
                    f"{schema_name}.{procedure_name}" if schema_name else procedure_name
                )
            cache_key = (schema_name or "", procedure_name)
            info, claim = self._metadata_or_claim_discovery(
                cache_key,
                refresh=refresh,
            )
            if connection is None:
                connection, prepared_state = self._connect()
            if info is None:
                assert claim is not None
                info = self._discover_and_cache(
                    connection,
                    schema_name,
                    procedure_name,
                    cache_key,
                    claim,
                )
            normalized = self._normalize_parameters(info, supplied)
            result = self.backend.execute(connection, info, normalized)
            if not self._is_autocommit(connection):
                commit_in_progress = True
                connection.commit()
                commit_in_progress = False
            return result
        except ProcoraError:
            if not self._rollback(connection):
                connection_healthy = False
            raise
        except Exception as exc:
            if commit_in_progress:
                # A driver error during commit leaves the transaction outcome unknown.
                connection_healthy = False
            if not self._rollback(connection):
                connection_healthy = False
            raise ProcedureExecutionError(
                f"Execution failed for {procedure_label} on {self.backend.name}: {exc}"
            ) from exc
        finally:
            if cache_key is not None:
                self._finish_discovery(cache_key, claim)
            if connection is not None:
                self._release_safely(
                    connection,
                    prepared_state,
                    discard=not connection_healthy,
                )

    def _normalize_parameters(
        self, info: ProcedureInfo, supplied: Mapping[str, Any]
    ) -> dict[int, Any]:
        if not isinstance(supplied, Mapping):
            raise ProcedureParameterError("parameters must be a mapping")
        exact = {parameter.python_name: parameter for parameter in info.parameters}
        folded: dict[str, list[ProcedureParameter]] = {}
        for item in info.parameters:
            folded.setdefault(item.python_name.casefold(), []).append(item)

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
        if self.backend.capabilities.metadata_defaults_are_reliable:
            missing = [
                parameter.python_name
                for parameter in info.input_parameters
                if not parameter.has_default and parameter.position not in normalized
            ]
            if missing:
                raise ProcedureParameterError(
                    f"Missing required parameters for {info.qualified_name}: {', '.join(missing)}"
                )
        return normalized

    def list_procedures(self) -> list[str]:
        connection = None
        prepared_state = _NOT_PREPARED
        connection_healthy = True
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
                connection_healthy = self._rollback(connection)
                self._release_safely(
                    connection,
                    prepared_state,
                    discard=not connection_healthy,
                )

    def ping(self) -> bool:
        connection = None
        prepared_state = _NOT_PREPARED
        connection_healthy = True
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
                connection_healthy = self._rollback(connection)
                self._release_safely(
                    connection,
                    prepared_state,
                    discard=not connection_healthy,
                )

    def _is_autocommit(self, connection: Any) -> bool:
        value = getattr(connection, "autocommit", self.autocommit)
        return bool(value() if callable(value) else value)

    def _rollback(self, connection: Any) -> bool:
        if connection is None:
            return True
        try:
            if not self._is_autocommit(connection):
                connection.rollback()
        except Exception as exc:
            self._report_cleanup_error(exc)
            return False
        return True
