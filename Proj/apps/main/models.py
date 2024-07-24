from django.db import models


class Procedure(models.Model):
    name = models.CharField(max_length=255)
    
class PlaceGcode(models.Model):
    name = models.CharField(max_length=255)
    
class CompanyCode(models.Model):
    name = models.CharField(max_length=255)

class MaliYear(models.Model):
    name = models.CharField(max_length=255
        
    )
    
    
class Form(models.Model):
    name = models.CharField(max_length=255)
    procedures = models.ManyToManyField(Procedure, blank=True)
    
class ProcedureFlag(models.Model):
    procedure = models.ForeignKey(Procedure,on_delete=models.CASCADE)
    can_add = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_see = models.BooleanField(default=False)
    can_print = models.BooleanField(default=False)
    can_log = models.BooleanField(default=False)
    can_flow = models.BooleanField(default=False)
    can_filter = models.BooleanField(default=False)
    can_confirm = models.BooleanField(default=False)
    can_return = models.BooleanField(default=False)