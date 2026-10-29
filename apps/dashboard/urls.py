# apps/dashboard/urls.py

from django.urls import path

from .views import ActivityView, DashboardView

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("activity/", ActivityView.as_view(), name="activity"),
]
