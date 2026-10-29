import glob
import json
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.test import SimpleTestCase

BASE_DIR = Path(settings.BASE_DIR)
FRONTEND = BASE_DIR / "frontend"
BUILT_CSS = sorted(glob.glob(f"{FRONTEND}/dist/assets/main-*.css"))

# Tailwind classes used only inside .svelte files. They vanish from the build
# when the ".svelte" line leaves @source in frontend/src/css/styles.css.
SVELTE_ONLY = ("lg\\:grid-cols-2", "divide-border")


class FrontendContractTests(SimpleTestCase):
    def test_turbo_stays_removed(self):
        package = json.loads((FRONTEND / "package.json").read_text())

        self.assertNotIn("@hotwired/turbo", package["dependencies"])

    def test_body_boost_uses_htmx_inheritance(self):
        shell = (BASE_DIR / "templates" / "base_app.html").read_text()

        self.assertIn('hx-boost:inherited="true"', shell)

    @skipUnless(BUILT_CSS, "run `just vite-build` first")
    def test_svelte_only_classes_survive_the_build(self):
        css = Path(BUILT_CSS[0]).read_text()

        missing = [selector for selector in SVELTE_ONLY if selector not in css]
        self.assertEqual(missing, [], "Tailwind purged Svelte-only classes")
