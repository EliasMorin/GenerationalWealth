import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional, List

class TechnicalAnalyzer:
    """
    Scanne le portefeuille pour détecter des signaux techniques:
    - RSI > 70 (Surachat) ou < 30 (Survente)
    - Croisement SMA (Golden Cross / Death Cross)
    - Tendance long terme (Prix > SMA 200)
    """
    def __init__(self):
        self.period_rsi = 14
        self.period_sma_short = 50
        self.period_sma_long = 200

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def analyze_ticker(self, ticker_symbol: str) -> Optional[Dict[str, Any]]:
        try:
            ticker = yf.Ticker(ticker_symbol)
            # Besoin de 250 jours (pour SMA 200)
            hist = ticker.history(period='1y')

            if len(hist) < 200:
                return None # Pas assez de données

            close = hist['Close']
            current_price = close.iloc[-1]

            # --- RSI ---
            rsi = self.calculate_rsi(close, self.period_rsi).iloc[-1]

            # --- SMA ---
            sma_50 = close.rolling(window=50).mean().iloc[-1]
            sma_200 = close.rolling(window=200).mean().iloc[-1]

            # --- FUNDAMENTALS (Basic) ---
            try:
                info = ticker.info
                pe = info.get('forwardPE')
                peg = info.get('pegRatio')
                beta = info.get('beta')
                target = info.get('targetMeanPrice')
                recommendation = info.get('recommendationKey', 'none').replace('_', ' ')
            except:
                pe, peg, beta, target, recommendation = None, None, None, None, 'none'

            signal = {
                'ticker': ticker_symbol,
                'price': round(float(current_price), 2),
                'rsi': round(float(rsi), 2),
                'sma_50': round(float(sma_50), 2),
                'sma_200': round(float(sma_200), 2),
                'fundamental': {
                    'pe': round(pe, 1) if pe else 'N/A',
                    'peg': round(peg, 2) if peg else 'N/A',
                    'beta': round(beta, 2) if beta else 'N/A',
                    'target_price': target,
                    'consensus': recommendation.title()
                },
                'alerts': []
            }

            # RSI Logic
            if rsi > 70:
                signal['alerts'].append({
                    'type': 'Technique',
                    'subtype': 'RSI',
                    'level': 'Warning',
                    'message': f"Surachat (RSI {int(rsi)}). Risque court terme.",
                    'color': 'red'
                })
            elif rsi < 30:
                signal['alerts'].append({
                    'type': 'Technique',
                    'subtype': 'RSI',
                    'level': 'Opportunity',
                    'message': f"Survente (RSI {int(rsi)}). Point d'entrée potentiel.",
                    'color': 'green'
                })

            # SMA Filter (Trend)
            if current_price > sma_200:
                signal['trend'] = 'Bullish'
            else:
                signal['trend'] = 'Bearish'

            # Golden Cross / Death Cross
            if sma_50 > sma_200:
                signal['cross_status'] = 'Golden'
                # Check for recent cross
                prev_sma_50 = close.rolling(window=50).mean().iloc[-2]
                prev_sma_200 = close.rolling(window=200).mean().iloc[-2]
                if prev_sma_50 <= prev_sma_200:
                     signal['alerts'].append({
                        'type': 'Technique',
                        'subtype': 'Cross',
                        'level': 'Opportunity',
                        'message': "GOLDEN CROSS Confirmé ! (50 croise 200 à la hausse)",
                        'color': 'green'
                    })
            else:
                signal['cross_status'] = 'Death'

            # Fundamental Alerts
            if peg and peg < 1 and peg > 0:
                 signal['alerts'].append({
                    'type': 'Fondamentale',
                    'subtype': 'Value',
                    'level': 'Opportunity',
                    'message': f"Sous-évaluée (PEG {peg}). Croissance peu chère.",
                    'color': 'green'
                })

            if recommendation in ['Strong Buy', 'Buy'] and target and target > current_price * 1.15:
                 signal['alerts'].append({
                    'type': 'Fondamentale',
                    'subtype': 'Consensus',
                    'level': 'Good',
                    'message': f"Analystes Bullish (Cible +{int(((target/current_price)-1)*100)}%)",
                    'color': 'blue'
                })

            # --- KEY LEVELS (Support/Resistance 3 Mois) ---
            try:
                # 60 jours de trading env. 3 mois
                recent_hist = hist.iloc[-60:]
                support = recent_hist['Low'].min()
                resistance = recent_hist['High'].max()

                signal['levels'] = {
                    'support': round(float(support), 2),
                    'resistance': round(float(resistance), 2),
                    'range_pos': round(((current_price - support) / (resistance - support)) * 100, 1)
                }
            except:
                signal['levels'] = None

            # --- NEWS CONTEXT (Simple Keyword Match) ---
            # Note: This is a basic heuristics. Real 'Analysis' would need AI summary.
            # We will handle the Deep Dive AI on frontend request to save tokens/time here.
            signal['news_context'] = None

            return signal

        except Exception as e:
            print(f"TA Error {ticker_symbol}: {e}")
            return None