"""Django settings for the Smart Attendance System.

All deployment-specific values come from environment variables (optionally
loaded from a local ``.env`` file) so that the same code runs unchanged on a
developer laptop, in a Docker container and on a cloud platform such as Render.
"""
import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
DEBUG = env_bool("DEBUG", False)

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "insecure-development-key-do-not-use-in-production"
    else:
        raise RuntimeError("The SECRET_KEY environment variable is required when DEBUG is off.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if _render_host:
    ALLOWED_HOSTS.append(_render_host)

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
if _render_host:
    CSRF_TRUSTED_ORIGINS.append(f"https://{_render_host}")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "accounts",
    "attendance",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------
# Database: SQLite by default, PostgreSQL when DATABASE_URL is set
# --------------------------------------------------------------------------
# An empty DATABASE_URL (as in .env.example) must fall back to SQLite, so it is
# treated as "not set" instead of being passed to dj_database_url.
DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL", "").strip() or f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

# --------------------------------------------------------------------------
# Users and passwords
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# Internationalisation
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Budapest"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Static files (only the Django admin needs them; the SPA is hosted separately)
# --------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Django REST framework and JWT
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "300/min",
        "login": "10/min",
        "scan": "20/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("ACCESS_TOKEN_MINUTES", 30)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("REFRESH_TOKEN_DAYS", 1)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --------------------------------------------------------------------------
# CORS
# --------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

# --------------------------------------------------------------------------
# Attendance rules
# --------------------------------------------------------------------------
ATTENDANCE = {
    # A QR token is valid for its own time window plus this many older windows.
    "QR_GRACE_WINDOWS": env_int("QR_GRACE_WINDOWS", 1),
    # Reject check-ins whose reported GPS accuracy is worse than this (metres).
    "MAX_GPS_ACCURACY_M": env_int("MAX_GPS_ACCURACY_M", 100),
    # Students below this attendance rate (percent) are flagged "at risk".
    "AT_RISK_THRESHOLD": 60,
}

# --------------------------------------------------------------------------
# Security hardening (active when DEBUG is off, e.g. on Render)
# --------------------------------------------------------------------------
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 3600)

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
