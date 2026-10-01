import tempfile

from .base import *  # noqa: F403

DEBUG = False
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405 - async tests must not hold connections open
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_SEND_IN_BACKGROUND = False  # tests assert on mail.outbox
EMAIL_MAX_ATTEMPTS = 1
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MEDIA_ROOT = tempfile.mkdtemp(prefix="se-media-")
PRIVATE_MEDIA_ROOT = tempfile.mkdtemp(prefix="se-private-")
