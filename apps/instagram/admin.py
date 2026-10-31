from auditlog.registry import auditlog
from django.contrib import admin

from .models import InstagramPublication, Reel, ReelGate


class ReelGateInline(admin.TabularInline):
    model = ReelGate
    extra = 0
    readonly_fields = ("position", "kind", "decided_by", "decided_at")


class PublicationInline(admin.TabularInline):
    model = InstagramPublication
    extra = 0
    can_delete = False
    readonly_fields = ("external_id", "url", "published_at", "stats")


@admin.register(Reel)
class ReelAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "campaign", "current_step", "created_at")
    list_filter = ("campaign__project__organization",)
    search_fields = ("title", "slug")
    inlines = [ReelGateInline, PublicationInline]

    @admin.display(description="Now")
    def current_step(self, reel):
        return reel.summary()


auditlog.register(Reel)
