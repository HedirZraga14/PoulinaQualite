from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path: Path, override: bool = False):
    if not path.exists():
        return

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (override or key not in os.environ):
            os.environ[key] = value


load_env_file(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'replace-me')

DEBUG = True

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost,host.docker.internal').split(',')
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        'DJANGO_CSRF_TRUSTED_ORIGINS',
        'http://127.0.0.1:4200,http://localhost:4200',
    ).split(',')
    if origin.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'user.apps.UserConfig',
]

AUTH_USER_MODEL = 'user.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'stage_project.middleware.ApiNoCacheMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'stage_project.urls'

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

WSGI_APPLICATION = 'stage_project.wsgi.application'

# Database configuration.
DB_ENGINE = os.environ.get('DB_ENGINE', 'sqlserver').strip().lower()

if DB_ENGINE == 'sqlite':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    mssql_name = os.environ.get('MSSQL_NAME', 'stage_db').strip() or 'stage_db'
    mssql_host = os.environ.get('MSSQL_HOST', r'HEDIRE\MSSQLSERVER05').strip() or r'HEDIRE\MSSQLSERVER05'
    mssql_port = os.environ.get('MSSQL_PORT', '1433').strip() or '1433'
    mssql_user = os.environ.get('MSSQL_USER', '').strip()
    mssql_password = os.environ.get('MSSQL_PASSWORD', '').strip()
    mssql_driver = os.environ.get('MSSQL_DRIVER', 'ODBC Driver 18 for SQL Server').strip() or 'ODBC Driver 18 for SQL Server'
    mssql_encrypt = os.environ.get('MSSQL_ENCRYPT', 'yes').strip().lower()
    mssql_trust_cert = os.environ.get('MSSQL_TRUST_SERVER_CERTIFICATE', 'yes').strip().lower()
    mssql_timeout = os.environ.get('MSSQL_CONNECTION_TIMEOUT', '30').strip() or '30'
    mssql_conn_max_age = int(os.environ.get('MSSQL_CONN_MAX_AGE', '300').strip() or '300')
    mssql_trusted = os.environ.get('MSSQL_TRUSTED_CONNECTION', 'yes').strip().lower() in {'1', 'true', 'yes', 'on'}

    extra_params = [
        f'Encrypt={mssql_encrypt}',
        f'TrustServerCertificate={mssql_trust_cert}',
        f'Connection Timeout={mssql_timeout}',
    ]

    if mssql_trusted and not mssql_user:
        extra_params.append('Trusted_Connection=yes')

    DATABASES = {
        'default': {
            'ENGINE': 'mssql',
            'NAME': mssql_name,
            'HOST': mssql_host,
            'PORT': mssql_port,
            'USER': mssql_user,
            'PASSWORD': mssql_password,
            'CONN_MAX_AGE': mssql_conn_max_age,
            'OPTIONS': {
                'driver': mssql_driver,
                'extra_params': ';'.join(extra_params),
            },
        }
    }

SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('GMAIL_USER', 'hedirzraga@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '123456789123456789')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
