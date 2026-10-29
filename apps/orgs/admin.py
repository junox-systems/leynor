from django.contrib import admin

from .models import OWNER, Invitation, Membership, Organization, Role


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]
    filter_horizontal = ["roles"]


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    inlines = [MembershipInline]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """AddRole / DeleteRole / GrantPermission / RevokePermission / AddInheritance for operators.

    Role.clean() enforces the limited hierarchy's acyclicity on save.
    """

    list_display = ("name", "descendant", "description")
    search_fields = ("name",)
    filter_horizontal = ["permissions"]

    def has_delete_permission(self, request, obj=None):
        # Every organization must keep an owner; see rbac.delete_role. Also
        # blocks bulk "delete selected" when the owner role is selected.
        if obj is not None and obj.name == OWNER:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "organization", "invited_by", "created_at")
    search_fields = ("email", "organization__name")
    exclude = ("token",)
