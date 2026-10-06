import pytest
from django.db import connection, IntegrityError


@pytest.mark.django_db
def test_user_can_be_saved_in_postgresql(django_user_model):
    assert connection.vendor == "postgresql"

    user = django_user_model.objects.create_user(
        email="user@gmail.com",
        username="user",
        password="test-password",
    )

    saved_user = django_user_model.objects.get(pk=user.pk)

    assert saved_user.email == "user@gmail.com"
    assert saved_user.username == "user"
    assert saved_user.check_password("test-password")


@pytest.mark.django_db
def test_user_with_mixed_case_email(django_user_model):
    assert connection.vendor == "postgresql"

    user = django_user_model.objects.create_user(
        email="USER@GMail.com",
        username="user",
        password="test-password",
    )
    saved_user = django_user_model.objects.get(pk=user.pk)
    assert saved_user.check_password("test-password")
    assert saved_user.email == "user@gmail.com"


@pytest.mark.django_db
def test_users_with_the_same_username(django_user_model):
    assert connection.vendor == "postgresql"
    user_1 = django_user_model.objects.create_user(
        email='user1@gmail.com',
        username="user",
        password="test-password",
    )
    user_2 = django_user_model.objects.create_user(
        email='user2@gmail.com',
        username="user",
        password="test-password",
    )

    saved_user_1 = django_user_model.objects.get(pk=user_1.pk)
    saved_user_2 = django_user_model.objects.get(pk=user_2.pk)

    assert saved_user_1.username == 'user'
    assert saved_user_2.username == 'user'


@pytest.mark.django_db
def test_users_with_the_same_email(django_user_model):
    assert connection.vendor == "postgresql"
    user_1 = django_user_model.objects.create_user(
        email='user@gmail.com',
        username="user",
        password="test-password",
    )

    with pytest.raises(IntegrityError):
        user_2 = django_user_model.objects.create_user(
            email='USER@gmail.com',
            username="user",
            password="test-password",
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