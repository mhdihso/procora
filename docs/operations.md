# Connections, transactions, and operational behavior

## Connection ownership

Every public operation borrows one connection. On the first procedure call, metadata
discovery and execution share that connection. Later calls reuse cached metadata.

Without `connection_releaser`, Procora closes each connection. With a releaser, Procora
first commits or rolls back as appropriate, restores temporary settings it changed, and
then invokes the releaser. Cleanup failures emit `RuntimeWarning` or are delivered to
`on_cleanup_error`.

When a pool can explicitly remove an unhealthy connection, pass its discard callback as
`connection_discarder`. Procora uses it if timeout/session preparation or reset fails,
if rollback fails, or if a commit error leaves the transaction outcome uncertain. If no
discard callback exists, Procora closes the unsafe connection rather than passing it to
the normal releaser.

Read-only operations (`inspect`, `list_procedures`, and `ping`) roll back transactions
started by catalog or health queries before returning a non-autocommit connection.

## Transaction boundaries

With `autocommit=False`, every successful `call()` commits independently and every
failed call rolls back. Multiple calls are not one atomic transaction:

```python
db.call("reserve_stock")  # committed
db.call("create_order")   # committed separately
```

Procora does not currently provide a multi-call transaction context.

## Timeout meanings

| Backend | Meaning of `query_timeout` |
|---|---|
| PostgreSQL | Server-side `statement_timeout`, transaction-local or restored after use |
| SQL Server | ODBC driver query timeout, restored after use |
| MySQL | Connector socket read/write timeouts, configured at connection creation |

MySQL timeouts are network I/O limits, not guaranteed server-side cancellation. A
custom MySQL factory must configure them in its pool and cannot combine them with
Procora's `query_timeout` option.

## Result buffering

All result sets are fetched into memory before the cursor and connection are released.
Keep procedure results bounded. Procora does not currently expose streaming results.

## Metadata visibility

Database accounts need both permission to execute routines and permission to see the
catalog metadata used for discovery. A login with `EXECUTE` but insufficient metadata
visibility may receive `ProcedureNotFoundError`.

Unknown supplied parameters are always rejected. PostgreSQL and MySQL metadata reliably
identifies required inputs, so Procora rejects missing ones before execution. SQL Server
does not reliably expose T-SQL default expressions in `sys.parameters`; omitted SQL
Server inputs are therefore passed to the server, which applies a default or returns its
native missing-parameter error.

## Schema-aware metadata caching

Before caching an unqualified procedure, PostgreSQL resolves effective `search_path`
visibility for that procedure name, MySQL resolves `DATABASE()`, and SQL Server resolves
its applicable schema. The resolved value is part of the
cache key, so connections with different session defaults cannot share metadata. An
unqualified `invalidate_metadata()` call removes matching entries across every resolved
schema; a qualified call removes only its exact entry.

Cache clearing and invalidation also cover discovery already in progress. The active
caller may receive the metadata it discovered, but Procora will not publish that stale
entry back into the cache after the invalidation generation changes. Per-key generation
state exists only while discovery is active and is removed on completion, so invalidating
arbitrary inactive names does not create an unbounded bookkeeping cache.

## Identifier limitations

The string API (`db.call("schema.procedure")`) is canonical. Attribute namespaces are
convenience syntax and may require `getattr()` for Python keywords or unusual names.

MySQL Connector/Python does not expose an identifier-quoting hook for `callproc()`, so
the built-in MySQL adapter accepts conventional unquoted identifiers only. PostgreSQL
uses effective `search_path` visibility for an unqualified name and rejects ambiguous
visible procedures; pass an explicit schema to choose one.

## Tested compatibility

CI exercises Python 3.10–3.14, installs every optional driver extra independently, and
tests both the exact minimum supported driver set and the newest versions allowed by the
package constraints. Its integration matrix covers PostgreSQL 11, 14, and 17; MySQL 8.0
and 8.4; and SQL Server 2019 and 2022 with ODBC Driver 18. Other server/driver
combinations should be validated before use in critical deployments.

## Azure SQL smoke test

The `Azure SQL Smoke` workflow runs every Monday and can also be started manually. Add
an encrypted repository secret named `PROCORA_AZURE_SQL_OPTIONS` containing the same JSON
accepted by `connect("sqlserver", ...)`, for example:

```json
{"host":"example.database.windows.net","database":"app","username":"user","password":"secret","driver":"ODBC Driver 18 for SQL Server"}
```

The workflow installs ODBC Driver 18 and calls `Database.ping()` through the SQL Server
backend. When the secret is absent, it reports a notice and skips external setup instead
of failing pull requests or scheduled builds.
