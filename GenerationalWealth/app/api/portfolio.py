from flask import Blueprint, request, jsonify
from ..utils.db import db_load_latest_portfolio, db_save_portfolio
from ..services.trade_republic import TradeRepublicAPI
import traceback

# Create blueprint
portfolio_bp = Blueprint('portfolio', __name__)


@portfolio_bp.route('', methods=['GET'])  # This maps to /api/portfolio
def get_portfolio():
    """Get current portfolio data"""
    try:
        portfolio = db_load_latest_portfolio()
        if portfolio:
            return jsonify({'status': 'success', 'data': portfolio})
        else:
            return jsonify({'status': 'warning', 'message': 'No portfolio data available', 'data': {}})
    except Exception as e:
        print(f"Portfolio Error: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@portfolio_bp.route('/refresh', methods=['POST'])
def refresh_portfolio():
    """Force refresh of portfolio data from Trade Republic"""
    try:
        # Get phone from header or config
        phone = request.headers.get('X-User-Phone')
        if not phone:
            try:
                import configparser
                config = configparser.ConfigParser()
                config.read('config.ini')
                phone = config.get('secret', 'phone_number', fallback=None)
            except Exception:
                pass

        # Initialize TR API
        tr_api = TradeRepublicAPI()

        # If we have phone, try to login/use existing session
        if phone:
            tr_api.config.read(tr_api.config_path)
            # Update phone number if provided
            if phone != tr_api.config.get("secret", "phone_number", fallback=None):
                tr_api.config.set("secret", "phone_number", phone)
                # Note: In a real implementation, we'd need to handle PIN securely
                with open(tr_api.config_path, "w") as f:
                    tr_api.config.write(f)

        # Fetch fresh portfolio data
        portfolio_data = tr_api.fetch_portfolio()
        if portfolio_data:
            # Save to database
            db_save_portfolio(portfolio_data, user_phone=phone)
            return jsonify({
                'status': 'success',
                'message': 'Portfolio refreshed successfully',
                'timestamp': portfolio_data.get('timestamp') if isinstance(portfolio_data, dict) else None
            })
        else:
            return jsonify({'status': 'error', 'message': 'Failed to fetch portfolio data'}), 500

    except Exception as e:
        print(f"Portfolio Refresh Error: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@portfolio_bp.route('/performance', methods=['GET'])
def get_portfolio_performance():
    """Get portfolio performance metrics"""
    try:
        portfolio = db_load_latest_portfolio()
        if not portfolio:
            return jsonify({'status': 'warning', 'message': 'No portfolio data available'})

        # Calculate basic performance metrics
        # This would typically involve comparing historical snapshots
        return jsonify({
            'status': 'success',
            'data': {
                'total_value': portfolio.get('total_value', 0),
                'cash': portfolio.get('cash', 0),
                'positions_count': portfolio.get('positions_count', 0),
                'performance': 'Performance calculation endpoint - implementation pending'
            }
        })
    except Exception as e:
        print(f"Portfolio Performance Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500