import pytest
from django.db import connection


@pytest.mark.django_db
def test_user_can_be_saved_in_postgresql(django_user_model):
    assert connection.vendor == "postgresql"

    user = django_user_model.objects.create_user(
        username="test_user",
        password="test-password",
    )

    saved_user = django_user_model.objects.get(pk=user.pk)

    assert saved_user.username == "test_user"