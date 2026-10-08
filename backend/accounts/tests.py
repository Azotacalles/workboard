import pytest
from django.db import connection, IntegrityError
from rest_framework.test import APIClient


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

@pytest.mark.django_db
def test_me_requires_authentication():
    # Клиент без сессии не должен получать данные пользователя.
    client = APIClient()
    response = client.get('/api/v1/auth/me/')
    assert response.status_code == 403

@pytest.mark.django_db
def test_me_returns_current_user(django_user_model):
    # Проверяем /me/ с готовой сессией; вход по паролю здесь не тестируем.
    user = django_user_model.objects.create_user(
        email="user@example.com",
        username="user",
        password="test-password",
    )

    client = APIClient()
    client.force_login(user)

    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 200
    assert response.json() == {
        "id": user.pk,
        "username": "user",
        "email": "user@example.com",
    }

def test_get_csrf(django_user_model):
    # Анонимный GET выдаёт токен в JSON и устанавливает отдельную CSRF-cookie.
    client = APIClient()
    response = client.get('/api/v1/auth/csrf/')
    assert response.status_code == 200

    data = response.json()
    assert "csrfToken" in data
    assert isinstance(data["csrfToken"], str)
    assert data["csrfToken"] != ""

    assert "csrftoken" in response.cookies
    assert response.cookies["csrftoken"].value != ""

@pytest.mark.django_db
def test_register(django_user_model):
    # Полный путь: CSRF → регистрация → автоматический вход → /me/.
    client = APIClient(enforce_csrf_checks=True)
    csrf_response = client.get('/api/v1/auth/csrf/')
    assert csrf_response.status_code == 200
    token = csrf_response.json()['csrfToken']
    password = 'Violet!River-72-Copper'
    payload = {
        'email': ' NewUser@EXAMPLE.COM ',
        'username': 'user',
        'password': password,
        'password_confirm': password,
    }
    count_before = django_user_model.objects.count()

    response = client.post(
        '/api/v1/auth/register/', payload, format='json',
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 201, response.content
    assert django_user_model.objects.count() == count_before + 1
    user = django_user_model.objects.get(pk=response.json()['id'])
    assert user.email == 'newuser@example.com'
    assert user.check_password(password)
    expected = {'id': user.pk, 'username': 'user', 'email': user.email}
    assert response.json() == expected

    # Тот же клиент уже хранит cookie сессии, созданной при регистрации.
    me_response = client.get('/api/v1/auth/me/')
    assert me_response.status_code == 200
    assert me_response.json() == expected

    # Вход меняет CSRF-секрет: перед следующим POST получаем свежий токен.
    csrf_response = client.get('/api/v1/auth/csrf/')
    assert csrf_response.status_code == 200
    response = client.post(
        '/api/v1/auth/register/', payload, format='json',
        HTTP_X_CSRFTOKEN=csrf_response.json()['csrfToken'],
    )
    assert response.status_code == 409
    assert django_user_model.objects.count() == count_before + 1
    assert client.get('/api/v1/auth/me/').json() == expected

@pytest.mark.django_db
def test_register_requires_csrf(django_user_model):
    # Даже с корректными данными запрос без CSRF не должен создать аккаунт.
    client = APIClient(enforce_csrf_checks=True)
    count_before = django_user_model.objects.count()
    response = client.post('/api/v1/auth/register/', {
        'email': 'newuser@example.com',
        'username': 'user',
        'password': 'Violet!River-72-Copper',
        'password_confirm': 'Violet!River-72-Copper',
    }, format='json')
    assert response.status_code == 403
    assert django_user_model.objects.count() == count_before

@pytest.mark.django_db
def test_register_rejects_mismatched_passwords(django_user_model):
    # CSRF корректен, но разные пароли дают ошибку поля без создания пользователя.
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    count_before = django_user_model.objects.count()
    response = client.post('/api/v1/auth/register/', {
        'email': 'newuser@example.com',
        'username': 'user',
        'password': 'Violet!River-72-Copper',
        'password_confirm': 'Another!River-81-Copper',
    }, format='json', HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 400
    assert 'password_confirm' in response.json()
    assert django_user_model.objects.count() == count_before

@pytest.mark.django_db
@pytest.mark.parametrize('email, expected_status', [
    ('EXISTING@example.com', 400),
    ('another@example.com', 201),
])
def test_register_duplicate_fields(django_user_model, email, expected_status):
    # Два запуска: повтор email запрещён, повтор username с новым email разрешён.
    django_user_model.objects.create_user(
        email='existing@example.com', username='user', password='test-password',
    )
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    count_before = django_user_model.objects.count()
    response = client.post('/api/v1/auth/register/', {
        'email': email,
        'username': 'user',
        'password': 'Violet!River-72-Copper',
        'password_confirm': 'Violet!River-72-Copper',
    }, format='json', HTTP_X_CSRFTOKEN=token)
    assert response.status_code == expected_status, response.content
    if expected_status == 400:
        assert 'email' in response.json()
        assert django_user_model.objects.count() == count_before
    else:
        assert django_user_model.objects.count() == count_before + 1

@pytest.mark.django_db
def test_user_login(django_user_model):
    # Создаём аккаунт без сессии, затем входим настоящим POST и проверяем /me/.
    # Пробелы в пароле сохраняются; регистр и пробелы по краям email игнорируются.
    password = ' passASD213! '
    user = django_user_model.objects.create_user(
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
    assert response.json() == expected
    response = client.get('/api/v1/auth/me/')
    assert response.status_code == 200
    assert response.json() == expected

    # Тот же клиент всё ещё отправляет sessionid пользователя user.
    # Создание other в БД не меняет эту сессию и не создаёт отдельный клиент.
    other = django_user_model.objects.create_user(
        email='other@example.com', username='other', password=password,
    )
    # После первого входа CSRF-секрет сменился: берём свежий токен.
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    response = client.post('/api/v1/auth/login/', {
        'email': other.email, 'password': password,
    }, format='json', HTTP_X_CSRFTOKEN=token)
    # По правилу проекта уже вошедший клиент не может переключиться через login.
    assert response.status_code == 409
    assert client.get('/api/v1/auth/me/').json() == expected


@pytest.mark.django_db
@pytest.mark.parametrize('case', ['wrong_password', 'unknown_email', 'inactive'])
def test_login_rejects_invalid_credentials(django_user_model, case):
    # Три запуска: неверный пароль, неизвестная почта и неактивный аккаунт.
    # Ответ одинаков во всех случаях; после отказа клиент остаётся анонимным.
    password = 'passASD213!'
    user = django_user_model.objects.create_user(
        email='existing@example.com', username='user', password=password,
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
def test_login_requires_csrf(django_user_model):
    # Правильного пароля недостаточно: без CSRF вход и создание сессии запрещены.
    password = 'passASD213!'
    user = django_user_model.objects.create_user(
        email='existing@example.com', username='user', password=password,
    )
    client = APIClient(enforce_csrf_checks=True)
    response = client.post('/api/v1/auth/login/', {
        'email': user.email, 'password': password,
    }, format='json')
    assert response.status_code == 403
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
