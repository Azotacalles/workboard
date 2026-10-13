from django.contrib.auth import authenticate, get_user_model, login, logout, settings
from django.db import transaction, IntegrityError
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils.cache import patch_cache_control
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views.csrf import csrf_failure as django_csrf_failure
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers
from functools import partial
from .emails import send_registration_email, send_password_reset_email
from .serializers import (
    RegisterSerializer,
    UserLoginSerializer,
    UserSerializer,
    PasswordResetSerializer, PasswordResetConfirmSerializer
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
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=data['email'],
                    username=data['username'],
                    password=data['password'],
                )
                transaction.on_commit(partial(send_registration_email, user=user))
        except IntegrityError as error:
             # Исходная ошибка PostgreSQL содержит имя нарушенного ограничения.
            constraint_name = error.__cause__.diag.constraint_name

            if constraint_name in {
                'unique_email',
                'accounts_user_email_b2644a56_uniq',
            }:
                # Возвращаем такую же ошибку поля, как при проверке сериализатора.
                raise serializers.ValidationError({
                    'email': 'Этот email уже занят.',
                }) from error

            # Другие ошибки базы не выдаём за занятую почту.
            raise

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

class PasswordResetConfirmAPIView(AuthAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        uid = urlsafe_base64_decode(data.get('uid')).decode()
        with transaction.atomic():
            try:
                user = User.objects.select_for_update().get(pk=uid)
            except (ValueError, TypeError, OverflowError, User.DoesNotExist) as exception:
                return Response({
                    'code': 'invalid_reset_link',
                    'detail': 'Ссылка недействительна или устарела. Запросите новую.'
                }, status=400)
            if user.is_active == False or not default_token_generator.check_token(user, data.get('token')):
                return Response({
                    'code': 'invalid_reset_link',
                    'detail': 'Ссылка недействительна или устарела. Запросите новую.'
                }, status=400)
            if data.get('password') != data.get('password_confirm'):
                raise serializers.ValidationError({'password_confirm': 'Пароли не совпадают.'})
            try:
                validate_password(data.get('password'), user=user)
            except DjangoValidationError as exception:
                raise serializers.ValidationError({'password': exception.messages})
            user.set_password(data.get('password'))
            user.save()
        return Response(status=204)