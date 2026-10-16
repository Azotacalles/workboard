from django.urls import path

from workspaces.views import WorkspaceListCreateView, WorkspaceDetailView

app_name = 'workspaces'

urlpatterns = [
    path('list/', WorkspaceListCreateView.as_view(), name='workspace_list'),
    path('<int:pk>/', WorkspaceDetailView.as_view(), name='workspace_detail'),
]