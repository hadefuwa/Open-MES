from django.urls import path

from . import views_machines as v

urlpatterns = [
    path("machines/", v.machines, name="machines"),
    path("machines/<int:pk>/", v.machine_detail, name="machine_detail"),
    path("machines/<int:pk>/status/", v.machine_status, name="machine_status"),
]
