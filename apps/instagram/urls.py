from django.urls import path

from . import views

urlpatterns = [
    path("new/<uuid:campaign_pk>/", views.reel_new, name="reel_new"),
    path("<uuid:pk>/", views.reel_detail, name="reel_detail"),
    path("<uuid:pk>/gates/<str:step>/", views.gate_decide, name="gate_decide"),
    path("<uuid:pk>/delete/", views.reel_delete, name="reel_delete"),
]
