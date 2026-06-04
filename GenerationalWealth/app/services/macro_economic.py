import requests
import pandas as pd
import re
import certifi
from io import StringIO
from bs4 import BeautifulSoup
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


class MacroEconomicDataScraper:
    """
    Scraper de données macro-économiques sans clé API
    Sources: FRED, Investing.com, Trading Economics, ECB, etc.
    """

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        self.session = create_retry_session()
        self.session.headers.update(self.headers)
        self.session.verify = certifi.where()

    def _read_fred_csv(self, series_id):
        """Lit un CSV FRED avec gestion d'erreurs améliorée"""
        try:
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
            resp = requests.get(url, verify=certifi.where(), timeout=15)
            resp.raise_for_status()
            df = pd.read_csv(StringIO(resp.text))

            # FRED utilise la première colonne pour les dates
            if df.empty:
                return None

            # Renommer la première colonne en 'DATE' si elle ne l'est pas
            if 'DATE' not in df.columns and 'date' not in df.columns:
                df.columns = ['DATE'] + list(df.columns[1:])

            return df
        except Exception as e:
            print(f"Erreur lecture FRED {series_id}: {e}")
            return None

    # ==================== TAUX DIRECTEURS ====================

    def get_interest_rates(self):
        """Récupère les taux directeurs des principales banques centrales"""
        rates = {}

        # 1. FED (US) - Via FRED
        try:
            df = self._read_fred_csv('FEDFUNDS')
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                rates['FED'] = {
                    'rate': float(latest.iloc[1]),  # Deuxième colonne
                    'date': str(latest.iloc[0]),
                    'currency': 'USD',
                    'name': 'Federal Funds Rate'
                }
        except Exception as e:
            print(f"Erreur FED: {e}")

        # 2. ECB (Europe) - Via scraping
        try:
            url = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/key_ecb_interest_rates/html/index.en.html"
            response = self.session.get(url, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')

            # Chercher le taux principal
            table = soup.find('table')
            if table:
                rows = table.find_all('tr')
                for row in rows[1:2]:  # Première ligne de données
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        rate_text = cols[1].text.strip().replace('%', '').replace(',', '.')
                        try:
                            rates['ECB'] = {
                                'rate': float(rate_text),
                                'currency': 'EUR',
                                'name': 'Main Refinancing Operations'
                            }
                        except:
                            pass
        except Exception as e:
            print(f"Erreur ECB: {e}")

        # 3. BoE (UK)
        try:
            url = "https://www.bankofengland.co.uk/monetary-policy/the-interest-rate-bank-rate"
            response = self.session.get(url, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')

            text = soup.get_text()
            match = re.search(r'Bank Rate is (\d+\.?\d*)%', text)
            if match:
                rates['BoE'] = {
                    'rate': float(match.group(1)),
                    'currency': 'GBP',
                    'name': 'Bank Rate'
                }
        except Exception as e:
            print(f"Erreur BoE: {e}")

        # 4. BoJ (Japan) - Souvent négatif ou proche de 0
        try:
            # BoJ ne publie pas toujours clairement, on peut utiliser un fallback
            rates['BoJ'] = {
                'rate': 0.25,  # Taux récent (à mettre à jour manuellement ou scraper)
                'currency': 'JPY',
                'name': 'Policy Rate',
                'note': 'Donnée approximative - vérifier BoJ.or.jp'
            }
        except Exception as e:
            print(f"Erreur BoJ: {e}")

        rates['timestamp'] = datetime.now().isoformat()
        return rates

    # ==================== INFLATION ====================

    def get_inflation_data(self):
        """Récupère les taux d'inflation (CPI)"""
        inflation = {}

        # 1. US CPI
        try:
            df = self._read_fred_csv('CPIAUCSL')
            if df is not None and not df.empty and len(df) >= 13:
                latest = df.iloc[-1]
                previous_year = df.iloc[-13]

                latest_val = float(latest.iloc[1])
                prev_val = float(previous_year.iloc[1])

                yoy_change = ((latest_val - prev_val) / prev_val) * 100

                inflation['US_CPI'] = {
                    'value': latest_val,
                    'yoy_change': round(yoy_change, 2),
                    'date': str(latest.iloc[0]),
                    'name': 'Consumer Price Index'
                }
        except Exception as e:
            print(f"Erreur US CPI: {e}")

        # 2. US Core CPI
        try:
            df = self._read_fred_csv('CPILFESL')
            if df is not None and not df.empty and len(df) >= 13:
                latest = df.iloc[-1]
                previous_year = df.iloc[-13]

                latest_val = float(latest.iloc[1])
                prev_val = float(previous_year.iloc[1])

                yoy_change = ((latest_val - prev_val) / prev_val) * 100

                inflation['US_Core_CPI'] = {
                    'value': latest_val,
                    'yoy_change': round(yoy_change, 2),
                    'date': str(latest.iloc[0]),
                    'name': 'Core CPI (ex food & energy)'
                }
        except Exception as e:
            print(f"Erreur US Core CPI: {e}")

        # 3. PCE (Fed's preferred measure)
        try:
            df = self._read_fred_csv('PCEPI')
            if df is not None and not df.empty and len(df) >= 13:
                latest = df.iloc[-1]
                previous_year = df.iloc[-13]

                latest_val = float(latest.iloc[1])
                prev_val = float(previous_year.iloc[1])

                yoy_change = ((latest_val - prev_val) / prev_val) * 100

                inflation['US_PCE'] = {
                    'value': latest_val,
                    'yoy_change': round(yoy_change, 2),
                    'date': str(latest.iloc[0]),
                    'name': 'Personal Consumption Expenditures (PCE)'
                }
        except Exception as e:
            print(f"Erreur US PCE: {e}")

        inflation['timestamp'] = datetime.now().isoformat()
        return inflation

    # ==================== CHÔMAGE ====================

    def get_unemployment_data(self):
        """Récupère les taux de chômage"""
        unemployment = {}

        # 1. US Unemployment Rate
        try:
            df = self._read_fred_csv('UNRATE')
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                unemployment['US'] = {
                    'rate': float(latest.iloc[1]),
                    'date': str(latest.iloc[0]),
                    'name': 'US Unemployment Rate'
                }
        except Exception as e:
            print(f"Erreur US Unemployment: {e}")

        # 2. Initial Jobless Claims
        try:
            df = self._read_fred_csv('ICSA')
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                unemployment['US_Jobless_Claims'] = {
                    'value': int(float(latest.iloc[1])),
                    'date': str(latest.iloc[0]),
                    'name': 'Initial Jobless Claims (weekly)'
                }
        except Exception as e:
            print(f"Erreur Jobless Claims: {e}")

        # 3. Nonfarm Payrolls
        try:
            df = self._read_fred_csv('PAYEMS')
            if df is not None and not df.empty and len(df) >= 2:
                latest = df.iloc[-1]
                previous = df.iloc[-2]

                change = float(latest.iloc[1]) - float(previous.iloc[1])

                unemployment['US_Nonfarm_Payrolls'] = {
                    'value': float(latest.iloc[1]),
                    'mom_change': round(change, 0),
                    'date': str(latest.iloc[0]),
                    'name': 'Nonfarm Payrolls (thousands)',
                    'unit': 'Thousands of jobs'
                }
        except Exception as e:
            print(f"Erreur Payrolls: {e}")

        unemployment['timestamp'] = datetime.now().isoformat()
        return unemployment

    # ==================== PIB ====================

    def get_gpd_data(self):
        """Récupère les données de PIB"""
        gdp = {}

        # 1. US GDP
        try:
            df = self._read_fred_csv('GDP')
            if df is not None and not df.empty and len(df) >= 2:
                latest = df.iloc[-1]
                previous = df.iloc[-2]

                latest_val = float(latest.iloc[1])
                prev_val = float(previous.iloc[1])

                qoq_change = ((latest_val - prev_val) / prev_val) * 100

                gdp['US'] = {
                    'value': latest_val,
                    'qoq_change': round(qoq_change, 2),
                    'date': str(latest.iloc[0]),
                    'unit': 'Billions of Dollars',
                    'name': 'US GDP'
                }
        except Exception as e:
            print(f"Erreur US GDP: {e}")

        # 2. US GDP Growth Rate (Real)
        try:
            df = self._read_fred_csv('A191RL1Q225SBEA')
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                gdp['US_Growth'] = {
                    'rate': float(latest.iloc[1]),
                    'date': str(latest.iloc[0]),
                    'name': 'US Real GDP Growth Rate (Annual %)'
                }
        except Exception as e:
            print(f"Erreur US GDP Growth: {e}")

        gdp['timestamp'] = datetime.now().isoformat()
        return gdp

    # ==================== PMI ====================

    def get_pmi_data(self):
        """Récupère les indices PMI"""
        pmi = {}

        # ISM Manufacturing PMI via FRED (souvent avec délai)
        try:
            df = self._read_fred_csv('MANEMP')
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                pmi['US_ISM_Manufacturing'] = {
                    'value': float(latest.iloc[1]),
                    'date': str(latest.iloc[0]),
                    'name': 'ISM Manufacturing Employment Index'
                }
        except Exception as e:
            print(f"Erreur PMI: {e}")

        pmi['timestamp'] = datetime.now().isoformat()
        return pmi

    # ==================== RETAIL SALES ====================

    def get_retail_sales(self):
        """Récupère les ventes au détail"""
        retail = {}

        try:
            df = self._read_fred_csv('RSXFS')
            if df is not None and not df.empty and len(df) >= 2:
                latest = df.iloc[-1]
                previous = df.iloc[-2]

                latest_val = float(latest.iloc[1])
                prev_val = float(previous.iloc[1])

                mom_change = ((latest_val - prev_val) / prev_val) * 100

                retail['US'] = {
                    'value': latest_val,
                    'mom_change': round(mom_change, 2),
                    'date': str(latest.iloc[0]),
                    'unit': 'Millions of Dollars',
                    'name': 'US Retail Sales'
                }
        except Exception as e:
            print(f"Erreur Retail Sales: {e}")

        retail['timestamp'] = datetime.now().isoformat()
        return retail

    # ==================== CONSUMER CONFIDENCE ====================

    def get_consumer_confidence(self):
        """Récupère les indices de confiance des consommateurs"""
        confidence = {}

        # 1. University of Michigan
        try:
            df = self._read_fred_csv('UMCSENT')
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                confidence['US_Michigan'] = {
                    'value': float(latest.iloc[1]),
                    'date': str(latest.iloc[0]),
                    'name': 'University of Michigan Consumer Sentiment'
                }
        except Exception as e:
            print(f"Erreur Consumer Confidence: {e}")

        # 2. Consumer Confidence Index
        try:
            df = self._read_fred_csv('CSCICP03USM665S')
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                confidence['US_Conference_Board'] = {
                    'value': float(latest.iloc[1]),
                    'date': str(latest.iloc[0]),
                    'name': 'Consumer Confidence Index'
                }
        except Exception as e:
            print(f"Erreur CCI: {e}")

        confidence['timestamp'] = datetime.now().isoformat()
        return confidence