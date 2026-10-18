from rest_framework import serializers

from workspaces.models import Workspace


class WorkspaceCreateSerializer(serializers.Serializer):
    name = serializers.CharField(required=True, trim_whitespace=False, allow_blank=False, max_length=100)

    def validate_name(self, value):
        if not value or len(value) == 0:
            raise serializers.ValidationError("Name cannot be an empty string")


class WorkspaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ('id', 'name', 'created_at')