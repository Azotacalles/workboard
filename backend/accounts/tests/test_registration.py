from django.conf import settings
from django.db import IntegrityError
import pytest
from rest_framework.test import APIClient

from accounts.serializers import RegisterSerializer


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
@pytest.mark.parametrize('field, value', [
    ('email', None), ('username', None), ('password', None), ('password_confirm', None),
    ('email', 'not-an-email'), ('username', 'bad name!'), ('password', 'short'),
], ids=['missing_email', 'missing_username', 'missing_password', 'missing_confirmation',
        'invalid_email', 'invalid_username', 'weak_password'])
def test_register_rejects_invalid_fields(
    field, value, django_user_model, mailoutbox, django_capture_on_commit_callbacks,
):
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    payload = {'email': 'new@example.com', 'username': 'new',
               'password': 'Violet!River-72-Copper', 'password_confirm': 'Violet!River-72-Copper'}
    if value is None:
        del payload[field]
    else:
        payload[field] = value
        if field == 'password':
            payload['password_confirm'] = value
    count_before = django_user_model.objects.count()
    # Правильный CSRF позволяет дойти до валидации конкретного поля.
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = client.post('/api/v1/auth/register/', payload, format='json', HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 400
    assert field in response.json()
    assert django_user_model.objects.count() == count_before
    assert callbacks == []
    assert mailoutbox == []
    assert settings.SESSION_COOKIE_NAME not in client.cookies


@pytest.mark.django_db
def test_register_does_not_accept_privilege_flags(django_user_model):
    # Клиент может прислать лишние поля, но регистрация не выдаёт права администратора.
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    response = client.post('/api/v1/auth/register/', {
        'email': 'new@example.com', 'username': 'new',
        'password': 'Violet!River-72-Copper', 'password_confirm': 'Violet!River-72-Copper',
        'is_staff': True, 'is_superuser': True,
    }, format='json', HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 201
    user = django_user_model.objects.get(pk=response.json()['id'])
    assert user.is_staff is False
    assert user.is_superuser is False


@pytest.mark.django_db
@pytest.mark.parametrize('stored_email', ['existing@example.com', 'EXISTING@example.com'])
def test_register_handles_database_email_conflict(
    stored_email, user_factory, django_user_model, monkeypatch,
    mailoutbox, django_capture_on_commit_callbacks,
):
    existing = user_factory(email='existing@example.com')
    # Обход менеджера здесь намеренный: проверяем также ограничение Lower(email).
    django_user_model.objects.filter(pk=existing.pk).update(email=stored_email)
    # Имитируем устаревшую предварительную проверку. Это НЕ тест параллельных запросов:
    # вставка ниже действительно нарушает ограничение PostgreSQL после успешной валидации.
    monkeypatch.setattr(RegisterSerializer, 'validate_email',
                        lambda self, email: django_user_model.objects.normalize_email(email))
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    count_before = django_user_model.objects.count()
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = client.post('/api/v1/auth/register/', {
            'email': 'existing@example.com', 'username': 'new',
            'password': 'Violet!River-72-Copper', 'password_confirm': 'Violet!River-72-Copper',
        }, format='json', HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 400
    # Формат тот же, что у сериализатора: React объединяет список сообщений через .join().
    assert response.json() == {'email': ['Этот email уже занят.']}
    assert django_user_model.objects.count() == count_before
    assert callbacks == []
    assert mailoutbox == []
    assert settings.SESSION_COOKIE_NAME not in client.cookies


@pytest.mark.django_db
def test_register_does_not_hide_other_database_errors(
    user_factory, django_user_model, monkeypatch, mailoutbox, django_capture_on_commit_callbacks,
):
    existing = user_factory()

    def duplicate_primary_key(**kwargs):
        # Настоящая ошибка PostgreSQL, но на id, а не на email.
        django_user_model(pk=existing.pk, email=kwargs['email'], username=kwargs['username']).save(
            force_insert=True,
        )

    monkeypatch.setattr(django_user_model.objects, 'create_user', duplicate_primary_key)
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
    count_before = django_user_model.objects.count()
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with pytest.raises(IntegrityError) as captured:
            client.post('/api/v1/auth/register/', {
                'email': 'new@example.com', 'username': 'new',
                'password': 'Violet!River-72-Copper', 'password_confirm': 'Violet!River-72-Copper',
            }, format='json', HTTP_X_CSRFTOKEN=token)
    assert captured.value.__cause__.diag.constraint_name == 'accounts_user_pkey'
    assert django_user_model.objects.count() == count_before
    assert callbacks == []
    assert mailoutbox == []
    assert settings.SESSION_COOKIE_NAME not in client.cookies
