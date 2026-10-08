from django.urls import path
from .views import me, csrf, RegisterAPIView, LoginAPIView

app_name = 'accounts'

urlpatterns = [
    path('me/', me, name='me'),
    path('csrf/', csrf, name='csrf'),
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('login/', LoginAPIView.as_view(), name='login'),
]