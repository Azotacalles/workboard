from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
import pytest

from workspaces.models import Workspace
from workspaces.models import Workspace, Membership


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
