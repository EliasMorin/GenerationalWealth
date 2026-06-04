from flask import Blueprint, request, jsonify
from ..utils.auth import require_auth, _get_github_token_for_request, GROQ_API_KEY, GROQ_MODEL, GITHUB_TOKENS, GITHUB_TOKEN, GITHUB_MODELS_URL, GITHUB_CLAUDE_MODEL
from ..utils.token_bucket import call_groq_api
import json
import traceback

# Create blueprint
claude_bp = Blueprint('claude', __name__)


@claude_bp.route('/status', methods=['GET'])
def claude_status():
    github_token = _get_github_token_for_request()
    return jsonify({
        'groq_configured': bool(GROQ_API_KEY),
        'github_configured': bool(GITHUB_TOKEN),
        'github_multi_account': len(GITHUB_TOKENS) > 1 if GITHUB_TOKENS else False,
        'available_models': {
            'groq': GROQ_MODEL if GROQ_API_KEY else None,
            'github_copilot': GITHUB_CLAUDE_MODEL if GITHUB_TOKEN else None
        }
    })


@claude_bp.route('/connect', methods=['POST', 'OPTIONS'])
def claude_connect():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json() or {}
    provider = data.get('provider', 'groq')  # groq or github
    model = data.get('model')

    # Validate provider
    if provider not in ['groq', 'github']:
        return jsonify({'status': 'error', 'message': 'Invalid provider'}), 400

    # For GitHub, check if token is available
    if provider == 'github' and not GITHUB_TOKEN:
        return jsonify({'status': 'error', 'message': 'GitHub token not configured'}), 400

    # For Groq, check if API key is available
    if provider == 'groq' and not GROQ_API_KEY:
        return jsonify({'status': 'error', 'message': 'Groq API key not configured'}), 400

    return jsonify({
        'status': 'connected',
        'provider': provider,
        'model': model or (GROQ_MODEL if provider == 'groq' else GITHUB_CLAUDE_MODEL)
    })


@claude_bp.route('/disconnect', methods=['POST', 'OPTIONS'])
def claude_disconnect():
    if request.method == 'OPTIONS':
        return '', 204
    return jsonify({'status': 'disconnected'})


@claude_bp.route('/bookmarklet/init', methods=['POST', 'OPTIONS'])
def claude_bookmarklet_init():
    if request.method == 'OPTIONS':
        return '', 204
    return jsonify({
        'status': 'ready',
        'instructions': 'Load the bookmarklet to start AI-powered browsing assistance'
    })


@claude_bp.route('/bookmarklet/submit', methods=['POST', 'OPTIONS'])
def claude_bookmarklet_submit():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json() or {}
    url = data.get('url')
    content = data.get('content')
    selector = data.get('selector')

    if not url:
        return jsonify({'status': 'error', 'message': 'URL required'}), 400

    # In a real implementation, this would process the content with AI
    # For now, just acknowledge receipt
    return jsonify({
        'status': 'received',
        'url': url,
        'content_length': len(content) if content else 0,
        'selector': selector
    })


@claude_bp.route('/bookmarklet/poll', methods=['GET'])
def claude_bookmarklet_poll():
    # Check if there are any pending AI tasks for the bookmarklet
    # This would typically check a queue or database
    return jsonify({
        'status': 'idle',
        'tasks': []
    })


@claude_bp.route('/browser-login/start', methods=['POST', 'OPTIONS'])
def claude_browser_login_start():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'status': 'error', 'message': 'Email and password required'}), 400

    # In a real implementation, this would start a browser automation process
    # For now, just acknowledge
    return jsonify({
        'status': 'started',
        'email': email,
        'message': 'Browser login process initiated'
    })


@claude_bp.route('/browser-login/status', methods=['GET'])
def claude_browser_login_status():
    # Check status of browser login process
    return jsonify({
        'status': 'idle',  # or 'in_progress', 'completed', 'failed'
        'progress': 0
    })


@claude_bp.route('/browser-login/reset', methods=['POST', 'OPTIONS'])
def claude_browser_login_reset():
    if request.method == 'OPTIONS':
        return '', 204
    return jsonify({'status': 'reset'})
