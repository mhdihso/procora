# myapp/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import pyodbc
import re
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from ..account.models import MainAccess , UserAccessForm ,Procedure ,Form , ProcedureFlag
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



    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'action',
                openapi.IN_QUERY,
                description="Action parameter",
                type=openapi.TYPE_STRING,
                required=True
            ),
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'procedure_name': openapi.Schema(type=openapi.TYPE_STRING, description='Procedure name'),
                'output_parameters': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'return_value': openapi.Schema(type=openapi.TYPE_INTEGER, description='Return value')
                    },
                    required=['return_value'],
                ),
                'parameters': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'mali_year': openapi.Schema(type=openapi.TYPE_INTEGER, description='Mali Year code'),
                        'place_gcode': openapi.Schema(type=openapi.TYPE_INTEGER, description='Places Gcode'),
                        'company_code': openapi.Schema(type=openapi.TYPE_STRING, description='Company Codes'),
                        'action': openapi.Schema(type=openapi.TYPE_STRING, description='Action')
                    },
                    required=['MaliYearGcode', 'PlacesGcode', 'company_codes'],
                ),
                'form_id': openapi.Schema(type=openapi.TYPE_STRING, description='Form ID')
            },
            required=['procedure_name', 'output_parameters', 'parameters'],
        ),
        responses={
            200: openapi.Response('Success', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'result': openapi.Schema(type=openapi.TYPE_OBJECT, description='Result of the stored procedure')
                }
            )),
            400: 'Bad Request',
            403: 'Forbidden',
        },
        operation_description='Execute stored procedure with the given parameters and action',
    )
    def post(self, request, *args, **kwargs):
        data = request.data

        user = request.user

        action_query_param = request.query_params.get("action")
        
        if not action_query_param:
            return Response({'error': 'Action is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not data or not data.get("procedure_name"):
            return Response({'error': 'Procedure name and body are required'}, status=status.HTTP_400_BAD_REQUEST)

        procedure_name = data.get('procedure_name', None)
        # if check_for_sql_injection(procedure_name):
        #     return Response({'error': 'SQL injection detected'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            procedure = Procedure.objects.get(name=procedure_name)
            form = Form.objects.get(id=form_id)
            if not form.procedures.filter(id=procedure.id).exists():
                return Response({'error': 'Procedure is not associated with the given form'}, status=status.HTTP_403_FORBIDDEN)
        except Procedure.DoesNotExist:
            return Response({'error': 'Procedure not found'}, status=status.HTTP_404_NOT_FOUND)
        except Form.DoesNotExist:
            return Response({'error': 'Form not found'}, status=status.HTTP_404_NOT_FOUND)
        
        mali_year = data.get("mali_year")
        place_gcode =  data.get("place_gcode")
        company_code = data.get("company_code")
        
        flag = True
        
        if mali_year:
            if not MainAccess.objects.filter(user=user, mali_year__name__icontains=mali_year).exists():
                flag = False
                
        if place_gcode:
            if not MainAccess.objects.filter(user=user, place_gcode__name__icontains=place_gcode).exists():
                flag = False
                
                
        if company_code:
            if not MainAccess.objects.filter(user=user, company_code__name__icontains=company_code).exists():
                flag = False
                
        if not flag:
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        
        form_id = data.pop('form_id', None)
        
        if not UserAccessForm.objects.filter(user=user, form_id=form_id).exists():
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        

        parameters = data.get('parameters', None)
        output_parameters = data.get('output_parameters', None)
        
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

        action_key_query_params = actions_mapping.get(action_query_param)
        filter_kwargs = {
            'procedure': procedure,
            action_key_query_params: True
        }

        if not ProcedureFlag.objects.filter(**filter_kwargs).exists():
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)


        final_procedure_name = f'[dbo].[{procedure_name}]'
        result = execute_stored_procedure(final_procedure_name, parameters, output_parameters)

        return Response({'result': result})
