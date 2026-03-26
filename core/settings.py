"""
Django settings for core project.
"""

import importlib.util
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

try:
    import dj_database_url
except ImportError:  # pragma: no cover - local fallback for incomplete environments
    dj_database_url = None


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None, required=False):
    value = os.getenv(name, default)
    if required and not value:
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return value


def env_list(name, default=""):
    raw_value = env(name, default, required=False) or ""
    return [item.strip() for item in raw_value.split(",") if item.strip()]


DEBUG = env("DEBUG", "true").lower() == "true"
SECRET_KEY = env("SECRET_KEY", "dev-insecure-secret-key" if DEBUG else None, required=not DEBUG)

RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME")
default_allowed_hosts = [
    "127.0.0.1",
    "localhost",
    "testserver",
    "serverdenis.pp.ua",
]
if RENDER_EXTERNAL_HOSTNAME:
    default_allowed_hosts.append(RENDER_EXTERNAL_HOSTNAME)
ALLOWED_HOSTS = list(dict.fromkeys(default_allowed_hosts + env_list("ALLOWED_HOSTS")))


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tournament",
    "users",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
]
if importlib.util.find_spec("whitenoise") is not None:
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")
MIDDLEWARE += [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "core.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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


WSGI_APPLICATION = "core.wsgi.application"


# Database configuration: prefer DATABASE_URL (Render), then individual vars, then SQLite
database_url = env("DATABASE_URL")
db_name = env("DB_NAME")
db_user = env("DB_USER")
db_password = env("DB_PASSWORD")
db_host = env("DB_HOST")
db_port = env("DB_PORT")

if database_url and dj_database_url:
    DATABASES = {
        "default": dj_database_url.parse(database_url)
    }
elif database_url:
    raise ImproperlyConfigured(
        "DATABASE_URL задано, але пакет dj-database-url не встановлений."
    )
elif all([db_name, db_user, db_password, db_host, db_port]):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": db_name,
            "USER": db_user,
            "PASSWORD": db_password,
            "HOST": db_host,
            "PORT": db_port,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


AUTH_USER_MODEL = "users.CustomUser"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/redirect/"
LOGOUT_REDIRECT_URL = "/login/"


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "uk"
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True


STATIC_URL = "/static/"
if (BASE_DIR / "static").exists():
    STATICFILES_DIRS = [
        BASE_DIR / "static",
    ]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if importlib.util.find_spec("whitenoise") is not None
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_BACKEND = env("EMAIL_BACKEND", "")
if not EMAIL_BACKEND:
    if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
        EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    else:
        EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_USE_SSL = env("EMAIL_USE_SSL", "false").lower() == "true"
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "20"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "noreply@serverdenis.pp.ua")


default_csrf_trusted_origins = [
    "https://*.trycloudflare.com",
    "https://serverdenis.pp.ua",
    "https://*.onrender.com",
]
CSRF_TRUSTED_ORIGINS = list(
    dict.fromkeys(default_csrf_trusted_origins + env_list("CSRF_TRUSTED_ORIGINS"))
)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
