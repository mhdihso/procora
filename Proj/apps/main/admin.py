from django.contrib import admin
from . import models

admin.site.register(models.PlaceGcode)
admin.site.register(models.Procedure)
admin.site.register(models.CompanyCode)
admin.site.register(models.Form)
admin.site.register(models.MaliYear)
admin.site.register(models.ProcedureFlag)
admin.site.register(models.ProcedureBaseTemplate)