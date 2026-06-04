"""
Configuration module for the Generational Wealth application.
Handles loading configuration from environment variables, config.ini, and provides defaults.
"""

import os
import configparser
import hashlib
from datetime import timedelta


class Config:
    """Base configuration class."""

    # Flask settings
    SECRET_KEY = None
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    # SQLAlchemy settings
    SQLALCHEMY_DATABASE_URI = 'sqlite:///financial_terminal_multiuser.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 30,
        'max_overflow': 50,
        'pool_timeout': 60,
        'pool_recycle': 1800
    }

    # CORS settings (handled by flask-cors extension)
    CORS_ORIGINS = "*"
    CORS_SUPPORTS_CREDENTIALS = True

    @staticmethod
    def init_app(app):
        """Initialize application with configuration."""
        pass


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    """Testing configuration."""
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


def load_config():
    """
    Load configuration from config.ini and environment variables.

    Returns:
        Config: Configuration object
    """
    # Determine which config to use
    config_name = os.environ.get('FLASK_ENV', 'development').lower()

    if config_name == 'production':
        config = ProductionConfig()
    elif config_name == 'testing':
        config = TestingConfig()
    else:
        config = DevelopmentConfig()

    # Load settings from config.ini if it exists
    config_parser = configparser.ConfigParser()
    if os.path.exists('config.ini'):
        config_parser.read('config.ini')

        # Override SECRET_KEY if present in config.ini
        try:
            secret_key = config_parser.get("app", "secret_key", fallback=None)
            if secret_key:
                config.SECRET_KEY = secret_key
        except (configparser.NoSectionError, configparser.NoOptionError):
            pass

        # Override database URI if present
        try:
            db_uri = config_parser.get("database", "uri", fallback=None)
            if db_uri:
                config.SQLALCHEMY_DATABASE_URI = db_uri
        except (configparser.NoSectionError, configparser.NoOptionError):
            pass

    # Generate secret key if not set
    if not config.SECRET_KEY:
        config.SECRET_KEY = _load_or_generate_secret_key(config_parser)

    return config


def _load_or_generate_secret_key(config_parser):
    """Load secret key from config or generate a stable one."""
    try:
        _sk = config_parser.get("app", "secret_key", fallback="")
        if not _sk:
            _sk = hashlib.sha256(os.urandom(32)).hexdigest()
            # Persist it so sessions survive restarts
            try:
                if not config_parser.has_section("app"):
                    config_parser.add_section("app")
                config_parser.set("app", "secret_key", _sk)
                with open("config.ini", "w") as _f:
                    config_parser.write(_f)
            except Exception:
                pass  # If we can't write, continue with generated key
        return _sk
    except Exception:
        # Ultimate fallback
        return hashlib.sha256(os.urandom(32)).hexdigest()


# Configuration mapping
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}