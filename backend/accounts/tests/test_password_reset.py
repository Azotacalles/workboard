from datetime import timedelta
from urllib.parse import urlsplit, parse_qs

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode
from django.utils.http import urlsafe_base64_encode
import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_password_reset_confirm(user_factory, mailoutbox):
    user = user_factory()
    client = APIClient(enforce_csrf_checks=True)

    # Получение CSRF — GET, а не POST.
    csrf_token = client.get('/api/v1/auth/csrf/').json()['csrfToken']

    # Отправляем JSON с email, а не сам объект User.
    response = client.post(
        '/api/v1/auth/password-reset/',
        {'email': user.email},
        format='json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 200, response.content
    assert len(mailoutbox) == 1
    # Ищем строку со ссылкой в тексте письма.
    reset_url = None

    for line in mailoutbox[0].body.splitlines():
        line = line.strip()

        if line.startswith('http://') or line.startswith('https://'):
            reset_url = line
            break

    assert reset_url is not None

    # Из ссылки берём параметры, которые потом прочитает React.
    params = parse_qs(urlsplit(reset_url).query)

    uid = params['uid'][0]
    reset_token = params['token'][0]

    new_password = 'Violet!River-72-Copper'

    # Имитируем отправку формы нового пароля.
    response = client.post('/api/v1/auth/password-reset/confirm/',{
            'uid': uid,
            'token': reset_token,
            'password': new_password,
            'password_confirm': new_password,
        }, format='json', HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 204, response.content
    assert response.content == b''

    # Обновляем объект из БД: пароль изменился внутри view.
    user.refresh_from_db()

    assert user.check_password(new_password)
    assert not user.check_password('test-password')

    # Сброс пароля не должен автоматически авторизовать клиента.
    assert client.get('/api/v1/auth/me/').status_code == 403

    # Теперь выполняем обычный вход с новым паролем.
    response = client.post('/api/v1/auth/login/',{
            'email': user.email,
            'password': new_password,
        }, format='json', HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 200, response.content
    assert response.json()['id'] == user.pk


@pytest.mark.django_db
def test_password_reset_link_cannot_be_reused(user_factory, reset_request):
    user = user_factory()
    client, csrf_token, payload = reset_request(user)
    response = client.post('/api/v1/auth/password-reset/confirm/', payload,
                           format='json', HTTP_X_CSRFTOKEN=csrf_token)
    assert response.status_code == 204, response.content
    user.refresh_from_db()
    saved_password = user.password

    # Та же ссылка не должна позволить установить ещё один пароль после успешного сброса.
    payload.update(password='Another!River-81-Copper', password_confirm='Another!River-81-Copper')
    response = client.post('/api/v1/auth/password-reset/confirm/', payload,
                           format='json', HTTP_X_CSRFTOKEN=csrf_token)
    assert response.status_code == 400
    assert response.json()['code'] == 'invalid_reset_link'
    user.refresh_from_db()
    assert user.password == saved_password


@pytest.mark.django_db
def test_password_reset_rejects_changed_token(user_factory, reset_request):
    user = user_factory()
    saved_password = user.password
    client, csrf_token, payload = reset_request(user)
    # Меняем один символ, гарантированно получая другой токен.
    last_character = '0' if payload['token'][-1] != '0' else '1'
    payload['token'] = payload['token'][:-1] + last_character
    response = client.post('/api/v1/auth/password-reset/confirm/', payload,
                           format='json', HTTP_X_CSRFTOKEN=csrf_token)
    assert response.status_code == 400
    assert response.json()['code'] == 'invalid_reset_link'
    user.refresh_from_db()
    assert user.password == saved_password


@pytest.mark.django_db
@pytest.mark.parametrize('uid', [
    'A',  # Некорректная длина base64.
    urlsafe_base64_encode(b'not-a-number'),
    urlsafe_base64_encode(b'\xff'),  # Байты, которые нельзя декодировать как UTF-8.
    urlsafe_base64_encode(force_bytes(999999999)),  # Несуществующий пользователь.
    urlsafe_base64_encode(force_bytes(10 ** 100)),  # ID вне диапазона столбца БД.
], ids=['broken_base64', 'not_numeric', 'invalid_utf8', 'unknown_user', 'oversized_id'])
def test_password_reset_rejects_invalid_uid(user_factory, reset_request, uid):
    user = user_factory()
    saved_password = user.password
    client, csrf_token, payload = reset_request(user)
    payload['uid'] = uid
    # Любой такой отказ должен стать JSON-ошибкой ссылки, а не необработанным исключением.
    response = client.post('/api/v1/auth/password-reset/confirm/', payload,
                           format='json', HTTP_X_CSRFTOKEN=csrf_token)
    assert response.status_code == 400
    assert response.json() == {
        'code': 'invalid_reset_link',
        'detail': 'Ссылка недействительна или устарела. Запросите новую.',
    }
    user.refresh_from_db()
    assert user.password == saved_password


@pytest.mark.django_db
def test_password_reset_rejects_expired_token(user_factory, reset_request, settings, monkeypatch):
    user = user_factory()
    saved_password = user.password
    settings.PASSWORD_RESET_TIMEOUT = 1
    created_at = default_token_generator._now()
    monkeypatch.setattr(default_token_generator, '_now', lambda: created_at)
    client, csrf_token, payload = reset_request(user)

    # Перемещаем часы генератора за срок ссылки: реального ожидания в тесте нет.
    monkeypatch.setattr(default_token_generator, '_now', lambda: created_at + timedelta(seconds=2))
    response = client.post('/api/v1/auth/password-reset/confirm/', payload,
                           format='json', HTTP_X_CSRFTOKEN=csrf_token)
    assert response.status_code == 400
    assert response.json()['code'] == 'invalid_reset_link'
    user.refresh_from_db()
    assert user.password == saved_password


@pytest.mark.django_db
def test_password_reset_rejects_inactive_user(user_factory, reset_request):
    user = user_factory()
    saved_password = user.password
    client, csrf_token, payload = reset_request(user)
    # Письмо получено активным аккаунтом, но к моменту подтверждения его отключили.
    user.is_active = False
    user.save(update_fields=['is_active'])
    response = client.post('/api/v1/auth/password-reset/confirm/', payload,
                           format='json', HTTP_X_CSRFTOKEN=csrf_token)
    assert response.status_code == 400
    assert response.json()['code'] == 'invalid_reset_link'
    user.refresh_from_db()
    assert user.password == saved_password


@pytest.mark.django_db
@pytest.mark.parametrize('password, password_confirm, field', [
    ('short', 'short', 'password'),
    ('Violet!River-72-Copper', 'different-password', 'password_confirm'),
], ids=['weak_password', 'mismatched_passwords'])
def test_password_reset_rejects_invalid_password(
    user_factory, reset_request, password, password_confirm, field,
):
    user = user_factory()
    saved_password = user.password
    client, csrf_token, payload = reset_request(user)
    payload.update(password=password, password_confirm=password_confirm)
    response = client.post('/api/v1/auth/password-reset/confirm/', payload,
                           format='json', HTTP_X_CSRFTOKEN=csrf_token)
    assert response.status_code == 400
    assert field in response.json()
    user.refresh_from_db()
    assert user.password == saved_password

    # Исправление полей допускает повтор с той же ссылкой: неудачная попытка её не расходует.
    payload.update(password='Violet!River-72-Copper', password_confirm='Violet!River-72-Copper')
    response = client.post('/api/v1/auth/password-reset/confirm/', payload,
                           format='json', HTTP_X_CSRFTOKEN=csrf_token)
    assert response.status_code == 204, response.content


@pytest.mark.django_db
def test_password_reset_invalidates_existing_sessions(user_factory, reset_request):
    user = user_factory()
    previous_clients = [APIClient(enforce_csrf_checks=True), APIClient(enforce_csrf_checks=True)]
    for previous_client in previous_clients:
        csrf_token = previous_client.get('/api/v1/auth/csrf/').json()['csrfToken']
        response = previous_client.post('/api/v1/auth/login/', {
            'email': user.email, 'password': 'test-password',
        }, format='json', HTTP_X_CSRFTOKEN=csrf_token)
        assert response.status_code == 200
        assert previous_client.get('/api/v1/auth/me/').status_code == 200

    # Письмо запрашиваем после входов: login меняет last_login, который участвует в токене.
    user.refresh_from_db()
    client, csrf_token, payload = reset_request(user)
    response = client.post('/api/v1/auth/password-reset/confirm/', payload,
                           format='json', HTTP_X_CSRFTOKEN=csrf_token)
    assert response.status_code == 204, response.content

    # Обе старые сессии перестают давать доступ; клиент сброса тоже не получает автоматический вход.
    for previous_client in previous_clients:
        response = previous_client.get('/api/v1/auth/me/')
        assert response.status_code == 403
        assert response.json()['code'] == 'not_authenticated'
    assert client.get('/api/v1/auth/me/').status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize('account', ['active', 'unknown', 'inactive', 'unusable_password'])
def test_password_reset_returns_neutral_response(account, user_factory, mailoutbox, settings):
    user = user_factory(is_active=account != 'inactive')
    if account == 'unusable_password':
        user.set_unusable_password()
        user.save(update_fields=['password'])
    old_password = user.password
    settings.FRONTEND_URL = 'https://frontend.example.test/'
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    email = 'unknown@example.com' if account == 'unknown' else f' {user.email.upper()} '
    response = client.post('/api/v1/auth/password-reset/', {'email': email},
                           format='json', HTTP_X_CSRFTOKEN=token)
    # Ответ не раскрывает существование, активность или пригодность пароля аккаунта.
    assert response.status_code == 200
    assert response.json() == {
        'detail': 'Если для этого адреса доступно восстановление мы отправим письмо с инструкцией.',
    }
    assert 'no-store' in response['Cache-Control']
    user.refresh_from_db()
    assert user.password == old_password
    assert settings.SESSION_COOKIE_NAME not in client.cookies
    if account == 'active':
        assert len(mailoutbox) == 1
        message = mailoutbox[0]
        assert message.to == [user.email]
        url = next(line.strip() for line in message.body.splitlines()
                   if line.strip().startswith('https://'))
        parts = urlsplit(url)
        assert parts.scheme == 'https'
        assert parts.netloc == 'frontend.example.test'
        assert parts.path == '/reset-password'
        params = parse_qs(parts.query)
        assert set(params) == {'uid', 'token'}
        assert urlsafe_base64_decode(params['uid'][0]).decode() == str(user.pk)
        assert default_token_generator.check_token(user, params['token'][0])
        assert old_password not in message.body
    else:
        assert mailoutbox == []
