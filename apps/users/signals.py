from types import SimpleNamespace

from allauth.account.signals import user_signed_up
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django_q.tasks import async_task
from imagekit.cachefiles import ImageCacheFile

from .models import User


@receiver(user_signed_up)
def queue_welcome_email(request, user, **kwargs):
    # on_commit: the worker must not race the signup transaction for the row.
    transaction.on_commit(
        lambda: async_task("apps.core.tasks.send_welcome_email", user.id)
    )


def _thumbnail_file(avatar_name):
    """The cached thumbnail imagekit generates for this avatar file."""
    spec = User.avatar_thumbnail.get_spec(source=SimpleNamespace(name=avatar_name))
    return ImageCacheFile(spec)


def _delete_avatar_files(avatar_name):
    User._meta.get_field("avatar").storage.delete(avatar_name)
    thumbnail = _thumbnail_file(avatar_name)
    thumbnail.storage.delete(thumbnail.name)


@receiver(pre_save, sender=User)
def remember_old_avatar(sender, instance, update_fields=None, **kwargs):
    """Read the stored avatar name before the row is written, so the old file
    can be removed once the new one is committed."""
    if instance._state.adding:
        return
    if update_fields is not None and "avatar" not in update_fields:
        return
    instance._old_avatar_name = (
        sender.objects.filter(pk=instance.pk).values_list("avatar", flat=True).first()
    )


@receiver(post_save, sender=User)
def delete_replaced_avatar(sender, instance, created, **kwargs):
    old_name = getattr(instance, "_old_avatar_name", None)
    instance._old_avatar_name = None
    if created or not old_name or old_name == instance.avatar.name:
        return
    transaction.on_commit(lambda: _delete_avatar_files(old_name), robust=True)


@receiver(post_delete, sender=User)
def delete_avatar_on_user_delete(sender, instance, **kwargs):
    if instance.avatar.name:
        transaction.on_commit(
            lambda: _delete_avatar_files(instance.avatar.name), robust=True
        )
