# apps/core/tasks.py
#
# Background task examples, run by django-q2. Tasks are plain functions;
# enqueue them by dotted path from anywhere (views, signals, commands):
#
#   from django_q.tasks import async_task
#   async_task("apps.core.tasks.send_welcome_email", user.id)
#
# Workers run in the `qcluster` container / `python manage.py qcluster`.
# The broker is the Django database (Q_CLUSTER["orm"]), so no Redis.

import functools
import smtplib
import time

import anymail.exceptions
from django.conf import settings
from django.core.mail import send_mail
from django.db import OperationalError

from apps.core.emails import html_body
from apps.users.models import User

EMAIL_ERRORS = (
    smtplib.SMTPException,
    anymail.exceptions.AnymailAPIError,
    OSError,
    TimeoutError,
)


def retry(*exceptions, retries=5, max_backoff=30):
    """Re-run the task on `exceptions` with exponential backoff (1s, 2s, 4s…).

    django-q2 only re-queues tasks that die or time out, not ones that raise.
    Backoff sleeps inside the worker; keep it short.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    if attempt == retries:
                        raise
                    time.sleep(min(2**attempt, max_backoff))

        return wrapper

    return decorator


@retry(*EMAIL_ERRORS)
def send_welcome_email(user_id):
    """Send a welcome email after signup. Queued by apps/users/signals.py."""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return
    subject = "Welcome aboard"
    message = f"Hi {user.username}, thanks for signing up."
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_body(subject, message),
    )


@retry(OperationalError, TimeoutError)
def export_user_data(user_id):
    """Example long-running job: build an export artifact for a user.

    Retries with exponential backoff up to 30s, 5 tries.
    """
    user = User.objects.get(id=user_id)
    # ... build the export ...
    return f"exports/user_{user.id}.csv"


@retry(*EMAIL_ERRORS)
def send_test_email(subject, message, recipient_list):
    """Send a test email (used by admin checks / debugging)."""
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_list,
        html_message=html_body(subject, message),
    )
