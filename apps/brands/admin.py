from auditlog.registry import auditlog
from django.contrib import admin

from .models import Brand


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "industry", "website", "created_at")
    list_filter = ("organization",)
    search_fields = ("name", "industry")


auditlog.register(Brand)
