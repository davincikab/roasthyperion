from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "status", "created_at")
    list_filter = ("status", "organization")
    search_fields = ("name",)
    readonly_fields = ("tiles_version", "ingest_error")
