from rest_framework import views, permissions, response, status, generics, decorators
from . import utils, models, serializers, services , docs , permissions as perms
from .. account.models import User
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
        procedures = request.data.get("procedures" , [])
        place_gcodes = request.data.get("place_gcodes" , [])
        company_codes = request.data.get("company_codes" , [])
        
        obj.procedures.set(procedures)
        obj.place_gcodes.set(place_gcodes)
        obj.company_codes.set(company_codes)
        
        return response.Response(status=status.HTTP_201_CREATED)
    
    
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