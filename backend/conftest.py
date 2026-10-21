import pytest
from rest_framework.test import APIClient


@pytest.fixture
def user_factory(db, django_user_model):
    # Общая фабрика для auth и workspace: значения можно переопределить в тесте.
    def create_user(**overrides):
        data = {
            'email': 'user@gmail.com',
            'username': 'user',
            'password': 'test-password',
        }
        data.update(overrides)
        return django_user_model.objects.create_user(**data)

    return create_user


@pytest.fixture
def logged_in_client():
    # Настоящий login: сессия, пароль и CSRF проходят через auth API.
    def login_user(user, password='test-password'):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
        response = client.post('/api/v1/auth/login/', {
            'email': user.email, 'password': password,
        }, format='json', HTTP_X_CSRFTOKEN=token)
        assert response.status_code == 200, response.content
        # Login меняет CSRF-секрет; для следующих POST нужен свежий токен.
        token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
        return client, token

    return login_user
