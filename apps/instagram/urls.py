from django.urls import path

from . import views

urlpatterns = [
    path("", views.reel_list, name="reels"),
    path("new/<uuid:campaign_pk>/", views.reel_new, name="reel_new"),
    path("ideas/<uuid:pk>/", views.pitch_detail, name="reel_pitch"),
    path("ideas/<uuid:pk>/decide/", views.pitch_decide, name="reel_pitch_decide"),
    path("<uuid:pk>/", views.reel_detail, name="reel_detail"),
    path("<uuid:pk>/gates/<str:step>/", views.gate_decide, name="gate_decide"),
    path("<uuid:pk>/gates/<str:step>/retry/", views.step_retry, name="step_retry"),
    path("<uuid:pk>/files/<path:name>", views.reel_media, name="reel_media"),
    path("<uuid:pk>/delete/", views.reel_delete, name="reel_delete"),
]
