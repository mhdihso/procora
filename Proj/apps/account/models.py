from django.db import models
from django.contrib.auth.models import AbstractUser
from Proj.settings.base import AUTH_USER_MODEL
from ..main.models import *


class User(AbstractUser):
    class Types(models.TextChoices):
        USER = "User"
        ADMIN = "Admin"

    type = models.CharField( max_length=50, choices=Types.choices)

    @property
    def full_name(self):
        return self.first_name + " " + self.last_name


class MainAccess(models.Model):
    user = models.OneToOneField(AUTH_USER_MODEL, on_delete=models.CASCADE)
    mali_years = models.ManyToManyField(MaliYear, blank=True)
    place_gcodes = models.ManyToManyField(PlaceGcode, blank=True)
    company_codes = models.ManyToManyField(CompanyCode, blank=True)
    
    
    
class UserAccessForm(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    form = models.ForeignKey(Form, on_delete=models.CASCADE)
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
        return self.form.name+' : '+str(self.user.id)
    