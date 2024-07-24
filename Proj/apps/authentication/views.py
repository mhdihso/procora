from rest_framework import views, permissions, response, status, generics, decorators
from . import utils, models, serializers, services , docs , permissions as perms
import base64
from django.contrib.auth import authenticate
from django.utils import timezone 
from datetime import timedelta
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
                    'username': openapi.Schema(type=openapi.TYPE_STRING),
                    'password': openapi.Schema(type=openapi.TYPE_STRING),

                },
            )),
        },
    ),
    responses={
        200: openapi.Response('Successful'),
        400: 'Bad Request',
    },
)
@decorators.api_view(['POST', ])
@decorators.permission_classes([permissions.AllowAny, ])
def base_login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)

    if not user:
        return response.Response({'detail': "نام کاربری یا رمز عبور اشتباه است"}, status=status.HTTP_400_BAD_REQUEST)

    data = serializers.UserSerializer(user).data
    token = utils.get_tokens_for_user(user)
    data['access'] = token['access']
    data['refresh'] = token['refresh']
    return response.Response(data, status=status.HTTP_200_OK)

# @swagger_auto_schema(operation_description= docs.change_pass ,methods=['post'],tags=['authentication'])
# @decorators.api_view(['POST', ])
# @decorators.permission_classes([permissions.IsAuthenticated, ])
# def change_password(request, phone):
#     try:
#         otp = models.Otp.objects.get(mobile=phone)
#     except models.Otp.DoesNotExist:
#         return response.Response({'detail': "چنین شماره ای ثبت نشده است"}, status=404)
#     if otp.is_expired:
#         return response.Response({'detail': "این کد منقضی شده است"}, status=status.HTTP_400_BAD_REQUEST)
#     serializer = serializers.ChangePasswordSerializer(data=request.data)
#     if not serializer.is_valid(raise_exception=True):
#         return response.Response({'detail': "تعداد ارقام كد نامعتبر است"}, status=status.HTTP_400_BAD_REQUEST)
#     code = serializer.validated_data['otp']
#     keygen = utils.GenerateKey()
#     key = base64.b32encode(keygen.returnValue(phone).encode())
#     OTP = pyotp.HOTP(key)
#     if OTP.verify(code, otp.counter):
#         user = request.user
#         user.set_password(serializer.validated_data['password'])
#         user.save()
#         return response.Response({'detail': "با موفقيت ثبت شد"}, status=status.HTTP_200_OK)
#     return response.Response({'detail': "کد وارد شده نامعتبر می باشد"}, status=status.HTTP_400_BAD_REQUEST)

# @swagger_auto_schema(operation_description= docs.logout ,methods=['post'],tags=['authentication'])
# @decorators.api_view(['POST', ])
# @decorators.permission_classes([permissions.IsAuthenticated, ])
# def base_logout(request):
#     push_id = request.data.get('push_id')
#     try:
#         p_id = PushId.objects.get(user_id = request.user.id , push_id = push_id)
#         p_id.delete()
#     except:
#         pass
#     return response.Response({'detail': "با موفقیت خارج شدید."}, status=status.HTTP_200_OK)

