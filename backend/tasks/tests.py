from django.urls import reverse


def test_health_check(client):
    response = client.get(reverse("tasks:health_check"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}