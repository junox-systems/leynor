"""Twitter publishing: the interface is registered, the client is not built."""

from apps.campaigns.adapters import UnconfiguredPublisher


class TweetPublisher(UnconfiguredPublisher):
    channel = "twitter"
