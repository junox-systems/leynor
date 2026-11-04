"""A campaign is one brief. Its output units belong to channel apps.

The campaign knows no channel: it holds the brief, and the registry in
`apps.campaigns.registry` is how its units are found. A new channel adds one
app and one registry line, never a field here.
"""

from django.db import models

from apps.core.models import BaseModel

GOAL_SAVES = "saves"
GOAL_SHARES = "shares"
GOAL_FOLLOWS = "follows"


class Goal(models.TextChoices):
    SAVES = GOAL_SAVES, "Saves"
    SHARES = GOAL_SHARES, "Shares"
    FOLLOWS = GOAL_FOLLOWS, "Follows"


class Campaign(BaseModel):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="campaigns"
    )
    title = models.CharField(max_length=120)
    goal = models.CharField(max_length=8, choices=Goal.choices, default=Goal.SAVES)
    audience = models.ForeignKey(
        "brands.Audience",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="campaigns",
        help_text="One of the brand's audiences. The campaign speaks to this slice.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def organization(self):
        """Tenancy comes from the project; RBAC reads this attribute."""
        return self.project.organization

    def units(self):
        """Every output unit of this campaign, one row per channel unit."""
        from apps.campaigns.registry import units

        return units(self)


class Unit(BaseModel):
    """What a channel produces for a campaign. Shared fields only."""

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="+"
    )
    title = models.CharField(max_length=120)
    prompt = models.TextField(
        blank=True,
        help_text="What this piece must say, in the operator's words.",
    )
    goal = models.CharField(
        max_length=8,
        choices=Goal.choices,
        blank=True,
        help_text="The primary goal this piece chases. Empty takes the campaign's.",
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.title

    @property
    def organization(self):
        """Tenancy resolves through the campaign, so every unit is scoped."""
        return self.campaign.organization

    @property
    def effective_goal(self) -> str:
        """The goal the piece is judged by: its own, or the brief's."""
        return self.goal or self.campaign.goal

    @property
    def has_route(self) -> bool:
        """True when this unit gates its work; false for a plain post."""
        return False

    @property
    def needs_person(self) -> bool:
        return False

    def summary(self) -> str:
        return "Draft"


class PublicationBase(BaseModel):
    """One published instance of a unit on one channel account."""

    external_id = models.CharField(max_length=200, blank=True)
    url = models.URLField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    stats = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True
