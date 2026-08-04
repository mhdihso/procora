from procora import connect

database = connect(
    "mysql",
    host="localhost",
    database="accounting",
    user="app_user",
    password="replace-me",
)

result = database.call("accounting.create_order", customer_id=42)
print(result.rows, result.output)
