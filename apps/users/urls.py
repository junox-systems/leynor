from django.urls import path

from .views import ProfileView, delete_account, export_data

urlpatterns = [
    path("profile/", ProfileView.as_view(), name="profile"),
    path("export/", export_data, name="export_data"),
    path("delete/", delete_account, name="delete_account"),
]
