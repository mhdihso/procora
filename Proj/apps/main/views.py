# myapp/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import pyodbc
import re
from ..account.models import MainAccess , UserAccessForm
# Database configuration
db_config = {
    'user': 'AvaBack1',
    'password': 'Av@B@ck1$',
    'host': '192.168.1.151',
    'port': '1433',
    'database': 'DsMaliA',
    'driver': '{ODBC Driver 17 for SQL Server}',
}


actions_mapping = {
    1:"can_add" ,
    2:"can_edit" ,
    3:"can_delete" ,
    4:"can_see" ,
    5:"can_print" ,
    6:"can_log" ,
    7:"can_flow" ,
    8:"can_filter" ,
    9:"can_confirm" ,
    10:"can_return" ,
}

sql_injection_pattern = re.compile(
    r"(?i)(?:script|<|>|%3c|%3e|select|update|insert|delete|grant|revoke|union|&lt;|&gt;)"
)

def check_for_sql_injection(input_text):
    if input_text is None or input_text == "" or isinstance(input_text, int):
        return False
    return sql_injection_pattern.search(input_text) is not None

def get_db():
    return pyodbc.connect(
        'DRIVER=' + db_config['driver'] +
        ';SERVER=' + db_config['host'] +
        ';PORT=' + db_config['port'] +
        ';DATABASE=' + db_config['database'] +
        ';UID=' + db_config['user'] +
        ';PWD=' + db_config['password']
    )

def execute_stored_procedure(proc_name, parameters, output_parameters):
    db = get_db()
    cursor = db.cursor()

    param_list = []
    output_param_list = []
    for param, value in parameters.items():
        if isinstance(value, str):
            value = "N'" + value.replace("'", "''") + "'"
        elif value is None:
            value = 'NULL'
        param_list.append(f"@{param} = {value}")

    for output_param, output_type in output_parameters.items():
        output_param_list.append(f"@{output_param} = @{output_param} OUTPUT")

    procedure_call = f"{proc_name}\n"
    procedure_call += "    " + ",\n    ".join(param_list + output_param_list)

    declare_output_vars = "\n".join([f"DECLARE @{param} {output_type}" for param, output_type in output_parameters.items()])
    select_output_vars = "\n".join([f"SELECT @{param} as '{param}'" for param in output_parameters])

    sql_script = f"""
    {declare_output_vars}

    EXEC {procedure_call}

    {select_output_vars}
    """

    cursor.execute(sql_script)
    result = cursor.fetchone()
    # output = {param: cursor.fetchone() for param in output_parameters} 
    
    output = {}
    i = 0
    for param in output_parameters:
        try:
            value = result[i]
            if type(value) == tuple:
                value = list(value)
        except: 
            value = None

        output.update({f"{param}" : f"{value}"})
        i += 1


    cursor.close()
    db.close()

    return output

class ExecuteProcedureView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        data = request.data
        body = data.get('body', None)
        user = request.user

        action_query_param = request.query_params.get("action")
        
        if not action_query_param:
            return Response({'error': 'Action is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not body or not body.get("procedure_name"):
            return Response({'error': 'Procedure name and body are required'}, status=status.HTTP_400_BAD_REQUEST)

        procedure_name = body.get('procedure_name', None)
        # if check_for_sql_injection(procedure_name):
        #     return Response({'error': 'SQL injection detected'}, status=status.HTTP_400_BAD_REQUEST)

        mali_year = body.get("mali_year")
        place_gcodes =  body.get("place_gcodes")
        company_codes = body.get("company_codes")
        
        flag = True
        
        if mali_year:
            if not MainAccess.objects.filter(user=user, mali_year__name__icontains=mali_year).exists():
                flag = False
                
        if place_gcodes:
            if not MainAccess.objects.filter(user=user, place_gcode__name__icontains=place_gcodes).exists():
                flag = False
                
                
        if company_codes:
            if not MainAccess.objects.filter(user=user, company_code__name__icontains=company_codes).exists():
                flag = False
                
        if not flag:
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        
        form_id = body.pop('form_id', None)
        
        if not UserAccessForm.objects.filter(user=user, form_id=form_id).exists():
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        

        parameters = body.get('parameters', None)
        output_parameters = body.get('output_parameters', None)
        
        parameters_action = parameters.get("action")
        if parameters_action:
            action_key = actions_mapping.get(parameters_action)
            filter_kwargs = {
                'user': user,
                'form_id': form_id,
                action_key: True
            }

            if not UserAccessForm.objects.filter(**filter_kwargs).exists():
                return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

        action_key_query_params = actions_mapping.get(action_query_param)
        filter_kwargs = {
            'user': user,
            'form_id': form_id,
            action_key_query_params: True
        }

        if not UserAccessForm.objects.filter(**filter_kwargs).exists():
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        # for key, value in parameters.items():
        #     if check_for_sql_injection(key) or check_for_sql_injection(value):
        #         return Response({'error': 'SQL injection detected'}, status=status.HTTP_400_BAD_REQUEST)

        if not procedure_name or not parameters or not output_parameters:
            return Response({'error': 'Procedure name, parameters, and output parameters are required in the body'}, status=status.HTTP_400_BAD_REQUEST)

        final_procedure_name = f'[dbo].[{procedure_name}]'
        result = execute_stored_procedure(final_procedure_name, parameters, output_parameters)

        return Response({'result': result})
