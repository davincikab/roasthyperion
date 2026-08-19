from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(template_name="accounts/password_reset.html"),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("team/", views.TeamView.as_view(), name="team"),
    path("team/invite/", views.InviteMemberView.as_view(), name="team_invite"),
    path(
        "team/<int:membership_id>/role/",
        views.UpdateMemberRoleView.as_view(),
        name="team_update_role",
    ),
    path(
        "team/<int:membership_id>/remove/",
        views.RemoveMemberView.as_view(),
        name="team_remove",
    ),
    path("organizations/", views.OrganizationListView.as_view(), name="organization_list"),
    path("organizations/new/", views.OrganizationCreateView.as_view(), name="organization_create"),
    path("organizations/<int:org_id>/team/", views.TeamView.as_view(), name="team"),
    path(
        "organizations/<int:org_id>/team/invite/",
        views.InviteMemberView.as_view(),
        name="team_invite",
    ),
    path(
        "organizations/<int:org_id>/team/<int:membership_id>/role/",
        views.UpdateMemberRoleView.as_view(),
        name="team_update_role",
    ),
    path(
        "organizations/<int:org_id>/team/<int:membership_id>/remove/",
        views.RemoveMemberView.as_view(),
        name="team_remove",
    ),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path(
        "profile/password/",
        views.ChangePasswordView.as_view(template_name="accounts/password_change.html"),
        name="password_change",
    ),
    path("users/", views.UserManagementListView.as_view(), name="user_management"),
    path(
        "users/<int:user_id>/toggle-active/",
        views.ToggleUserActiveView.as_view(),
        name="user_toggle_active",
    ),
]
