from django.contrib import admin

from .models import Gate, Project


class GateInline(admin.TabularInline):
    model = Gate
    extra = 0
    readonly_fields = ("position", "kind", "decided_by", "decided_at")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "organization", "current_step", "created_at")
    list_filter = ("organization",)
    search_fields = ("title", "slug")
    inlines = [GateInline]

    @admin.display(description="Now")
    def current_step(self, project):
        return project.summary()
