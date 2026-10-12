from django.core.mail import send_mail
from django.template.loader import render_to_string
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(filename='smtp.log', encoding='utf-8', level=logging.DEBUG)

def send_registration_email(user, **kwargs):
    subject = 'Регистрация в WorkBoard'
    from_email = 'workboard@localhost.com'
    to = [user.email]
    message = 'Добро пожаловать в WorkBoard!'
    try:
        send_mail(subject, message, from_email, to)
    except OSError:
        logger.exception(
            'Не удалось отправить приветственное письмо пользователю id=%s',
            user.pk,
        )

def send_password_reset_email(user, reset_url):
    message = render_to_string(
        'accounts/emails/password_reset.txt',
        {
            'username': user.username,
            'reset_url': reset_url,
        }
    )
    try:
        send_mail(
            subject='Восстановление пароля WorkBoard',
            message=message,
            from_email='workboard@localhost.com',
            recipient_list=[user.email],
        )
    except OSError:
        logger.exception(
            'Не удалось отправить письмо восстановления пользователю id=%s',
            user.pk,
        )