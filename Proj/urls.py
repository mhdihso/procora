"""Madtalk URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from Proj.apps.main import urls as main_urls
from Proj.apps.account import urls as account_urls
from Proj.apps.authentication import urls as authentication_urls

from decouple import config
from Proj.settings import local as settings
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator
class CustomOpenAPISchemaGenerator(OpenAPISchemaGenerator):
  def get_schema(self, request=None, public=False):
    """Generate a :class:.Swagger object with custom tags"""

    swagger = super().get_schema(request, public)
    swagger.tags = [
        {
            "name": "",
            "description": ""
        },
    ]

    return swagger

schema_view = get_schema_view(
    openapi.Info(
        title="Proj API",
        default_version='v1',
        description="description",
        terms_of_service="",
        # contact=openapi.Contact(email=""),
        license=openapi.License(name="Test License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    generator_class=CustomOpenAPISchemaGenerator,
)


urlpatterns = [
    # path('^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    # path('api/api.json/', schema_view.without_ui(cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('admin/', admin.site.urls),
    path('main/', include(main_urls)),
    path('account/', include(account_urls)),
    path('authentication/', include(authentication_urls)
        
    )
]

if config('ENVIRONMENT') == 'local':
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
