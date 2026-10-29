import glob
import os
import re
from pathlib import Path

from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase

TEMPLATE_ROOT = os.path.join(settings.BASE_DIR, "templates")


def template_files():
    paths = glob.glob(f"{TEMPLATE_ROOT}/**/*.html", recursive=True)
    return sorted((os.path.relpath(path, TEMPLATE_ROOT), path) for path in paths)


class TemplateCompileTests(SimpleTestCase):
    def test_every_template_compiles(self):
        broken = {}

        for name, path in template_files():
            try:
                get_template(name)
            except Exception as exc:
                broken[name] = exc

        self.assertEqual(broken, {})

    def test_django_comments_stay_on_one_line(self):
        # Cotton compiles inside comments: a multi-line {# #} leaks its text and
        # can close <head> early. Use {% comment %} for blocks.
        offenders = []

        for name, path in template_files():
            source = Path(path).read_text(encoding="utf-8")
            if any("\n" in match for match in re.findall(r"{#.*?#}", source, re.S)):
                offenders.append(name)

        self.assertEqual(offenders, [])
