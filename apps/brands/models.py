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
    audience = models.CharField(max_length=200, blank=True)
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
