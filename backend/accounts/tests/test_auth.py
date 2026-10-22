from datetime import timedelta

from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone
import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_me_requires_authentication():
    # Клиент без сессии не должен получать данные пользователя.
    client = APIClient()
    response = client.get('/api/v1/auth/me/')
    assert response.status_code == 403


@pytest.mark.django_db
def test_me_returns_current_user(user_factory, logged_in_client):
    # /me/ должен узнать пользователя по сессии, полученной настоящим входом.
    user = user_factory(
        email="user@example.com",
    )

    client, _ = logged_in_client(user)

    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 200
    assert response.json() == {
        "id": user.pk,
        "username": "user",
        "email": "user@example.com",
    }


@pytest.mark.django_db
def test_user_login(user_factory):
    # Создаём аккаунт без сессии, затем входим настоящим POST и проверяем /me/.
    # Пробелы в пароле сохраняются; регистр и пробелы по краям email игнорируются.
    password = ' passASD213! '
    user = user_factory(
        email='new_user@example.com', username='new_user', password=password,
    )
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    response = client.post('/api/v1/auth/login/', {
        'email': ' NEW_USER@EXAMPLE.COM ',
        'password': password,
    }, format='json', HTTP_X_CSRFTOKEN=token)

    expected = {'id': user.pk, 'email': user.email, 'username': user.username}
    assert response.status_code == 200, response.content
    assert 'no-store' in response['Cache-Control']
    assert response.json() == expected
    response = client.get('/api/v1/auth/me/')
    assert response.status_code == 200
    assert response.json() == expected

    # Тот же клиент всё ещё отправляет sessionid пользователя user.
    # Создание other в БД не меняет эту сессию и не создаёт отдельный клиент.
    other = user_factory(
        email='other@example.com', username='other', password=password,
    )
    # После первого входа CSRF-секрет сменился: берём свежий токен.
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    response = client.post('/api/v1/auth/login/', {
        'email': other.email, 'password': password,
    }, format='json', HTTP_X_CSRFTOKEN=token)
    # По правилу проекта уже вошедший клиент не может переключиться через login.
    assert response.status_code == 409
    assert response.json() == {
        'code': 'already_authenticated',
        'detail': 'Вы уже вошли в приложение.',
    }
    assert 'no-store' in response['Cache-Control']
    assert client.get('/api/v1/auth/me/').json() == expected


