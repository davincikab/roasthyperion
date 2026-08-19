from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Membership, Organization, User
from apps.projects.models import Project

from .models import Annotation


class AnnotationApiTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Acme", slug="acme")
        self.project = Project.objects.create(organization=self.org, name="North Field")

        self.viewer = User.objects.create_user(email="viewer@example.com", password="pw")
        Membership.objects.create(user=self.viewer, organization=self.org, role=Membership.Role.VIEWER)

        self.editor = User.objects.create_user(email="editor@example.com", password="pw")
        Membership.objects.create(user=self.editor, organization=self.org, role=Membership.Role.EDITOR)

        self.outsider = User.objects.create_user(email="outsider@example.com", password="pw")

        self.list_url = reverse("annotations:list_create", args=[self.project.id])

    def test_viewer_can_list_but_not_create(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.list_url).status_code, 200)

        response = self.client.post(
            self.list_url,
            {"lat": 35.1, "lng": -101.96, "title": "Septic tank"},
        )
        self.assertEqual(response.status_code, 403)

    def test_editor_can_create_and_it_records_creator(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            self.list_url,
            {"lat": 35.1, "lng": -101.96, "title": "Septic tank"},
        )
        self.assertEqual(response.status_code, 201)
        annotation = Annotation.objects.get()
        self.assertEqual(annotation.created_by, self.editor)
        self.assertEqual(annotation.project, self.project)

    def test_outsider_is_forbidden(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)

    def test_editor_can_create_line_annotation(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            self.list_url,
            {
                "kind": "line",
                "path": [[35.1, -101.96], [35.11, -101.95], [35.12, -101.94]],
                "title": "Fenceline",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        annotation = Annotation.objects.get()
        self.assertEqual(annotation.kind, Annotation.Kind.LINE)
        self.assertEqual(len(annotation.path), 3)

    def test_line_annotation_requires_at_least_two_points(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            self.list_url,
            {"kind": "line", "path": [[35.1, -101.96]], "title": "Too short"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_point_annotation_requires_lat_lng(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            self.list_url,
            {"kind": "point", "title": "Missing coordinates"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_editor_can_delete_viewer_cannot(self):
        annotation = Annotation.objects.create(
            project=self.project, lat=35.1, lng=-101.96, title="Septic tank"
        )
        detail_url = reverse("annotations:detail", args=[self.project.id, annotation.id])

        self.client.force_login(self.viewer)
        self.assertEqual(self.client.delete(detail_url).status_code, 403)

        self.client.force_login(self.editor)
        self.assertEqual(self.client.delete(detail_url).status_code, 204)
        self.assertFalse(Annotation.objects.filter(pk=annotation.pk).exists())
