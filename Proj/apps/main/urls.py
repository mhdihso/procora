from django.urls import path, include
from . import views

urlpatterns = [
    path('base/', views.ExecuteProcedureView.as_view(), name='base'),
    path("mali-year/list/" , views.MaliYearListView.as_view(), name="mali-year-list"),
    path('company-code/list/' , views.CompanyCodeListView.as_view(), name="company-gcode-list"),
    path('place-gcode/list/' , views.PlaceGcodeListView.as_view(), name="place-gcode-list"),
    path('form/list/' , views.FormListView.as_view(), name="form-list"),
    path('procedure/list/' , views.ProcedureListView.as_view(), name="procedure-list"),
]
