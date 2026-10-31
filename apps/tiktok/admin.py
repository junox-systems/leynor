from django.contrib import admin

from .models import TikTok


@admin.register(TikTok)
class TikTokAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "campaign", "created_at")
    list_filter = ("campaign__project__organization",)
    search_fields = ("title", "slug")
