# API reference

## `connect`

```python
connect(
    backend,
    *,
    connection_factory=None,
    connection_releaser=None,
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
- `call(name, parameters=None, *, schema=None, refresh=False, **values) -> ProcedureResult`:
  discover and execute a procedure.
- `procedure(name, *, schema=None) -> Procedure`: create a reusable callable proxy.
- `procedures.<name>(**values)`: call a procedure in the backend's default schema.
- `schemas.<schema>.<name>(**values)`: call a schema-qualified procedure.

Every operation borrows a new connection. The connection is closed afterward, or
passed to `connection_releaser` when one is configured.

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

`ResultSet.columns` preserves column order. `ResultSet.rows` is an immutable tuple of
row dictionaries, while `ResultSet.as_list()` returns a mutable copy.

## Metadata models

`ProcedureInfo` provides `backend`, `schema`, `name`, `qualified_name`, `parameters`,
`input_parameters`, and `output_parameters`.

Each `ProcedureParameter` provides `position`, `name`, `python_name`, `native_type`,
`mode`, and `has_default`. `mode` is one of `ParameterMode.IN`, `OUT`, or `INOUT`.

## Exceptions

Catch `ProcoraError` for every expected library error, or a specific subclass:

- `ConfigurationError`
- `DriverNotInstalledError`
- `DatabaseConnectionError`
- `ProcedureNotFoundError`
- `AmbiguousProcedureError`
- `ProcedureParameterError`
- `UnsupportedParameterError`
- `ProcedureExecutionError`

The original driver exception is retained as `exception.__cause__` when Procora wraps
an unexpected connection, discovery, or execution failure.
