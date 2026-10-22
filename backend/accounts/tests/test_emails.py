import logging
from smtplib import SMTPException

import pytest
from rest_framework.test import APIClient

from accounts.emails import send_registration_email


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
