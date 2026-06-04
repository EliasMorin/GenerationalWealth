from datetime import datetime
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

class MarketCorrelator:
    """
    Analyse le portefeuille et identifie les corrélations de marché pertinentes.
    Crée des 'Surveillances' basées sur la composition du portefeuille.
    """
    def __init__(self):
        # Règles de corrélation (Mots-clés vs Indicateurs)
        self.rules = [
            {
                'category': 'Technology & Growth',
                'keywords': ['Technology', 'Software', 'Semiconductor', 'NVIDIA', 'Apple', 'Microsoft', 'Google', 'Meta', 'Amazon', 'Tesla', 'ASML', 'AMD', 'Intel', 'Tech', 'AI', 'Cyber'],
                'indicators': [
                    {'symbol': '^IXIC', 'name': 'NASDAQ', 'type': 'index', 'reason': 'Corrélation Secteur Tech'},
                    {'symbol': '^TNX', 'name': 'Taux US 10 Ans', 'type': 'yield', 'reason': 'Sensibilité aux Taux (Growth)'}
                ]
            },
            {
                'category': 'Energy',
                'keywords': ['Energy', 'Oil', 'Gas', 'Petroleum', 'Shell', 'Total', 'Exxon', 'Chevron', 'BP', 'Eni', 'Equinor'],
                'indicators': [
                    {'symbol': 'CL=F', 'name': 'Pétrole WTI', 'type': 'commodity', 'reason': 'Prix de l\'Énergie'},
                    {'symbol': 'NG=F', 'name': 'Gaz Naturel', 'type': 'commodity', 'reason': 'Prix de l\'Énergie'}
                ]
            },
            {
                'category': 'Precious Metals',
                'keywords': ['Gold', 'Silver', 'Mining', 'Precious', 'Agnico', 'Barrick', 'Newmont', 'Franco-Nevada', 'Wheaton'],
                'indicators': [
                    {'symbol': 'GC=F', 'name': 'Or (Gold)', 'type': 'commodity', 'reason': 'Actif Sous-jacent'},
                    {'symbol': 'SI=F', 'name': 'Argent (Silver)', 'type': 'commodity', 'reason': 'Actif Sous-jacent'}
                ]
            },
            {
                'category': 'Crypto & Blockchain',
                'keywords': ['Bitcoin', 'Crypto', 'Coinbase', 'MicroStrategy', 'Blockchain', 'Ethereum', 'Miner', 'Riot', 'Marathon'],
                'indicators': [
                    {'symbol': 'BTC-USD', 'name': 'Bitcoin', 'type': 'crypto', 'reason': 'Leader du Marché Crypto'},
                    {'symbol': 'ETH-USD', 'name': 'Ethereum', 'type': 'crypto', 'reason': 'Alternative Crypto Majeure'}
                ]
            },
            {
                'category': 'Financials',
                'keywords': ['Bank', 'Financial', 'Insurance', 'JPM', 'Chase', 'Goldman', 'Sachs', 'BNP', 'Axa', 'Allianz', 'Santander'],
                'indicators': [
                    {'symbol': '^TNX', 'name': 'Taux US 10 Ans', 'type': 'yield', 'reason': 'Marge d\'Intérêt'},
                    {'symbol': '10Y_2Y_Spread', 'name': 'Yield Curve', 'type': 'spread', 'reason': 'Indicateur de Récession/Marge'}
                ]
            },
            {
                'category': 'China Exposure',
                'keywords': ['Alibaba', 'Tencent', 'JD.com', 'Nio', 'Baidu', 'China', 'Emerging'],
                'indicators': [
                    {'symbol': '000001.SS', 'name': 'Shanghai Composite', 'type': 'index', 'reason': 'Exposition Marché Chinois'},
                    {'symbol': 'USDCNY=X', 'name': 'USD/CNY', 'type': 'forex', 'reason': 'Risque de Change (Yuan)'}
                ]
            },
            {
                'category': 'European Stocks',
                'keywords': ['LVMH', 'L\'Oreal', 'Airbus', 'Siemens', 'SAP', 'Inditex', 'Euro'],
                # Note: Détection simpliste, idéalement enrichir avec la devise de l'actif (EUR)
                'indicators': [
                    {'symbol': 'EURUSD=X', 'name': 'EUR/USD', 'type': 'forex', 'reason': 'Impact Taux de Change Export'}
                ]
            }
        ]

    def get_market_data_subset(self, symbols_needed: List[Dict[str, str]]) -> Dict[str, Any]:
        """Récupère les données live pour une liste de symboles spécifiques"""
        data = {}
        # Mapping symbol -> Nom pour affichage propre
        symbol_map = {item['symbol']: item for item in symbols_needed}

        # Optimisation: Bulk fetch via yfinance pour actions/indices/crypto/forex/futures
        # Note: yfinance gère bien le mix
        unique_symbols = list(symbol_map.keys())
        # Filtrer les symboles spéciaux calculés (ex: spreads)
        fetch_symbols = [s for s in unique_symbols if 'Spread' not in s]

        if fetch_symbols:
            try:
                tickers = yf.Tickers(' '.join(fetch_symbols))

                for symbol in fetch_symbols:
                    try:
                        ticker = tickers.tickers[symbol]
                        # History est plus fiable pour le prix temps réel que info
                        hist = ticker.history(period="5d")

                        if not hist.empty:
                            current = hist['Close'].iloc[-1]
                            prev = hist['Close'].iloc[-2] if len(hist) > 1 else hist['Open'].iloc[-1]
                            change = current - prev
                            pct = (change / prev) * 100 if prev != 0 else 0

                            info = symbol_map[symbol]
                            data[symbol] = {
                                'symbol': symbol,
                                'name': info['name'],
                                'price': current,
                                'change': change,
                                'change_pct': pct,
                                'reason': info['reason'],
                                'type': info.get('type', 'generic')
                            }
                    except Exception as e:
                        print(f"Error fetching correlation data for {symbol}: {e}")
            except Exception as e:
                print(f"Bulk fetch error: {e}")

        # Gestion Spéciale: Spreads
        if '10Y_2Y_Spread' in unique_symbols:
            # Besoin de fetcher TNX et FVX manuellement si pas déjà fait
            try:
                t10 = yf.Ticker('^TNX').history(period='1d')['Close'].iloc[-1]
                t2 = yf.Ticker('^FVX').history(period='1d')['Close'].iloc[-1]
                val = t10 - t2
                data['10Y_2Y_Spread'] = {
                    'symbol': '10Y_2Y_Spread',
                    'name': 'Yield Curve (10Y-2Y)',
                    'price': val,
                    'change': 0, # Difficile à calc sans historique spread
                    'change_pct': 0,
                    'reason': symbol_map['10Y_2Y_Spread']['reason'],
                    'type': 'spread',
                    'interpretation': 'Normal' if val > 0 else 'Inverted (Warning)'
                }
            except: pass

        return data

    def analyze(self, portfolio_positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyse les positions et retourne une liste d'indicateurs à surveiller.
        portfolio_positions: Liste de dicts {'name': '...', 'ticker': '...', 'isin': '...'}
        """
        active_indicators = {} # Utiliser dict pr dédoublonner par symbole

        for pos in portfolio_positions:
            name = pos.get('name', '').lower()
            ticker = pos.get('ticker', '').lower() if pos.get('ticker') else ''

            # 1. Check Keywords
            for rule in self.rules:
                match = False
                # Vérifier mots-clés dans Nom ou Ticker
                for kw in rule['keywords']:
                    kw_lower = kw.lower()
                    if kw_lower in name or kw_lower in ticker:
                         match = True
                         break

                if match:
                    for ind in rule['indicators']:
                        # On garde la raison la plus pertinente (ou on concatène)
                        sym = ind['symbol']
                        if sym not in active_indicators:
                            active_indicators[sym] = {
                                'symbol': sym,
                                'name': ind['name'],
                                'type': ind['type'],
                                'reason': f"Impacté par {pos.get('name', 'Position')}"
                            }
                        else:
                            # Ajouter la position à la raison si pas trop long
                            if "Impacté par" in active_indicators[sym]['reason']:
                                current_reasons = active_indicators[sym]['reason'].split(', ')
                                if len(current_reasons) < 3:
                                     active_indicators[sym]['reason'] += f", {pos.get('name')}"
                                elif "..." not in active_indicators[sym]['reason']:
                                     active_indicators[sym]['reason'] += ", ..."

        # Récupérer les données Data Live pour ces indicateurs
        symbols_list = list(active_indicators.values())
        live_data = self.get_market_data_subset(symbols_list)

        # Merger les données live avec les métadonnées
        results = []
        for sym, meta in active_indicators.items():
            if sym in live_data:
                results.append(live_data[sym])
            else:
                # Fallback si data pas dispo
                results.append({
                    **meta,
                    'price': 'N/A',
                    'change_pct': 0
                })

        return results