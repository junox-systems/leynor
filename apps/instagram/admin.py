from auditlog.registry import auditlog
from django.contrib import admin

from .models import Reel, ReelGate


class ReelGateInline(admin.TabularInline):
    model = ReelGate
    extra = 0
    readonly_fields = ("position", "kind", "decided_by", "decided_at")


@admin.register(Reel)
class ReelAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "campaign", "current_step", "created_at")
    list_filter = ("campaign__project__organization",)
    search_fields = ("title", "slug")
    inlines = [ReelGateInline]

    @admin.display(description="Now")
    def current_step(self, reel):
        return reel.summary()


auditlog.register(Reel)
