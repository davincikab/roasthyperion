from django.urls import path

from . import views

app_name = "annotations"

urlpatterns = [
    path(
        "projects/<int:project_id>/annotations/",
        views.AnnotationListCreateView.as_view(),
        name="list_create",
    ),
    path(
        "projects/<int:project_id>/annotations/<int:annotation_id>/",
        views.AnnotationDetailView.as_view(),
        name="detail",
    ),
]
