import os
import json
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional

# Assuming these will be imported from utils or defined locally if not available
try:
    from ..utils.http import create_retry_session
except ImportError:
    def create_retry_session(retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 504)):
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        session = requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session


class CapitolTradesScraper:
    """Scraper pour Capitol Trades - Trades des politiciens au Congrès"""

    # Dictionnaire de mapping nom de compagnie -> ticker
    NAME_TO_TICKER = {
        'AT&T Inc': 'T',
        'Abbott Laboratories': 'ABT',
        'Advanced Micro Devices': 'AMD',
        'Alibaba': 'BABA',
        'Alphabet Inc': 'GOOGL',
        'Amazon': 'AMZN',
        'Apple Inc': 'AAPL',
        'Broadcom Inc': 'AVGO',
        'Chevron Corporation': 'CVX',
        'Cisco Systems': 'CSCO',
        'Eli Lilly': 'LLY',
        'ExxonMobil': 'XOM',
        'GE Aerospace': 'GE',
        'Intel Corporation': 'INTC',
        'JPMorgan Chase': 'JPM',
        'Johnson & Johnson': 'JNJ',
        'Meta Platforms': 'META',
        'Microsoft': 'MSFT',
        'Nvidia': 'NVDA',
        'Procter & Gamble': 'PG',
        'Tesla Inc': 'TSLA',
        'The Coca-Cola Company': 'KO',
        'The Home Depot': 'HD',
        'The Walt Disney Company': 'DIS',
        'Walmart Inc': 'WMT',
        'Visa Inc': 'V',
    }

    def __init__(self):
        self.base_url = "https://www.capitoltrades.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.cache_file = 'capitol_trades_cache.json'
        self.all_issuers_file = 'all_issuers.json'
        self.cache_data = self._load_cache()
        self.all_issuers = self._load_all_issuers()

    def _load_all_issuers(self):
        """Charge la liste complète des issuers"""
        try:
            if os.path.exists(self.all_issuers_file):
                with open(self.all_issuers_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[ERROR] Erreur chargement all_issuers.json: {e}")
        return []

    def _load_cache(self):
        """Charge le cache local depuis la DB"""
        try:
            # Import here to avoid circular imports
            from ..utils.db import db_load_generic
            return db_load_generic('capitol_trades_cache', {'issuers': {}, 'issuers_index': {}, 'last_updated': None})
        except ImportError:
            # Fallback if db utils not ready
            return {'issuers': {}, 'issuers_index': {}, 'last_updated': None}

    def _save_cache(self):
        """Sauvegarde le cache local dans la DB"""
        try:
            # Import here to avoid circular imports
            from ..utils.db import db_save_generic
            db_save_generic('capitol_trades_cache', self.cache_data)
        except ImportError:
            # Fallback if db utils not ready
            pass  # In a real implementation, we'd want to handle this better

    def _match_ticker_from_name(self, company_name: str) -> Optional[str]:
        """Extrait le ticker à partir du nom de la compagnie"""
        if not company_name:
            return None

        company_lower = company_name.lower()
        # Cherche une correspondance exacte
        for name, ticker in self.NAME_TO_TICKER.items():
            if name.lower() in company_lower or company_lower in name.lower():
                return ticker

        return None

    def _get_total_pages(self, soup):
        """Extract total number of pages from pagination"""
        # Implementation would go here - simplified for now
        return 1

    def _extract_trade_data(self, row):
        """Extract trade data from a table row"""
        # Implementation would go here - simplified for now
        return {}

    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent political trades"""
        # Implementation would go here - simplified for now
        return []

    def get_politician_trades(self, politician_name: str) -> List[Dict[str, Any]]:
        """Get trades for a specific politician"""
        # Implementation would go here - simplified for now
        return []

    def get_issuer_trades(self, issuer_name: str) -> List[Dict[str, Any]]:
        """Get trades for a specific company/issuer"""
        # Implementation would go here - simplified for now
        return []