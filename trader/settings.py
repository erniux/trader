import os
from dotenv import load_dotenv
from celery.schedules import crontab
from pathlib import Path
import environ

# Cargar variables del archivo .env
load_dotenv()

env = environ.Env()
environ.Env.read_env()  # Carga el archivo .env

# Ahora puedes acceder a las variables de entorno
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
BINANCE_TESTNET_API_KEY = os.getenv('BINANCE_TESTNET_API_KEY')
BINANCE_TESTNET_API_SECRET = os.getenv('BINANCE_TESTNET_API_SECRET')
TESTNET_BASE_URL = os.getenv('TESTNET_BASE_URL')

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-f#y8b%41ct4k)_%a=&yv-6gma=3gz!##svz_^$4j2x+m$)l)y^'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

import os

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'dashboard',
    'realtime.apps.RealtimeConfig',
    'django_celery_beat',
    "rest_framework",
    "django_filters",
    "rest_framework.authtoken",
    "drf_spectacular",
    "drf_spectacular_sidecar",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'trader.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, "templates")],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'trader.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('POSTGRES_DB'),
        'USER': env('POSTGRES_USER'),
        'PASSWORD': env('POSTGRES_PASSWORD'),
        'HOST': env('POSTGRES_HOST'),
        'PORT': env('POSTGRES_PORT'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

#docker exec -it postgres_db psql -U postgres -d postgres


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True
TIME_ZONE = 'UTC' 

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'

# Opcional: Ruta donde se recopilan los archivos estáticos al hacer collectstatic
#STATIC_ROOT = BASE_DIR / 'staticfiles'

# Carpetas adicionales donde buscar archivos estáticos
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,                # 50 señales por página (ajusta a gusto)
}

REST_FRAMEWORK.update({
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
})


SPECTACULAR_SETTINGS = {
    "TITLE": "Trader Signals API",
    "DESCRIPTION": "Endpoints para consultar señales de trading (SMA, RSI, etc.).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,   # solo sirve vía view
}



CELERY_BROKER_URL = "redis://redis:6379/0"
CELERY_RESULT_BACKEND = "redis://redis:6379"
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'


CELERY_BEAT_SCHEDULE = {
    # cada minuto ejecuta el cruce para BTCUSDT (SMA 3/5)
    "btc_load_prices": {
        "task": "dashboard.tasks.load_recent_prices",
        "schedule": 60.0,
        "args": ("BTCUSDT", 60),          # los últimos 60 candles (~1 h)
    },
    "btc_ma_cross": {
        "task": "dashboard.tasks.detectar_ma_cross",
        "schedule": 60.0,            # en segundos
        "args": ("BTCUSDT", 3, 5),
    },
    # ejemplo extra: cada 5 min para ETH
    "eth_ma_cross": {
        "task": "dashboard.tasks.detectar_ma_cross",
        "schedule": 300.0,
        "args": ("ETHUSDT", 5, 20),
    },

    "btc_rsi_extremos": {
        "task": "dashboard.tasks.detectar_rsi_extremos",
        "schedule": 60.0,                 # cada minuto
        "args": ("BTCUSDT", 14, 30, 70),
    },

    "btc_auto_trade": {
    "task": "dashboard.tasks.ejecutar_ordenes_por_senal",
    "schedule": 60.0,
    "args": ("BTCUSDT",),
},

    
}
