from django.urls import path

from . import views_bom as v

urlpatterns = [
    path("products/<int:pk>/bom/", v.bom, name="bom"),
    path("components/<int:pk>/", v.component_detail, name="component_detail"),
]
