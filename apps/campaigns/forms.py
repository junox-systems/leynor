"""The one form that briefs a campaign."""

from django import forms

from apps.campaigns.models import Campaign


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["title", "goal", "audience"]
        widgets = {
            "title": forms.TextInput(attrs={"autofocus": True}),
            "audience": forms.TextInput(attrs={"placeholder": "Who this is for"}),
        }

    def __init__(self, *args, project, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        campaign = super().save(commit=False)
        campaign.project = self.project
        if commit:
            campaign.save()
        return campaign
