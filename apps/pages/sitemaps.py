from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Public, indexable pages. Add URL names here as marketing pages grow."""

    def items(self):
        return ["home", "terms", "privacy"]

    def location(self, item):
        return reverse(item)
