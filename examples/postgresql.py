from procora import connect

database = connect(
    "postgresql",
    dsn="postgresql://app_user:replace-me@localhost/accounting",
)

result = database.call("sales.create_order", customer_id=42)
print(result.rows, result.output)
