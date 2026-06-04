from flask import Blueprint, request, jsonify
from ..utils.db import db_load_generic, db_save_generic
from ..services.bank_forecast import BankForecastScraper
from ..services.capitol_trades import CapitolTradesScraper
from datetime import datetime
import threading
import traceback

# Create blueprint
refresh_bp = Blueprint('refresh', __name__)


@refresh_bp.route('/insiders', methods=['POST'])
def refresh_insiders():
    """Rafraîchit les données insiders pour les tickers spécifiés"""
    try:
        data = request.get_json() or {}
        tickers = data.get('tickers', ['NVDA', 'GOOGL', 'AVGO', 'TSM', 'AAPL'])

        # In a real implementation, this would fetch from an API
        # For now, return mock data
        result = {}
        for ticker in tickers:
            result[ticker] = {
                'all': [],
                'recent_7days': []
            }

        return jsonify({
            'status': 'success',
            'data_type': 'insiders',
            'timestamp': datetime.now().isoformat(),
            'tickers_processed': tickers,
            'data': result
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@refresh_bp.route('/portfolio', methods=['POST'])
def refresh_portfolio():
    """Refresh portfolio data"""
    try:
        # This would trigger a portfolio refresh
        # For now, just acknowledge
        return jsonify({
            'status': 'success',
            'message': 'Portfolio refresh initiated',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@refresh_bp.route('/bank-forecasts', methods=['POST'])
def refresh_bank_forecasts():
    """Trigger bank forecasts refresh"""
    try:
        # Run in background thread to avoid blocking
        def background_refresh():
            try:
                scraper = BankForecastScraper()
                scraper.scrape_all()
            except Exception as e:
                print(f"Bank forecast refresh error: {e}")

        thread = threading.Thread(target=background_refresh, daemon=True)
        thread.start()

        return jsonify({
            'status': 'success',
            'message': 'Bank forecasts refresh initiated',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@refresh_bp.route('/capitol-trades', methods=['POST'])
def refresh_capitol_trades():
    """Trigger Capitol Trades scrape"""
    try:
        # Run in background thread
        def background_refresh():
            try:
                scraper = CapitolTradesScraper()
                # This would actually scrape data
                print("Capitol Trades refresh initiated")
            except Exception as e:
                print(f"Capitol Trades refresh error: {e}")

        thread = threading.Thread(target=background_refresh, daemon=True)
        thread.start()

        return jsonify({
            'status': 'success',
            'message': 'Capitol Trades refresh initiated',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500