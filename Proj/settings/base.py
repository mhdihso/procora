from pathlib import Path
import os
from decouple import config
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent



SECRET_KEY = config('SECRET_KEY')


ALLOWED_HOSTS = ['*']
CORS_ORIGIN_ALLOW_ALL = True

# Application definition
AUTH_USER_MODEL = 'account.User'
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'corsheaders',
    'drf_yasg',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'Proj.apps.authentication',
    'Proj.apps.account',
    'Proj.apps.main',

]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

INTERNAL_IPS = [
    # ...
    '127.0.0.1',
    # ...
]


ROOT_URLCONF = 'Proj.urls'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': (
        'rest_framework.schemas.coreapi.AutoSchema'
    ),
    'DEFAULT_PAGINATION_CLASS': 'Proj.apps.main.classes.CustomPageNumberPagination',
    'PAGE_SIZE': 30,
    'DATETIME_FORMAT': '%Y/%m/%d %H:%M',
    'DATETIME_INPUT_FORMATS': ['%Y/%m/%d %H:%M', '%Y-%m-%d %H:%M'],
    'DATE_FORMAT': '%Y/%m/%d',
    'DATE_INPUT_FORMATS': ['%Y/%m/%d', '%Y-%m-%d'],
    'TIME_FORMAT': '%H:%M',
    'TIME_INPUT_FORMATS': ['%H:%M', ],
}
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        "Auth Token eg [Bearer {JWT}]": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header"
        }
    }
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=90),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=120),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',

    'JTI_CLAIM': 'jti',

    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'Proj.wsgi.application'

# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

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

# Password Hashing Algorithm
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]


LANGUAGE_CODE = 'en'

TIME_ZONE = 'Asia/Tehran'
# TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True



STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static/')
MEDIA_URL = 'media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


TOKEN_HASH_ALGORITHM = config('TOKEN_HASH_ALGORITHM')
REFRESH_TOKEN_SECRET = config('REFRESH_TOKEN_SECRET')
DATA_UPLOAD_MAX_MEMORY_SIZE = 100242880

JAZZMIN_SETTINGS = {
    "site_title": "Proj Admin",
    "site_header": "Proj",
    "site_brand": "Proj",
    "welcome_sign": "Welcome to Proj admin panel",
    "search_model": "account.User",
    "user_avatar": None,
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "related_modal_active": False,
    "custom_css": None,
    "custom_js": None,
    "show_ui_builder": False,
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
