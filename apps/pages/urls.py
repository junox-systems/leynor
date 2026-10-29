from django.urls import path
from django.views.generic import TemplateView

from .views import home

urlpatterns = [
    path("", home, name="home"),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
        name="robots",
    ),
]
