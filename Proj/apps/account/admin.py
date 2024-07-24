from django.contrib import admin
from .models import *
from django.contrib.auth.admin import UserAdmin


class MyUserAdmin(UserAdmin):
    # fieldsets =  (
    #     (None, {'fields': ('type', 'school')}),
    # )+UserAdmin.fieldsets 

    fieldsets = (
        *UserAdmin.fieldsets, 
        (
            'Custom Field',  
            {
                'fields': (
                    'type',

                ),
            },
        ),
    )


admin.site.register(User, MyUserAdmin)
admin.site.register(MainAccess)
admin.site.register(UserAccessForm)