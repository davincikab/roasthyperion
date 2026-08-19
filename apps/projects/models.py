from django.conf import settings
from django.db import models

from apps.accounts.models import Organization, User
from apps.core.models import TrackingModel


class Project(TrackingModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting upload"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="projects"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    # Tiles themselves live on disk at `tiles_dir`, not in a Django FileField —
    # they're a directory of thousands of small files (a QGIS/gdal2tiles XYZ
    # pyramid), not a single manageable file.
    tiles_version = models.CharField(max_length=32, blank=True)
    tms_scheme = models.BooleanField(
        default=False,
        help_text="Enable if the uploaded tiles use TMS (y-flipped) ordering instead of XYZ.",
    )

    center_lat = models.FloatField(null=True, blank=True)
    center_lng = models.FloatField(null=True, blank=True)
    min_zoom = models.PositiveSmallIntegerField(default=0)
    max_zoom = models.PositiveSmallIntegerField(default=22)

    ingest_error = models.TextField(blank=True)

    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    def __str__(self):
        return self.name

    @property
    def landing_dir(self):
        return settings.FTP_LANDING_ROOT / f"org_{self.organization_id}" / f"project_{self.pk}"

    @property
    def tiles_dir(self):
        return settings.MEDIA_ROOT / "tiles" / f"org_{self.organization_id}" / f"project_{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.landing_dir.mkdir(parents=True, exist_ok=True)
