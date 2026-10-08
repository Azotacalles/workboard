from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from django.contrib.auth import get_user_model


User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email')


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField(max_length=50, validators=[User.username_validator])
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_email(self, value):
        email = User.objects.normalize_email(value)

        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Этот email уже занят.")

        return email

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Пароли не совпадают.'})
        user = User(
            email=data['email'],
            username=data['username'],
        )
        try:
            validate_password(data['password'], user=user)
        except DjangoValidationError as exception:
            raise serializers.ValidationError({'password': exception.messages})
        return data


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_email(self, data):
        email = User.objects.normalize_email(data)
        return email