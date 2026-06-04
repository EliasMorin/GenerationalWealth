from flask import Blueprint, request, jsonify, session as flask_session
from ..models.user import AppUser
from ..utils.auth import require_auth, _get_github_token_for_request
import hashlib

# Create blueprint
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    github_token = (data.get('github_token') or '').strip()
    tr_phone = (data.get('tr_phone') or '').strip()
    tr_pin = (data.get('tr_pin') or '').strip()

    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Nom d\'utilisateur et mot de passe requis'}), 400
    if len(password) < 4:
        return jsonify({'status': 'error', 'message': 'Mot de passe trop court (min 4 caractères)'}), 400

    # Import here to avoid circular imports
    from .. import db

    if AppUser.query.filter_by(username=username).first():
        return jsonify({'status': 'error', 'message': 'Ce nom d\'utilisateur est déjà pris'}), 409

    is_first = AppUser.query.count() == 0
    user = AppUser(
        username=username,
        password_hash=AppUser.hash_password(password),
        github_token=github_token,
        tr_phone=tr_phone,
        tr_pin_hash=AppUser.hash_password(tr_pin) if tr_pin else '',
        is_admin=is_first,
    )
    db.session.add(user)
    db.session.commit()
    flask_session.permanent = True
    flask_session['app_user_id'] = user.id
    flask_session['app_username'] = user.username
    return jsonify({'status': 'ok', 'username': user.username, 'is_admin': user.is_admin}), 201


@auth_bp.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Identifiants requis'}), 400

    # Import here to avoid circular imports
    from .. import db

    user = AppUser.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'status': 'error', 'message': 'Identifiants incorrects'}), 401

    flask_session.permanent = True
    flask_session['app_user_id'] = user.id
    flask_session['app_username'] = user.username
    return jsonify({'status': 'ok', 'username': user.username, 'is_admin': user.is_admin})


@auth_bp.route('/logout', methods=['POST', 'OPTIONS'])
def logout():
    if request.method == 'OPTIONS':
        return '', 204
    flask_session.clear()
    return jsonify({'status': 'ok'})


@auth_bp.route('/status', methods=['GET'])
def status():
    # Import here to avoid circular imports
    from .. import db

    user = _get_current_app_user()
    if not user:
        return jsonify({'status': 'unauthenticated'})
    return jsonify({
        'status': 'authenticated',
        'username': user.username,
        'is_admin': user.is_admin,
        'has_github_token': bool(user.github_token),
        'has_tr_config': bool(user.tr_phone),
    })


@auth_bp.route('/update', methods=['POST', 'OPTIONS'])
@require_auth
def update():
    """Update current user's settings (github token, TR credentials, password)."""
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json(silent=True) or {}

    # Import here to avoid circular imports
    from .. import db

    user = _get_current_app_user()
    if not user:
        return jsonify({'status': 'error', 'message': 'Non authentifié'}), 401

    user = AppUser.query.get(user.id)
    if data.get('github_token') is not None:
        user.github_token = data['github_token'].strip()
    if data.get('tr_phone') is not None:
        user.tr_phone = data['tr_phone'].strip()
    if data.get('tr_pin') is not None and data['tr_pin']:
        user.tr_pin_hash = AppUser.hash_password(data['tr_pin'])
    if data.get('new_password') and len(data['new_password']) >= 4:
        user.password_hash = AppUser.hash_password(data['new_password'])
    db.session.commit()
    return jsonify({'status': 'ok'})


# Helper to get GitHub token for current user (falls back to config)
def _get_github_token_for_request():
    try:
        user = _get_current_app_user()
        if user and user.github_token:
            return user.github_token
    except Exception:
        pass
    # Multi-comptes : distribue les tokens par hash d'IP
    # Note: GITHUB_TOKENS would need to be imported from utils.auth
    try:
        from ..utils.auth import GITHUB_TOKENS, GITHUB_TOKEN
        if GITHUB_TOKENS:
            try:
                ip = _get_client_ip()
                idx = hash(ip) % len(GITHUB_TOKENS)
                return GITHUB_TOKENS[idx]
            except Exception:
                pass
        return GITHUB_TOKEN
    except ImportError:
        # Fallback if utils not available yet
        return ""

def _get_client_ip():
    """Returns the real client IP, considering X-Forwarded-For from proxies."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or '0.0.0.0'


def _get_current_app_user():
    """Returns the AppUser for the current session, or None."""
    uid = flask_session.get('app_user_id')
    if not uid:
        return None
    try:
        from ..models.user import AppUser
        return AppUser.query.get(uid)
    except Exception:
        return None