from django.contrib.auth.forms import PasswordResetForm

from .models import Membership, Organization, User


def get_active_organization(user) -> Organization | None:
    """The organization this user operates in.

    MVP simplification: a user belongs to a single organization. If a user
    ever needs multiple, this is the one function to change to add an
    org-switcher rather than threading org selection through every view.
    """
    if not user.is_authenticated:
        return None
    membership = user.memberships.select_related("organization").first()
    return membership.organization if membership else None


def invite_member(organization: Organization, email: str, role: str, request=None) -> Membership:
    email = User.objects.normalize_email(email)
    user, created = User.objects.get_or_create(email=email, defaults={"username": email})
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])

    membership, _ = Membership.objects.update_or_create(
        user=user, organization=organization, defaults={"role": role}
    )

    if created:
        reset_form = PasswordResetForm(data={"email": email})
        if reset_form.is_valid():
            reset_form.save(
                email_template_name="accounts/emails/invite_email.txt",
                subject_template_name="accounts/emails/invite_subject.txt",
                request=request,
            )

    return membership
