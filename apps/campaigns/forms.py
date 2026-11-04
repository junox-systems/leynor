"""The one form that briefs a campaign."""

from django import forms

from apps.brands.models import Audience
from apps.campaigns.models import Campaign


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["title", "goal", "audience"]
        widgets = {"title": forms.TextInput(attrs={"autofocus": True})}

    def __init__(self, *args, project, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)
        brand = project.brand
        self.fields["audience"].queryset = (
            brand.audiences.all() if brand else Audience.objects.none()
        )
        self.fields["audience"].empty_label = (
            "The brand's primary audience"
            if brand and brand.primary_audience
            else "No audience yet"
        )
        if brand is None:
            self.fields["audience"].help_text = (
                "Set a brand on this project to choose an audience."
            )

    def save(self, commit=True):
        campaign = super().save(commit=False)
        campaign.project = self.project
        if commit:
            campaign.save()
        return campaign
