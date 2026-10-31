"""The one form that starts a project."""

from django import forms

from apps.projects.models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "client", "description"]
        widgets = {
            "title": forms.TextInput(attrs={"autofocus": True}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {"client": "Client or brand"}
