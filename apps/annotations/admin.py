from django.contrib import admin

from .models import Annotation


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "project", "lat", "lng", "created_by", "created_at")
    list_filter = ("kind", "project")
    search_fields = ("title",)
