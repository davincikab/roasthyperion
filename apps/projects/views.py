from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from apps.accounts.models import Membership
from apps.accounts.permissions import RoleRequiredMixin, has_role
from apps.accounts.services import get_active_organization

from .ingestion import IngestError, list_pending_files, run_ingestion
from .models import Project

PROJECT_FIELDS = ("name", "description", "center_lat", "center_lng", "min_zoom", "max_zoom", "tms_scheme")


class ProjectListView(RoleRequiredMixin, ListView):
    model = Project
    template_name = "projects/list.html"
    context_object_name = "projects"
    required_roles = ()  # any membership (viewer or above)
    paginate_by = 12

    def get_organization(self):
        return get_active_organization(self.request.user)

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Project.objects.select_related("organization").order_by("-created_at")
        return Project.objects.filter(organization=self.get_organization()).order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        can_edit = organization is not None and has_role(
            self.request.user, organization, Membership.Role.EDITOR, Membership.Role.ADMIN
        )
        context["can_create"] = can_edit
        context["can_edit"] = can_edit
        context["show_organization"] = self.request.user.is_superuser
        if can_edit:
            for project in context["projects"]:
                project.pending_files = list_pending_files(project)
        return context


class ProjectCreateView(RoleRequiredMixin, CreateView):
    model = Project
    fields = ("name", "description")
    template_name = "projects/create.html"
    required_roles = (Membership.Role.EDITOR, Membership.Role.ADMIN)

    def get_organization(self):
        return get_active_organization(self.request.user)

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("projects:detail", args=[self.object.pk])


class ProjectUpdateView(RoleRequiredMixin, UpdateView):
    model = Project
    fields = PROJECT_FIELDS
    template_name = "projects/edit.html"
    required_roles = (Membership.Role.EDITOR, Membership.Role.ADMIN)

    def get_organization(self):
        self._project = get_object_or_404(Project, pk=self.kwargs["pk"])
        return self._project.organization

    def get_object(self, queryset=None):
        return self._project

    def get_success_url(self):
        return reverse("projects:detail", args=[self.object.pk])


class ProjectDetailView(RoleRequiredMixin, DetailView):
    model = Project
    template_name = "projects/detail.html"
    context_object_name = "project"
    required_roles = ()  # any membership

    def get_organization(self):
        self._project = get_object_or_404(Project, pk=self.kwargs["pk"])
        return self._project.organization

    def get_object(self, queryset=None):
        return self._project

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self._project.organization
        context["can_edit"] = has_role(
            self.request.user, organization, Membership.Role.EDITOR, Membership.Role.ADMIN
        )
        return context


class IngestView(RoleRequiredMixin, View):
    required_roles = (Membership.Role.EDITOR, Membership.Role.ADMIN)

    def get_organization(self):
        self._project = get_object_or_404(Project, pk=self.kwargs["pk"])
        return self._project.organization

    def post(self, request, pk):
        filename = request.POST.get("filename")
        project = self._project
        project.status = Project.Status.PROCESSING
        project.ingest_error = ""
        project.save(update_fields=["status", "ingest_error"])

        try:
            run_ingestion(project, filename)
        except IngestError as exc:
            project.status = Project.Status.FAILED
            project.ingest_error = str(exc)
            project.save(update_fields=["status", "ingest_error"])

        return redirect(reverse("projects:detail", args=[pk]))


@require_GET
def tile_view(request, pk, z, x, y):
    project = get_object_or_404(Project, pk=pk)
    if not has_role(request.user, project.organization):
        raise PermissionDenied
    if project.status != Project.Status.READY:
        return HttpResponse(status=404)

    tile_path = project.tiles_dir / str(z) / str(x) / f"{y}.png"
    try:
        tile_path = tile_path.resolve()
        if project.tiles_dir.resolve() not in tile_path.parents or not tile_path.is_file():
            raise Http404
    except (OSError, RuntimeError) as exc:
        raise Http404 from exc

    response = HttpResponse(tile_path.read_bytes(), content_type="image/png")
    response["Cache-Control"] = "public, max-age=86400"
    return response
