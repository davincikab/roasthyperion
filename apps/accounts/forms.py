from django import forms
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm
from django.contrib.auth.forms import UserCreationForm as DjangoUserCreationForm

from .models import Membership, User


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


class MembershipRoleForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ("role",)
