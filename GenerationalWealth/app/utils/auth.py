import os
import json
import base64
import configparser
from typing import List, Optional
from datetime import datetime, timedelta

# Assuming these will be imported from Flask or defined locally if not available
try:
    from flask import session as flask_session
except ImportError:
    # Fallback if Flask not available
    flask_session = {}


def _load_groq_key() -> str:
    """Read Groq API key from environment variable or config.ini."""
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        try:
            _cfg = configparser.ConfigParser()
            _cfg.read("config.ini")
            key = _cfg.get("groq", "api_key", fallback="")
        except Exception:
            pass
    return key


def _load_github_tokens() -> List[str]:
    """Load all GitHub tokens from environment or config.ini.
    Supports api_token, api_token_2, api_token_3, ... for multi-account."""
    tokens = []
    # Environment variable (comma-separated)
    env_tokens = os.environ.get("GITHUB_TOKEN", "")
    if env_tokens:
        tokens = [t.strip() for t in env_tokens.split(',') if t.strip()]
    if not tokens:
        try:
            _cfg = configparser.ConfigParser()
            _cfg.read("config.ini")
            if _cfg.has_section("github"):
                # Get api_token, api_token_2, api_token_3, ...
                primary = _cfg.get("github", "api_token", fallback="").strip()
                if primary:
                    tokens.append(primary)
                idx = 2
                while True:
                    key = _cfg.get("github", f"api_token_{idx}", fallback="").strip()
                    if not key:
                        break
                    tokens.append(key)
                    idx += 1
        except Exception:
            pass
    return tokens


def _jwt_expiry(token: str) -> int:
    """Return the expiration timestamp (exp) of a JWT without verifying signature.
    Returns 0 on failure."""
    try:
        payload = token.split('.')[1]
        # Add padding if needed
        payload += '=' * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return int(data.get('exp', 0))
    except Exception:
        return 0


def _get_current_app_user():
    """Returns the AppUser for the current session, or None."""
    try:
        # Import here to avoid circular imports
        from ..models.user import AppUser
        uid = flask_session.get('app_user_id')
        if not uid:
            return None
        return AppUser.query.get(uid)
    except Exception:
        return None


def require_auth(f):
    """Decorator: returns 401 if no valid session."""
    from functools import wraps
    from flask import jsonify
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _get_current_app_user():
            return jsonify({'status': 'error', 'message': 'Non authentifié', 'code': 'UNAUTHENTICATED'}), 401
        return f(*args, **kwargs)
    return decorated


# Constants that would be initialized at module load
GROQ_API_KEY = _load_groq_key()
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

GITHUB_TOKENS = _load_github_tokens()
GITHUB_TOKEN = GITHUB_TOKENS[0] if GITHUB_TOKENS else ""
# GitHub Copilot API — access to Claude Sonnet 4.6 (included in Copilot Pro)
GITHUB_MODELS_URL = "https://api.githubcopilot.com/chat/completions"
GITHUB_CLAUDE_MODEL = "claude-sonnet-4.6"