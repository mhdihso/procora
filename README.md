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
| PostgreSQL 11+ | `psycopg` 3 | procedure output row | yes | not applicable |
| MySQL | MySQL Connector/Python | yes | yes | not applicable |

MariaDB can use the MySQL adapter when its Connector/Python-compatible behavior matches the called routines. Additional databases can implement Procora's small `Backend` interface.

SQLite is not listed because SQLite does not implement stored procedures.

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
)
```

`connection_releaser` returns borrowed connections to the pool. Without it, Procora
calls `close()` after each operation. Driver connection options cannot be mixed with
a custom factory.

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
- PostgreSQL overloaded procedure names are ambiguous without a signature; Procora asks for a uniquely named wrapper rather than guessing a type overload.
- PostgreSQL functions are not procedures and should be queried with `SELECT`, so the PostgreSQL adapter intentionally discovers only `prokind = 'p'`.
- MySQL requires every IN/INOUT argument. OUT placeholders are provided automatically.
- Table-valued and cursor parameters can require a custom, application-specific adapter.

More detail is in [backend notes](docs/backends.md).

The public classes, result fields, methods, and exception hierarchy are listed in the
[API reference](docs/api.md).

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
