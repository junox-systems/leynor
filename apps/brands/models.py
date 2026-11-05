"""A brand is the organization-level client a project works for.

Brands live beside projects, not inside them: several projects can answer the
same brand, and a project may start before the brand is written down.
"""

from django.db import models

from apps.core.models import BaseModel


class Brand(BaseModel):
    organization = models.ForeignKey(
        "orgs.Organization", on_delete=models.CASCADE, related_name="brands"
    )
    name = models.CharField(max_length=120)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True, help_text="What it is and what it stands for.")
    industry = models.CharField(max_length=120, blank=True)
    tone = models.CharField(
        max_length=200, blank=True, help_text="How it sounds when it speaks."
    )

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_brand_name_per_org"
            )
        ]

    def __str__(self):
        return self.name

    @property
    def primary_audience(self):
        """The audience this brand speaks to by default, if it named one."""
        return self.audiences.filter(primary=True).first()


class Audience(BaseModel):
    """One group of people a brand makes work for.

    The brand owns the audience, because who it serves outlives any campaign.
    A campaign picks one of these; it never retypes the description.
    """

    brand = models.ForeignKey(
        Brand, on_delete=models.CASCADE, related_name="audiences"
    )
    name = models.CharField(
        max_length=120, help_text="A handle a person would say out loud."
    )
    description = models.TextField(
        blank=True, help_text="Who they are, in a paragraph."
    )
    wants = models.CharField(max_length=200, blank=True, help_text="What they want.")
    barrier = models.CharField(
        max_length=200, blank=True, help_text="What stands in their way."
    )
    primary = models.BooleanField(
        default=False, help_text="The audience this brand speaks to by default."
    )

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["brand", "name"], name="unique_audience_name_per_brand"
            ),
            models.UniqueConstraint(
                fields=["brand"],
                condition=models.Q(primary=True),
                name="one_primary_audience_per_brand",
            ),
        ]

    def __str__(self):
        return self.name
