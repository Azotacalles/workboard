from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime
import pytest
from rest_framework.test import APIClient

from workspaces.models import Membership
from workspaces.models import Workspace
from workspaces.models import Workspace, Membership


@pytest.mark.django_db
@pytest.mark.parametrize(('user_key', 'private_key'), [('a', 'x'), ('b', 'y')])
def test_workspace_get_not_empty_list(workspace_list_data, logged_in_client, user_key, private_key):
    users, workspaces = workspace_list_data
    client, _ = logged_in_client(users[user_key])

    response = client.get('/api/v1/workspaces/')

    assert response.status_code == 200, response.content
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    expected = {workspaces[private_key].pk: workspaces[private_key], workspaces['z'].pk: workspaces['z']}
    assert {item['id'] for item in data} == set(expected)
    assert sum(item['id'] == workspaces['z'].pk for item in data) == 1
    for item in data:
        # Ни membership, ни пользователь/email не должны попадать в ответ.
        assert set(item) == {'id', 'name', 'created_at'}
        assert item['name'] == expected[item['id']].name
        assert parse_datetime(item['created_at']) == expected[item['id']].created_at


@pytest.mark.django_db
def test_workspace_get_empty_list(workspace_list_data, logged_in_client):
    users, _ = workspace_list_data
    client, _ = logged_in_client(users['c'])

    response = client.get('/api/v1/workspaces/')

    assert response.status_code == 200, response.content
    # В БД есть чужие пространства, но C получает именно пустой массив, не объект.
    assert Workspace.objects.count() == 3
    assert response.json() == []


@pytest.mark.django_db
def test_workspace_get_orders_by_date_then_id(user_factory, logged_in_client):
    user = user_factory()
    client, _ = logged_in_client(user)
    newest = Workspace.objects.create(name='Новое с меньшим id')
    older_low_id = Workspace.objects.create(name='Старое с меньшим id')
    older_high_id = Workspace.objects.create(name='Старое с большим id')
    for workspace in (newest, older_low_id, older_high_id):
        Membership.objects.create(workspace=workspace, user=user, role=Membership.Role.OWNER)
    now = timezone.now()
    Workspace.objects.filter(pk=newest.pk).update(created_at=now)
    Workspace.objects.filter(pk__in=[older_low_id.pk, older_high_id.pk]).update(
        created_at=now - timedelta(days=1),
    )

    response = client.get('/api/v1/workspaces/')

    assert response.status_code == 200, response.content
    assert [item['id'] for item in response.json()] == [
        newest.pk, older_high_id.pk, older_low_id.pk,
    ]


@pytest.mark.django_db
def test_workspace_get_requires_session():
    Workspace.objects.create(name='Приватное пространство')
    client = APIClient(enforce_csrf_checks=True)

    response = client.get('/api/v1/workspaces/')

    assert response.status_code == 403, response.content
    assert set(response.json()) == {'detail'}


@pytest.mark.django_db
def test_workspace_get_superuser_also_needs_membership(
        user_factory, logged_in_client, workspace_list_data):
    _, workspaces = workspace_list_data
    admin = user_factory(email='admin@example.com', is_superuser=True, is_staff=True)
    client, _ = logged_in_client(admin)

    response = client.get('/api/v1/workspaces/')

    assert response.status_code == 200, response.content
    assert response.json() == []

    Membership.objects.create(workspace=workspaces['z'], user=admin, role=Membership.Role.OWNER)
    response = client.get('/api/v1/workspaces/')

    assert response.status_code == 200, response.content
    assert [item['id'] for item in response.json()] == [workspaces['z'].pk]


@pytest.mark.django_db
def test_workspace_get_uses_current_memberships(workspace_list_data, logged_in_client):
    users, workspaces = workspace_list_data
    client, _ = logged_in_client(users['a'])
    response = client.get('/api/v1/workspaces/')
    assert response.status_code == 200, response.content
    assert {item['id'] for item in response.json()} == {workspaces['x'].pk, workspaces['z'].pk}

    # Сессия та же: доступ должен измениться сразу после удаления связи.
    Membership.objects.get(workspace=workspaces['z'], user=users['a']).delete()
    response = client.get('/api/v1/workspaces/')

    assert response.status_code == 200, response.content
    assert [item['id'] for item in response.json()] == [workspaces['x'].pk]
    assert workspaces['z'].memberships.filter(user=users['b']).exists()
