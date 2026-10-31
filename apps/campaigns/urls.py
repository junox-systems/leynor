from django.urls import path

from . import views

urlpatterns = [
    path("<uuid:pk>/", views.campaign_detail, name="campaign_detail"),
    path("new/<uuid:project_pk>/", views.campaign_new, name="campaign_new"),
]
