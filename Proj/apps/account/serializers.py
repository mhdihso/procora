from rest_framework import serializers
from . import models, selectors
from datetime import datetime, timedelta


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(min_length=8, write_only=True, required=False)

    class Meta:
        ref_name = 'user'
        model = models.User
        fields = ['username', 'password', 'first_name', 'last_name', 'id']
        extra_kwargs = {
            'username': {'validators': []},
        }

    def create(self, validated_data):
        user = models.User.objects.create_user(**validated_data)
        return user

    def update(self, instance, validated_data):
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.username = validated_data.get('username', instance.username)
        instance.save()
        return instance
    
class UserRawSerializer(serializers.ModelSerializer):
    class Meta:
        ref_name = 'user_raw'
        model = models.User
        exclude = ('password' ,)


class MainAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MainAccess
        fields = '__all__'


class FormAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserAccessForm
        fields = '__all__'
