"""What a drafting run returns. A value object, not a row."""

from pydantic import BaseModel


class DraftResult(BaseModel):
    draft: str
    critique: str
    revised: str
    revisions: int
