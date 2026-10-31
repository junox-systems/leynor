"""The one form that starts a reel."""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from apps.instagram.models import Reel
from apps.projects.specs import SLUG


class ReelForm(forms.ModelForm):
    slug = forms.SlugField(
        max_length=64,
        required=False,
        help_text="Lowercase letters, digits and dashes. Left empty, it comes from the title.",
    )

    class Meta:
        model = Reel
        fields = ["title", "slug", "target_seconds"]
        help_texts = {"target_seconds": "Between 60 and 120 seconds."}
        widgets = {"title": forms.TextInput(attrs={"autofocus": True})}

    def __init__(self, *args, campaign, **kwargs):
        self.campaign = campaign
        super().__init__(*args, **kwargs)

    def clean_slug(self):
        slug = self.cleaned_data.get("slug") or slugify(
            self.cleaned_data.get("title", "")
        )
        if not slug:
            raise ValidationError(
                "Give the reel a slug, or a title a slug can come from."
            )
        if not SLUG.match(slug):
            raise ValidationError(
                "Use 2 to 64 lowercase letters, digits or dashes, starting with a letter or digit."
            )
        if Reel.objects.filter(campaign=self.campaign, slug=slug).exists():
            raise ValidationError(
                "Another reel in this campaign already uses that slug."
            )
        return slug

    def clean_target_seconds(self):
        seconds = self.cleaned_data["target_seconds"]
        if not 60 <= seconds <= 120:
            raise ValidationError("A reel runs 60 to 120 seconds.")
        return seconds

    def save(self, commit=True):
        reel = super().save(commit=False)
        reel.campaign = self.campaign
        if commit:
            reel.save()
        return reel
