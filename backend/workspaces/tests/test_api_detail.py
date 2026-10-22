from django.utils.dateparse import parse_datetime
import pytest
from rest_framework.test import APIClient

from workspaces.models import Membership
from workspaces.models import Workspace


@pytest.mark.django_db
@pytest.mark.parametrize(('user_key', 'workspace_key'), [
    ('a', 'x'), ('b', 'y'), ('a', 'z'), ('b', 'z'),
])
def test_workspace_detail_returns_member_workspace(
        workspace_list_data, logged_in_client, user_key, workspace_key):
    users, workspaces = workspace_list_data
    workspace = workspaces[workspace_key]
    client, _ = logged_in_client(users[user_key])

    response = client.get(f'/api/v1/workspaces/{workspace.pk}/')

    assert response.status_code == 200, response.content
    data = response.json()
    assert set(data) == {'id', 'name', 'created_at'}
    assert data['id'] == workspace.pk
    assert data['name'] == workspace.name
    assert parse_datetime(data['created_at']) == workspace.created_at

    # Представление detail совпадает с соответствующим элементом списка.
    list_response = client.get('/api/v1/workspaces/')
    assert list_response.status_code == 200, list_response.content
    assert data == next(item for item in list_response.json() if item['id'] == workspace.pk)


@pytest.mark.django_db
@pytest.mark.parametrize('is_superuser', [False, True], ids=['ordinary-user', 'superuser'])
def test_workspace_detail_hides_foreign_and_missing_objects(
        workspace_list_data, user_factory, logged_in_client, is_superuser):
    users, workspaces = workspace_list_data
    user = users['a']
    if is_superuser:
        user = user_factory(email='admin@example.com', is_superuser=True, is_staff=True)
    client, _ = logged_in_client(user)
    foreign_workspace = workspaces['y']
    missing_pk = max(workspace.pk for workspace in workspaces.values()) + 1

    foreign = client.get(f'/api/v1/workspaces/{foreign_workspace.pk}/')
    missing = client.get(f'/api/v1/workspaces/{missing_pk}/')

    assert foreign.status_code == 404, foreign.content
    assert missing.status_code == 404, missing.content
    assert foreign.content == missing.content
    assert set(foreign.json()) == {'detail'}
    assert foreign_workspace.name not in str(foreign.json())

    # Подставленный id настоящего участника не меняет права пользователя сессии.
    forged = client.get(f'/api/v1/workspaces/{foreign_workspace.pk}/', {
        'user_id': users['b'].pk,
        'owner_id': users['b'].pk,
    })
    assert forged.status_code == 404, forged.content
    assert forged.content == missing.content


@pytest.mark.django_db
def test_workspace_detail_requires_session_before_object_lookup():
    workspace = Workspace.objects.create(name='Приватное пространство')
    client = APIClient(enforce_csrf_checks=True)

    existing = client.get(f'/api/v1/workspaces/{workspace.pk}/')
    missing = client.get(f'/api/v1/workspaces/{workspace.pk + 1}/')

    assert existing.status_code == 403, existing.content
    assert missing.status_code == 403, missing.content
    assert existing.content == missing.content
    assert set(existing.json()) == {'detail'}
    assert workspace.name not in str(existing.json())


@pytest.mark.django_db
def test_workspace_detail_does_not_reuse_other_users_access(workspace_list_data, logged_in_client):
    users, workspaces = workspace_list_data
    client_a, _ = logged_in_client(users['a'])
    client_b, _ = logged_in_client(users['b'])
    url = f'/api/v1/workspaces/{workspaces["x"].pk}/'

    first = client_a.get(url)
    assert first.status_code == 200, first.content
    assert first.json()['id'] == workspaces['x'].pk

    foreign = client_b.get(url)
    assert foreign.status_code == 404, foreign.content

    repeated = client_a.get(url)
    assert repeated.status_code == 200, repeated.content
    assert repeated.json() == first.json()


@pytest.mark.django_db
def test_workspace_detail_uses_current_memberships(workspace_list_data, logged_in_client):
    users, workspaces = workspace_list_data
    user = users['a']
    workspace = workspaces['z']
    client, _ = logged_in_client(user)
    url = f'/api/v1/workspaces/{workspace.pk}/'
    before = client.get(url)
    assert before.status_code == 200, before.content
    assert before.json()['id'] == workspace.pk

    # Workspace и membership второго пользователя остаются; отзывается только доступ A.
    Membership.objects.get(workspace=workspace, user=user).delete()
    revoked = client.get(url)
    missing_pk = max(item.pk for item in workspaces.values()) + 1
    missing = client.get(f'/api/v1/workspaces/{missing_pk}/')

    assert revoked.status_code == 404, revoked.content
    assert missing.status_code == 404, missing.content
    assert revoked.content == missing.content
    assert workspace.memberships.filter(user=users['b']).exists()

    # Новая связь восстанавливает доступ без повторного входа в ту же сессию.
    Membership.objects.create(workspace=workspace, user=user, role=Membership.Role.OWNER)
    restored = client.get(url)
    assert restored.status_code == 200, restored.content
    assert restored.json() == before.json()
