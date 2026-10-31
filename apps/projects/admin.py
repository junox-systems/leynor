from auditlog.registry import auditlog
from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "organization", "created_at")
    list_filter = ("organization",)
    search_fields = ("title", "slug")


auditlog.register(Project)
