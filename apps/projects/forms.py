"""The one form that creates a project."""

from django import forms

from apps.projects.models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "brand", "description"]
        widgets = {
            "title": forms.TextInput(attrs={"autofocus": True}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand"].queryset = organization.brands.all()
        self.fields["brand"].empty_label = "No brand yet"
