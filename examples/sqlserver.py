from procora import connect

database = connect(
    "sqlserver",
    host="localhost",
    database="Accounting",
    username="app_user",
    password="replace-me",
    trust_server_certificate=True,  # Local development only.
)

result = database.call("dbo.GetCustomerInvoices", CustomerId=42)
print(result.rows, result.output, result.return_value)
