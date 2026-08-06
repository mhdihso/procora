# Procora

**One Python API for stored procedures across databases.**

```python
from procora import connect

db = connect("postgresql", dsn="postgresql://app:secret@localhost/shop")
result = db.call("sales.create_order", customer_id=42)

print(result.rows)
print(result.output)
print(result.return_value)
```

Procora reads procedure metadata from the connected database, binds Python values through the native driver, executes the procedure, and returns a portable `ProcedureResult`.

There are no duplicated procedure definitions, SQL templates, Django project, or REST server.

## Supported databases

| Backend | Driver | Result sets | OUT/INOUT | Integer return code |
|---|---|---:|---:|---:|
| SQL Server / Azure SQL | `pyodbc` | yes | yes | yes |
| PostgreSQL 11+ | `psycopg` 3 | procedure output row | INOUT on 11+; OUT on 14+ | not applicable |
| MySQL | MySQL Connector/Python | yes | yes | not applicable |

MariaDB can use the MySQL adapter when its Connector/Python-compatible behavior matches the called routines. Additional databases can implement Procora's small `Backend` interface.

Real-database CI covers PostgreSQL 11, 14, and 17; MySQL 8.0 and 8.4; and SQL Server
2019 and 2022. Azure SQL uses the SQL Server backend and is validated separately through
an optional smoke workflow.

SQLite is not listed because SQLite does not implement stored procedures.

Procora follows Semantic Versioning. In the 1.x line, the exported Python API,
documented result and error behavior, and custom backend contract remain backward
compatible; internal catalog SQL and underscore-prefixed helpers are not public API.

## Installation

Install only the driver you need:

```bash
pip install 'procora[sqlserver]'
pip install 'procora[postgresql]'
pip install 'procora[mysql]'
```

Or install every built-in adapter:

```bash
pip install 'procora[all]'
```

For local development from this repository:

```bash
python -m pip install -e '.[all,dev]'
```

SQL Server also requires Microsoft ODBC Driver 18 or 17 at the operating-system level.

## Connect

### SQL Server

```python
from procora import connect

db = connect(
    "sqlserver",
    host="sql.example.internal",
    database="Accounting",
    username="app_user",
    password="secret-from-a-secret-manager",
    encrypt=True,
)
```

Procora automatically prefers installed Microsoft ODBC Driver 18, then Driver 17. You can also provide a complete ODBC string:

```python
db = connect("sqlserver", connection_string=odbc_connection_string)
```

Aliases: `mssql`, `sql-server`.

### PostgreSQL

```python
db = connect(
    "postgresql",
    dsn="postgresql://app_user:secret@localhost:5432/accounting",
)
```

Or pass normal psycopg connection options:

```python
db = connect(
    "postgres",
    host="localhost",
    dbname="accounting",
    user="app_user",
    password="secret",
)
```

Aliases: `postgres`, `psql`.

### MySQL

```python
db = connect(
    "mysql",
    host="localhost",
    database="accounting",
    user="app_user",
    password="secret",
)
```

Alias: `mariadb`.

Creating a Procora client is lazy: it does not connect until `ping`, `inspect`, `list_procedures`, or `call` is used.

## Call procedures

The API is the same for every backend:

```python
# Standard
result = db.call("sales.create_order", customer_id=42, note="first order")

# Mapping form—including database parameter prefixes when convenient
result = db.call("sales.create_order", {"customer_id": 42, "@note": None})

# Reusable callable
create_order = db.procedure("sales.create_order")
result = create_order(customer_id=42)

# Mapping form also works through proxies, including reserved call option names
special = db.procedure("special_parameter_names")
result = special({"schema": "procedure-value", "refresh": "procedure-value"})

# Attribute namespaces
result = db.procedures.daily_maintenance()
result = db.schemas.sales.create_order(customer_id=42)
```

Mapping and keyword styles cannot be combined in one call. Parameter matching first uses exact database casing, then an unambiguous case-insensitive match.

Use the mapping form if a procedure itself has parameters named `schema` or `refresh`, because those names are options on `db.call`.

## Read responses

```python
result.rows          # First result set as list[dict]
result.first         # First row or None
result.scalar        # First column of the first row or None
result.result_sets   # Every portable ResultSet
result.output        # OUT and INOUT values
result.return_value  # SQL Server integer RETURN; otherwise None
result.json()        # Decode JSON text from result.scalar
```

Duplicate column labels are made unique (`Name`, `Name_2`, and so on). Driver-native Python types such as `Decimal`, `date`, `datetime`, `bytes`, and UUID values are preserved.

Procora buffers every returned result set in memory before releasing the connection.
Use it for bounded procedure results; a streaming API is not currently provided. Stored
result rows and output mappings are read-only, while `result.rows` returns mutable copies.

## Live discovery

Procora does not need a local registry:

```python
print(db.list_procedures())

info = db.inspect("sales.create_order")
for parameter in info.parameters:
    print(
        parameter.position,
        parameter.name,
        parameter.native_type,
        parameter.mode,
    )
```

Metadata is cached after first use. Refresh it after changing a procedure:

