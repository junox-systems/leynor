"""The one form that creates a reel."""

from django import forms
from django.core.exceptions import ValidationError

from apps.instagram.models import Reel


class ReelForm(forms.ModelForm):
    class Meta:
        model = Reel
        fields = ["title", "prompt", "goal", "target_seconds"]
        widgets = {
            "title": forms.TextInput(attrs={"autofocus": True}),
            "prompt": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "title": "The slug every render is keyed by comes from this.",
            "target_seconds": "Between 60 and 180 seconds. Past 180, Instagram stops recommending it.",
        }

    def __init__(self, *args, campaign, **kwargs):
        self.campaign = campaign
        super().__init__(*args, **kwargs)

    def clean_target_seconds(self):
        seconds = self.cleaned_data["target_seconds"]
        if not 60 <= seconds <= 180:
            raise ValidationError("A reel runs 60 to 180 seconds.")
        return seconds

    def save(self, commit=True):
        reel = super().save(commit=False)
        reel.campaign = self.campaign
        if commit:
            reel.save()
        return reel
