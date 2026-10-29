# apps/api/urls.py

from django.urls import path

from .views import (
    DashboardActivityController,
    UserDetailController,
    UserListController,
)

urlpatterns = [
    path("users/", UserListController.as_view(), name="user-list"),
    path("users/<uuid:user_id>/", UserDetailController.as_view(), name="user-detail"),
    path(
        "dashboard/activity/",
        DashboardActivityController.as_view(),
        name="dashboard-activity",
    ),
]
