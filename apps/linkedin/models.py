"""Linkedin: a channel unit of a campaign. Content shape only for now."""

from django.db import models

from apps.campaigns.models import Unit


class Post(Unit):
    body = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
