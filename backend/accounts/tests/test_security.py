from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sessions.models import Session
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
import pytest
from rest_framework.test import APIClient


def test_get_csrf(django_user_model):
    # Анонимный GET выдаёт токен в JSON и устанавливает отдельную CSRF-cookie.
    client = APIClient()
    response = client.get('/api/v1/auth/csrf/')
    assert response.status_code == 200

    data = response.json()
    assert "csrfToken" in data
    assert 'no-store' in response['Cache-Control']
    assert isinstance(data["csrfToken"], str)
    assert data["csrfToken"] != ""

    assert "csrftoken" in response.cookies
    assert response.cookies["csrftoken"].value != ""


def test_admin_csrf_failure_keeps_html():
    # JSON-обработчик auth API не меняет стандартную CSRF-страницу Admin.
    client = APIClient(enforce_csrf_checks=True)
    response = client.post('/admin/login/', {})
    assert response.status_code == 403
    assert response['Content-Type'].startswith('text/html')


@pytest.mark.parametrize('endpoint', [
    'register', 'login', 'logout', 'password-reset', 'password-reset/confirm',
])
def test_auth_get_does_not_allow_changes(endpoint):
    # Создание аккаунта, вход и выход доступны только через POST.
    response = APIClient().get(f'/api/v1/auth/{endpoint}/')
    assert response.status_code == 405
    assert 'no-store' in response['Cache-Control']


@pytest.mark.django_db
@pytest.mark.parametrize('endpoint', [
    'register', 'login', 'logout', 'password-reset', 'password-reset/confirm',
])
@pytest.mark.parametrize('rejection', ['missing_token', 'wrong_token', 'untrusted_origin'])
def test_auth_csrf_rejection_has_no_side_effects(
    endpoint, rejection, user_factory, logged_in_client, django_user_model,
    mailoutbox, django_capture_on_commit_callbacks,
):
    # Общая проверка всех POST: 403 недостаточно, запись/письмо/сессия не должны измениться.
    user = user_factory()
    signed_in, fresh_token = logged_in_client(user)
    user.refresh_from_db()
    old_password = user.password
    old_last_login = user.last_login
    expected_user = {'id': user.pk, 'email': user.email, 'username': user.username}

    # Logout проверяем со входом; остальные запросы отправляет отдельный анонимный клиент.
    client = signed_in if endpoint == 'logout' else APIClient(enforce_csrf_checks=True)
    token = fresh_token if endpoint == 'logout' else client.get('/api/v1/auth/csrf/').json()['csrfToken']
    new_password = 'Violet!River-72-Copper'
    payloads = {
        'register': {'email': 'new@example.com', 'username': 'new',
                     'password': new_password, 'password_confirm': new_password},
        'login': {'email': user.email, 'password': 'test-password'},
        'logout': {},
        'password-reset': {'email': user.email},
        'password-reset/confirm': {
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': default_token_generator.make_token(user),
            'password': new_password, 'password_confirm': new_password,
        },
    }
    headers = {'HTTP_X_CSRFTOKEN': token}
    if rejection == 'missing_token':
        headers = {}
    elif rejection == 'wrong_token':
        # Меняем секрет cookie при сохранении корректного формата заголовка.
        secret = client.cookies[settings.CSRF_COOKIE_NAME].value
        headers['HTTP_X_CSRFTOKEN'] = ('A' if secret[0] != 'A' else 'B') + secret[1:]
    else:
        # Токен правильный: причиной отказа должен стать именно посторонний Origin.
        headers['HTTP_ORIGIN'] = 'https://untrusted.example'

    user_count = django_user_model.objects.count()
    session_keys = set(Session.objects.values_list('session_key', flat=True))
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = client.post(f'/api/v1/auth/{endpoint}/', payloads[endpoint],
                               format='json', **headers)
    assert response.status_code == 403
    assert response.json() == {
        'code': 'csrf_failed',
        'detail': 'Не удалось проверить запрос. Обновите страницу.',
    }
    assert 'no-store' in response['Cache-Control']
    assert django_user_model.objects.count() == user_count
    assert set(Session.objects.values_list('session_key', flat=True)) == session_keys
    user.refresh_from_db()
    assert user.password == old_password
    assert user.last_login == old_last_login
    assert callbacks == []
    assert mailoutbox == []
    assert signed_in.get('/api/v1/auth/me/').json() == expected_user
    if endpoint != 'logout':
        assert settings.SESSION_COOKIE_NAME not in client.cookies
        assert client.get('/api/v1/auth/me/').json()['code'] == 'not_authenticated'


@pytest.mark.parametrize('origin, allowed', [
    ('http://localhost:5173', True), ('http://127.0.0.1:5173', False),
])
def test_cors_preflight_for_auth(origin, allowed):
    # OPTIONS с этими заголовками браузер отправляет перед JSON POST с CSRF-заголовком.
    response = APIClient().options('/api/v1/auth/login/',
        HTTP_ORIGIN=origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS='content-type,x-csrftoken',
    )
    assert response.status_code == 200
    if allowed:
        assert response['Access-Control-Allow-Origin'] == origin
        assert response['Access-Control-Allow-Credentials'] == 'true'
        assert 'POST' in response['Access-Control-Allow-Methods']
        allowed_headers = response['Access-Control-Allow-Headers'].lower()
        assert 'content-type' in allowed_headers
        assert 'x-csrftoken' in allowed_headers
    else:
        # 200 сам по себе ничего не разрешает: без allow-origin браузер блокирует запрос.
        assert 'Access-Control-Allow-Origin' not in response
