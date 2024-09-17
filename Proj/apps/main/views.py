# myapp/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.exceptions import ValidationError

from rest_framework import status , generics
from rest_framework.permissions import IsAuthenticated ,AllowAny
import pyodbc
import re
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import json
from . import models ,serializers
from ..account.models import MainAccess , UserAccessForm ,Procedure ,Form , ProcedureFlag ,ProcedureBaseTemplate
from db import maindb 


def convert_sql_to_dict(sql_declaration):
    # Remove the initial DECLARE part and split the variables by commas
    variables = sql_declaration.replace("DECLARE", "").strip().split(",")
    
    # Create a dictionary to hold the output parameters
    output_parameters = {}
    
    # Regex pattern to match the variable declaration
    pattern = re.compile(r"@\w+\s+[\w\(\)]+")
    
    # Process each variable
    for var in variables:
        match = pattern.search(var.strip())
        if match:
            var_declaration = match.group()
            var_name, var_type = var_declaration.split()
            # Remove the @ from the variable name
            var_name = var_name.lstrip('@')
            # Add the variable to the dictionary
            output_parameters[var_name] = var_type
    
    return output_parameters

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

def execute_stored_procedure(proc_name, parameters ,procedure):
    
    try:
        db = maindb.get_db()
        cursor = db.cursor()
    except:
        db = maindb.re_connect()
        cursor = db.cursor()
    
        

    procedure_type_obj = procedure.base_template
    
    dict_output = convert_sql_to_dict(procedure_type_obj.output_part)
    
    
    
    param_list = []
    if procedure.is_get==False:
        output_param_list = ["CodeOut","Error","ErrorDescription"]
    else:output_param=[]
    for param, value in parameters.items():
        if isinstance(value, str):
            value = "N'" + value.replace("'", "''") + "'"
        elif value is None:
            value = 'NULL'
        param_list.append(f"@{param} = {value}")

    for output_param, output_type in dict_output.items():
        output_param_list.append(f"@{output_param} = @{output_param} OUTPUT")

    procedure_call = f"{proc_name}\n"
    procedure_call += "    " + ",\n    ".join(param_list)
    procedure_call += "    " + ",\n    ".join(output_param_list)
    procedure_call = procedure_call + ",\n" 

    final = ""
    for key , value in dict_output.items():
        x= f"@{key} {value},"
        final = final + x
    try:
        sql_script = f"""
            {procedure_type_obj.output_part}
            {procedure_type_obj.first_part}
            {procedure_call}
            {procedure_type_obj.second_part} 
        """
        return sql_script
        cursor.execute(sql_script)
    except:
        sql_script = f"""
        {procedure_type_obj.output_part}
        {procedure_type_obj.first_part}
        {procedure_call[:-2]}
        {procedure_type_obj.second_part} 
    """
        return sql_script
        cursor.execute(sql_script)
    
    result = cursor.fetchone()
    # print(list(result))
    # output = {param: cursor.fetchone() for param in output_parameters} 

    output = cursor.fetchone()
    output = {}

    i = 0
    if procedure.is_get:
        json_string = result[0]
        try:
            output = json.loads(json_string)
        except:
            return None

    else:
        dict_output=["CodeOut","Error","ErrorDescription"]
        output = {}
        i = 0
        for param in dict_output:
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
    permission_classes = [AllowAny]



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
        form_id = data.pop('form_id', None)
        action_query_param = request.query_params.get("action")
        
        if not action_query_param:
            return Response({'error': 'Action is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # if not data or not data.get("procedure_name"):
        #     return Response({'error': 'Procedure name and body are required'}, status=status.HTTP_400_BAD_REQUEST)

        procedure_name = data.get('procedure_name', None)
        # if check_for_sql_injection(procedure_name):
        #     return Response({'error': 'SQL injection detected'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            procedure = Procedure.objects.get(name=procedure_name)
            if procedure.is_public:
                pass
            else:
                form = Form.objects.get(id=form_id)
                if not form.procedures.filter(id=procedure.id).exists():
                    return Response({'error': 'Procedure is not associated with the given form'}, status=status.HTTP_403_FORBIDDEN)
        except Procedure.DoesNotExist:
            return Response({'error': 'Procedure not found'}, status=status.HTTP_404_NOT_FOUND)
        except Form.DoesNotExist:
            return Response({'error': 'Form not found'}, status=status.HTTP_404_NOT_FOUND)
        
        
        parameters = data.get('parameters', None)
        if procedure.is_public:
            pass
        else:
            if not  request.user.is_authenticated:
                return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

            mali_year = data.get("MaliYearGcode")
            place_gcode =  data.get("PlacesGcode")
            company_code = data.get("CompanyCode")
            
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
        
        
            if not UserAccessForm.objects.filter(user=user, form_id=form_id).exists():
                return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        
            
            parameters_action = parameters.get("Action")
            if parameters_action:
                action_key = actions_mapping.get(int(parameters_action))
                filter_kwargs = {
                    'user': user,
                    'form_id': form_id,
                    action_key: True
                }

                if not UserAccessForm.objects.filter(**filter_kwargs).exists():
                    return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

            action_key_query_params = actions_mapping.get(int(action_query_param))
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


            action_key_query_params = actions_mapping.get(int(action_query_param))
            filter_kwargs = {
                'procedure': procedure,
                action_key_query_params: True
            }

            if not ProcedureFlag.objects.filter(**filter_kwargs).exists():
                return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

        if not procedure_name  :
            return Response({'error': 'Procedure name, parameters, and output parameters are required in the body'}, status=status.HTTP_400_BAD_REQUEST)


        final_procedure_name = f'[dbo].[{procedure_name}]'
        result = execute_stored_procedure(final_procedure_name, parameters , procedure)

        return Response({'result': result})


class MaliYearListView(generics.ListAPIView):
    queryset = models.MaliYear.objects.all()
    serializer_class = serializers.MaliYearSerializer


class PlaceGcodeListView(generics.ListAPIView):
    queryset = models.PlaceGcode.objects.all()
    serializer_class = serializers.PlaceGcodeSerializer
    

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
    
class CompanyCodeListView(generics.ListAPIView):
    queryset = models.CompanyCode.objects.all()
    serializer_class = serializers.CompanyCodeSerializer
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
    
class FormListView(generics.ListAPIView):
    queryset = models.Form.objects.all()
    serializer_class = serializers.FormSerializer
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
    
class ProcedureListView(generics.ListAPIView):
    queryset = models.Procedure.objects.all()
    serializer_class = serializers.ProcedureSerializer
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)