from rest_framework import serializers

from workspaces.models import Workspace


class WorkspaceCreateSerializer(serializers.Serializer):
    name = serializers.CharField(required=True, trim_whitespace=False, allow_blank=False, max_length=100)


class WorkspaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ('id', 'name', 'created_at')