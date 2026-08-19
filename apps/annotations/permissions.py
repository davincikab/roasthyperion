from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.models import Membership
from apps.accounts.permissions import has_role


class IsOrganizationMember(BasePermission):
    """Viewer role (or above) can read; editor/admin can write. Scoped to the
    organization that owns the project the annotation belongs to."""

    def has_permission(self, request, view):
        organization = view.get_project().organization
        if request.method in SAFE_METHODS:
            return has_role(request.user, organization)
        return has_role(request.user, organization, Membership.Role.EDITOR, Membership.Role.ADMIN)

    def has_object_permission(self, request, view, obj):
        organization = obj.project.organization
        if request.method in SAFE_METHODS:
            return has_role(request.user, organization)
        return has_role(request.user, organization, Membership.Role.EDITOR, Membership.Role.ADMIN)
