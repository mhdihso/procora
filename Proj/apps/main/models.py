from django.db import models


class CompanyCode(models.Model):
    name = models.CharField(max_length=255, unique=True)
    
    def __str__(self) -> str:
        return self.name
    
class PlaceGcode(models.Model):
    company_code = models.ForeignKey(CompanyCode, on_delete=models.CASCADE)
    name = models.CharField(max_length=255 , unique=True)
    
    
    def __str__(self) -> str:
        return self.name
    


class MaliYear(models.Model):
    name = models.CharField(max_length=255 , unique=True   
    )
    def __str__(self) -> str:
        return self.name
    
    

    
class ProcedureBaseTemplate(models.Model):
    name = models.CharField(max_length=255 , null=True, blank=True)
    output_part = models.TextField(null=True ,blank=True)
    first_part = models.TextField(null=True,blank=True)
    second_part = models.TextField(null=True,blank=True)
    
    def __str__(self) -> str:
        return self.name if self.name else str(self.id)
    
class Procedure(models.Model):
    name = models.CharField(max_length=255, unique=True)
    is_get = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    base_template = models.ForeignKey(ProcedureBaseTemplate, on_delete=models.CASCADE)
    
    
    def __str__(self) -> str:
        return self.name + ' : '+ str(self.id)
    
class Form(models.Model):
    name = models.CharField(max_length=255)
    procedures = models.ManyToManyField(Procedure, blank=True)
    
    def __str__(self) -> str:
        return self.name + ' : '+ str(self.id)
    
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
    
    def __str__(self) -> str:
        return self.procedure.name + ' : '+str(self.procedure.id)