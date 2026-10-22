import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_admin_can_create_user_with_repeated_username(user_factory, django_user_model, mailoutbox):
    # Приёмка Admin: настоящий вход по email и сохранение через подключённую add_form.
    admin = user_factory(email='admin@example.com', username='admin', is_staff=True, is_superuser=True)
    user_factory(email='existing@example.com', username='shared')
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    response = client.post('/admin/login/', {
        'username': admin.email, 'password': 'test-password', 'next': '/admin/accounts/user/',
    }, HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 302
    assert response['Location'] == '/admin/accounts/user/'
    assert client.get('/admin/accounts/user/').status_code == 200

    response = client.get('/admin/accounts/user/add/')
    assert response.status_code == 200
    form = response.context['adminform'].form
    assert {'email', 'username', 'password1', 'password2'} <= set(form.fields)

    # Вход Admin тоже меняет CSRF-секрет; повтор username допустим, email нормализуется.
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    password = 'Violet!River-72-Copper'
    response = client.post('/admin/accounts/user/add/', {
        'email': ' NEW@EXAMPLE.COM ', 'username': 'shared',
        'password1': password, 'password2': password,
    }, HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 302, response.content
    created = django_user_model.objects.get(email='new@example.com')
    assert created.username == 'shared'
    assert created.check_password(password)
    assert created.is_staff is False
    assert created.is_superuser is False
    # Приветственное письмо относится к API-регистрации; Admin его не отправляет.
    assert mailoutbox == []
