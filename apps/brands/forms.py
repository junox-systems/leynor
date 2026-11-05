"""The forms that create a brand and the audiences it speaks to."""

from django import forms
from django.core.exceptions import ValidationError

from apps.brands.models import Audience, Brand


class BrandForm(forms.ModelForm):
    # Explicit so Django does not warn about the default http scheme.
    website = forms.URLField(required=False, assume_scheme="https", max_length=200)

    class Meta:
        model = Brand
        fields = ["name", "website", "description", "industry", "tone"]
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


class AudienceForm(forms.ModelForm):
    class Meta:
        model = Audience
        fields = ["name", "description", "wants", "barrier", "primary"]
        widgets = {
            "name": forms.TextInput(attrs={"autofocus": True}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, brand, **kwargs):
        self.brand = brand
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if Audience.objects.filter(brand=self.brand, name=name).exists():
            raise ValidationError("This brand already has an audience by that name.")
        return name

    def clean_primary(self):
        primary = self.cleaned_data["primary"]
        if primary and Audience.objects.filter(brand=self.brand, primary=True).exists():
            raise ValidationError(
                "This brand already has a primary audience. Clear that one first."
            )
        return primary

    def save(self, commit=True):
        audience = super().save(commit=False)
        audience.brand = self.brand
        if commit:
            audience.save()
        return audience
