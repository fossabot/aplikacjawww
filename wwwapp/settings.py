# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
import socket
import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.7/howto/deployment/checklist/

# openshift is our PAAS for now.
ON_PAAS = 'OPENSHIFT_REPO_DIR' in os.environ

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.6/howto/deployment/checklist/

if ON_PAAS:
    SECRET_KEY = os.environ['OPENSHIFT_SECRET_TOKEN']
else:
    # SECURITY WARNING: keep the secret key used in production secret!
    SECRET_KEY = ')_7av^!cy(wfx=k#3*7x+(=j^fzv+ot^1@sh9s9t=8$bu@r(z$'

# SECURITY WARNING: don't run with debug turned on in production!
# adjust to turn off when on Openshift, but allow an environment variable to
# override on PAAS
DEBUG = not ON_PAAS
DEBUG = DEBUG or 'DEBUG' in os.environ
if ON_PAAS and DEBUG:
    print("*** Warning - Debug mode is on ***")

if ON_PAAS:
    ALLOWED_HOSTS = [os.environ['OPENSHIFT_APP_DNS'], socket.gethostname(), 'warsztatywww.pl', 'www.warsztatywww.pl']
else:
    ALLOWED_HOSTS = ["*"]

# E-mail settings

ADMINS = (('Sebastian Jaszczur', 'sebastian.jaszczur+aplikacjawww@gmail.com'),
          ('Marcin Wrochna', 'mwrochna+django@gmail.com'),
          ('Michał Zieliński', 'michal@zielinscy.org.pl'),
          )

MANAGERS = (('Sebastian Jaszczur', 'sebastian.jaszczur+aplikacjawww@gmail.com'),
            ('Marcin Wrochna', 'mwrochna+django@gmail.com'),
            ('Michał Zieliński', 'michal@zielinscy.org.pl'),
            )

if ON_PAAS:
    if 'GMAIL_ADDRESS' in os.environ and 'GMAIL_PASSWORD' in os.environ:
        EMAIL_HOST = "smtp.gmail.com"
        EMAIL_PORT = 587
        EMAIL_HOST_USER = os.environ['GMAIL_ADDRESS']
        EMAIL_USE_TLS = True
        EMAIL_HOST_PASSWORD = os.environ['GMAIL_PASSWORD']
    else:
        print("ERROR: There is no Gmail credentials!")

# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'allaccess',
    'crispy_forms',
    'django_select2',
    'django_bleach',
    'compressor',
    'wwwapp',
    'django_cleanup',
)

if DEBUG:
    INSTALLED_APPS = INSTALLED_APPS + ('debug_toolbar',)

MIDDLEWARE = (
    'django.middleware.common.BrokenLinkEmailsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

if DEBUG:
    MIDDLEWARE = ('debug_toolbar.middleware.DebugToolbarMiddleware',) + MIDDLEWARE

ROOT_URLCONF = 'wwwapp.urls'

WSGI_APPLICATION = 'wwwapp.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.7/ref/settings/#databases

if ON_PAAS and "OPENSHIFT_POSTGRESQL_DB_USERNAME" in os.environ:
    # determine if we are on MySQL or POSTGRESQL
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': os.environ['OPENSHIFT_APP_NAME'],
            'USER': os.environ['OPENSHIFT_POSTGRESQL_DB_USERNAME'],
            'PASSWORD': os.environ['OPENSHIFT_POSTGRESQL_DB_PASSWORD'],
            'HOST': os.environ['OPENSHIFT_POSTGRESQL_DB_HOST'],
            'PORT': os.environ['OPENSHIFT_POSTGRESQL_DB_PORT'],
        }
    }
else:
    # stock django
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': 'database.sqlite3',
        }
    }

# Set cripsy forms template pack
CRISPY_TEMPLATE_PACK = 'bootstrap3'
SELECT2_BOOTSTRAP = True

# Which HTML tags are allowed
BLEACH_ALLOWED_TAGS = [
    'p', 'b', 'i', 'u', 'em', 'strong', 'a', 'pre', 'div', 'strong', 'sup', 'sub', 'ol', 'ul', 'li', 'address',
    'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'code', 'table', 'tbody', 'tr', 'td', 'hr', 'img',
]

# Which HTML attributes are allowed
BLEACH_ALLOWED_ATTRIBUTES = [
    'href', 'title', 'style', 'alt', 'src', 'dir', 'class', 'border', 'cellpadding', 'cellspacing', 'id',
    'name', 'align',
]

# Which CSS properties are allowed in 'style' attributes (assuming
# style is an allowed attribute)
BLEACH_ALLOWED_STYLES = [
    'font-family', 'font-weight', 'text-decoration', 'font-variant', 'float', 'height', 'width', 'margin-right',
    'margin-left', 'text-align', 'title', 'page-break-after', 'display', 'color', 'background-color',
    'margin', 'padding-top', 'font-size', 'border-bottom-width', 'border-bottom-style', 'border-bottom-color',
    'line-height', 'border-collapse', 'border-spacing', 'empty-cells',
]

# Strip unknown tags if True, replace with HTML escaped characters if
# False
BLEACH_STRIP_TAGS = True

# Strip comments, or leave them in.
BLEACH_STRIP_COMMENTS = False

# Logging and authentication

LOGIN_URL = '/login/'

LOGIN_REDIRECT_URL = '/login/'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allaccess.backends.AuthorizedServiceBackend',
)

# Internationalization
# https://docs.djangoproject.com/en/1.7/topics/i18n/

LANGUAGE_CODE = 'pl'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.7/howto/static-files/
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(BASE_DIR, 'static'),
)
STATIC_ROOT = os.path.join(BASE_DIR, os.pardir, 'static')
STATIC_URL = '/static/'

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

MEDIA_URL = '/media/'
if 'OPENSHIFT_DATA_DIR' in os.environ:
    MEDIA_ROOT = os.path.join(os.environ.get('OPENSHIFT_DATA_DIR', ''), 'media')
else:
    MEDIA_ROOT = os.path.join(BASE_DIR, *MEDIA_URL.strip("/").split("/"))

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.request',
                'django.template.context_processors.debug',
                'django.template.context_processors.media',
                'django.template.context_processors.i18n',
                'django.template.context_processors.static',
                'allaccess.context_processors.available_providers',
            ],
        },
    },
]

CURRENT_YEAR = 2019
WORKSHOPS_START_DATE = datetime.date(2019, 7, 1)
WORKSHOPS_END_DATE = datetime.date(2019, 7, 13)

COMPRESS_ENABLED = True

if ON_PAAS and not DEBUG:
    GOOGLE_ANALYTICS_KEY = 'UA-12926426-8'
else:
    GOOGLE_ANALYTICS_KEY = None

if ON_PAAS:
    INSTALLED_APPS = INSTALLED_APPS + (
        'raven.contrib.django.raven_compat',
    )

    RAVEN_CONFIG = {
        'dsn': 'https://4709ef020c9f4ab5b69d5b910829ca88:23aca2a24534495893f31c96cd893b74@sentry.civsync.com/11',
    }

INTERNAL_IPS = [
    '127.0.0.1',
]

# Max amount of points that a participant can get during qualification (relative to configured max_points for a given workshop)
# This allows to give some people bonus points above 100%
MAX_POINTS_PERCENT = 200
