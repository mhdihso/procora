from rest_framework import serializers , response
from ..account.serializers import *
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

class LoginPanelSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, min_length=5)

    class Meta:
        fields = ['otp', ]


class ChangePasswordSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, min_length=5)
    password = serializers.CharField(min_length=8, error_messages={"message": "طول رمز عبور حداقل بايد 6 باشد "},
                                     write_only=True)

    class Meta:
        fields = ['otp', 'password']

