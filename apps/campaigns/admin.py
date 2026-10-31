from auditlog.registry import auditlog
from django.contrib import admin

from .models import Campaign


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "project", "goal", "created_at")
    list_filter = ("goal", "project__organization")
    search_fields = ("title", "slug")


auditlog.register(Campaign)
