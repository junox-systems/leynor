"""Publish and measure a Reel through the Instagram Graph API.

Skeleton with the real shape: a media container, then media_publish, then the
publication row. It refuses to post without credentials or a public video URL,
so a missing setup can never look like a successful post.

`transport(method, url, params) -> dict` is injectable: tests pass a fake, the
default speaks HTTP with the standard library.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.utils import timezone

from apps.campaigns.adapters import PublishUnavailable
from apps.instagram.models import InstagramPublication

GRAPH = "https://graph.facebook.com/v21.0"


class InstagramPublisher:
    channel = "reel"

    def __init__(
        self,
        *,
        account_id=None,
        token=None,
        media_base=None,
        transport=None,
    ):
        self.account_id = (
            settings.INSTAGRAM_ACCOUNT_ID if account_id is None else account_id
        )
        self.token = (
            settings.INSTAGRAM_ACCESS_TOKEN if token is None else token
        )
        self.media_base = (
            settings.PUBLIC_MEDIA_BASE_URL if media_base is None else media_base
        )
        self.transport = transport or self._request

    def publish(self, unit, *, video_url=None) -> str:
        self._require()
        url = video_url or self._video_url(unit)
        container = self.transport(
            "POST",
            f"{GRAPH}/{self.account_id}/media",
            {
                "media_type": "REELS",
                "video_url": url,
                "access_token": self.token,
            },
        )
        result = self.transport(
            "POST",
            f"{GRAPH}/{self.account_id}/media_publish",
            {"creation_id": container["id"], "access_token": self.token},
        )
        InstagramPublication.objects.update_or_create(
            reel=unit,
            defaults={
                "external_id": result["id"],
                "published_at": timezone.now(),
            },
        )
        return result["id"]

    def stats(self, unit) -> dict:
        publication = unit.publications.first()
        if publication is None or not publication.external_id:
            return {}
        self._require()
        data = self.transport(
            "GET",
            f"{GRAPH}/{publication.external_id}",
            {
                "fields": "like_count,comments_count,permalink",
                "access_token": self.token,
            },
        )
        publication.stats = data
        publication.save(update_fields=["stats", "updated_at"])
        return data

    def refresh(self, unit) -> None:
        self.stats(unit)

    def _require(self):
        if not (self.account_id and self.token):
            raise PublishUnavailable(
                "Instagram publishing needs INSTAGRAM_ACCOUNT_ID and "
                "INSTAGRAM_ACCESS_TOKEN."
            )

    def _video_url(self, unit) -> str:
        # A render has no stored public URL yet; guessing one would post garbage.
        if not self.media_base:
            raise PublishUnavailable(
                "Instagram publishing needs PUBLIC_MEDIA_BASE_URL to reach the file."
            )
        raise PublishUnavailable(
            "No stored render URL for this reel yet; pass video_url explicitly."
        )

    def _request(self, method: str, url: str, params: dict) -> dict:
        data = urllib.parse.urlencode(params).encode()
        if method == "GET":
            request = urllib.request.Request(
                f"{url}?{data.decode()}", method="GET"
            )
        else:
            request = urllib.request.Request(url, data=data, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            body = exc.read()[:500].decode(errors="replace")
            raise PublishUnavailable(f"Instagram rejected the call: {body}") from None
        except urllib.error.URLError as exc:
            raise PublishUnavailable(
                f"Instagram could not be reached: {exc.reason}"
            ) from None
