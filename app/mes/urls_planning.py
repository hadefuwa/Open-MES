from django.urls import path

from . import views_planning as v

urlpatterns = [
    path("timeline/", v.timeline, name="timeline"),
]
