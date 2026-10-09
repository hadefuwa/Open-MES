from django.urls import path

from . import views_defects as v

urlpatterns = [
    path("defects/", v.defects, name="defects"),
    path("defects/add/<int:order_pk>/", v.defect_add, name="defect_add"),
]
