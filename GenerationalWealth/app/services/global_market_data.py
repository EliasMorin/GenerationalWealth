import yfinance as yf
import requests
from datetime import datetime
from typing import Dict, Any

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


class GlobalMarketData:
    """
    Récupère les données des marchés mondiaux :
    - Matières premières (Or, Pétrole, etc.)
    - Devises (Forex)
    - Obligations (Treasury Yields)
    - Indices mondiaux (CAC 40, DAX, etc.)
    """

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        self.session = create_retry_session()
        self.session.headers.update(self.headers)

    def _fetch_realtime(self, symbol):
        """Real-time price via fast_info (works outside US market hours). Falls back to intraday history."""
        t = yf.Ticker(symbol)
        try:
            fi = t.fast_info
            current = fi.last_price
            prev = fi.previous_close
            if current is not None and prev is not None and float(prev) > 0:
                change = float(current) - float(prev)
                pct = round(change / float(prev) * 100, 2)
                return round(float(current), 4), round(float(change), 4), pct
        except Exception:
            pass
        # Fallback: intraday 2d/5m bars
        hist = t.history(period='2d', interval='5m')
        if hist.empty:
            raise ValueError(f'No data for {symbol}')
        current = float(hist['Close'].iloc[-1])
        today = hist.index[-1].date()
        prev_bars = hist[hist.index.map(lambda x: x.date()) < today]
        prev = float(prev_bars['Close'].iloc[-1]) if not prev_bars.empty else float(hist['Close'].iloc[0])
        change = current - prev
        pct = round((change / prev * 100) if prev else 0, 2)
        return round(current, 4), round(change, 4), pct

    # ==================== MATIÈRES PREMIÈRES ====================
    def get_commodities(self):
        commodities = {}
        symbols = {
            'Gold': 'GC=F', 'Silver': 'SI=F', 'Platinum': 'PL=F', 'Palladium': 'PA=F', 'Copper': 'HG=F',
            'Crude_Oil_WTI': 'CL=F', 'Crude_Oil_Brent': 'BZ=F', 'Natural_Gas': 'NG=F', 'Heating_Oil': 'HO=F', 'Gasoline': 'RB=F',
            'Wheat': 'ZW=F', 'Corn': 'ZC=F', 'Soybeans': 'ZS=F', 'Coffee': 'KC=F', 'Sugar': 'SB=F', 'Cotton': 'CT=F', 'Cocoa': 'CC=F',
        }
        print("[PKG] Recuperation des matieres premieres (real-time)...")
        for name, symbol in symbols.items():
            try:
                price, change, change_pct = self._fetch_realtime(symbol)
                commodities[name] = {
                    'symbol': symbol,
                    'price': round(price, 2),
                    'change': round(change, 2),
                    'change_pct': change_pct,
                    'currency': 'USD',
                    'last_update': datetime.now().isoformat()
                }
            except Exception as e:
                print(f"  [ERROR] Erreur {name}: {e}")
                commodities[name] = {'error': str(e), 'symbol': symbol}
        commodities['timestamp'] = datetime.now().isoformat()
        return commodities

    # ==================== DEVISES (FOREX) ====================
    def get_forex(self):
        forex = {}
        pairs = {
            'EUR/USD': 'EURUSD=X', 'GBP/USD': 'GBPUSD=X', 'USD/JPY': 'USDJPY=X', 'USD/CHF': 'USDCHF=X',
            'AUD/USD': 'AUDUSD=X', 'NZD/USD': 'NZDUSD=X', 'USD/CAD': 'USDCAD=X', 'EUR/GBP': 'EURGBP=X',
            'EUR/JPY': 'EURJPY=X', 'GBP/JPY': 'GBPJPY=X', 'USD/CNY': 'USDCNY=X', 'USD/HKD': 'USDHKD=X', 'USD/SGD': 'USDSGD=X',
        }
        print("\n[FOREX] Recuperation des devises Forex (real-time)...")
        for pair_name, symbol in pairs.items():
            try:
                rate, change, change_pct = self._fetch_realtime(symbol)
                forex[pair_name] = {
                    'symbol': symbol,
                    'rate': round(rate, 4),
                    'change': round(change, 4),
                    'change_pct': change_pct,
                    'last_update': datetime.now().isoformat()
                }
            except Exception as e:
                print(f"  [ERROR] Erreur {pair_name}: {e}")
                forex[pair_name] = {'error': str(e), 'symbol': symbol}
        forex['timestamp'] = datetime.now().isoformat()
        return forex

    # ==================== OBLIGATIONS (TREASURY YIELDS) ====================
    def get_treasury_yields(self):
        yields = {}
        symbols = {
            '1_Month': '^IRX', '3_Month': '^IRX', '2_Year': '^FVX', '5_Year': '^FVX', '10_Year': '^TNX', '30_Year': '^TYX',
        }
        print("\n[DATA] Recuperation des taux obligataires US...")
        for name, symbol in symbols.items():
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='5d')
                if not hist.empty:
                    current_yield = hist['Close'].iloc[-1]
                    prev_yield = hist['Close'].iloc[0] if len(hist) > 1 else current_yield
                    change = current_yield - prev_yield
                    yields[name] = {
                        'symbol': symbol,
                        'yield': round(float(current_yield), 3),
                        'change': round(float(change), 3),
                        'last_update': datetime.now().isoformat(),
                        'unit': '%'
                    }
            except Exception as e:
                print(f"  [ERROR] Erreur {name}: {e}")
                yields[name] = {'error': str(e), 'symbol': symbol}

        # Calcul des spreads
        if '10_Year' in yields and '2_Year' in yields and 'yield' in yields['10_Year'] and 'yield' in yields['2_Year']:
            spread = yields['10_Year']['yield'] - yields['2_Year']['yield']
            yields['10Y_2Y_Spread'] = {
                'value': round(spread, 3),
                'interpretation': 'Normal' if spread > 0 else 'Inverted (Recession Signal)',
                'unit': 'bps'
            }
        yields['timestamp'] = datetime.now().isoformat()
        return yields

    # ==================== INDICES MONDIAUX ====================
    def get_global_indices(self):
        indices = {}
        symbols = {
            'S&P_500': '^GSPC', 'Dow_Jones': '^DJI', 'NASDAQ': '^IXIC', 'Russell_2000': '^RUT',
            'CAC_40': '^FCHI', 'DAX': '^GDAXI', 'FTSE_100': '^FTSE', 'EURO_STOXX_50': '^STOXX50E',
            'Nikkei_225': '^N225', 'Hang_Seng': '^HSI', 'Shanghai_Composite': '000001.SS',
            'VIX': '^VIX', 'Brazil_Bovespa': '^BVSP'
        }
        print("\n[WORLD] Recuperation des indices mondiaux (real-time)...")
        for name, symbol in symbols.items():
            try:
                price, change, change_pct = self._fetch_realtime(symbol)
                indices[name] = {
                    'symbol': symbol,
                    'price': round(price, 2),
                    'change': round(change, 2),
                    'change_pct': change_pct,
                    'last_update': datetime.now().isoformat()
                }
                if name == 'VIX':
                    sentiment = 'Low Fear (Complacent)' if price < 15 else 'Normal' if price < 20 else 'Elevated Fear' if price < 30 else 'High Fear (Panic)'
                    indices[name]['interpretation'] = sentiment
            except Exception as e:
                print(f"  [ERROR] Erreur {name}: {e}")
                indices[name] = {'error': str(e), 'symbol': symbol}
        indices['timestamp'] = datetime.now().isoformat()
        return indices

    def get_all_market_data(self):
        return {
            'commodities': self.get_commodities(),
            'forex': self.get_forex(),
            'treasury_yields': self.get_treasury_yields(),
            'indices': self.get_global_indices(),
            'timestamp': datetime.now().isoformat()
        }