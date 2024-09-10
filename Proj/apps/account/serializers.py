from rest_framework import serializers
from . import models, selectors
from datetime import datetime, timedelta


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(min_length=8, write_only=True, required=False)

    class Meta:
        ref_name = "user"
        model = models.User
        fields = ["username", "password", "first_name", "last_name", "id"]
        extra_kwargs = {
            "username": {"validators": []},
        }

    def create(self, validated_data):
        user = models.User.objects.create_user(**validated_data)
        return user

    def update(self, instance, validated_data):
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        instance.username = validated_data.get("username", instance.username)
        instance.save()
        return instance


class UserRawSerializer(serializers.ModelSerializer):
    class Meta:
        ref_name = "user_raw"
        model = models.User
        exclude = ("password",)


class MainAccessSerializer(serializers.ModelSerializer):

    mali_years = serializers.SerializerMethodField()
    place_gcodes = serializers.SerializerMethodField()
    company_codes = serializers.SerializerMethodField()

    class Meta:
        model = models.MainAccess
        fields = ['user', 'mali_years', 'place_gcodes', 'company_codes']
        
    def get_mali_years(self, obj):
        return [
            {"id": mali_year.id, "name": mali_year.name}
            for mali_year in obj.mali_years.all()
        ]

    def get_place_gcodes(self, obj):
        return [
            {"id": place_gcode.id, "name": place_gcode.name}
            for place_gcode in obj.place_gcodes.all()
        ]

    def get_company_codes(self, obj):
        return [
            {"id": company_code.id, "name": company_code.name}
            for company_code in obj.company_codes.all()
        ]


class FormAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserAccessForm
        fields = "__all__"
