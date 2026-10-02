from django.urls import path
from .views import health_check

app_name = 'tasks'

urlpatterns = [
    path('', health_check, name='health_check'),
]