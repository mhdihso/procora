from django.urls import path, include
from . import views

urlpatterns = [
    path('base/', views.ExecuteProcedureView.as_view(), name='base')

]
