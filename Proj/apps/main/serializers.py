from rest_framework import serializers 
from . import models

class MaliYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MaliYear
        fields = '__all__'
        
class CompanyCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CompanyCode
        fields = '__all__'
        
class PlaceGcodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PlaceGcode
        fields = '__all__'
        
class FormSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Form
        fields = '__all__'
        
class ProcedureSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Procedure
        fields = '__all__'