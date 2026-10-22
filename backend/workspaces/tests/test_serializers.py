from datetime import datetime, timezone

import pytest

from workspaces.models import Workspace
from workspaces.serializers import WorkspaceCreateSerializer
from workspaces.serializers import WorkspaceSerializer


@pytest.mark.parametrize(
    ('name', 'expected'),
    [
        pytest.param('Команда', 'Команда', id='ordinary'),
        pytest.param('  Команда  ', 'Команда', id='trim-edges'),
        pytest.param('Команда  A', 'Команда  A', id='keep-case-and-inner-spaces'),
        pytest.param('Я', 'Я', id='minimum-length'),
        pytest.param('Я' * 100, 'Я' * 100, id='maximum-length'),
        pytest.param('  ' + 'Я' * 100 + '  ', 'Я' * 100, id='length-after-trim'),
    ],
)
def test_create_serializer_validated_name(name, expected):
    serializer = WorkspaceCreateSerializer(data={'name': name})

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == {'name': expected}


@pytest.mark.parametrize(
    'payload',
    [
        pytest.param({}, id='missing'),
        pytest.param({'name': ''}, id='empty'),
        pytest.param({'name': '   '}, id='only-spaces'),
        pytest.param({'name': '\t\n'}, id='only-whitespace'),
        pytest.param({'name': None}, id='null'),
        pytest.param({'name': 'Я' * 101}, id='too-long'),
    ],
)
def test_create_serializer_rejects_invalid_name(payload):
    serializer = WorkspaceCreateSerializer(data=payload)

    assert not serializer.is_valid()
    assert set(serializer.errors) == {'name'}
    assert serializer.errors['name']
    assert serializer.validated_data == {}


def test_create_serializer_ignores_client_owned_fields():
    serializer = WorkspaceCreateSerializer(data={
        'name': 'Команда',
        'id': 999,
        'created_at': '2000-01-01T00:00:00Z',
        'owner_id': 123,
        'user_id': 456,
        'role': 'ADMIN',
    })

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == {'name': 'Команда'}


def test_workspace_serializer_exposes_only_public_fields():
    workspace = Workspace(
        id=42, name='Команда', created_at=datetime(2026, 10, 21, tzinfo=timezone.utc),
    )

    data = WorkspaceSerializer(workspace).data

    assert data == {'id': 42, 'name': 'Команда', 'created_at': '2026-10-21T00:00:00Z'}
    assert WorkspaceSerializer([workspace], many=True).data == [data]
    assert WorkspaceSerializer([], many=True).data == []
