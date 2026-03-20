# config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration"""

    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    FLASK_APP = os.getenv('FLASK_APP', 'run.py')
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')

    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'giztech.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }

    # File uploads
    UPLOAD_FOLDER = os.path.join('app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}

    # Image optimization
    IMAGE_MAX_WIDTH = 1920
    IMAGE_MAX_HEIGHT = 1080
    IMAGE_QUALITY = 85
    THUMBNAIL_SIZE = (300, 300)

    # Cache
    CACHE_TYPE = os.getenv('CACHE_TYPE', 'SimpleCache')
    CACHE_DEFAULT_TIMEOUT = 300
    CACHE_REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_REFRESH_EACH_REQUEST = True

    # Security
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # Rate limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URL = os.getenv('REDIS_URL', 'memory://')
    RATELIMIT_DEFAULT = '200 per day; 50 per hour'
    RATELIMIT_STRATEGY = 'fixed-window'

    # CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    WTF_CSRF_SSL_STRICT = True

    # Mail (for future email notifications)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@giztech.com')

    # WhatsApp
    WHATSAPP_NUMBER = os.getenv('WHATSAPP_NUMBER', '265983142415')
    WHATSAPP_API_KEY = os.getenv('WHATSAPP_API_KEY')

    # Owner
    OWNER_PASSWORD = os.getenv('OWNER_PASSWORD', 'admin123')  # Change in production!

    # SEO
    SITE_NAME = 'GIZ-tech'
    SITE_URL = os.getenv('SITE_URL', 'https://buy-from-me.onrender.com')
    DEFAULT_META_TITLE = 'GIZ-tech - Premium Tech Products'
    DEFAULT_META_DESCRIPTION = 'Discover premium tech products at GIZ-tech. Quality gadgets and electronics for tech enthusiasts.'
    DEFAULT_META_IMAGE = '/static/images/og-image.jpg'

    # Pagination
    PRODUCTS_PER_PAGE = 12
    MESSAGES_PER_PAGE = 20

    # Feature flags
    ENABLE_ANALYTICS = True
    ENABLE_CACHING = True
    ENABLE_RATE_LIMITING = True
    ENABLE_CSRF = True

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/giztech.log')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FLASK_ENV = 'development'

    # Less strict security for development
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    WTF_CSRF_SSL_STRICT = False

    # Faster caching for development
    CACHE_TYPE = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 60

    # More lenient rate limiting
    RATELIMIT_ENABLED = False

    # SQLite for development
    SQLALCHEMY_DATABASE_URI = os.getenv('DEV_DATABASE_URL', 'sqlite:///dev.db')

    # Logging
    LOG_LEVEL = 'DEBUG'


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    FLASK_ENV = 'testing'

    # In-memory database for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

    # Disable features for testing
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    ENABLE_CACHING = False

    # File uploads in temp
    UPLOAD_FOLDER = '/tmp/giztech_test_uploads'

    # Logging
    LOG_LEVEL = 'ERROR'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FLASK_ENV = 'production'

    # Require strong secret key
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY must be set in production")

    # Use PostgreSQL in production
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

    # Redis for caching in production
    if os.getenv('REDIS_URL'):
        CACHE_TYPE = 'RedisCache'
        CACHE_REDIS_URL = os.getenv('REDIS_URL')
        RATELIMIT_STORAGE_URL = os.getenv('REDIS_URL')

    # Secure cookies
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True

    # Logging
    LOG_LEVEL = 'WARNING'


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}