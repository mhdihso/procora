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