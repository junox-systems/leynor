"""What a drafting step returns. A value object, not a row."""

from pydantic import BaseModel

from apps.projects.gates import Step


class DraftResult(BaseModel):
    step: Step
    draft: str
    critique: str
    revised: str
    revisions: int
