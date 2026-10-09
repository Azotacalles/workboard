from .base import *

DEBUG = True

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
]

# Локально frontend и backend работают по HTTP.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
