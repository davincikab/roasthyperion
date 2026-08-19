from django.db import models

from apps.accounts.models import User
from apps.core.models import TrackingModel
from apps.projects.models import Project


class Annotation(TrackingModel):
    class Kind(models.TextChoices):
        POINT = "point", "Point"
        LINE = "line", "Line"
        POLYGON = "polygon", "Polygon"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="annotations")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.POINT)

    # Point annotations use lat/lng. Line and polygon annotations use path (a
    # list of [lat, lng] pairs) instead — kept as separate fields rather than
    # folding everything into `path` so existing point annotations/queries
    # stay simple.
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    path = models.JSONField(null=True, blank=True)

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    def __str__(self):
        return self.title
