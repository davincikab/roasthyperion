from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, FormView, ListView, TemplateView, View

from .forms import InviteMemberForm, MembershipRoleForm, OrganizationForm, PasswordChangeForm
from .models import Membership, Organization, User
from .permissions import RoleRequiredMixin, SuperuserRequiredMixin
from .services import get_active_organization, invite_member

MEMBERS_PER_PAGE = 20
USERS_PER_PAGE = 25
ORGANIZATIONS_PER_PAGE = 25


class OrganizationScopedMixin:
    """Resolves the organization being managed from an optional `org_id` URL kwarg
    (superusers reaching in from the org list) or, if absent, the requesting
    user's own organization. RoleRequiredMixin still enforces that a non-superuser
    can only ever land on an org they actually have the right role in."""

    def get_organization(self):
        org_id = self.kwargs.get("org_id")
        if org_id is not None:
            return get_object_or_404(Organization, pk=org_id)
        return get_active_organization(self.request.user)

    def get_team_url(self):
        org_id = self.kwargs.get("org_id")
        if org_id is not None:
            return reverse("accounts:team", kwargs={"org_id": org_id})
        return reverse("accounts:team")


class TeamView(OrganizationScopedMixin, RoleRequiredMixin, TemplateView):
    template_name = "accounts/team.html"
    required_roles = (Membership.Role.ADMIN,)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        org_id = self.kwargs.get("org_id")
        context["organization"] = organization
        context["org_id"] = org_id

        memberships = (
            organization.memberships.select_related("user").order_by("user__email")
            if organization
            else Membership.objects.none()
        )
        paginator = Paginator(memberships, MEMBERS_PER_PAGE)
        page_obj = paginator.get_page(self.request.GET.get("page"))
        for membership in page_obj:
            role_kwargs = {"membership_id": membership.pk}
            remove_kwargs = {"membership_id": membership.pk}
            if org_id is not None:
                role_kwargs["org_id"] = org_id
                remove_kwargs["org_id"] = org_id
            membership.update_role_url = reverse("accounts:team_update_role", kwargs=role_kwargs)
            membership.remove_url = reverse("accounts:team_remove", kwargs=remove_kwargs)
        context["page_obj"] = page_obj
        context["memberships"] = page_obj

        context["invite_url"] = (
            reverse("accounts:team_invite", kwargs={"org_id": org_id})
            if org_id is not None
            else reverse("accounts:team_invite")
        )
        context["invite_form"] = InviteMemberForm()
        context["role_choices"] = Membership.Role.choices
        return context


class InviteMemberView(OrganizationScopedMixin, RoleRequiredMixin, FormView):
    form_class = InviteMemberForm
    required_roles = (Membership.Role.ADMIN,)

    def form_valid(self, form):
        organization = self.get_organization()
        if organization is None:
            messages.error(self.request, "You don't belong to an organization.")
            return redirect(self.get_team_url())
        invite_member(
            organization=organization,
            email=form.cleaned_data["email"],
            role=form.cleaned_data["role"],
            password=form.cleaned_data["password"],
            request=self.request,
        )
        if form.cleaned_data["password"]:
            messages.success(self.request, f"Added {form.cleaned_data['email']} with the password you set.")
        else:
            messages.success(self.request, f"Invited {form.cleaned_data['email']}.")
        return redirect(self.get_team_url())

    def form_invalid(self, form):
        errors = " ".join(e for field in form.errors.values() for e in field)
        messages.error(self.request, errors or "Could not add member — check the form.")
        return redirect(self.get_team_url())


class UpdateMemberRoleView(OrganizationScopedMixin, RoleRequiredMixin, View):
    required_roles = (Membership.Role.ADMIN,)

    def post(self, request, membership_id, **kwargs):
        membership = get_object_or_404(
            Membership, pk=membership_id, organization=self.get_organization()
        )
        form = MembershipRoleForm(request.POST, instance=membership)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated role for {membership.user}.")
        else:
            messages.error(request, "Could not update role.")
        return redirect(self.get_team_url())


class RemoveMemberView(OrganizationScopedMixin, RoleRequiredMixin, View):
    required_roles = (Membership.Role.ADMIN,)

    def post(self, request, membership_id, **kwargs):
        membership = get_object_or_404(
            Membership, pk=membership_id, organization=self.get_organization()
        )
        if membership.user_id == request.user.id:
            messages.error(request, "You cannot remove yourself from the organization.")
        else:
            user_label = str(membership.user)
            membership.delete()
            messages.success(request, f"Removed {user_label}.")
        return redirect(self.get_team_url())


class OrganizationListView(SuperuserRequiredMixin, ListView):
    """Superuser-only: every organization on the platform, with a way to create more."""

    model = Organization
    template_name = "accounts/organization_list.html"
    context_object_name = "organizations"
    paginate_by = ORGANIZATIONS_PER_PAGE

    def get_queryset(self):
        return Organization.objects.annotate(member_count=Count("memberships")).order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = OrganizationForm()
        return context


class OrganizationCreateView(SuperuserRequiredMixin, CreateView):
    model = Organization
    form_class = OrganizationForm
    template_name = "accounts/organization_list.html"

    def get_success_url(self):
        return reverse("accounts:team", kwargs={"org_id": self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Created organization {self.object.name}.")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Could not create organization — check the name.")
        return redirect(reverse("accounts:organization_list"))


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

        organization_id = self.request.GET.get("organization", "").strip()
        if organization_id:
            queryset = queryset.filter(memberships__organization_id=organization_id)

        active = self.request.GET.get("active", "").strip()
        if active == "active":
            queryset = queryset.filter(is_active=True)
        elif active == "inactive":
            queryset = queryset.filter(is_active=False)

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["organization_filter"] = self.request.GET.get("organization", "")
        context["active_filter"] = self.request.GET.get("active", "")
        context["organizations"] = Organization.objects.order_by("name")
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
