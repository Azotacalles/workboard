from urllib.parse import urlsplit, parse_qs

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def reset_request(mailoutbox):
    # Общая подготовка: настоящий запрос письма и параметры именно из полученной ссылки.
    # Пользователя передаёт тест, чтобы при необходимости сначала создать старые сессии.
    def request_reset(user):
        client = APIClient(enforce_csrf_checks=True)
        csrf_token = client.get('/api/v1/auth/csrf/').json()['csrfToken']
        response = client.post('/api/v1/auth/password-reset/', {'email': user.email},
                               format='json', HTTP_X_CSRFTOKEN=csrf_token)
        assert response.status_code == 200, response.content
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == [user.email]

        reset_url = None
        for line in mailoutbox[0].body.splitlines():
            if line.strip().startswith(('http://', 'https://')):
                reset_url = line.strip()
                break
        assert reset_url is not None
        assert '&amp;' not in reset_url
        params = parse_qs(urlsplit(reset_url).query)
        password = 'Violet!River-72-Copper'
        payload = {
            'uid': params['uid'][0],
            'token': params['token'][0],
            'password': password,
            'password_confirm': password,
        }
        return client, csrf_token, payload

    return request_reset
