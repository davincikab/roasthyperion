from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView, ListView, TemplateView, View

from .forms import InviteMemberForm, MembershipRoleForm, PasswordChangeForm
from .models import Membership, User
from .permissions import RoleRequiredMixin, SuperuserRequiredMixin
from .services import get_active_organization, invite_member

MEMBERS_PER_PAGE = 20
USERS_PER_PAGE = 25


class TeamView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/team.html"
    required_roles = (Membership.Role.ADMIN,)

    def get_organization(self):
        return get_active_organization(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        context["organization"] = organization

        memberships = (
            organization.memberships.select_related("user").order_by("user__email")
            if organization
            else Membership.objects.none()
        )
        paginator = Paginator(memberships, MEMBERS_PER_PAGE)
        context["page_obj"] = paginator.get_page(self.request.GET.get("page"))
        context["memberships"] = context["page_obj"]

        context["invite_form"] = InviteMemberForm()
        context["role_choices"] = Membership.Role.choices
        return context


class InviteMemberView(RoleRequiredMixin, FormView):
    form_class = InviteMemberForm
    required_roles = (Membership.Role.ADMIN,)

    def get_organization(self):
        return get_active_organization(self.request.user)

    def form_valid(self, form):
        organization = self.get_organization()
        if organization is None:
            messages.error(self.request, "You don't belong to an organization.")
            return redirect(reverse("accounts:team"))
        invite_member(
            organization=organization,
            email=form.cleaned_data["email"],
            role=form.cleaned_data["role"],
        )
        messages.success(self.request, f"Invited {form.cleaned_data['email']}.")
        return redirect(reverse("accounts:team"))

    def form_invalid(self, form):
        messages.error(self.request, "Could not send invite — check the email address.")
        return redirect(reverse("accounts:team"))


class UpdateMemberRoleView(RoleRequiredMixin, View):
    required_roles = (Membership.Role.ADMIN,)

    def get_organization(self):
        return get_active_organization(self.request.user)

    def post(self, request, membership_id):
        membership = get_object_or_404(
            Membership, pk=membership_id, organization=self.get_organization()
        )
        form = MembershipRoleForm(request.POST, instance=membership)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated role for {membership.user}.")
        else:
            messages.error(request, "Could not update role.")
        return redirect(reverse("accounts:team"))


class RemoveMemberView(RoleRequiredMixin, View):
    required_roles = (Membership.Role.ADMIN,)

    def get_organization(self):
        return get_active_organization(self.request.user)

    def post(self, request, membership_id):
        membership = get_object_or_404(
            Membership, pk=membership_id, organization=self.get_organization()
        )
        if membership.user_id == request.user.id:
            messages.error(request, "You cannot remove yourself from the organization.")
        else:
            user_label = str(membership.user)
            membership.delete()
            messages.success(request, f"Removed {user_label}.")
        return redirect(reverse("accounts:team"))


class ProfileView(LoginRequiredMixin, TemplateView):
    """Self-service page: view your own account + organization memberships."""

    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["memberships"] = self.request.user.memberships.select_related("organization")
        return context


class ChangePasswordView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = PasswordChangeForm
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Password updated.")
        return response


class UserManagementListView(SuperuserRequiredMixin, ListView):
    """Superuser-only: every user across every organization, with search."""

    template_name = "accounts/user_management.html"
    context_object_name = "users"
    paginate_by = USERS_PER_PAGE

    def get_queryset(self):
        queryset = User.objects.prefetch_related("memberships__organization").order_by("email")
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(email__icontains=query)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        return context


class ToggleUserActiveView(SuperuserRequiredMixin, View):
    def post(self, request, user_id):
        target = get_object_or_404(User, pk=user_id)
        if target.id == request.user.id:
            messages.error(request, "You cannot deactivate your own account.")
        else:
            target.is_active = not target.is_active
            target.save(update_fields=["is_active"])
            messages.success(
                request, f"{target.email} is now {'active' if target.is_active else 'inactive'}."
            )
        return redirect(reverse("accounts:user_management"))
