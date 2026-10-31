"""The one form that starts a project."""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from apps.projects.models import Project
from apps.projects.specs import SLUG


class ProjectForm(forms.ModelForm):
    slug = forms.SlugField(
        max_length=64,
        required=False,
        help_text="Lowercase letters, digits and dashes. Left empty, it comes from the title.",
    )

    class Meta:
        model = Project
        fields = ["title", "slug"]
        widgets = {"title": forms.TextInput(attrs={"autofocus": True})}

    def __init__(self, *args, organization, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)

    def clean_slug(self):
        slug = self.cleaned_data.get("slug") or slugify(
            self.cleaned_data.get("title", "")
        )
        if not slug:
            raise ValidationError(
                "Give the project a slug, or a title a slug can come from."
            )
        if not SLUG.match(slug):
            raise ValidationError(
                "Use 2 to 64 lowercase letters, digits or dashes, starting with a letter or digit."
            )
        if Project.objects.filter(organization=self.organization, slug=slug).exists():
            raise ValidationError(
                "Another project in this organization already uses that slug."
            )
        return slug
