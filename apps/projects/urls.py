from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="list"),
    path("new/", views.ProjectCreateView.as_view(), name="create"),
    path("<int:pk>/", views.ProjectDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.ProjectUpdateView.as_view(), name="edit"),
    path("<int:pk>/ingest/", views.IngestView.as_view(), name="ingest"),
    path("<int:pk>/tiles/<int:z>/<int:x>/<int:y>.png", views.tile_view, name="tile"),
]
