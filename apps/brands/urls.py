from django.urls import path

from . import views

urlpatterns = [
    path("", views.brand_list, name="brands"),
    path("new/", views.brand_new, name="brand_new"),
]
