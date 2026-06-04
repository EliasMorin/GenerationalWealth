from flask import Blueprint, request, jsonify
import configparser
from ..models.user import AppUser
from ..utils.auth import require_auth, _get_github_token_for_request
from ..services.cash_analyzer import CashAnalyzer
from ..utils.db import db_load_generic

# Create blueprint
cash_bp = Blueprint('cash', __name__)


@cash_bp.route('/analysis', methods=['GET'])
def get_cash_analysis():
    # Try to get phone from header
    phone = request.headers.get('X-User-Phone')

    # Try to fallback to config if not in header (for monolithic app)
    if not phone:
        try:
            config = configparser.ConfigParser()
            config.read('config.ini')
            phone = config.get('secret', 'phone_number', fallback=None)
        except Exception:
            pass

    key = f'tr_transactions_{phone}' if phone else 'tr_transactions'

    # Load transactions
    transactions = db_load_generic(key)

    # Fallback: if specific key failed, try generic default
    if not transactions and phone:
        transactions = db_load_generic('tr_transactions')

    if not transactions:
        transactions = []

    analyzer = CashAnalyzer(transactions)
    result = analyzer.analyze()
    return jsonify({"status": "success", "data": result})


def _get_current_app_user():
    """Returns the AppUser for the current session, or None."""
    uid = request.headers.get('X-User-ID') or request.headers.get('X-User-Phone')  # Simplified for now
    if not uid:
        return None
    try:
        # Import here to avoid circular imports
        from ..models.user import AppUser
        # This is simplified - in reality we'd need to look up by phone or session
        return AppUser.query.first()  # Placeholder
    except Exception:
        return None
