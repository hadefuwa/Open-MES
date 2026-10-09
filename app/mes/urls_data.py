from django.urls import path

from . import views_data as v

urlpatterns = [
    path("data/", v.data_browser, name="data_browser"),
    path("data/<str:model_name>/", v.data_table, name="data_table"),
]
