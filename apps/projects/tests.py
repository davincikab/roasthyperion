import tempfile
import zipfile
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import Membership, Organization, User

from .ingestion import IngestError, run_ingestion
from .models import Project
from .testing import write_sample_tile_zip, write_tile


class ProjectTestCase(TestCase):
    """Base class that isolates FTP_LANDING_ROOT/MEDIA_ROOT to a temp dir."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.override = override_settings(
            FTP_LANDING_ROOT=Path(self.tmp_dir.name) / "ftp_landing",
            MEDIA_ROOT=Path(self.tmp_dir.name) / "media",
        )
        self.override.enable()
        self.addCleanup(self.override.disable)

        self.org = Organization.objects.create(name="Acme", slug="acme")
        self.project = Project.objects.create(organization=self.org, name="North Field")


class RunIngestionTests(ProjectTestCase):
    def test_valid_zip_ingests_successfully(self):
        self.project.landing_dir.mkdir(parents=True, exist_ok=True)
        write_sample_tile_zip(self.project.landing_dir / "tiles.zip")

        run_ingestion(self.project, "tiles.zip")

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.READY)
        self.assertTrue(self.project.tiles_version)
        self.assertTrue((self.project.tiles_dir / "14" / "0" / "0.png").is_file())
        self.assertFalse((self.project.landing_dir / "tiles.zip").exists())
        self.assertTrue((self.project.landing_dir / "archive" / "tiles.zip").exists())

    def test_zip_with_wrapper_folder_is_handled(self):
        self.project.landing_dir.mkdir(parents=True, exist_ok=True)
        zip_path = self.project.landing_dir / "tiles.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("my_export/14/0/0.png", b"fake-png-bytes")

        run_ingestion(self.project, "tiles.zip")

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.READY)
        self.assertTrue((self.project.tiles_dir / "14" / "0" / "0.png").is_file())

    def test_missing_file_raises(self):
        with self.assertRaises(IngestError):
            run_ingestion(self.project, "does-not-exist.zip")

    def test_non_zip_file_raises(self):
        self.project.landing_dir.mkdir(parents=True, exist_ok=True)
        (self.project.landing_dir / "not-a-zip.zip").write_text("hello")

        with self.assertRaises(IngestError):
            run_ingestion(self.project, "not-a-zip.zip")

    def test_zip_without_zoom_folders_raises(self):
        self.project.landing_dir.mkdir(parents=True, exist_ok=True)
        zip_path = self.project.landing_dir / "tiles.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", "not a tile pyramid")

        with self.assertRaises(IngestError):
            run_ingestion(self.project, "tiles.zip")

    def test_path_traversal_filename_is_rejected(self):
        with self.assertRaises(IngestError):
            run_ingestion(self.project, "../../etc/passwd")

    def test_zip_slip_entry_is_rejected(self):
        self.project.landing_dir.mkdir(parents=True, exist_ok=True)
        zip_path = self.project.landing_dir / "tiles.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../evil.png", b"fake-png-bytes")

        with self.assertRaises(IngestError):
            run_ingestion(self.project, "tiles.zip")


class IngestViewTests(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.editor = User.objects.create_user(email="editor@example.com", password="pw")
        Membership.objects.create(user=self.editor, organization=self.org, role=Membership.Role.EDITOR)

    def test_editor_can_ingest_via_view(self):
        self.project.landing_dir.mkdir(parents=True, exist_ok=True)
        write_sample_tile_zip(self.project.landing_dir / "tiles.zip")

        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("projects:ingest", args=[self.project.id]), {"filename": "tiles.zip"}
        )
        self.assertRedirects(response, reverse("projects:detail", args=[self.project.id]))

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.READY)

    def test_bad_filename_marks_project_failed(self):
        self.client.force_login(self.editor)
        self.client.post(
            reverse("projects:ingest", args=[self.project.id]), {"filename": "missing.zip"}
        )

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.FAILED)
        self.assertTrue(self.project.ingest_error)


class TileViewTests(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.viewer = User.objects.create_user(email="viewer@example.com", password="pw")
        Membership.objects.create(user=self.viewer, organization=self.org, role=Membership.Role.VIEWER)
        self.outsider = User.objects.create_user(email="outsider@example.com", password="pw")

        self.project.status = Project.Status.READY
        self.project.save(update_fields=["status"])
        write_tile(self.project.tiles_dir, 14, 0, 0)

    def test_member_can_fetch_existing_tile(self):
        self.client.force_login(self.viewer)
        url = reverse("projects:tile", args=[self.project.id, 14, 0, 0])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")

    def test_missing_tile_returns_404(self):
        self.client.force_login(self.viewer)
        url = reverse("projects:tile", args=[self.project.id, 14, 99, 99])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_non_member_is_forbidden(self):
        self.client.force_login(self.outsider)
        url = reverse("projects:tile", args=[self.project.id, 14, 0, 0])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_not_ready_project_returns_404(self):
        self.project.status = Project.Status.PENDING
        self.project.save(update_fields=["status"])
        self.client.force_login(self.viewer)
        url = reverse("projects:tile", args=[self.project.id, 14, 0, 0])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