@pytest.mark.django_db
@pytest.mark.parametrize('case', ['wrong_password', 'unknown_email', 'inactive'])
def test_login_rejects_invalid_credentials(user_factory, case):
    # Три запуска: неверный пароль, неизвестная почта и неактивный аккаунт.
    # Ответ одинаков во всех случаях; после отказа клиент остаётся анонимным.
    password = 'passASD213!'
    user = user_factory(
        email='existing@example.com', password=password,
        is_active=case != 'inactive',
    )
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    response = client.post('/api/v1/auth/login/', {
        'email': 'unknown@example.com' if case == 'unknown_email' else user.email,
        'password': 'wrong-password' if case == 'wrong_password' else password,
    }, format='json', HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 400
    assert response.json() == {
        'code': 'invalid_credentials',
        'detail': 'Неверная почта или пароль.',
    }
    assert client.get('/api/v1/auth/me/').status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize('payload, field', [
    ({'password': 'passASD213!'}, 'email'),
    ({'email': 'user@example.com'}, 'password'),
    ({'email': 'not-an-email', 'password': 'passASD213!'}, 'email'),
])
def test_login_validates_input(payload, field):
    # Пропущенные поля и некорректный email дают 400 с именем проблемного поля.
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    response = client.post('/api/v1/auth/login/', payload, format='json',
                           HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 400
    assert field in response.json()


@pytest.mark.django_db
def test_user_logout(user_factory):
    # Настоящий вход → проверка CSRF на выходе → выход → повтор → старая cookie.
    user = user_factory(
        password='passASD123!',
    )
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    response = client.post('/api/v1/auth/login/', {
        'email': 'user@gmail.com',
        'password': 'passASD123!',
    }, format='json', HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200

    expected = {'id': user.id, 'email': user.email, 'username': user.username}
    assert client.get('/api/v1/auth/me/').json() == expected

    old_session = client.cookies[settings.SESSION_COOKIE_NAME].value

    # Без токена выход отклоняется, а действующая сессия сохраняется.
    response = client.post('/api/v1/auth/logout/')
    assert response.status_code == 403
    assert response.json() == {
        'code': 'csrf_failed',
        'detail': 'Не удалось проверить запрос. Обновите страницу.',
    }
    assert 'no-store' in response['Cache-Control']
    assert client.get('/api/v1/auth/me/').json() == expected

    # GET не выполняет выход.
    assert client.get('/api/v1/auth/logout/').status_code == 405
    assert client.get('/api/v1/auth/me/').json() == expected

    # После login нужен свежий токен; cookie клиент отправляет автоматически.
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    response = client.post('/api/v1/auth/logout/', HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 204
    assert response.content == b''
    assert 'no-store' in response['Cache-Control']

    response = client.get('/api/v1/auth/me/')
    assert response.status_code == 403
    assert response.json() == {
        'code': 'not_authenticated',
        'detail': 'Необходим вход в приложение.',
    }
    assert 'no-store' in response['Cache-Control']

    # Повторный logout разрешён анонимному клиенту с корректным CSRF.
    response = client.post('/api/v1/auth/logout/', HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 204
    assert response.content == b''

    # Возврат старой cookie не восстанавливает удалённую серверную сессию.
    other_client = APIClient()
    other_client.cookies[settings.SESSION_COOKIE_NAME] = old_session
    assert other_client.get('/api/v1/auth/me/').status_code == 403


@pytest.mark.django_db
def test_clients_keep_independent_sessions(user_factory, logged_in_client):
    # Два браузера видят разных пользователей; выход первого не завершает второй вход.
    first = user_factory(email='first@example.com', username='first')
    second = user_factory(email='second@example.com', username='second')
    first_client, first_token = logged_in_client(first)
    second_client, _ = logged_in_client(second)
    for client, user in [(first_client, first), (second_client, second)]:
        assert client.get('/api/v1/auth/me/').json() == {
            'id': user.pk, 'email': user.email, 'username': user.username,
        }
    first_session = first_client.cookies[settings.SESSION_COOKIE_NAME].value
    second_session = second_client.cookies[settings.SESSION_COOKIE_NAME].value
    assert first_session != second_session
    response = first_client.post('/api/v1/auth/logout/', HTTP_X_CSRFTOKEN=first_token)
    assert response.status_code == 204
    assert not Session.objects.filter(session_key=first_session).exists()
    assert Session.objects.filter(session_key=second_session).exists()
    assert first_client.get('/api/v1/auth/me/').json()['code'] == 'not_authenticated'
    assert second_client.get('/api/v1/auth/me/').json()['id'] == second.pk


@pytest.mark.django_db
def test_me_rejects_expired_server_session(user_factory, logged_in_client):
    user = user_factory()
    client, _ = logged_in_client(user)
    session_key = client.cookies[settings.SESSION_COOKIE_NAME].value
    # Cookie всё ещё есть. Истёк именно срок серверной записи, а не браузерной cookie.
    Session.objects.filter(session_key=session_key).update(
        expire_date=timezone.now() - timedelta(seconds=1),
    )
    assert client.cookies[settings.SESSION_COOKIE_NAME].value == session_key
    response = client.get('/api/v1/auth/me/')
    assert response.status_code == 403
    assert response.json() == {
        'code': 'not_authenticated',
        'detail': 'Необходим вход в приложение.',
    }
    assert 'no-store' in response['Cache-Control']


@pytest.mark.django_db
def test_dev_auth_cookie_attributes(user_factory, logged_in_client):
    # Проверяем атрибуты Set-Cookie; фактическое поведение браузера проверяется отдельно.
    client, _ = logged_in_client(user_factory())
    session_cookie = client.cookies[settings.SESSION_COOKIE_NAME]
    csrf_cookie = client.cookies[settings.CSRF_COOKIE_NAME]
    assert session_cookie['httponly'] is True
    assert session_cookie['max-age'] == settings.SESSION_COOKIE_AGE
    for cookie in [session_cookie, csrf_cookie]:
        assert cookie['samesite'] == 'Lax'
        assert not cookie['secure']  # Dev работает по HTTP.
