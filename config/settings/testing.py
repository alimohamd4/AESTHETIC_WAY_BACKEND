"""
AESTHETIC WAY Backend - Test Settings
Uses SQLite for speed; no Redis/Celery required.
"""
import tempfile

from .base import *  # noqa: F401, F403

DEBUG = True


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Use local-memory cache for tests (OTP service writes here)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}

# Celery always eager in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Use fast password hashing in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Use mock SMS provider — tests inspect MockSmsProvider.sent_messages
SMS_PROVIDER = "mock"

# Fixed OTP secret for reproducible tests
OTP_SECRET_KEY = "test-otp-secret-key-do-not-use-in-production"

# Disable throttling in tests
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

MEDIA_ROOT = tempfile.mkdtemp(prefix="aw_test_media_")

