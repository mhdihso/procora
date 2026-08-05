# Backend notes

## Common guarantees

All built-in backends:

- discover procedures from live system catalogs;
- validate supplied names against discovered parameters;
- keep values out of generated SQL text;
- close cursors and connections they own;
- preserve all available tabular results;
- collect output values where the database supports them;
- commit successful calls and roll back failed calls when autocommit is disabled.

## SQL Server

Discovery uses `sys.procedures`, `sys.schemas`, `sys.parameters`, and `sys.types`. Input values use ODBC parameter markers. Output parameters and the integer return code use local T-SQL variables selected in a final private marker result set.

SQL Server reports `OUTPUT` parameters as capable of receiving an initial input. Supply
one normally if the procedure uses INOUT behavior; otherwise Procora initializes the
output variable to `NULL`.

This also applies when an `OUTPUT` parameter has a default in its T-SQL declaration.
Procora must pass a local variable to capture the output, and SQL Server does not apply
the declared default to that explicitly passed `NULL`. Procora cannot reliably discover
the default from `sys.parameters` and does not parse module definitions. Supply the
desired initial value explicitly:

```python
# CREATE PROCEDURE dbo.increment @value int = 5 OUTPUT ...
result = db.call("dbo.increment", value=5)
assert result.output["value"] == 6
```

Character lengths, binary lengths, `max`, decimal precision/scale, temporal scale, and user-defined alias types are reconstructed from catalog metadata for output variables.

Generic cursor output parameters are rejected. The built-in SQL Server backend does not
support table-valued parameters; use an application-specific custom backend for them.

Driver-level query timeouts are restored to their previous value before a pooled
connection is released. Procora does not change the session's `NOCOUNT` setting.

For an unqualified procedure name, Procora follows SQL Server object resolution: it
checks the connected principal's effective default schema first and then `dbo`. If the
procedure exists in neither schema, it raises `ProcedureNotFoundError`. An explicit
schema bypasses this lookup.

SQL Server catalog collation controls identifier case sensitivity. Procora preserves
identifier spelling in metadata cache keys rather than assuming a collation. Use one
consistent schema/procedure casing for calls and `invalidate_metadata()` so a
case-insensitive database does not accumulate duplicate cache entries.

The database principal needs enough metadata visibility to discover the procedure and `EXECUTE` permission to call it.

## PostgreSQL

Discovery uses `pg_catalog.pg_proc` and `pg_catalog.pg_namespace`, selecting only stored procedures (`prokind = 'p'`). PostgreSQL functions are deliberately outside Procora's stored-procedure API.

When no schema is supplied, Procora resolves the requested procedure using PostgreSQL's
effective `search_path` visibility. No visible procedure raises `ProcedureNotFoundError`;
multiple visible procedures or overloads raise `AmbiguousProcedureError`. Pass an
explicit schema to select a particular namespace.

Calls use named notation whenever parameters have names. This allows defaulted input parameters to be omitted while required OUT placeholders are still supplied as `NULL`. PostgreSQL returns OUT/INOUT values as one row; Procora converts that row into `result.output`.

Inside an explicit transaction, `query_timeout` uses a transaction-local
`statement_timeout` that disappears on commit or rollback. In autocommit mode, Procora
captures and restores the previous session value before releasing the connection.

PostgreSQL allows overloaded procedures. Procora refuses to guess among multiple routines with the same schema and name. Create a uniquely named wrapper or implement a signature-aware custom backend.

Variadic procedure parameters are rejected explicitly because Procora does not yet
provide a portable variadic calling convention. Trailing unnamed default parameters
can be omitted; an unnamed default before a later argument cannot be represented safely
and produces a clear parameter error.

If a procedure performs transaction control internally, use `autocommit=True`; PostgreSQL does not allow transaction control inside a procedure called from an existing transaction block.

## MySQL

Discovery uses `information_schema.parameters` and `information_schema.routines`. Execution uses Connector/Python's `callproc`, which returns a modified argument sequence containing OUT and INOUT values. Stored result cursors are converted to portable `ResultSet` objects.

Connector/Python deprecated `stored_results()` in 9.3 without documenting an equivalent
iterator for `callproc()` result sets. Procora isolates that compatibility call, filters
only its exact warning, tests current driver releases, and tracks replacement work in
[issue #3](https://github.com/mhdihso/procora/issues/3).

MySQL calls require all IN and INOUT parameters. Procora automatically supplies `None` placeholders for pure OUT parameters.

The adapter passes a metadata-resolved, schema-qualified procedure name to Connector/Python.
Connector/Python constructs its `CALL` statement from this name without an identifier
quoting API, so the built-in adapter accepts conventional unquoted MySQL identifiers
only. Names containing spaces, hyphens, dots, backticks, or other special characters
raise `UnsupportedParameterError` instead of producing a cryptic driver error.
`query_timeout` is applied to Connector/Python's socket read and write timeouts. These
are network I/O limits, not a server-side statement cancellation guarantee. They require
Connector/Python 9.2 or newer.

Connector/Python's C extension only accepts these timeouts while creating a connection.
Consequently, when using a custom MySQL connection factory, configure timeouts in the
pool itself and do not pass `query_timeout` to Procora; Procora raises a configuration
error instead of silently ignoring it.

## Unsupported databases

SQLite has no stored-procedure feature to adapt. Databases such as Oracle, IBM Db2, Firebird, and others can be integrated through the public `Backend` abstraction without changing the Procora core.
