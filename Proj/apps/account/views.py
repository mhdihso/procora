from rest_framework import views, permissions, response, status, generics, decorators
from . import utils, models, serializers, services , docs , permissions as perms
from .. account.models import User
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

@swagger_auto_schema(
    method='post', 
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'requirement': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'user': openapi.Schema(type=openapi.TYPE_NUMBER),
                    'mali_years': openapi.Schema(type=openapi.TYPE_NUMBER),
                    'place_gcodes': openapi.Schema(type=openapi.TYPE_STRING),
                    'company_codes': openapi.Schema(type=openapi.TYPE_STRING),
                },
            )),
        },
    ),
    responses={
        200: openapi.Response('Successful'),
        400: 'Bad Request',
    },
    operation_description='دسترسی های اصلی',
)
@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter(
            'user_id',
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING
        ),
    ],
)

@decorators.api_view(['GET', 'POST'])
@decorators.permission_classes([permissions.IsAuthenticated,perms.IsAdmin])
def main_access_list(request ):
    
    if request.method == 'GET':
        objs = models.MainAccess.objects.all(
        )
        user_id = request.query_params.get("user_id")
        if user_id:
            objs = objs.filter(user_id=user_id)
        serializer = serializers.MainAccessSerializer(objs, many=True)
        return response.Response(serializer.data)
    
    else:
        user = request.data.get("user")
        obj , crt = models.MainAccess.objects.get_or_create(user_id=user)
        mali_years = request.data.get("mali_years" , [])
        place_gcodes = request.data.get("place_gcodes" , [])
        company_codes = request.data.get("company_codes" , [])
        
        obj.mali_years.set(mali_years)
        obj.place_gcodes.set(place_gcodes)
        obj.company_codes.set(company_codes)
        
        return response.Response(status=status.HTTP_201_CREATED)
    
@swagger_auto_schema(
    method='post', 
    
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'requirement': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'form': openapi.Schema(type=openapi.TYPE_NUMBER),
                    'user': openapi.Schema(type=openapi.TYPE_NUMBER),
                    'can_add': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'can_edit': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'can_delete': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'can_see': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'can_print': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'can_log': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'can_flow': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'can_filter': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'can_confirm': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'can_return': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                },
            )),
        },
    ),
    responses={
        200: openapi.Response('Successful'),
        400: 'Bad Request',
    },
    operation_description='دسترسی های فرم',
)
@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter(
            'user',
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'form',
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING
        ),
    ],
)    
@decorators.api_view(['GET', 'POST'])
@decorators.permission_classes([permissions.IsAuthenticated,perms.IsAdmin])
def form_access_list(request):
    if request.method == 'GET':
        objs = models.UserAccessForm.objects.all()
        user_id = request.query_params.get("user_id")
        form_id = request.query_params.get("form_id")
        
        if user_id:
            objs = objs.filter(user_id=user_id)
        if form_id:
            objs = objs.filter(form_id=form_id)
            
        serializer = serializers.FormAccessSerializer(objs, many=True)
        return response.Response(serializer.data)
    
    else:
        form = request.data.get("form")
        user  = request.data.get("user")
        obj = models.UserAccessForm.objects.filter(form_id=form,
                                                                user_id = user
        )
        if obj.count() == 0:
            serializer = serializers.FormAccessSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            serializer = serializers.FormAccessSerializer(obj.first(), data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return response.Response({"data": serializer.data}, status=status.HTTP_201_CREATED)    
    
    
@swagger_auto_schema(
    method='post', 
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'under_coverage_id': openapi.Schema(type=openapi.TYPE_STRING),
            'requirement': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'username': openapi.Schema(type=openapi.TYPE_STRING),
                    'password': openapi.Schema(type=openapi.TYPE_STRING),
                    'first_name': openapi.Schema(type=openapi.TYPE_STRING),
                    'last_name': openapi.Schema(type=openapi.TYPE_STRING),
                },
            )),
        },
    ),
    responses={
        200: openapi.Response('Successful'),
        400: 'Bad Request',
    },
    operation_description='ثبت نام',
)
@decorators.api_view(['POST', ])
@decorators.permission_classes([permissions.IsAuthenticated,perms.IsAdmin])
def base_register(request):

    username = request.data.get("username")
    password = request.data.get("password")
    first_name = request.data.get("first_name")
    last_name = request.data.get("last_name")
    if User.objects.filter(username=username).exists():
        return response.Response({"error": "user already exists"}, status=status.HTTP_400_BAD_REQUEST)
    user = User.objects.create_user(username=username, password=password , first_name = first_name ,
                                                last_name = last_name  ,type=models.User.Types.USER)
    user.set_password(password)
    data = serializers.UserSerializer(user).data
    token = utils.get_tokens_for_user(user)
    data['access'] = token['access']
    data['refresh'] = token['refresh']



    return response.Response(data, status=status.HTTP_200_OK)