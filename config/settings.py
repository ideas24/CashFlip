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
    'TITLE': 'Cashflip Platform API',
    'DESCRIPTION': (
        '# Cashflip Platform API\n\n'
        'Complete API documentation for the Cashflip platform — a provably fair, '
        'real-money coin-flip game engine built for the African mobile-first market.\n\n'
        '---\n\n'
        '## API Products\n\n'
        '### 1. Partner / GaaS API (`/api/partner/v1/`)\n'
        'Games-as-a-Service integration for operators (e.g., betting platforms). '
        'Operators embed Cashflip into their apps via REST API with seamless wallet integration.\n\n'
        '### 2. OTP as a Service (`/api/otp/v1/`)\n'
        'Production-grade WhatsApp & SMS OTP delivery API. '
        'Businesses integrate OTP verification into their apps with tiered pricing, '
        'whitelabel sender IDs, rate limiting, and usage analytics.\n\n'
        '### 3. Game Features API (`/api/game/`)\n'
        'Player-facing endpoints for achievements, daily bonus wheel, feature config, '
        'and game operations.\n\n'
        '---\n\n'
        '## Authentication\n\n'
        '### Partner API (HMAC-SHA256)\n'
        'All Partner API requests must include:\n'
        '- `X-API-Key`: Your public API key (format: `cf_live_xxxx`)\n'
        '- `X-Signature`: HMAC-SHA256 of the raw request body using your API secret\n'
        '- `X-Timestamp` *(optional)*: Unix timestamp for replay protection (5-min window)\n\n'
        '### OTPaaS API (HMAC-SHA256)\n'
        'All OTPaaS requests must include:\n'
        '- `X-OTP-Key`: Your OTP API key (format: `otp_live_xxxx`)\n'
        '- `X-OTP-Signature`: HMAC-SHA256 of the raw request body using your OTP API secret\n'
        '- `X-OTP-Timestamp` *(optional)*: Unix timestamp for replay protection\n\n'
        '### Game API (JWT Bearer)\n'
        'Player-facing endpoints use JWT Bearer tokens:\n'
        '- `Authorization: Bearer <access_token>`\n'
        '- Access tokens expire in 60 minutes; refresh tokens last 7 days\n\n'
        '---\n\n'
        '## Seamless Wallet (Partner API)\n'
        'Cashflip does NOT hold operator player funds. Instead:\n'
        '1. **Game Start**: Cashflip calls your `debit_url` to deduct the stake\n'
        '2. **Win/Cashout**: Cashflip calls your `credit_url` to credit winnings\n'
        '3. **Failure**: Cashflip calls your `rollback_url` to reverse a failed debit\n\n'
        'Configure wallet URLs in the Cashflip admin portal or via your account manager.\n\n'
        '---\n\n'
        '## Provably Fair System\n'
        'Every game session is cryptographically verifiable:\n'
        '1. Game start → server provides SHA-256 hash of the server seed\n'
        '2. Each flip → result = HMAC-SHA256(server_seed, client_seed:nonce:flip_number)\n'
        '3. Game end → full server seed revealed for verification\n'
        '4. Public verify endpoint available per session\n\n'
        '---\n\n'
        '## OTPaaS Pricing Tiers\n\n'
        '| Tier | WhatsApp | SMS | Whitelabel | Base Fee |\n'
        '|------|----------|-----|------------|----------|\n'
        '| Starter | ₵0.030 | ₵0.050 | No | Free |\n'
        '| Growth | ₵0.020 | ₵0.035 | ₵200/mo | ₵50/mo |\n'
        '| Business | ₵0.012 | ₵0.025 | ₵500/mo | ₵200/mo |\n'
        '| Enterprise | ₵0.008 | ₵0.015 | Included | ₵500/mo |\n\n'
        '---\n\n'
        '## Rate Limits\n'
        '- **Partner API**: Configurable per API key (default 120 req/min)\n'
        '- **OTPaaS**: Configurable per client (default 60 req/min, 5 per phone/hour)\n'
        '- Rate limit headers: `X-RateLimit-Remaining`, `Retry-After`\n\n'
        '---\n\n'
        '## Support\n'
        '- Email: support@cashflip.amoano.com\n'
        '- Dashboard: https://console.cashflip.amoano.com\n'
    ),
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SERVERS': [
        {'url': 'https://demo.cashflip.amoano.com', 'description': 'Staging'},
        {'url': 'https://cashflip.amoano.com', 'description': 'Production'},
    ],
    'TAGS': [
        # Partner / GaaS
        {'name': 'Partner: Players', 'description': 'Register and authenticate operator players'},
        {'name': 'Partner: Game Config', 'description': 'Retrieve operator-specific game configuration'},
        {'name': 'Partner: Game Operations', 'description': 'Start sessions, flip, cashout, check state, history, and verify fairness'},
        {'name': 'Partner: Reports', 'description': 'GGR reports and detailed session reports'},
        {'name': 'Partner: Settlements', 'description': 'View settlement history and details'},
        {'name': 'Partner: Webhooks', 'description': 'Configure webhook endpoints for real-time event delivery'},
        # OTPaaS
        {'name': 'OTPaaS: Send & Verify', 'description': 'Send OTP codes via WhatsApp or SMS, and verify them'},
        {'name': 'OTPaaS: Status', 'description': 'Check delivery status of individual OTP requests'},
        {'name': 'OTPaaS: Billing & Usage', 'description': 'View prepaid balance, usage analytics, and pricing tiers'},
        # Game Features
        {'name': 'Game: Features', 'description': 'Feature configuration, achievement badges, and daily bonus wheel'},
    ],
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/api/',
    'SCHEMA_PATH_PREFIX_TRIM': False,
    'PREPROCESSING_HOOKS': ['config.spectacular_hooks.preprocess_exclude_admin'],
}

# ============ Celery ============
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/3')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/8')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Azure Redis requires SSL cert config when using rediss://
if CELERY_BROKER_URL.startswith('rediss://'):
    import ssl
    CELERY_BROKER_USE_SSL = {'ssl_cert_reqs': ssl.CERT_REQUIRED}
    CELERY_REDIS_BACKEND_USE_SSL = {'ssl_cert_reqs': ssl.CERT_REQUIRED}

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
TWILIO_FALLBACK_NUMBER = os.getenv('TWILIO_FALLBACK_NUMBER', '')

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
