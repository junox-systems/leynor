"""App identity for every template.

`APP_NAME` is declared once in `config/app.py`. Templates never hardcode it:
`base.html` sets the document title, the shell renders the brand, and page
titles read `{{ app_name }}`.
"""

from django.conf import settings


def app(request):
    return {
        "app_name": settings.APP_NAME,
        "app_slug": settings.APP_SLUG,
    }
