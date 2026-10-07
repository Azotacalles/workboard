from django.urls import path
from .views import me, csrf

app_name = 'accounts'

urlpatterns = [
    path('me/', me, name='me'),
    path('csrf/', csrf, name='csrf'),
]