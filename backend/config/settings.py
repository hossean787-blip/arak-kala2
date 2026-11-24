import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv("ARAK_DEVELOPMENT") == "1"
SECRET_KEY = os.getenv("ARAK_SECRET_KEY") or (
    "insecure-local-development-key-arak-kala-do-not-deploy" if DEBUG else ""
)
ALLOWED_HOSTS = [host.strip() for host in os.getenv(
    "ARAK_ALLOWED_HOSTS", "localhost,127.0.0.1,10.0.2.2" if DEBUG else ""
).split(",") if host.strip()]
if not DEBUG and (len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5
                  or SECRET_KEY.startswith(("insecure-", "REPLACE_WITH_", "django-insecure-"))
                  or not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Set ARAK_SECRET_KEY and ARAK_ALLOWED_HOSTS for deployment.")

STORE_NAME = "اراک کالا"
STORE_MANAGER_EMAIL = os.getenv("ARAK_MANAGER_EMAIL", "hossean787@gmail.com").strip().lower()
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles", "store.apps.StoreConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "store.security.AuthThrottleMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": Path(os.getenv("ARAK_DB_PATH", str(BASE_DIR / "db.sqlite3"))),
    "OPTIONS": {"timeout": 12, "transaction_mode": "IMMEDIATE"},
}}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"
LANGUAGE_CODE = "fa"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = Path(os.getenv("ARAK_MEDIA_ROOT", str(BASE_DIR / "media")))
MEDIA_URL = "/uploads/"
DATA_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_REFERRER_POLICY = "same-origin"
if os.getenv("ARAK_TRUST_LOCAL_PROXY") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Proxy headers are deliberately ignored for rate limiting unless the gateway
# is explicitly trusted and overwrites X-Real-IP (never append client input).
ARAK_TRUST_REAL_IP = os.getenv("ARAK_TRUST_REAL_IP") == "1"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
