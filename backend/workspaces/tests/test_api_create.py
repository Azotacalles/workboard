from django.db import IntegrityError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
import pytest
from rest_framework.test import APIClient

from workspaces import views as workspace_views
from workspaces.models import Workspace, Membership


@pytest.mark.django_db
@pytest.mark.parametrize(('name', 'expected'), [
    pytest.param('  Команда  A  ', 'Команда  A', id='trim-and-keep-inner-spaces'),
    pytest.param('Я', 'Я', id='minimum-length'),
    pytest.param('Я' * 100, 'Я' * 100, id='maximum-length'),
    pytest.param('  ' + 'Я' * 100 + '  ', 'Я' * 100, id='maximum-after-trim'),
])
def test_workspace_list_create_view_post(user_factory, logged_in_client, name, expected):
    # Реальная сессия и свежий CSRF после login, без принудительной аутентификации.
    user = user_factory()
    client, token = logged_in_client(user)
    before = timezone.now()

    response = client.post('/api/v1/workspaces/', {'name': name},
                           format='json', HTTP_X_CSRFTOKEN=token)

    assert response.status_code == 201, response.content
    data = response.json()
    assert set(data) == {'id', 'name', 'created_at'}
    assert data['name'] == expected
    workspace = Workspace.objects.get(pk=data['id'])
    assert workspace.name == expected
    assert before <= workspace.created_at <= timezone.now()
    assert parse_datetime(data['created_at']) == workspace.created_at
    assert Workspace.objects.count() == 1
    assert Membership.objects.count() == 1
    membership = Membership.objects.get(workspace=workspace)
    assert membership.user_id == user.pk
    assert membership.role == Membership.Role.OWNER
    assert workspace.created_at <= membership.joined_at <= timezone.now()


@pytest.mark.django_db
def test_workspace_post_allows_duplicate_names(user_factory, logged_in_client):
    user = user_factory()
    client, token = logged_in_client(user)
    created_ids = []

    for _ in range(2):
        response = client.post('/api/v1/workspaces/', {'name': 'Команда'},
                               format='json', HTTP_X_CSRFTOKEN=token)
        assert response.status_code == 201, response.content
        created_ids.append(response.json()['id'])

    assert len(set(created_ids)) == 2
    assert Workspace.objects.count() == 2
    assert list(Workspace.objects.values_list('name', flat=True)) == ['Команда', 'Команда']
    assert set(Membership.objects.values_list('workspace_id', 'user_id', 'role')) == {
        (workspace_id, user.pk, Membership.Role.OWNER) for workspace_id in created_ids
    }
    assert Membership.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize('payload', [
    pytest.param({}, id='missing'),
    pytest.param({'name': ''}, id='empty'),
    pytest.param({'name': '   '}, id='spaces'),
    pytest.param({'name': '\t\n'}, id='whitespace'),
    pytest.param({'name': None}, id='null'),
    pytest.param({'name': 'Я' * 101}, id='too-long'),
])
def test_workspace_post_invalid_name_creates_nothing(user_factory, logged_in_client, payload):
    user = user_factory()
    client, token = logged_in_client(user)

    response = client.post('/api/v1/workspaces/', payload,
                           format='json', HTTP_X_CSRFTOKEN=token)

    assert response.status_code == 400, response.content
    assert set(response.json()) == {'name'}
    assert response.json()['name']
    assert Workspace.objects.count() == 0
    assert Membership.objects.count() == 0


@pytest.mark.django_db
def test_workspace_post_ignores_forged_owner_user_and_role(user_factory, logged_in_client):
    user = user_factory()
    other_user = user_factory(email='other@example.com')
    client, token = logged_in_client(user)

    response = client.post('/api/v1/workspaces/', {
        'name': 'Команда',
        'owner_id': other_user.pk,
        'user_id': other_user.pk,
        'owner': other_user.pk,
        'user': other_user.pk,
        'role': 'ADMIN',
        'id': 999999,
        'created_at': '2000-01-01T00:00:00Z',
    }, format='json', HTTP_X_CSRFTOKEN=token)

    assert response.status_code == 201, response.content
    data = response.json()
    assert set(data) == {'id', 'name', 'created_at'}
    workspace = Workspace.objects.get(pk=data['id'])
    assert workspace.name == 'Команда'
    assert workspace.pk != 999999
    assert workspace.created_at.year != 2000
    assert Workspace.objects.count() == 1
    assert Membership.objects.count() == 1
    membership = Membership.objects.get(workspace=workspace)
    assert membership.user_id == user.pk
    assert membership.role == Membership.Role.OWNER
    assert not other_user.workspace_memberships.exists()


@pytest.mark.django_db
@pytest.mark.parametrize('csrf_header', [None, 'a' * 64], ids=['missing', 'incorrect'])
def test_workspace_post_requires_csrf(user_factory, logged_in_client, csrf_header):
    user = user_factory()
    client, _ = logged_in_client(user)
    headers = {} if csrf_header is None else {'HTTP_X_CSRFTOKEN': csrf_header}

    response = client.post('/api/v1/workspaces/', {'name': 'Команда'},
                           format='json', **headers)

    assert response.status_code == 403, response.content
    assert 'detail' in response.json()
    assert Workspace.objects.count() == 0
    assert Membership.objects.count() == 0


@pytest.mark.django_db
def test_workspace_post_requires_session():
    client = APIClient(enforce_csrf_checks=True)
    # Даже наличие CSRF-токена не заменяет действующую сессию.
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']

    response = client.post('/api/v1/workspaces/', {'name': 'Команда'},
                           format='json', HTTP_X_CSRFTOKEN=token)

    assert response.status_code == 403, response.content
    assert 'detail' in response.json()
    assert Workspace.objects.count() == 0
    assert Membership.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_workspace_post_rolls_back_when_membership_creation_fails(
        user_factory, logged_in_client, monkeypatch):
    # Без внешней тестовой транзакции: откат обязан обеспечить сам обработчик.
    user = user_factory()
    client, token = logged_in_client(user)
    existing = Workspace.objects.create(name='Существующее пространство')
    existing_membership = Membership.objects.create(
        workspace=existing, user=user, role=Membership.Role.OWNER,
    )
    attempted_ids = []

    def fail_membership_create(**kwargs):
        workspace = kwargs['workspace']
        # Сбой действительно происходит после записи Workspace, а не вместо всей view.
        assert Workspace.objects.filter(pk=workspace.pk, name='Новое пространство').exists()
        assert Workspace.objects.count() == 2
        assert kwargs['user'].pk == user.pk
        assert kwargs['role'] == Membership.Role.OWNER
        attempted_ids.append(workspace.pk)
        raise IntegrityError('stage37 membership creation failure')

    monkeypatch.setattr(workspace_views.Membership.objects, 'create', fail_membership_create)

    with pytest.raises(IntegrityError, match='stage37 membership creation failure'):
        client.post('/api/v1/workspaces/', {'name': 'Новое пространство'},
                    format='json', HTTP_X_CSRFTOKEN=token)

    assert len(attempted_ids) == 1
    assert not Workspace.objects.filter(pk=attempted_ids[0]).exists()
    assert list(Workspace.objects.values_list('pk', flat=True)) == [existing.pk]
    assert list(Membership.objects.values_list('pk', flat=True)) == [existing_membership.pk]
