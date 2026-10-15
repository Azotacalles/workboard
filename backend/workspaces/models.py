from django.conf import settings
from django.db import models

# Create your models here.
class Workspace(models.Model):
    class Meta:
        ordering = ('-created_at', '-id')

    name = models.CharField(max_length=100, verbose_name='имя')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='дата создания')

    def __str__(self):
        return self.name

class Membership(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'user'],
                name='unique_workspace_user'
            )
        ]

    class Role(models.TextChoices):
        OWNER = 'OWNER', 'owner'

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='workspace_memberships')
    role = models.CharField(max_length=10, choices=Role.choices)
    joined_at = models.DateTimeField(auto_now_add=True)