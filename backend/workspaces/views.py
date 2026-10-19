from django.shortcuts import render
from rest_framework import permissions, authentication
from rest_framework.views import APIView


# Create your views here.
class WorkspaceListCreateView(APIView):
    def get(self, request):
        pass

    def post(self, request):
        permission_classes = [permissions.IsAuthenticated]
        authentication_classes = [authentication.SessionAuthentication]


class WorkspaceDetailView(APIView):
    def get(self, request):
        pass