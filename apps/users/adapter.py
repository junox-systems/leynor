from allauth.account.adapter import DefaultAccountAdapter

from apps.core.emails import html_body


class AccountAdapter(DefaultAccountAdapter):
    def render_mail(self, template_prefix, email, context, headers=None):
        """Add an HTML part to every allauth/MFA email that only ships a .txt template."""
        msg = super().render_mail(template_prefix, email, context, headers=headers)
        if hasattr(msg, "attach_alternative") and not msg.alternatives:
            msg.attach_alternative(html_body(msg.subject, msg.body), "text/html")
        return msg
