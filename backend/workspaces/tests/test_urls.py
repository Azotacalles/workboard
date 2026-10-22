from django.urls import Resolver404, resolve
from django.urls import resolve, reverse
import pytest

from workspaces.views import WorkspaceDetailView, WorkspaceListCreateView


@pytest.mark.parametrize(
    ('url', 'url_name', 'view', 'kwargs'),
    [
        ('/api/v1/workspaces/', 'workspaces:workspace_list', WorkspaceListCreateView, {}),
        ('/api/v1/workspaces/42/', 'workspaces:workspace_detail', WorkspaceDetailView, {'pk': 42}),
    ],
)
def test_workspace_routes(url, url_name, view, kwargs):
    match = resolve(url)

    assert match.func.view_class is view
    assert match.kwargs == kwargs
    assert reverse(url_name, kwargs=kwargs) == url


@pytest.mark.parametrize('url', [
    '/api/v1/workspaces/abc/',
    '/api/v1/workspaces/-1/',
    '/api/v1/workspaces/workspaces/',
])
def test_workspace_routes_reject_invalid_paths(url):
    with pytest.raises(Resolver404):
        resolve(url)
