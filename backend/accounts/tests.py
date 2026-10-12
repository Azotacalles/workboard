import logging
from smtplib import SMTPException

import pytest
from django.conf import settings
from django.db import connection, IntegrityError
from rest_framework.test import APIClient
from accounts.emails import send_registration_email


@pytest.fixture
def user_factory(db, django_user_model):
    # Фабрика создаёт пользователя для каждого вызова; нужные тесту поля можно переопределить.
    def create_user(**overrides):
        data = {
            'email': 'user@gmail.com',
            'username': 'user',
            'password': 'test-password',
        }
        data.update(overrides)
        return django_user_model.objects.create_user(**data)

    return create_user


@pytest.mark.django_db
def test_user_can_be_saved_in_postgresql(django_user_model, user_factory):
    assert connection.vendor == "postgresql"

    user = user_factory()

    saved_user = django_user_model.objects.get(pk=user.pk)

    assert saved_user.email == "user@gmail.com"
    assert saved_user.username == "user"
    assert saved_user.check_password("test-password")

@pytest.mark.django_db
def test_user_with_mixed_case_email(django_user_model, user_factory):
    assert connection.vendor == "postgresql"

    user = user_factory(
        email="USER@GMail.com",
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
def test_me_requires_authentication():
    # Клиент без сессии не должен получать данные пользователя.
    client = APIClient()
    response = client.get('/api/v1/auth/me/')
    assert response.status_code == 403

@pytest.mark.django_db
def test_me_returns_current_user(user_factory):
    # Проверяем /me/ с готовой сессией; вход по паролю здесь не тестируем.
    user = user_factory(
        email="user@example.com",
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
    assert 'no-store' in response['Cache-Control']
    assert isinstance(data["csrfToken"], str)
    assert data["csrfToken"] != ""

    assert "csrftoken" in response.cookies
    assert response.cookies["csrftoken"].value != ""

@pytest.mark.django_db
def test_register(django_user_model, mailoutbox, django_capture_on_commit_callbacks):
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

    # Тест обёрнут внешней транзакцией: fixture выполняет отложенную отправку при выходе.
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = client.post(
            '/api/v1/auth/register/', payload, format='json',
            HTTP_X_CSRFTOKEN=token,
        )
        # До выполнения callback письмо ещё не отправлено.
        assert mailoutbox == []
    assert response.status_code == 201, response.content
    assert 'no-store' in response['Cache-Control']
    assert django_user_model.objects.count() == count_before + 1
    user = django_user_model.objects.get(pk=response.json()['id'])
    assert user.email == 'newuser@example.com'
    assert user.check_password(password)
    expected = {'id': user.pk, 'username': 'user', 'email': user.email}
    assert response.json() == expected

    # Успешная регистрация инициирует ровно одно письмо нужному пользователю.
    assert len(callbacks) == 1
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [user.email]
    assert 'Добро пожаловать в WorkBoard!' in mailoutbox[0].body

    # Тот же клиент уже хранит cookie сессии, созданной при регистрации.
    me_response = client.get('/api/v1/auth/me/')
    assert me_response.status_code == 200
    assert 'no-store' in me_response['Cache-Control']
    assert me_response.json() == expected

    # Вход меняет CSRF-секрет: перед следующим POST получаем свежий токен.
    csrf_response = client.get('/api/v1/auth/csrf/')
    assert csrf_response.status_code == 200
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = client.post(
            '/api/v1/auth/register/', payload, format='json',
            HTTP_X_CSRFTOKEN=csrf_response.json()['csrfToken'],
        )
    assert response.status_code == 409
    assert response.json() == {
        'code': 'already_authenticated',
        'detail': 'Вы уже вошли в приложение.',
    }
    assert 'no-store' in response['Cache-Control']
    assert django_user_model.objects.count() == count_before + 1
    assert client.get('/api/v1/auth/me/').json() == expected
    # Повторная регистрация вошедшего клиента не отправляет ещё одно письмо.
    assert callbacks == []
    assert len(mailoutbox) == 1

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
def test_register_rejects_mismatched_passwords(
    django_user_model, mailoutbox, django_capture_on_commit_callbacks,
):
    # CSRF корректен, но разные пароли дают ошибку поля без создания пользователя.
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    count_before = django_user_model.objects.count()
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = client.post('/api/v1/auth/register/', {
            'email': 'newuser@example.com',
            'username': 'user',
            'password': 'Violet!River-72-Copper',
            'password_confirm': 'Another!River-81-Copper',
        }, format='json', HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 400
    assert 'password_confirm' in response.json()
    assert 'no-store' in response['Cache-Control']
    assert django_user_model.objects.count() == count_before
    # Ошибка валидации не должна даже планировать отправку письма.
    assert callbacks == []
    assert mailoutbox == []

@pytest.mark.django_db
@pytest.mark.parametrize('email, expected_status', [
    ('EXISTING@example.com', 400),
    ('another@example.com', 201),
])
def test_register_duplicate_fields(
    django_user_model, user_factory, email, expected_status,
    mailoutbox, django_capture_on_commit_callbacks,
):
    # Два запуска: повтор email запрещён, повтор username с новым email разрешён.
    user_factory(
        email='existing@example.com',
    )
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    count_before = django_user_model.objects.count()
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
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
        assert callbacks == []
        assert mailoutbox == []
    else:
        assert django_user_model.objects.count() == count_before + 1
        assert len(callbacks) == 1
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == [email]

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
def test_login_requires_csrf(user_factory):
    # Правильного пароля недостаточно: без CSRF вход и создание сессии запрещены.
    password = 'passASD213!'
    user = user_factory(
        email='existing@example.com', password=password,
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



@pytest.mark.parametrize('endpoint', ['register', 'login', 'logout'])
def test_auth_csrf_error_is_json(endpoint):
    # Анонимные POST тоже защищены; ошибка данных не должна опередить CSRF.
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(f'/api/v1/auth/{endpoint}/', {}, format='json')
    assert response.status_code == 403
    assert response.json() == {
        'code': 'csrf_failed',
        'detail': 'Не удалось проверить запрос. Обновите страницу.',
    }
    assert 'no-store' in response['Cache-Control']


def test_admin_csrf_failure_keeps_html():
    # JSON-обработчик auth API не меняет стандартную CSRF-страницу Admin.
    client = APIClient(enforce_csrf_checks=True)
    response = client.post('/admin/login/', {})
    assert response.status_code == 403
    assert response['Content-Type'].startswith('text/html')


@pytest.mark.parametrize('endpoint', ['register', 'login', 'logout'])
def test_auth_get_does_not_allow_changes(endpoint):
    # Создание аккаунта, вход и выход доступны только через POST.
    response = APIClient().get(f'/api/v1/auth/{endpoint}/')
    assert response.status_code == 405
    assert 'no-store' in response['Cache-Control']

@pytest.mark.django_db
def test_send_registration_email(user_factory, mailoutbox):
    password = 'passABC123!'
    user = user_factory(
        password = password,
    )
    send_registration_email(user)
    assert len(mailoutbox) == 1
    message = mailoutbox[0]
    assert message.to == [user.email]
    assert message.subject == 'Регистрация в WorkBoard'
    assert 'Добро пожаловать в WorkBoard!' in message.body

    # В письмо не должны попасть ни исходный пароль, ни его хеш.
    assert password not in message.body
    assert user.password not in message.body


@pytest.mark.django_db
@pytest.mark.parametrize('delivery_error', [
    SMTPException('SMTP rejected the message'),
    ConnectionRefusedError('SMTP connection refused'),
], ids=['smtp_error', 'connection_error'])
def test_register_succeeds_when_email_delivery_fails(
    django_user_model, mailoutbox, django_capture_on_commit_callbacks,
    monkeypatch, caplog, delivery_error,
):
    # Подменяем только доставку: настоящая почтовая функция должна обработать исключение.
    def fail_delivery(*args, **kwargs):
        raise delivery_error

    monkeypatch.setattr('accounts.emails.send_mail', fail_delivery)
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    password = 'Violet!River-72-Copper'
    count_before = django_user_model.objects.count()

    # Выполняем callback, иначе тест не дошёл бы до подменённой отправки.
    with caplog.at_level(logging.ERROR, logger='accounts.emails'):
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            response = client.post('/api/v1/auth/register/', {
                'email': 'learner@example.com',
                'username': 'learner',
                'password': password,
                'password_confirm': password,
            }, format='json', HTTP_X_CSRFTOKEN=token)

    # Отказ SMTP не отменяет аккаунт и автоматический вход.
    assert response.status_code == 201, response.content
    assert django_user_model.objects.count() == count_before + 1
    user = django_user_model.objects.get(pk=response.json()['id'])
    assert user.email == 'learner@example.com'
    assert user.check_password(password)
    me_response = client.get('/api/v1/auth/me/')
    assert me_response.status_code == 200
    assert me_response.json() == response.json()
    assert len(callbacks) == 1
    assert mailoutbox == []

    # Причина доставки записана в лог, пароль и текст письма туда не попали.
    records = [record for record in caplog.records if record.name == 'accounts.emails']
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert records[0].exc_info[0] is type(delivery_error)
    assert str(delivery_error) in caplog.text
    assert password not in caplog.text
    assert user.password not in caplog.text
    assert 'Добро пожаловать в WorkBoard!' not in caplog.text
