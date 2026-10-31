from auditlog.registry import auditlog
from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "brand", "organization", "status", "created_at")
    list_filter = ("status", "organization", "brand")
    search_fields = ("title", "brand__name")


auditlog.register(Project)
