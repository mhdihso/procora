from django.conf import settings
import pyodbc

db_config = {
    'user': 'AvaBack1',
    'password': 'Av@B@ck1$',
    'host': '172.16.101.10',
    'port': '1433',
    'database': 'DsMaliA',
    'driver': '{ODBC Driver 17 for SQL Server}',
}

class MainDb:

    def __init__(self):
        self.conn = pyodbc.connect(
        'DRIVER=' + db_config['driver'] +
        ';SERVER=' + db_config['host'] +
        ';PORT=' + db_config['port'] +
        ';DATABASE=' + db_config['database'] +
        ';UID=' + db_config['user'] +
        ';PWD=' + db_config['password']
    )

    def get_db(self):
        return self.conn
    
    def re_connect(self):
        return  pyodbc.connect(
        'DRIVER=' + db_config['driver'] +
        ';SERVER=' + db_config['host'] +
        ';PORT=' + db_config['port'] +
        ';DATABASE=' + db_config['database'] +
        ';UID=' + db_config['user'] +
        ';PWD=' + db_config['password']
    )
        
    
    
maindb = MainDb()