"""The one form that briefs a campaign."""

from django import forms

from apps.campaigns.models import Campaign


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["title", "goal", "audience"]
        widgets = {
            "title": forms.TextInput(attrs={"autofocus": True}),
            "goal": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "goal": "What this campaign must achieve, in words. Each output picks its own outcome.",
        }

    def __init__(self, *args, project, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)
        brand = project.brand
        field = self.fields["audience"]
        # Read through the relation: campaigns may not import the brands app.
        field.queryset = brand.audiences.all() if brand else field.queryset.none()
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
