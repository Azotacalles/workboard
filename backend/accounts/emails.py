from django.core.mail import send_mail
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