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

SQL Server reports `OUTPUT` parameters as capable of receiving an initial input. Supply one normally if the procedure uses INOUT behavior; otherwise Procora initializes the output variable to `NULL`.

Character lengths, binary lengths, `max`, decimal precision/scale, temporal scale, and user-defined alias types are reconstructed from catalog metadata for output variables.

Generic cursor output parameters are rejected. Table-valued input support depends on driver-compatible row sequences and the application-specific table type.

The database principal needs enough metadata visibility to discover the procedure and `EXECUTE` permission to call it.

## PostgreSQL

Discovery uses `pg_catalog.pg_proc` and `pg_catalog.pg_namespace`, selecting only stored procedures (`prokind = 'p'`). PostgreSQL functions are deliberately outside Procora's stored-procedure API.

Calls use named notation whenever parameters have names. This allows defaulted input parameters to be omitted while required OUT placeholders are still supplied as `NULL`. PostgreSQL returns OUT/INOUT values as one row; Procora converts that row into `result.output`.

PostgreSQL allows overloaded procedures. Procora refuses to guess among multiple routines with the same schema and name. Create a uniquely named wrapper or implement a signature-aware custom backend.

If a procedure performs transaction control internally, use `autocommit=True`; PostgreSQL does not allow transaction control inside a procedure called from an existing transaction block.

## MySQL

Discovery uses `information_schema.parameters` and `information_schema.routines`. Execution uses Connector/Python's `callproc`, which returns a modified argument sequence containing OUT and INOUT values. Stored result cursors are converted to portable `ResultSet` objects.

MySQL calls require all IN and INOUT parameters. Procora automatically supplies `None` placeholders for pure OUT parameters.

The adapter passes a metadata-resolved, schema-qualified procedure name to Connector/Python.
`query_timeout` is applied to Connector/Python's socket read and write timeouts.

## Unsupported databases

SQLite has no stored-procedure feature to adapt. Databases such as Oracle, IBM Db2, Firebird, and others can be integrated through the public `Backend` abstraction without changing the Procora core.
