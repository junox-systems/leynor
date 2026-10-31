"""Channel units and publishers, found by name.

Lazy imports: the campaign layer never imports a channel app, and a channel app
is only loaded when a campaign page asks for its units. Same shape as every
other registry here, one dict per axis.
"""

from django.urls import reverse
from django.utils.module_loading import import_string

UNITS = {
    "reel": "apps.instagram.models.Reel",
}

PUBLISHERS = {
    "reel": "apps.instagram.publisher.InstagramPublisher",
}

UNIT_URLS = {
    "reel": "reel_detail",
}


def unit_models() -> dict[str, type]:
    return {channel: import_string(path) for channel, path in UNITS.items()}


def units(campaign) -> list[dict]:
    """Every unit of one campaign, tagged with its channel and its own URL."""
    rows = []
    for channel, model in unit_models().items():
        for unit in model.objects.filter(campaign=campaign):
            rows.append(
                {
                    "channel": channel,
                    "unit": unit,
                    "url": reverse(UNIT_URLS[channel], args=[unit.pk]),
                }
            )
    return rows


def publisher(channel: str):
    return import_string(PUBLISHERS[channel])()
