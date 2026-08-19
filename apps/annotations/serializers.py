from rest_framework import serializers

from .models import Annotation


class AnnotationSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Annotation
        fields = [
            "id",
            "kind",
            "lat",
            "lng",
            "path",
            "title",
            "description",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def validate(self, data):
        kind = data.get("kind", getattr(self.instance, "kind", Annotation.Kind.POINT))

        if kind == Annotation.Kind.POINT:
            lat = data.get("lat", getattr(self.instance, "lat", None))
            lng = data.get("lng", getattr(self.instance, "lng", None))
            if lat is None or lng is None:
                raise serializers.ValidationError("Point annotations require lat and lng.")
        elif kind in (Annotation.Kind.LINE, Annotation.Kind.POLYGON):
            path = data.get("path", getattr(self.instance, "path", None))
            min_points = 2 if kind == Annotation.Kind.LINE else 3
            if not path or len(path) < min_points:
                raise serializers.ValidationError(
                    f"{kind.capitalize()} annotations require a path with at least {min_points} points."
                )
            for point in path:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    raise serializers.ValidationError("Each path point must be a [lat, lng] pair.")

        return data
