"""The one form that starts a campaign."""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from apps.campaigns.models import Campaign
from apps.projects.specs import SLUG


class CampaignForm(forms.ModelForm):
    slug = forms.SlugField(
        max_length=64,
        required=False,
        help_text="Lowercase letters, digits and dashes. Left empty, it comes from the title.",
    )

    class Meta:
        model = Campaign
        fields = ["title", "slug", "goal", "audience"]
        widgets = {"title": forms.TextInput(attrs={"autofocus": True})}

    def __init__(self, *args, project, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)

    def clean_slug(self):
        slug = self.cleaned_data.get("slug") or slugify(
            self.cleaned_data.get("title", "")
        )
        if not slug:
            raise ValidationError(
                "Give the campaign a slug, or a title a slug can come from."
            )
        if not SLUG.match(slug):
            raise ValidationError(
                "Use 2 to 64 lowercase letters, digits or dashes, starting with a letter or digit."
            )
        if Campaign.objects.filter(project=self.project, slug=slug).exists():
            raise ValidationError(
                "Another campaign in this project already uses that slug."
            )
        return slug

    def save(self, commit=True):
        campaign = super().save(commit=False)
        campaign.project = self.project
        if commit:
            campaign.save()
        return campaign
