"""The one form that starts a reel: an idea, a goal, a length."""

from django import forms

from apps.instagram.models import ReelPitch

LENGTHS = [(60, "60 s"), (90, "90 s"), (120, "2 min"), (180, "3 min")]


class PitchForm(forms.ModelForm):
    target_seconds = forms.TypedChoiceField(
        choices=LENGTHS,
        coerce=int,
        initial=60,
        label="Length",
        widget=forms.RadioSelect,
        help_text="Past 3 minutes, Instagram stops recommending a reel.",
    )

    class Meta:
        model = ReelPitch
        fields = ["idea", "goal", "target_seconds"]
        widgets = {
            "idea": forms.Textarea(
                attrs={
                    "rows": 5,
                    "autofocus": True,
                    "maxlength": 2000,
                    "placeholder": "Why most people quit a new habit on day three, and the one change that keeps them going.",
                }
            ),
            "goal": forms.RadioSelect,
        }
        labels = {"idea": "Your idea", "goal": "What it should earn"}
        help_texts = {
            "idea": "A sentence or a paragraph. You will get three takes on it to choose from.",
            "goal": "Saves for reference value, shares for something people send on, follows for a reason to come back.",
        }

    def __init__(self, *args, campaign, **kwargs):
        self.campaign = campaign
        super().__init__(*args, **kwargs)
        self.fields["goal"].choices = [
            c for c in self.fields["goal"].choices if c[0]
        ]

    def save(self, commit=True):
        pitch = super().save(commit=False)
        pitch.campaign = self.campaign
        if commit:
            pitch.save()
        return pitch
