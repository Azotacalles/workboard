from django.urls import path
from .views import me

app_name = 'accounts'

urlpatterns = [
    path('me/', me, name='me'),
]