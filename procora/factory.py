"""Backend selection and the top-level ``connect`` function."""

from __future__ import annotations

from typing import Any

from .backend import Backend, ConnectionFactory, ConnectionReleaser
from .database import CleanupErrorHandler, Database
from .errors import ConfigurationError


def _builtins() -> tuple[Backend, ...]:
    from .backends.mysql import MySQLBackend
    from .backends.postgresql import PostgreSQLBackend
    from .backends.sqlserver import SQLServerBackend

    return (SQLServerBackend(), PostgreSQLBackend(), MySQLBackend())


def get_backend(name: str) -> Backend:
    normalized = name.casefold().replace("-", "").replace("_", "")
    for backend in _builtins():
        names = (backend.name, *backend.aliases)
        if normalized in {item.casefold().replace("-", "").replace("_", "") for item in names}:
            return backend
    supported = ", ".join(backend.name for backend in _builtins())
    raise ConfigurationError(f"Unknown backend {name!r}; built-in backends: {supported}")


def connect(
    backend: str | Backend,
    *,
    connection_factory: ConnectionFactory | None = None,
    connection_releaser: ConnectionReleaser | None = None,
    on_cleanup_error: CleanupErrorHandler | None = None,
    autocommit: bool = True,
    connect_timeout: int = 30,
    query_timeout: int = 0,
    metadata_cache_ttl: float | None = None,
    metadata_cache_max_size: int | None = 1024,
    **driver_options: Any,
) -> Database:
    """Create a lazy, reusable procedure client."""
    if connect_timeout < 0 or query_timeout < 0:
        raise ConfigurationError("timeouts cannot be negative")
    selected = get_backend(backend) if isinstance(backend, str) else backend
    if not isinstance(selected, Backend):
        raise ConfigurationError("backend must be a built-in name or Backend instance")
    if connection_factory is not None and driver_options:
        raise ConfigurationError(
            "Driver options cannot be combined with a custom connection_factory"
        )
    if (
        connection_factory is not None
        and query_timeout
        and not selected.capabilities.supports_per_borrow_timeout
    ):
        raise ConfigurationError(
            f"{selected.name} query_timeout cannot be applied to connections from a "
            "custom factory; configure the timeout in the pool"
        )
    factory = connection_factory or selected.create_connection_factory(
        autocommit=autocommit,
        connect_timeout=connect_timeout,
        query_timeout=query_timeout,
        options=driver_options,
    )
    return Database(
        selected,
        factory,
        autocommit=autocommit,
        query_timeout=query_timeout,
        connection_releaser=connection_releaser,
        on_cleanup_error=on_cleanup_error,
        metadata_cache_ttl=metadata_cache_ttl,
        metadata_cache_max_size=metadata_cache_max_size,
    )