```python
result = db.call("sales.create_order", refresh=True, customer_id=42)
```

After a migration, invalidate one procedure or the complete cache explicitly:

```python
db.invalidate_metadata("sales.create_order")
removed_count = db.clear_metadata_cache()
```

The cache keeps at most 1,024 procedures by default. Dynamic-schema applications can
set `metadata_cache_ttl=300`, adjust `metadata_cache_max_size`, or use size `0` to
disable metadata storage.

For unqualified calls, built-in backends resolve the active schema/database on the
borrowed connection before looking in the cache. Metadata from different tenant schemas
therefore remains isolated even when pooled connections have different session defaults.
Calling `invalidate_metadata("procedure")` removes that name from every resolved schema;
pass an explicit schema to remove only one entry.
Invalidation and clearing are generation-safe: metadata discovery that started before
either operation may finish for its caller, but cannot repopulate the invalidated cache.

Cache identity preserves the schema and procedure spelling returned or supplied to the
API. Use consistent canonical casing for calls and invalidation. This matters on a
case-insensitive SQL Server database, where `dbo.GetUsers` and `DBO.getusers` may resolve
to the same object but intentionally remain distinct cache identities; Procora does not
case-fold names because that would be incorrect for case-sensitive databases.

## Transactions and timeouts

Autocommit is enabled by default. For explicit per-call commit/rollback:

```python
db = connect(
    "postgresql",
    dsn=dsn,
    autocommit=False,
    connect_timeout=10,
    query_timeout=60,
)
```

Each operation owns and closes its connection, making a client safe to share across threads when the provided connection factory is thread-safe. Driver pooling can still reuse physical connections.

Procora never automatically retries a failed procedure; retrying a partially completed write can duplicate work.

## Custom connection pools

Use any pool that returns compatible DB-API connections:

```python
db = connect(
    "postgresql",
    connection_factory=my_pool.getconn,
    connection_releaser=my_pool.putconn,
    connection_discarder=lambda connection: my_pool.putconn(connection, close=True),
)
```

`connection_releaser` returns borrowed connections to the pool. Without it, Procora
calls `close()` after each operation. Driver connection options cannot be mixed with
a custom factory. Before returning a connection, Procora cleans up read transactions
and restores temporary backend settings it changed.
Provide `connection_discarder` for production pools. Procora uses it instead of the
normal releaser after failed session reset or rollback, and when a commit outcome is
uncertain. If no discard callback exists, Procora closes that unsafe connection.

## Add another database

Subclass `procora.Backend` and implement four operations:

- create a connection factory;
- discover one procedure;
- execute a discovered procedure;
- list procedures.

Then pass the backend instance to `connect`:

```python
db = connect(MyOracleBackend(), connection_factory=oracle_pool.acquire)
```

See [custom backends](docs/custom-backends.md) for a complete minimal implementation.

## Database-specific behavior

- SQL Server T-SQL procedure defaults are left to SQL Server because their expressions are not reliably present in `sys.parameters`.
- A defaulted SQL Server `OUTPUT` parameter must receive its desired initial value
  explicitly. Procora passes a local variable to capture the output, so omitting that
  input passes `NULL` rather than activating the T-SQL default.
- PostgreSQL overloaded procedure names are ambiguous without a signature; Procora asks for a uniquely named wrapper rather than guessing a type overload.
- PostgreSQL functions are not procedures and should be queried with `SELECT`, so the PostgreSQL adapter intentionally discovers only `prokind = 'p'`.
- MySQL requires every IN/INOUT argument. OUT placeholders are provided automatically.
- Table-valued and cursor parameters can require a custom, application-specific adapter.

More detail is in [backend notes](docs/backends.md).

The public classes, result fields, methods, and exception hierarchy are listed in the
[API reference](docs/api.md).

Production connection ownership, transaction boundaries, timeout meanings, buffering,
permissions, identifiers, and tested versions are covered in the
[operations guide](docs/operations.md).

## Testing

```bash
python -m pip install -e '.[all,dev]'
ruff check procora tests examples
pytest
python -m build
```

Real health checks run automatically when their JSON option variables are configured:

```bash
export PROCORA_POSTGRESQL_OPTIONS='{"dsn":"postgresql://app:secret@localhost/db"}'
export PROCORA_MYSQL_OPTIONS='{"host":"localhost","database":"db","user":"app","password":"secret"}'
export PROCORA_SQLSERVER_OPTIONS='{"connection_string":"DRIVER={ODBC Driver 18 for SQL Server};..."}'
pytest tests/test_live_databases.py
```

The end-to-end integration suite creates and drops procedures, so run it only against
dedicated disposable databases:

```bash
export PROCORA_INTEGRATION_POSTGRESQL_OPTIONS='{"dsn":"postgresql://app:secret@localhost/procora_test"}'
export PROCORA_INTEGRATION_MYSQL_OPTIONS='{"host":"localhost","database":"procora_test","user":"root","password":"secret"}'
pytest -m integration
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete development workflow and
[CHANGELOG.md](CHANGELOG.md) for release history.

