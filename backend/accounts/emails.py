from django.core.mail import send_mail

def send_registration_email(user, **kwargs):
    subject = 'Регистрация в WorkBoard'
    from_email = 'workboard@localhost.com'
    to = [user.email]
    message = 'Добро пожаловать в WorkBoard!'
    try:
        send_mail(subject, message, from_email, to)
    except Exception as e:
        pass