from django.urls import path, include
from . import views

urlpatterns = [
    path('main-access/list/', views.main_access_list, name='main_access_list'),
    path('form-access/list/' , views.form_access_list, name='form_access_list'),
    path('register/base/', views.base_register),
    path('user/list/' , views.UserList.as_view(), name='user_list'),

]
