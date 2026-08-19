from django.shortcuts import get_object_or_404
from rest_framework import generics

from apps.projects.models import Project

from .models import Annotation
from .permissions import IsOrganizationMember
from .serializers import AnnotationSerializer


class ProjectScopedMixin:
    def get_project(self):
        if not hasattr(self, "_project"):
            self._project = get_object_or_404(Project, pk=self.kwargs["project_id"])
        return self._project


class AnnotationListCreateView(ProjectScopedMixin, generics.ListCreateAPIView):
    serializer_class = AnnotationSerializer
    permission_classes = [IsOrganizationMember]

    def get_queryset(self):
        return Annotation.objects.filter(project=self.get_project()).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(project=self.get_project(), created_by=self.request.user)


class AnnotationDetailView(ProjectScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AnnotationSerializer
    permission_classes = [IsOrganizationMember]
    lookup_url_kwarg = "annotation_id"

    def get_queryset(self):
        return Annotation.objects.filter(project=self.get_project())
