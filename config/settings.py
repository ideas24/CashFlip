"""
Cashflip - Django Settings
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'cf-insecure-dev-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Admin subdomain - only this host can access /admin/
ADMIN_DOMAIN = os.getenv('ADMIN_DOMAIN', 'manage.cashflip.amoano.com')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'corsheaders',
    'rest_framework',
    'django_filters',
    'import_export',
    'social_django',
    'drf_spectacular',
    # Cashflip apps
    'accounts',
    'game',
    'wallet',
    'payments',
    'ads',
    'referrals',
    'analytics',
    'partner',
    'dashboard',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'config.middleware.AdminHostRestrictionMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Custom user model
AUTH_USER_MODEL = 'accounts.Player'

# Database
DATABASES = {
    'default': dj_database_url.config(
        default='postgres://cashflip_user:cashflip_pass_2026@localhost:5432/cashflip_db'
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============ REST Framework ============
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'accounts.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/minute',
        'user': '120/minute',
        'otp': '3/minute',
        'flip': '100/minute',
    },
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ============ API Documentation (drf-spectacular) ============
SPECTACULAR_SETTINGS = {
    'TITLE': 'Cashflip Partner API',
    'DESCRIPTION': (
        'Games-as-a-Service API for Cashflip — a provably fair coin-flip game engine.\n\n'
        'Operators integrate via HMAC-signed API calls. Cashflip processes everything:\n'
        'game logic, provably fair verification, settlements, and webhooks.\n\n'
        '## Authentication\n'
        'All requests must include:\n'
        '- `X-API-Key`: Your API key\n'
        '- `X-Signature`: HMAC-SHA256 signature of the request body using your API secret\n'
        '- `X-Timestamp` (optional): Unix timestamp for replay protection\n\n'
        '## Seamless Wallet\n'
        'Cashflip calls your debit/credit/rollback endpoints per bet/win/refund.\n'
        'Configure these URLs in the Cashflip admin portal.\n\n'
        '## Provably Fair\n'
        'Every game session uses HMAC-SHA256 with server seed, client seed, and nonce.\n'
        'Server seed hash is provided at game start; full seed revealed after cashout/loss.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SERVERS': [
        {'url': 'https://demo.cashflip.amoano.com', 'description': 'Staging'},
    ],
    'TAGS': [
        {'name': 'Players', 'description': 'Player registration and authentication'},
        {'name': 'Game', 'description': 'Game operations: start, flip, cashout, state, history, verify'},
        {'name': 'Reports', 'description': 'GGR reports and session details'},
        {'name': 'Settlements', 'description': 'Settlement management'},
        {'name': 'Webhooks', 'description': 'Webhook configuration'},
    ],
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/api/partner/v1/',
}

# ============ Celery ============
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/3')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/8')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# ============ CORS ============
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'https://demo.cashflip.amoano.com').split(',')
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if os.getenv('CSRF_TRUSTED_ORIGINS') else []

# ============ Security ============
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ============ Domain ============
BACKEND_DOMAIN = os.getenv('BACKEND_DOMAIN', 'https://demo.cashflip.amoano.com')
SITE_URL = os.getenv('SITE_URL', 'https://demo.cashflip.amoano.com')

# ============ Payment: Orchard (CTM deposits) ============
ORCHARD_API_URL = os.getenv('ORCHARD_API_URL')
ORCHARD_SERVICE_ID = os.getenv('ORCHARD_SERVICE_ID')
ORCHARD_CLIENT_ID = os.getenv('ORCHARD_CLIENT_ID')
ORCHARD_SECRET_KEY = os.getenv('ORCHARD_SECRET_KEY')
ORCHARD_CALLBACK_URL = os.getenv('ORCHARD_CALLBACK_URL')

# ============ Payment: Orchard WANAOWN (MTC payouts) ============
ORCHARD_API_URL_WANAOWN = os.getenv('ORCHARD_API_URL_WANAOWN')
ORCHARD_SERVICE_ID_WANAOWN = os.getenv('ORCHARD_SERVICE_ID_WANAOWN')
ORCHARD_CLIENT_ID_WANAOWN = os.getenv('ORCHARD_CLIENT_ID_WANAOWN')
ORCHARD_SECRET_KEY_WANAOWN = os.getenv('ORCHARD_SECRET_KEY_WANAOWN')
ORCHARD_CALLBACK_URL_WANAOWN = os.getenv('ORCHARD_CALLBACK_URL_WANAOWN')

# ============ Orchard Proxy for Verification ============
ORCHARD_PROXY_URL = os.getenv('ORCHARD_PROXY_URL')

# ============ Payment: Paystack ============
PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY')
PAYSTACK_PUBLIC_KEY = os.getenv('PAYSTACK_PUBLIC_KEY')
PAYSTACK_CALLBACK_URL = os.getenv('PAYSTACK_CALLBACK_URL')
PAYSTACK_WEBHOOK_URL = os.getenv('PAYSTACK_WEBHOOK_URL')

# ============ Payment Reference Prefixes ============
# Staging: CF-PS-, CF-DEP-, CF-PAY-  |  Production: CFP-PS-, CFP-DEP-, CFP-PAY-
PAYMENT_PREFIX_PAYSTACK = os.getenv('PAYMENT_PREFIX_PAYSTACK', 'CF-PS-')
PAYMENT_PREFIX_DEPOSIT = os.getenv('PAYMENT_PREFIX_DEPOSIT', 'CF-DEP-')
PAYMENT_PREFIX_PAYOUT = os.getenv('PAYMENT_PREFIX_PAYOUT', 'CF-PAY-')

# ============ WhatsApp OTP (reachmint bot — authentication template) ============
WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv('WHATSAPP_BUSINESS_ACCOUNT_ID')
WHATSAPP_AUTH_TEMPLATE_NAME = os.getenv('WHATSAPP_AUTH_TEMPLATE_NAME', 'cashflip_auth_otp')

# ============ Twilio SMS OTP ============
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

# ============ Social Auth ============
AUTHENTICATION_BACKENDS = (
    'social_core.backends.google.GoogleOAuth2',
    'social_core.backends.facebook.FacebookOAuth2',
    'django.contrib.auth.backends.ModelBackend',
)

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.getenv('GOOGLE_CLIENT_ID', '')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
SOCIAL_AUTH_FACEBOOK_KEY = os.getenv('FACEBOOK_APP_ID', '')
SOCIAL_AUTH_FACEBOOK_SECRET = os.getenv('FACEBOOK_APP_SECRET', '')
SOCIAL_AUTH_FACEBOOK_SCOPE = ['email']

SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.user.create_user',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
    'accounts.pipeline.create_player_profile',
)

LOGIN_REDIRECT_URL = '/'
SOCIAL_AUTH_LOGIN_REDIRECT_URL = '/'

# ============ JWT ============
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
JWT_ACCESS_TOKEN_LIFETIME_MINUTES = int(os.getenv('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', '60'))
JWT_REFRESH_TOKEN_LIFETIME_DAYS = int(os.getenv('JWT_REFRESH_TOKEN_LIFETIME_DAYS', '7'))

# ============ Logging ============
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'cashflip.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': os.getenv('LOG_LEVEL', 'INFO'),
    },
}
