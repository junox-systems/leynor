from auditlog.registry import auditlog
from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "organization", "status", "created_at")
    list_filter = ("status", "organization")
    search_fields = ("title", "client")


auditlog.register(Project)
