from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient

from . import views as workspace_views
from .models import Workspace, Membership


@pytest.mark.django_db
def test_workspaces(db, user_factory):
    user = user_factory()
    before = timezone.now()
    workspace = Workspace.objects.create(name='workspace_1')
    membership = Membership.objects.create(workspace=workspace, user=user, role=Membership.Role.OWNER)
    workspace.refresh_from_db()
    membership.refresh_from_db()
    assert workspace.pk is not None
    assert workspace.name == 'workspace_1'
    assert str(workspace) == 'workspace_1'
    assert before <= workspace.created_at <= membership.joined_at <= timezone.now()
    assert timezone.is_aware(workspace.created_at)
    assert timezone.is_aware(membership.joined_at)
    assert membership.workspace_id == workspace.pk
    assert membership.user_id == user.pk
    assert membership.role == 'OWNER'
    assert workspace.memberships.count() == 1
    assert workspace.memberships.all()[0].user == user
    assert user.workspace_memberships.all()[0].workspace == workspace

@pytest.mark.django_db
def test_different_workspaces(db, user_factory):
    user = user_factory()
    workspace_1 = Workspace.objects.create(name='workspace')
    workspace_2 = Workspace.objects.create(name='workspace')
    Membership.objects.create(workspace=workspace_1, user=user, role=Membership.Role.OWNER)
    Membership.objects.create(workspace=workspace_2, user=user, role=Membership.Role.OWNER)
    memberships = user.workspace_memberships.all()
    assert memberships[0].workspace.name == memberships[1].workspace.name
    assert workspace_1.pk != workspace_2.pk
    assert set(memberships.values_list('workspace_id', flat=True)) == {
        workspace_1.pk, workspace_2.pk,
    }

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Membership.objects.create(workspace=workspace_2, user=user, role=Membership.Role.OWNER)

    # После отката дублирующей записи транзакция пригодна для дальнейших запросов.
    assert Membership.objects.filter(workspace=workspace_2, user=user).count() == 1
    assert user.workspace_memberships.count() == 2


@pytest.mark.django_db
def test_workspace_can_have_multiple_users(user_factory):
    user_a = user_factory()
    user_b = user_factory(email='second@example.com')
    workspace = Workspace.objects.create(name='Общее пространство')
    membership_a = Membership.objects.create(
        workspace=workspace, user=user_a, role=Membership.Role.OWNER,
    )
    membership_b = Membership.objects.create(
        workspace=workspace, user=user_b, role=Membership.Role.OWNER,
    )

    assert set(workspace.memberships.values_list('pk', 'user_id')) == {
        (membership_a.pk, user_a.pk), (membership_b.pk, user_b.pk),
    }
    assert list(user_a.workspace_memberships.values_list('pk', flat=True)) == [membership_a.pk]
    assert list(user_b.workspace_memberships.values_list('pk', flat=True)) == [membership_b.pk]


@pytest.mark.django_db
def test_same_workspace_names_do_not_mix_user_memberships(user_factory):
    user_a = user_factory()
    user_b = user_factory(email='second@example.com')
    workspace_a = Workspace.objects.create(name='Команда')
    workspace_b = Workspace.objects.create(name='Команда')
    Membership.objects.create(workspace=workspace_a, user=user_a, role=Membership.Role.OWNER)
    Membership.objects.create(workspace=workspace_b, user=user_b, role=Membership.Role.OWNER)

    # Это проверка связей ORM; проверка доступа HTTP появится в части Backend API.
    assert list(Workspace.objects.filter(memberships__user=user_a)) == [workspace_a]
    assert list(Workspace.objects.filter(memberships__user=user_b)) == [workspace_b]


@pytest.mark.django_db
@pytest.mark.parametrize('same_time', [False, True])
def test_workspace_ordering(same_time):
    lower_id = Workspace.objects.create(name='Первое')
    higher_id = Workspace.objects.create(name='Второе')
    now = timezone.now()
    Workspace.objects.filter(pk=lower_id.pk).update(created_at=now)
    Workspace.objects.filter(pk=higher_id.pk).update(
        created_at=now if same_time else now - timedelta(days=1),
    )

    expected = [higher_id.pk, lower_id.pk] if same_time else [lower_id.pk, higher_id.pk]
    assert list(Workspace.objects.values_list('pk', flat=True)) == expected


