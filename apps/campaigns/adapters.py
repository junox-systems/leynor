"""What every channel app implements, and what the campaign layer can rely on.

One Protocol, so publishing, stats and refresh look the same from outside the
channel. Implementations live in the channel app; no shared network code.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class PublishUnavailable(RuntimeError):
    """This channel has no credentials, media URL, or client wired yet."""


@runtime_checkable
class ChannelPublisher(Protocol):
    channel: str

    def publish(self, unit) -> str:
        """Post the unit and return the channel's external id."""
        ...

    def stats(self, unit) -> dict:
        """Latest metrics for the published unit."""
        ...

    def refresh(self, unit) -> None:
        """Pull fresh metrics into the publication record."""
        ...


class UnconfiguredPublisher:
    """A channel with an interface but no API client yet.

    Every method fails loudly or does nothing, so the registry can hand it out
    without pretending a post happened.
    """

    channel = ""

    def publish(self, unit) -> str:
        raise PublishUnavailable(f"{self.channel or 'this channel'} has no client yet.")

    def stats(self, unit) -> dict:
        return {}

    def refresh(self, unit) -> None:
        return None
