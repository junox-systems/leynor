from django.urls import path

from . import views

urlpatterns = [
    path("", views.project_list, name="projects"),
    path("new/", views.project_new, name="project_new"),
    path("<uuid:pk>/", views.project_detail, name="project_detail"),
    path("<uuid:pk>/delete/", views.project_delete, name="project_delete"),
]
