"""A project is the workspace its campaigns belong to.

One organization owns many projects; one project holds many campaigns. The
content itself lives in the channel apps, one unit per campaign.
"""

from django.db import models

from apps.core.models import BaseModel


class Project(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    organization = models.ForeignKey(
        "orgs.Organization", on_delete=models.CASCADE, related_name="projects"
    )
    title = models.CharField(max_length=120)
    client = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.ACTIVE
    )

    def __str__(self):
        return self.title

    @classmethod
    def start(cls, *, organization, title, client="", description=""):
        return cls.objects.create(
            organization=organization,
            title=title,
            client=client,
            description=description,
        )

    @property
    def archived(self) -> bool:
        return self.status == self.Status.ARCHIVED
