from django.urls import path

from . import views

urlpatterns = [
    path("", views.org_list, name="orgs"),
    path("switch/", views.org_switch, name="org_switch"),
    path("<uuid:pk>/", views.org_detail, name="org_detail"),
    path("<uuid:pk>/delete/", views.org_delete, name="org_delete"),
    path(
        "<uuid:pk>/members/<uuid:membership_pk>/remove/",
        views.membership_remove,
        name="membership_remove",
    ),
    path(
        "<uuid:pk>/members/<uuid:membership_pk>/role/",
        views.membership_role,
        name="membership_role",
    ),
    path(
        "<uuid:pk>/invitations/<uuid:invitation_pk>/revoke/",
        views.invitation_revoke,
        name="invitation_revoke",
    ),
    path("invite/<str:token>/", views.invitation_accept, name="invitation_accept"),
]
