"""The slug rule shared by projects, campaigns and channel units."""

import re

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
