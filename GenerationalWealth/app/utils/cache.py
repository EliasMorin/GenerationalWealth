import threading
from typing import Any, Optional

# Assuming these will be imported from db utils or defined locally if not available
try:
    from .db import db_load_generic, db_save_generic
except ImportError:
    # Fallback definitions if db utils not yet created
    def db_load_generic(key: str, default=None):
        """Fallback - to be replaced when db.py is created"""
        return default

    def db_save_generic(key: str, data: Any):
        """Fallback - to be replaced when db.py is created"""
        pass


# Global ISIN cache variables
_isin_cache = {}
_isin_cache_lock = threading.Lock()
_isin_cache_loaded = False

# Metadata cache variables
_metadata_cache = {}
_metadata_lock = threading.Lock()


def ensure_isin_cache():
    """Ensure ISIN cache is loaded from database."""
    global _isin_cache, _isin_cache_loaded
    if not _isin_cache_loaded:
        with _isin_cache_lock:
            if not _isin_cache_loaded:
                try:
                    # Try to get app context if available
                    try:
                        from flask import current_app
                        if current_app:
                            with current_app.app_context():
                                data = db_load_generic('isin_cache')
                                if data:
                                    _isin_cache.update(data)
                                _isin_cache_loaded = True
                    except ImportError:
                        # If Flask not available, try direct db access
                        data = db_load_generic('isin_cache')
                        if data:
                            _isin_cache.update(data)
                        _isin_cache_loaded = True
                except Exception as e:
                    print(f"ISIN Cache load error: {e}")
                    # Even if load fails, mark as loaded to prevent repeated attempts
                    _isin_cache_loaded = True


def save_cache():
    """Save ISIN cache to database."""
    global _isin_cache
    with _isin_cache_lock:
        try:
            # Try to get app context if available
            try:
                from flask import current_app
                if current_app:
                    with current_app.app_context():
                        db_save_generic('isin_cache', _isin_cache)
            except ImportError:
                # If Flask not available, try direct db access
                db_save_generic('isin_cache', _isin_cache)
        except Exception as e:
            print(f"Error saving ISIN cache: {e}")


def get_isin_cache() -> dict:
    """Get the current ISIN cache."""
    ensure_isin_cache()
    return _isin_cache.copy()


def set_isin_cache(key: str, value: Any):
    """Set a value in the ISIN cache."""
    with _isin_cache_lock:
        _isin_cache[key] = value


def get_isin_value(key: str, default=None) -> Any:
    """Get a value from the ISIN cache."""
    ensure_isin_cache()
    return _isin_cache.get(key, default)


# --- METADATA CACHE (Sector/Country) ---

def get_sector_reference_index(sector: str, country: str = "USA") -> Optional[str]:
    """
    Returns a reference index ticker based on sector and country.
    Uses caching to avoid repeated lookups.
    """
    if not sector:
        return None

    # Normalize sector
    if hasattr(sector, 'lower'):
        sector = sector.lower()

    cache_key = f"{sector}:{country}"

    with _metadata_lock:
        if cache_key in _metadata_cache:
            return _metadata_cache[cache_key]

    # Default mappings - in a real implementation, this might come from a database or config
    sector_map = {
        'technology': 'XLK',
        'healthcare': 'XLV',
        'financial': 'XLF',
        'energy': 'XLE',
        'consumer cyclical': 'XLY',
        'consumer defensive': 'XLP',
        'industrial': 'XLI',
        'basic materials': 'XLB',
        'utilities': 'XLU',
        'real estate': 'XLRE',
        'communication services': 'XLC'
    }

    result = sector_map.get(sector)

    with _metadata_lock:
        _metadata_cache[cache_key] = result

    return result


def fetch_metadata_for_ticker(ticker: str) -> dict:
    """
    Fetch sector/country/currency data for a ticker.
    Uses caching to avoid repeated API calls.
    """
    if not ticker:
        return {}

    cache_key = f"metadata:{ticker}"

    with _metadata_lock:
        if cache_key in _metadata_cache:
            return _metadata_cache[cache_key].copy()

    # Default fallback - in a real implementation, this would call an API
    # For now, return basic info
    result = {
        'ticker': ticker,
        'sector': 'Unknown',
        'country': 'USA',
        'currency': 'USD',
        'exchange': 'Unknown'
    }

    # Try to get from yfinance if available
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        if info:
            result.update({
                'sector': info.get('sector', 'Unknown'),
                'country': info.get('country', 'USA'),
                'currency': info.get('currency', 'USD'),
                'exchange': info.get('exchange', 'Unknown')
            })
    except Exception:
        pass  # Keep defaults if yfinance fails

    with _metadata_lock:
        _metadata_cache[cache_key] = result.copy()

    return result


def clear_metadata_cache():
    """Clear the metadata cache."""
    with _metadata_lock:
        _metadata_cache.clear()


def get_metadata_cache_stats() -> dict:
    """Get statistics about the metadata cache."""
    with _metadata_lock:
        return {
            'size': len(_metadata_cache),
            'keys': list(_metadata_cache.keys())
        }