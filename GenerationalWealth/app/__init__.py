import os
import logging
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

# Initialize extensions
db = SQLAlchemy()
cors = CORS()


def create_app(config_object=None):
    """
    Application factory pattern for creating Flask app instances.

    Args:
        config_object: Configuration object to use (optional)

    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)

    # Load configuration
    if config_object is None:
        # Import and use the config from config.py
        from .config import load_config
        config_object = load_config()

    app.config.from_object(config_object)

    # Initialize extensions
    db.init_app(app)
    cors.init_app(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    # Register blueprints
    from .api.auth import auth_bp
    from .api.portfolio import portfolio_bp
    from .api.market import market_bp
    from .api.claude import claude_bp
    from .api.institutional import institutional_bp
    from .api.cash import cash_bp
    from .api.ai import ai_bp
    from .api.refresh import refresh_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(portfolio_bp, url_prefix='/api/portfolio')
    app.register_blueprint(market_bp, url_prefix='/api/market')
    app.register_blueprint(claude_bp, url_prefix='/api/claude')
    app.register_blueprint(institutional_bp, url_prefix='/api/institutional')
    app.register_blueprint(cash_bp, url_prefix='/api/cash')
    app.register_blueprint(ai_bp, url_prefix='/api/ai')
    app.register_blueprint(refresh_bp, url_prefix='/api/refresh')

    # Add CORS headers after request (maintaining existing behavior)
    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-User-Phone'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        return response

    # Initialize database tables
    with app.app_context():
        db.create_all()

        # Initialize cache if needed
        try:
            from .utils.cache import ensure_isin_cache
            ensure_isin_cache()
        except ImportError:
            pass  # Cache utils might not be ready yet

    # Start background tasks
    start_background_tasks(app)

    return app


def start_background_tasks(app):
    """Start background tasks for the application."""
    try:
        # Import and start live updates thread
        from .tasks.live_updates import start_live_updates_thread
        start_live_updates_thread(app)

        # Import and start session watchdog thread
        from .tasks.session_watchdog import start_session_watchdog_thread
        start_session_watchdog_thread(app)

        print("[OK] Background tasks started")
    except Exception as e:
        print(f"[WARN] Could not start background tasks: {e}")


# Import request at the module level for use in add_cors_headers
from flask import request
