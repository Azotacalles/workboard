from django.db import models

# Create your models here.
class Workboard(models.Model):
    class Meta:
        ordering = ('-created_at', '-id')

    name = models.CharField(max_length=100, verbose_name='имя')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='дата создания')

    def __str__(self):
        return self.name