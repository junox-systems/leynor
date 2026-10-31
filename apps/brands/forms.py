"""The one form that creates a brand."""

from django import forms
from django.core.exceptions import ValidationError

from apps.brands.models import Brand


class BrandForm(forms.ModelForm):
    # Explicit so Django does not warn about the default http scheme.
    website = forms.URLField(required=False, assume_scheme="https", max_length=200)

    class Meta:
        model = Brand
        fields = ["name", "website", "description", "industry", "audience", "tone"]
        widgets = {
            "name": forms.TextInput(attrs={"autofocus": True}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, organization, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if Brand.objects.filter(organization=self.organization, name=name).exists():
            raise ValidationError("This organization already has a brand by that name.")
        return name

    def save(self, commit=True):
        brand = super().save(commit=False)
        brand.organization = self.organization
        if commit:
            brand.save()
        return brand
