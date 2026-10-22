from django.db import connection
from django.db import connection, IntegrityError
import pytest


@pytest.mark.django_db
def test_user_can_be_saved_in_postgresql(django_user_model, user_factory):
    assert connection.vendor == "postgresql"

    user = user_factory()

    saved_user = django_user_model.objects.get(pk=user.pk)

    assert saved_user.email == "user@gmail.com"
    assert saved_user.username == "user"
    assert saved_user.check_password("test-password")
    assert saved_user.password != 'test-password'


@pytest.mark.django_db
def test_user_with_mixed_case_email(django_user_model, user_factory):
    assert connection.vendor == "postgresql"

    user = user_factory(
        email=" USER@GMail.com ",
    )
    saved_user = django_user_model.objects.get(pk=user.pk)
    assert saved_user.check_password("test-password")
    assert saved_user.email == "user@gmail.com"


@pytest.mark.django_db
def test_users_with_the_same_username(django_user_model, user_factory):
    assert connection.vendor == "postgresql"
    user_1 = user_factory(
        email='user1@gmail.com',
    )
    user_2 = user_factory(
        email='user2@gmail.com',
    )

    saved_user_1 = django_user_model.objects.get(pk=user_1.pk)
    saved_user_2 = django_user_model.objects.get(pk=user_2.pk)

    assert saved_user_1.username == 'user'
    assert saved_user_2.username == 'user'


@pytest.mark.django_db
def test_users_with_the_same_email(django_user_model, user_factory):
    assert connection.vendor == "postgresql"
    user_1 = user_factory()

    with pytest.raises(IntegrityError):
        user_2 = user_factory(
            email='USER@gmail.com',
        )


@pytest.mark.django_db
def test_superuser_can_be_saved_in_postgresql(django_user_model):
    assert connection.vendor == "postgresql"

    user = django_user_model.objects.create_superuser(
        email="user@gmail.com",
        username="superuser",
        password="test-password",
    )

    saved_user = django_user_model.objects.get(pk=user.pk)

    assert saved_user.email == "user@gmail.com"
    assert saved_user.username == "superuser"
    assert saved_user.check_password("test-password")
    assert saved_user.is_staff is True
    assert saved_user.is_superuser is True


@pytest.mark.django_db
@pytest.mark.parametrize('flag', ['is_staff', 'is_superuser'])
def test_create_superuser_rejects_false_flags(django_user_model, flag):
    # Менеджер не должен создавать противоречивого суперпользователя.
    count_before = django_user_model.objects.count()
    with pytest.raises(ValueError):
        django_user_model.objects.create_superuser(
            email='admin@example.com', username='admin', password='test-password', **{flag: False},
        )
    assert django_user_model.objects.count() == count_before
