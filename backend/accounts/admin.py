from django.contrib.auth.admin import UserAdmin
from django.contrib import admin
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm


# Register your models here.
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    )