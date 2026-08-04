# Custom backends

A backend translates one database's catalogs and procedure-call protocol into Procora's portable models.

Custom factories can use the exported `ConnectionProtocol` and `CursorProtocol` for
static typing. They describe the minimum DB-API behavior consumed by the portable core;
backend-specific drivers may expose additional methods.

```python
from collections.abc import Mapping
from typing import Any

from procora import (
    Backend,
    ParameterMode,
    ProcedureInfo,
    ProcedureParameter,
    ProcedureResult,
    connect,
)


class ExampleBackend(Backend):
    name = "example"

    def create_connection_factory(
        self,
        *,
        autocommit,
        connect_timeout,
        query_timeout,
        options,
    ):
        def factory():
            return example_driver.connect(
                autocommit=autocommit,
                timeout=connect_timeout,
                **options,
            )

        return factory

    def resolve_schema(self, connection, schema):
        if schema is not None:
            return schema
        return connection.current_schema

    def discover(self, connection, name, schema):
        # Query the database catalog here.
        return ProcedureInfo(
            backend=self.name,
            schema=schema or "default_schema",
            name=name,
            parameters=(
                ProcedureParameter(1, "customer_id", "INTEGER", ParameterMode.IN),
                ProcedureParameter(2, "new_id", "INTEGER", ParameterMode.OUT),
            ),
        )

    def execute(
        self,
        connection: Any,
        procedure: ProcedureInfo,
        supplied: Mapping[int, Any],
    ) -> ProcedureResult:
        # Call the native driver and return portable result sets/output values.
        return ProcedureResult(procedure, output={"new_id": 123})

    def list_procedures(self, connection):
        return ["default_schema.example_procedure"]


database = connect(
    ExampleBackend(),
    connection_factory=example_pool.acquire,
    connection_releaser=example_pool.release,
)
```

`Database` handles connection ownership or pool release, metadata caching, parameter-name normalization, transaction commit/rollback, errors, and callable namespaces. The backend owns only database-specific discovery and execution.

Override `resolve_schema` when an unqualified procedure depends on per-connection state;
Procora uses its result as the metadata-cache namespace. Override `ping` or
`set_query_timeout` when the driver's behavior differs from the DB-API defaults.
