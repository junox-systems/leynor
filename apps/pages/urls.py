from django.contrib.sitemaps.views import sitemap
from django.urls import path
from django.views.generic import TemplateView

from .sitemaps import StaticViewSitemap
from .views import home

urlpatterns = [
    path("", home, name="home"),
    path(
        "terms/", TemplateView.as_view(template_name="pages/terms.html"), name="terms"
    ),
    path(
        "privacy/",
        TemplateView.as_view(template_name="pages/privacy.html"),
        name="privacy",
    ),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
        name="robots",
    ),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": {"static": StaticViewSitemap}},
        name="sitemap",
    ),
]
