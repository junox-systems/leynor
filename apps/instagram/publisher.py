"""Publishing a Reel to Instagram.

The interface is real and registered; the network client is not wired yet. When
the Graph API credentials exist, `publish`, `stats` and `refresh` are the only
methods to fill in.
"""

from apps.campaigns.adapters import PublishUnavailable


class InstagramPublisher:
    channel = "reel"

    def publish(self, unit) -> str:
        raise PublishUnavailable(
            "Instagram publishing needs a Graph API token and a business account."
        )

    def stats(self, unit) -> dict:
        return {}

    def refresh(self, unit) -> None:
        return None
