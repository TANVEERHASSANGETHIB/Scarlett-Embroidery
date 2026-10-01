from pathlib import Path

import environ

SRC_DIR = Path(__file__).resolve().parent.parent.parent
APP_ROOT = SRC_DIR.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
)
environ.Env.read_env(APP_ROOT / ".env", overwrite=False)

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
SITE_URL = env("SITE_URL", default="http://localhost:8000").rstrip("/")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "channels",
    "apps.core",
    "apps.accounts",
    "apps.orders",
    "apps.blog",
    "apps.chat",
    "apps.console",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [SRC_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
                "apps.console.context_processors.console",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "core:home"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="America/Chicago")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = APP_ROOT / "staticfiles"
STATICFILES_DIRS = [SRC_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Public uploads (blog covers, portfolio photos)
MEDIA_URL = "/media/"
MEDIA_ROOT = env("MEDIA_ROOT", default=str(APP_ROOT / "media"))
# Private uploads (customer artwork, proofs, deliverables) — never served directly
PRIVATE_MEDIA_ROOT = env("PRIVATE_MEDIA_ROOT", default=str(APP_ROOT / "private_media"))

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 20
ORDER_UPLOAD_MAX_BYTES = 25 * 1024 * 1024
ARTWORK_EXTENSIONS = [
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "ai",
    "eps",
    "pdf",
    "svg",
    "psd",
    "cdr",
    "tif",
    "tiff",
]
DELIVERABLE_EXTENSIONS = ARTWORK_EXTENSIONS + [
    "dst",
    "pes",
    "exp",
    "jef",
    "vp3",
    "xxx",
    "hus",
    "emb",
    "zip",
    "rar",
    "7z",
]

# ── Outgoing mail ──────────────────────────────────────────
# Preferred: explicit SMTP credentials (EMAIL_HOST_USER may contain "@", which a
# URL would need escaped). Falls back to a single EMAIL_URL if EMAIL_HOST is unset.
# Credentials live in .env only — never in code, and never logged or shown in the UI.
if env("EMAIL_HOST", default=""):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=EMAIL_PORT == 587)
    EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=EMAIL_PORT == 465)
else:
    EMAIL_CONFIG = env.email("EMAIL_URL", default="consolemail://")
    vars().update(EMAIL_CONFIG)
IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "webp", "gif"]
PORTFOLIO_IMAGE_MAX_BYTES = env.int("PORTFOLIO_IMAGE_MAX_BYTES", default=10 * 1024 * 1024)

EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=30)
# Delivery happens on a background thread with retries, so a slow mail server
# never blocks a customer's request and a transient failure is retried.
EMAIL_SEND_IN_BACKGROUND = env.bool("EMAIL_SEND_IN_BACKGROUND", default=True)
EMAIL_MAX_ATTEMPTS = env.int("EMAIL_MAX_ATTEMPTS", default=3)
EMAIL_RETRY_DELAY_SECONDS = env.int("EMAIL_RETRY_DELAY_SECONDS", default=3)

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Scarlett Embroidery <no-reply@sedigitizer.com>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Fallback recipient for order alerts; the live value is editable in the console.
STAFF_NOTIFY_EMAIL = env("STAFF_NOTIFY_EMAIL", default="orders@sedigitizer.com")

# Email verification (6-digit code)
VERIFICATION_CODE_TTL_MINUTES = 15
VERIFICATION_CODE_MAX_ATTEMPTS = 5
VERIFICATION_RESEND_COOLDOWN_SECONDS = 60

# Trust X-Forwarded-For only when running behind our own reverse proxy
TRUST_PROXY_HEADERS = env.bool("TRUST_PROXY_HEADERS", default=True)

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {"django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False}},
}
