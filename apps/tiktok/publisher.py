"""Tiktok publishing: the interface is registered, the client is not built."""

from apps.campaigns.adapters import UnconfiguredPublisher


class TikTokPublisher(UnconfiguredPublisher):
    channel = "tiktok"
