# API reference

## `connect`

```python
connect(
    backend,
    *,
    connection_factory=None,
    connection_releaser=None,
    on_cleanup_error=None,
    autocommit=True,
    connect_timeout=30,
    query_timeout=0,
    **driver_options,
) -> Database
```

`backend` is `sqlserver`, `postgresql`, `mysql`, an accepted alias, or a custom
`Backend` instance. Driver options are passed to the selected driver's connection
constructor. A custom factory cannot be combined with driver options.

## `Database`

- `ping() -> bool`: run a lightweight database health check.
- `list_procedures() -> list[str]`: list user procedures visible to the login.
- `inspect(name, *, schema=None, refresh=False) -> ProcedureInfo`: discover and cache
  procedure metadata.
- `invalidate_metadata(name, *, schema=None) -> bool`: remove one cached procedure.
- `clear_metadata_cache() -> int`: clear the cache and return the number of entries.
- `call(name, parameters=None, *, schema=None, refresh=False, **values) -> ProcedureResult`:
  discover and execute a procedure.
- `procedure(name, *, schema=None) -> Procedure`: create a reusable callable proxy. The
  proxy accepts either a parameter mapping or keyword arguments and uses
  `refresh_metadata=True` to refresh discovery.
- `procedures.<name>(**values)`: call a procedure in the backend's default schema.
- `schemas.<schema>.<name>(**values)`: call a schema-qualified procedure.

Every operation borrows a new connection. The connection is closed afterward, or
passed to `connection_releaser` when one is configured.

Cleanup failures do not replace a successful procedure result or the original database
error. By default they emit `RuntimeWarning`; pass `on_cleanup_error=callback` to route
them to application logging or monitoring.

## `ProcedureResult`

| Member | Meaning |
|---|---|
| `result_sets` | Tuple of all portable `ResultSet` objects |
| `rows` | First result set as a new `list[dict]` |
| `first` | First row, or `None` |
| `scalar` | First value in the first row, or `None` |
| `output` | OUT and INOUT values keyed by discovered parameter name |
| `return_value` | SQL Server integer `RETURN` value; otherwise `None` |
| `json()` | Decode JSON text stored in `scalar` |

`ResultSet.columns` preserves column order. Result rows, output parameters, and metadata
backend data are exposed as read-only mappings. `ResultSet.as_list()` and `result.rows`
return mutable dictionary copies.

## Metadata models

`ProcedureInfo` provides `backend`, `schema`, `name`, `qualified_name`, `parameters`,
`input_parameters`, and `output_parameters`.

Each `ProcedureParameter` provides `position`, `name`, `python_name`, `native_type`,
`mode`, and `has_default`. `mode` is one of `ParameterMode.IN`, `OUT`, or `INOUT`.

Every backend exposes immutable `BackendCapabilities` through `backend.capabilities`,
including result-set, output, return-value, overload, timeout, default-metadata, and
buffering behavior.

## Exceptions

Catch `ProcoraError` for every expected library error, or a specific subclass:

- `ConfigurationError`
- `DriverNotInstalledError`
- `DatabaseConnectionError`
- `ProcedureNotFoundError`
- `AmbiguousProcedureError`
- `ProcedureDiscoveryError`
- `ProcedureParameterError`
- `UnsupportedParameterError`
- `ProcedureExecutionError`

`CleanupErrorHandler` is the callback type accepted by `on_cleanup_error`.

The original driver exception is retained as `exception.__cause__` when Procora wraps
an unexpected connection, discovery, or execution failure.
