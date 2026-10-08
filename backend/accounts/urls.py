from django.urls import path
from .views import MeAPIView, CSRFAPIView, RegisterAPIView, LoginAPIView, LogoutAPIView

app_name = 'accounts'

urlpatterns = [
    path('me/', MeAPIView.as_view(), name='me'),
    path('csrf/', CSRFAPIView.as_view(), name='csrf'),
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('login/', LoginAPIView.as_view(), name='login'),
    path('logout/', LogoutAPIView.as_view(), name='logout'),
]
