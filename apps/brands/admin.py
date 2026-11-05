from auditlog.registry import auditlog
from django.contrib import admin

from .models import Audience, Brand


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "industry", "website", "created_at")
    list_filter = ("organization",)
    search_fields = ("name", "industry")


@admin.register(Audience)
class AudienceAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "primary", "created_at")
    list_filter = ("primary", "brand__organization")
    search_fields = ("name", "description", "wants", "barrier")


auditlog.register(Brand)
auditlog.register(Audience)
