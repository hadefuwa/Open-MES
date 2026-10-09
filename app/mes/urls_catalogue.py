from django.urls import path

from . import views_catalogue as v

urlpatterns = [
    path("products/", v.products, name="products"),
    path("products/<int:pk>/", v.product_detail, name="product_detail"),
    path("assemblies/", v.assemblies, name="assemblies"),
    path("components/", v.components, name="components"),
]
