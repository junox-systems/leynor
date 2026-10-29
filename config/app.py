"""App identity. One declaration, importable with or without Django.

`config.otel` initializes before Django reads settings, so the name cannot live
in `settings/base.py` alone. It reads the same environment variables here.
"""

import os

APP_NAME = os.environ.get("APP_NAME", "Leynor")
APP_SLUG = os.environ.get("APP_SLUG", APP_NAME.lower().replace(" ", "-"))
