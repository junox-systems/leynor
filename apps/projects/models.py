"""A project is the workspace its campaigns belong to.

One organization owns many projects; one project holds many campaigns. The
content itself lives in the channel apps, one unit per campaign.
"""

from django.db import models

from apps.core.models import BaseModel


class Project(BaseModel):
    organization = models.ForeignKey(
        "orgs.Organization", on_delete=models.CASCADE, related_name="projects"
    )
    slug = models.SlugField(max_length=64)
    title = models.CharField(max_length=120)

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"], name="unique_project_slug_per_org"
            )
        ]

    def __str__(self):
        return self.title

    @classmethod
    def start(cls, *, organization, title, slug):
        return cls.objects.create(organization=organization, title=title, slug=slug)
