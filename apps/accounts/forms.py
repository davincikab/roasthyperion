from django import forms
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm
from django.contrib.auth.forms import UserCreationForm as DjangoUserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify

from .models import Membership, Organization, User


class UserCreationForm(DjangoUserCreationForm):
    class Meta(DjangoUserCreationForm.Meta):
        model = User
        fields = ("email",)


class PasswordChangeForm(DjangoPasswordChangeForm):
    """Same validation as Django's PasswordChangeForm, without the wall of
    validator help text (it renders a <ul> nested inside as_p's <p>, which
    browsers close early and break the field layout)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].help_text = None
        self.fields["new_password2"].help_text = None


class UserChangeForm(DjangoUserChangeForm):
    class Meta(DjangoUserChangeForm.Meta):
        model = User
        fields = ("email",)


class InviteMemberForm(forms.Form):
    email = forms.EmailField()
    role = forms.ChoiceField(choices=Membership.Role.choices)
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        help_text="Optional — set it directly instead of emailing an invite link (useful if email isn't configured).",
    )

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            validate_password(password)
        return password


class MembershipRoleForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ("role",)


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ("name",)

    def save(self, commit=True):
        organization = super().save(commit=False)
        if not organization.slug:
            base_slug = slugify(organization.name)[:50] or "org"
            slug = base_slug
            suffix = 1
            while Organization.objects.filter(slug=slug).exclude(pk=organization.pk).exists():
                suffix += 1
                slug = f"{base_slug}-{suffix}"
            organization.slug = slug
        if commit:
            organization.save()
        return organization
