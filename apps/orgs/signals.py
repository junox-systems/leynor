from allauth.account.signals import user_signed_up
from django.dispatch import receiver

from .models import Organization


@receiver(user_signed_up)
def create_personal_organization(request, user, **kwargs):
    """Every new account starts with its own organization, owned by them."""
    name = f"{user.username or user.email}'s workspace"
    Organization.create_with_owner(
        name[: Organization._meta.get_field("name").max_length], user
    )
