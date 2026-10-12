"""Django settings for trucksafe backend."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-secret-key-trucksafe-spotter-ai")

DEBUG = os.getenv("DJANGO_DEBUG", "1") in ("1", "true", "True")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(",")
    if host.strip()
]
if DEBUG and "*" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("*")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "trucksafe",
]

MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR.parent / "frontend" / "dist"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# LocMemCache (1 worker in production keeps cache consistent)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "trucksafe-cache",
        "TIMEOUT": int(os.getenv("WEATHER_CACHE_TTL_S", "1800")),
    }
}

REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "analyze": "12/min",
        "heatmap": "12/min",
    },
    "UNAUTHENTICATED_USER": None,
}

# Static and WhiteNoise configuration
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

SPA_DIR = BASE_DIR.parent / "frontend" / "dist"
if SPA_DIR.exists():
    WHITENOISE_ROOT = str(SPA_DIR)
    WHITENOISE_INDEX_FILE = True

CORS_ALLOW_ALL_ORIGINS = True

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Trucksafe Domain & Adapter Configuration
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")
ROUTING_PROVIDER = os.getenv("ROUTING_PROVIDER", "mapbox")
GEOCODE_COUNTRIES = os.getenv("GEOCODE_COUNTRIES", "us,ca")
TRUCK_MAX_AVG_SPEED_MPH = float(os.getenv("TRUCK_MAX_AVG_SPEED_MPH", "62"))
WEATHER_CACHE_TTL_S = int(os.getenv("WEATHER_CACHE_TTL_S", "1800"))
WIND_METRIC = os.getenv("WIND_METRIC", "sustained")
