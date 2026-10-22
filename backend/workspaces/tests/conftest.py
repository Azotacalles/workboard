import pytest

from workspaces.models import Workspace, Membership


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
