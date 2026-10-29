from django.template.loader import render_to_string


def html_body(subject, text):
    """Wrap a plain-text email body in the shared HTML layout (links become clickable)."""
    return render_to_string("email/base.html", {"subject": subject, "body": text})
