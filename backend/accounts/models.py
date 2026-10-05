from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower

from .managers import UserManager

# Create your models here.
class User(AbstractUser):
    class Meta:
        constraints = [
            UniqueConstraint(Lower('email'), name='unique_email'),
        ]

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=50, unique=False, validators=[AbstractUser.username_validator])
    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def __str__(self):
        return self.email