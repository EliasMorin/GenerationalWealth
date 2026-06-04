from flask import Blueprint, request, jsonify
from ..services.global_market_data import GlobalMarketData
from ..services.market_correlator import MarketCorrelator
from ..services.technical_analyzer import TechnicalAnalyzer
from ..utils.db import db_load_generic, db_save_generic
from datetime import datetime
import traceback

# Create blueprint
market_bp = Blueprint('market', __name__)


@market_bp.route('/all', methods=['GET'])
def get_market_data():
    """Returns cached market data"""
    keys = ['market_commodities', 'market_forex', 'market_treasury', 'market_indices']
    response = {}
    for key in keys:
        data = db_load_generic(key)
        if data:
            short_key = key.replace('market_', '')
            if short_key == 'treasury': short_key = 'treasury_yields'
            response[short_key] = data
    return jsonify(response)


@market_bp.route('/update', methods=['POST'])
def update_market_data():
    """Forces update of market data"""
    try:
        market = GlobalMarketData()
        data = market.get_all_market_data()

        if 'commodities' in data: db_save_generic('market_commodities', data['commodities'])
        if 'forex' in data: db_save_generic('market_forex', data['forex'])
        if 'treasury_yields' in data: db_save_generic('market_treasury', data['treasury_yields'])
        if 'indices' in data: db_save_generic('market_indices', data['indices'])

        return jsonify({"status": "success", "message": "Market data updated", "timestamp": data['timestamp']})
    except Exception as e:
        print(f"Validation Error: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@market_bp.route('/correlations', methods=['GET'])
def get_portfolio_correlations():
    """Endpoint pour récupérer les indicateurs clés basés sur le portfolio"""
    try:
        # Charger le portfolio depuis la DB
        portfolio = db_load_latest_portfolio()
        if not portfolio:
            return jsonify({'status': 'warning', 'message': 'Portfolio empty', 'data': []})

        positions = portfolio.get('positions', [])
        if not positions:
            positions = portfolio.get('my_investments', [])

        correlator = MarketCorrelator()
        analysis = correlator.analyze(positions)

        return jsonify({'status': 'success', 'data': analysis})
    except Exception as e:
        print(f"Correlation Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@market_bp.route('/analysis/technicals', methods=['GET'])
def get_technical_signals():
    """Scanne le portefeuille utilisateur pour les signaux techniques"""
    try:
        portfolio = db_load_latest_portfolio()
        if not portfolio:
            return jsonify({'status': 'warning', 'message': 'Portfolio empty', 'data': []})

        positions = portfolio.get('positions', [])
        unique_tickers = list(set([p.get('ticker') for p in positions if p.get('ticker')]))

        # Analyser TOUT le portfolio (max 20 pour perf)
        unique_tickers = unique_tickers[:20]

        analyzer = TechnicalAnalyzer()
        results = []

        # Parallel Execution
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(analyzer.analyze_ticker, t): t for t in unique_tickers}
            for future in futures:
                res = future.result()
                if res:
                    # On retourne TOUT maintenant, pas juste les alertes
                    results.append(res)

        return jsonify({'status': 'success', 'data': results})
    except Exception as e:
        print(f"Scan Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@market_bp.route('/assets/enriched/<ticker>', methods=['GET'])
def get_enriched_asset(ticker):
    """Get enriched data for a specific asset"""
    try:
        # This would typically call an external service or aggregate data
        # For now, return basic info
        return jsonify({
            'status': 'success',
            'data': {
                'ticker': ticker.upper(),
                'message': 'Enriched asset data endpoint - implementation pending'
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500