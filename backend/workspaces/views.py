from django.db import transaction
from rest_framework import permissions, authentication, status
from rest_framework.response import Response
from rest_framework.views import APIView

from workspaces.models import Workspace, Membership
from workspaces.serializers import WorkspaceCreateSerializer, WorkspaceSerializer


# Create your views here.
class WorkspaceListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication]

    def get(self, request):
        pass

    def post(self, request):
        serializer = WorkspaceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data['name']
        user = request.user
        with transaction.atomic():
            workspace = Workspace.objects.create(name=name)
            Membership.objects. create(user=user, workspace=workspace, role=Membership.Role.OWNER)
        serializer_out = WorkspaceSerializer(workspace)
        return Response(serializer_out.data, status=status.HTTP_201_CREATED)


class WorkspaceDetailView(APIView):
    def get(self, request):
        pass