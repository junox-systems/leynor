# apps/api/urls.py

from django.urls import path

from .views import (
    DashboardActivityController,
    ReelPitchController,
    ReelRouteController,
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
    path(
        "reels/<uuid:reel_id>/route/",
        ReelRouteController.as_view(),
        name="api-reel-route",
    ),
    path(
        "reels/pitches/<uuid:pitch_id>/",
        ReelPitchController.as_view(),
        name="api-reel-pitch",
    ),
]
