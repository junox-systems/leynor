from allauth.account.adapter import get_adapter
from django import forms
from django.core.exceptions import ValidationError

from .models import User

MAX_AVATAR_BYTES = 5 * 1024 * 1024
# Thumbnailing decodes the whole image in the request; cap memory per upload.
MAX_AVATAR_PIXELS = 4096 * 4096


class AvatarInput(forms.ClearableFileInput):
    """Current avatar preview, upload button and remove toggle (avatar-preview controller)."""

    template_name = "users/widgets/avatar_input.html"
    user = None  # set by ProfileForm: the value is None without a file, so no .instance

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["user"] = self.user
        return context


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "avatar"]
        widgets = {"avatar": AvatarInput}
        help_texts = {"avatar": "Max 5 MB, up to 4096×4096 pixels."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["avatar"].widget.user = self.instance

    def clean_username(self):
        """Allauth's signup rules; case-insensitive uniqueness is a DB constraint."""
        username = self.cleaned_data["username"]
        if "username" in self.changed_data:
            get_adapter().clean_username(username, shallow=True)
        return username

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        # Only a new upload: the stored file may be missing, and size hits storage.
        if not avatar or "avatar" not in self.changed_data:
            return avatar
        if avatar.size > MAX_AVATAR_BYTES:
            raise ValidationError("Image must be 5 MB or smaller.")
        width, height = avatar.image.size
        if width * height > MAX_AVATAR_PIXELS:
            raise ValidationError("Image must be 4096×4096 pixels or smaller.")
        return avatar
