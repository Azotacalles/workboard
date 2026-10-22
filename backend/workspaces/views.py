from django.db import transaction
from django.shortcuts import get_object_or_404
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
        qs = Workspace.objects.filter(memberships__user=request.user)
        serializer = WorkspaceSerializer(qs, many=True)
        return Response(serializer.data if serializer.data else [], status=status.HTTP_200_OK)

    def post(self, request):
        serializer = WorkspaceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data['name']
        user = request.user
        with transaction.atomic():
            workspace = Workspace.objects.create(name=name)
            Membership.objects.create(user=user, workspace=workspace, role=Membership.Role.OWNER)
        serializer_out = WorkspaceSerializer(workspace)
        return Response(serializer_out.data, status=status.HTTP_201_CREATED)


class WorkspaceDetailView(APIView):
    def get(self, request, pk):
        qs = Workspace.objects.filter(memberships__user=request.user)
        workspace = get_object_or_404(qs, pk=pk)
        serializer = WorkspaceSerializer(workspace)
        return Response(serializer.data, status=status.HTTP_200_OK)