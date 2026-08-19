from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied

from .models import Membership


def get_role(user, organization):
    """Return the user's role string for this organization, or None if they have no membership."""
    if not user or not user.is_authenticated or organization is None:
        return None
    membership = Membership.objects.filter(user=user, organization=organization).first()
    return membership.role if membership else None


def has_role(user, organization, *roles):
    """True if the user has a membership in organization, optionally restricted to one of `roles`.

    Superusers always pass, regardless of membership — they're platform
    operators, not tenant members, and can view/manage any organization.
    """
    if user and user.is_authenticated and user.is_superuser:
        return True
    role = get_role(user, organization)
    if role is None:
        return False
    return not roles or role in roles


class RoleRequiredMixin(AccessMixin):
    """CBV mixin: require the requesting user to hold one of `required_roles` in
    the organization returned by `get_organization()`. An empty `required_roles`
    means any membership (i.e. viewer or above) is sufficient.

    Anonymous users are redirected to login (like LoginRequiredMixin); an
    authenticated user lacking the right role gets a 403.
    """

    required_roles = ()

    def get_organization(self):
        raise NotImplementedError("Subclasses must implement get_organization()")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        organization = self.get_organization()
        if not has_role(request.user, organization, *self.required_roles):
            raise PermissionDenied("You do not have access to this organization.")
        return super().dispatch(request, *args, **kwargs)


class SuperuserRequiredMixin(AccessMixin):
    """CBV mixin: require an authenticated superuser. Anonymous users are
    redirected to login; an authenticated non-superuser gets a 403."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_superuser:
            raise PermissionDenied("Superuser access required.")
        return super().dispatch(request, *args, **kwargs)