@pytest.mark.django_db
def test_creation_dates_do_not_change_on_save(user_factory):
    user = user_factory()
    workspace = Workspace.objects.create(name='До изменения')
    membership = Membership.objects.create(workspace=workspace, user=user, role=Membership.Role.OWNER)
    # Явно старые даты позволяют отличить auto_now_add от auto_now без ожидания.
    created_at = timezone.now() - timedelta(days=2)
    joined_at = created_at + timedelta(hours=1)
    Workspace.objects.filter(pk=workspace.pk).update(created_at=created_at)
    Membership.objects.filter(pk=membership.pk).update(joined_at=joined_at)
    workspace.refresh_from_db()
    membership.refresh_from_db()

    workspace.name = 'После изменения'
    workspace.save()
    membership.save()
    workspace.refresh_from_db()
    membership.refresh_from_db()

    assert workspace.name == 'После изменения'
    assert workspace.created_at == created_at
    assert membership.joined_at == joined_at


@pytest.mark.django_db
@pytest.mark.parametrize('delete_target', ['user', 'workspace'])
def test_cascade_deletes_only_related_memberships(user_factory, delete_target):
    user_a = user_factory()
    user_b = user_factory(email='second@example.com')
    workspace_a = Workspace.objects.create(name='A')
    workspace_b = Workspace.objects.create(name='B')
    for user in (user_a, user_b):
        for workspace in (workspace_a, workspace_b):
            Membership.objects.create(workspace=workspace, user=user, role=Membership.Role.OWNER)

    if delete_target == 'user':
        user_a.delete()
        assert Workspace.objects.count() == 2
        assert set(Membership.objects.values_list('user_id', 'workspace_id')) == {
            (user_b.pk, workspace_a.pk), (user_b.pk, workspace_b.pk),
        }
    else:
        workspace_a.delete()
        assert type(user_a).objects.count() == 2
        assert set(Membership.objects.values_list('user_id', 'workspace_id')) == {
            (user_a.pk, workspace_b.pk), (user_b.pk, workspace_b.pk),
        }


@pytest.mark.django_db
@pytest.mark.parametrize('name', ['', None, 'x' * 101])
def test_workspace_model_validation_rejects_invalid_name(name):
    workspace = Workspace(name=name)
    with pytest.raises(ValidationError) as error:
        workspace.full_clean()
    assert 'name' in error.value.message_dict
    assert Workspace.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize('name', ['Я', 'Я' * 100, 'Команда  A'])
def test_workspace_model_accepts_valid_names(name):
    workspace = Workspace(name=name)
    workspace.full_clean()
    workspace.save()
    workspace.refresh_from_db()
    assert workspace.name == name


@pytest.mark.django_db
def test_membership_model_validation_rejects_unknown_role(user_factory):
    user = user_factory()
    workspace = Workspace.objects.create(name='Команда')
    membership = Membership(workspace=workspace, user=user, role='ADMIN')

    with pytest.raises(ValidationError) as error:
        membership.full_clean()
    assert 'role' in error.value.message_dict
    assert Membership.objects.count() == 0

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


@pytest.fixture
def workspace_list_data(user_factory):
    users = {
        key: user_factory(email=f'user_{key}@example.com') for key in ('a', 'b', 'c')
    }
    # Совпадение названий не должно влиять на доступ к разным объектам.
    workspaces = {
        'x': Workspace.objects.create(name='Команда'),
        'y': Workspace.objects.create(name='Команда'),
        'z': Workspace.objects.create(name='Общее пространство'),
    }
    for user_key, workspace_key in (('a', 'x'), ('b', 'y'), ('a', 'z'), ('b', 'z')):
        Membership.objects.create(
            workspace=workspaces[workspace_key],
            user=users[user_key],
            role=Membership.Role.OWNER,
        )
    return users, workspaces


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
