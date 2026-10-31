"""What every channel app implements, and what the campaign layer can rely on.

One Protocol, so publishing, stats and refresh look the same from outside the
channel. Implementations live in the channel app; no shared network code.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class PublishUnavailable(RuntimeError):
    """This channel has no credentials or client wired yet."""


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
