from flask import Blueprint, request, jsonify
from ..services.institutional_data import RealInstitutionalDataScraper
from ..utils.db import db_load_generic, db_save_generic, db_load_insiders, db_save_insiders
from ..utils.cache import fetch_metadata_for_ticker
import traceback

# Create blueprint
institutional_bp = Blueprint('institutional', __name__)


@institutional_bp.route('/cot/<commodity>', methods=['GET'])
def get_cot_data(commodity):
    """Get COT (Commitments of Traders) data for a commodity"""
    try:
        limit = request.args.get('limit', 10, type=int)
        scraper = RealInstitutionalDataScraper()
        data = scraper.get_cot_data_real(commodity=commodity, limit=limit)
        return jsonify({'status': 'success', 'data': data.to_dict('records') if not data.empty else []})
    except Exception as e:
        print(f"COT Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@institutional_bp.route('/stock/<ticker>', methods=['GET'])
def get_institutional_holders(ticker):
    """Get institutional holders for a stock"""
    try:
        scraper = RealInstitutionalDataScraper()
        holders = scraper.get_institutional_holders(ticker.upper())
        if holders is not None and not holders.empty:
            return jsonify({'status': 'success', 'data': holders.to_dict('records')})
        else:
            return jsonify({'status': 'success', 'data': []})
    except Exception as e:
        print(f"Institutional holders error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@institutional_bp.route('/13f/<institution>', methods=['GET'])
def get_13f_holdings(institution):
    """Get 13F holdings for an institution"""
    try:
        scraper = RealInstitutionalDataScraper()
        # First, try to get CIK from institution name
        cik = scraper.search_cik_real(institution)
        if not cik:
            return jsonify({'status': 'error', 'message': f'Could not find CIK for institution: {institution}'}), 404

        # Get latest 13F holdings
        data = scraper.get_latest_13f_holdings(cik)
        return jsonify({'status': 'success', 'data': data.to_dict('records') if not data.empty else []})
    except Exception as e:
        print(f"13F holdings error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@institutional_bp.route('/assets/enriched/<ticker>', methods=['GET'])
def get_enriched_asset(ticker):
    """Get enriched asset data including metadata"""
    try:
        # Get metadata (sector, country, currency)
        metadata = fetch_metadata_for_ticker(ticker.upper())

        scraper = RealInstitutionalDataScraper()

        # Get institutional data
        institutional = scraper.get_institutional_holders(ticker.upper())
        mutual_funds = scraper.get_mutual_fund_holders(ticker.upper())

        # Get Finviz data
        finviz_data = scraper.get_finviz_data(ticker.upper())

        result = {
            'ticker': ticker.upper(),
            'metadata': metadata,
            'institutional_holders': institutional.to_dict('records') if institutional is not None and not institutional.empty else [],
            'mutual_fund_holders': mutual_funds.to_dict('records') if mutual_funds is not None and not mutual_funds.empty else [],
            'finviz_data': finviz_data
        }

        return jsonify({'status': 'success', 'data': result})
    except Exception as e:
        print(f"Enriched asset error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# Helper function to fetch insiders data (would normally be called via background task)
def fetch_insiders_api(tickers=None):
    """Fetch insiders data for given tickers"""
    # This would normally call an external API or scrape data
    # For now, return empty structure
    if tickers is None:
        tickers = ['AAPL', 'GOOGL', 'MSFT', 'TSLA']

    result = {}
    for ticker in tickers:
        result[ticker] = {
            'all': [],
            'recent_7days': []
        }
    return result