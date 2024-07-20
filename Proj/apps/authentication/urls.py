from django.urls import path, include
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # path('register/panel/<str:phone>/', views.Register.as_view()),
    # path('login/otp/<str:phone>/', views.otp_login),
    path('login/base/', views.base_login),
    # path('logout/', views.base_logout),
    # path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    # path('change-password/<str:phone>/', views.change_password),
]
