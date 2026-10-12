from django.contrib.auth import authenticate, get_user_model, login, logout, settings
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils.cache import patch_cache_control
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.csrf import csrf_failure as django_csrf_failure
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.tokens import default_token_generator
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from functools import partial
from .emails import send_registration_email, send_password_reset_email
from .serializers import (
    RegisterSerializer,
    UserLoginSerializer,
    UserSerializer,
    PasswordResetSerializer
)

User = get_user_model()


def csrf_failure(request, reason=''):
    # CSRF может отклонить запрос до DRF, поэтому здесь нужен Django JsonResponse.
    if request.path.startswith('/api/v1/auth/'):
        response = JsonResponse({
            'code': 'csrf_failed',
            'detail': 'Не удалось проверить запрос. Обновите страницу.',
        }, status=403)
        patch_cache_control(response, no_store=True)
        return response
    # Для Admin и остальных страниц сохраняем стандартный ответ Django.
    return django_csrf_failure(request, reason=reason)


@method_decorator(csrf_protect, name='dispatch')
class AuthAPIView(APIView):
    """Общие правила только для auth API: CSRF, ошибки и запрет кеширования."""

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        if isinstance(exc, NotAuthenticated):
            response.data = {
                'code': 'not_authenticated',
                'detail': 'Необходим вход в приложение.',
            }
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        patch_cache_control(response, no_store=True)
        return response


class MeAPIView(AuthAPIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class CSRFAPIView(AuthAPIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'csrfToken': get_token(request)})


class RegisterAPIView(AuthAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if request.user.is_authenticated:
            return Response({
                'code': 'already_authenticated',
                'detail': 'Вы уже вошли в приложение.',
            }, status=409)
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            user = User.objects.create_user(
                email=data['email'],
                username=data['username'],
                password=data['password'],
            )
            transaction.on_commit(partial(send_registration_email, user=user))
        login(request, user)
        return Response(UserSerializer(user).data, status=201)


class LoginAPIView(AuthAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if request.user.is_authenticated:
            return Response({
                'code': 'already_authenticated',
                'detail': 'Вы уже вошли в приложение.',
            }, status=409)
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = authenticate(request, email=data['email'], password=data['password'])
        if user is None:
            return Response({
                'code': 'invalid_credentials',
                'detail': 'Неверная почта или пароль.',
            }, status=400)
        login(request, user)
        return Response(UserSerializer(user).data, status=200)


class LogoutAPIView(AuthAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Повторный выход тоже успешен: logout допустим для анонимного запроса.
        logout(request)
        return Response(status=204)


class PasswordResetAPIView(AuthAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = User.objects.filter(email=data['email'], is_active=True).first()
        if user is not None and user.has_usable_password():
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            frontend_url = settings.FRONTEND_URL.rstrip('/')
            reset_url = f'{frontend_url}/reset-password?uid={uid}&token={token}'
            send_password_reset_email(user, reset_url)
        return Response({
            'detail': (
                'Если для этого адреса доступно восстановление мы отправим письмо с инструкцией.'
            ),
        })