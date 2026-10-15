import pytest
from django.db import IntegrityError, transaction

from .models import Workspace, Membership
from django.test import TestCase

# Create your tests here.
@pytest.fixture
def user_factory(django_user_model):
    def create_user(**fields):
        data = {
            'email': 'test@mail.com',
            'password': 'passTEST123!',
            'username': 'testuser',
        }
        data.update(fields)
        return django_user_model.objects.create_user(**data)

    return create_user

@pytest.mark.django_db
def test_workspaces(db, user_factory):
    user = user_factory()
    workspace = Workspace.objects.create(name='workspace_1')
    membership = Membership.objects.create(workspace=workspace, user=user, role=Membership.Role.OWNER)
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

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Membership.objects.create(workspace=workspace_2, user=user, role=Membership.Role.OWNER)

