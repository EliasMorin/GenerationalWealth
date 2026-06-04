import requests
import pandas as pd
import xml.etree.ElementTree as ET
import time
import yfinance as yf
from bs4 import BeautifulSoup

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


class RealInstitutionalDataScraper:
    """Scraper de données institutionnelles réelles"""

    def __init__(self):
        self.cftc_base_url = "https://publicreporting.cftc.gov/resource"
        self.sec_base_url = "https://www.sec.gov"
        self.headers = {
            'User-Agent': 'GenerationalWealth/1.0 (generationalwealth@example.com)',
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'www.sec.gov',
            'Connection': 'keep-alive'
        }
        self.session = create_retry_session()
        self.session.headers.update(self.headers)

    # ========== 1. RAPPORTS COT RÉELS (CFTC) ==========

    def get_cot_data_real(self, commodity: str = "silver", limit: int = 10) -> pd.DataFrame:
        """
        Récupère les VRAIES données COT depuis la CFTC.
        """
        commodity_codes = {
            "silver": "084691",
            "gold": "088691",
            "crude_oil": "067651",
            "natural_gas": "023651",
            "copper": "085692",
            "wheat": "001612",
            "corn": "002602",
            "soybeans": "005602"
        }

        if commodity.lower() not in commodity_codes:
            print(f"[ERROR] Commodite non reconnue: {commodity}")
            return pd.DataFrame()

        cftc_code = commodity_codes[commodity.lower()]
        url = f"{self.cftc_base_url}/jun7-fc8e.json"
        params = {
            "$limit": limit,
            "$where": f"cftc_contract_market_code='{cftc_code}'",
            "$order": "report_date_as_yyyy_mm_dd DESC"
        }

        try:
            print(f"[NET] Connexion a la CFTC pour {commodity}...")
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data)

            # Sélection des colonnes importantes
            cols = {
                'report_date_as_yyyy_mm_dd': 'Date',
                'market_and_exchange_names': 'Marché',
                'open_interest_all': 'Intérêt_Ouvert',
                'dealer_positions_long_all': 'Dealer_Long',
                'dealer_positions_short_all': 'Dealer_Short',
                'asset_mgr_positions_long_all': 'Asset_Mgr_Long',
                'asset_mgr_positions_short_all': 'Asset_Mgr_Short',
                'lev_money_positions_long_all': 'Lev_Money_Long',
                'lev_money_positions_short_all': 'Lev_Money_Short'
            }

            available = [c for c in cols.keys() if c in df.columns]
            df_clean = df[available].copy()
            df_clean.columns = [cols[c] for c in available]

            # Conversion en numérique
            for col in df_clean.columns[2:]:
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

            # Calcul positions nettes
            if 'Dealer_Long' in df_clean.columns:
                df_clean['Dealer_Net'] = df_clean['Dealer_Long'] - df_clean['Dealer_Short']
            if 'Asset_Mgr_Long' in df_clean.columns:
                df_clean['Asset_Mgr_Net'] = df_clean['Asset_Mgr_Long'] - df_clean['Asset_Mgr_Short']
            if 'Lev_Money_Long' in df_clean.columns:
                df_clean['Lev_Money_Net'] = df_clean['Lev_Money_Long'] - df_clean['Lev_Money_Short']

            return df_clean

        except Exception as e:
            print(f"[ERROR] Erreur COT: {e}")
            return pd.DataFrame()

    # ========== 2. YAHOO FINANCE - DÉTENTEURS INSTITUTIONNELS RÉELS ==========

    def get_institutional_holders(self, ticker):
        """
        Récupère les détenteurs institutionnels d'une action
        """
        try:
            stock = yf.Ticker(ticker)

            # Récupérer les informations institutionnelles
            institutional = stock.institutional_holders

            if institutional is not None and not institutional.empty:
                return institutional
            else:
                return None

        except Exception as e:
            return None

    def get_mutual_fund_holders(self, ticker):
        """
        Récupère les fonds communs de placement détenant l'action
        """
        try:
            stock = yf.Ticker(ticker)

            # Récupérer les fonds communs
            mutualfund = stock.mutualfund_holders

            if mutualfund is not None and not mutualfund.empty:
                return mutualfund
            else:
                return None

        except Exception as e:
            return None

    def analyze_institutional_ownership(self, ticker):
        """
        Analyse complète de la propriété institutionnelle
        """
        stock = yf.Ticker(ticker)

        # Récupérer les détenteurs
        inst_holders = self.get_institutional_holders(ticker)
        fund_holders = self.get_mutual_fund_holders(ticker)

        return {
            'institutional': inst_holders,
            'mutual_funds': fund_holders
        }

    def compare_institutional_holdings(self, tickers):
        """
        Compare les détentions institutionnelles pour plusieurs tickers
        """
        results = {}

        for ticker in tickers:
            results[ticker] = self.analyze_institutional_ownership(ticker)

        return results

    # ========== 3. FINVIZ - DONNÉES FONDAMENTALES RÉELLES ==========

    def get_finviz_data(self, ticker: str) -> dict:
        try:
            url = f"https://finviz.com/quote.ashx?t={ticker}"

            # Finviz requires standard browser headers to avoid 403
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0'
            }

            time.sleep(1) # Be nice
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            tables = soup.find_all('table', class_='snapshot-table2')

            if not tables:
                return {}

            data = {}
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    for i in range(0, len(cols)-1, 2):
                        key = cols[i].get_text(strip=True)
                        value = cols[i+1].get_text(strip=True)
                        data[key] = value

            institutional_data = {
                'Ticker': ticker,
                'Institutional_Own': data.get('Inst Own', 'N/A'),
                'Insider_Own': data.get('Insider Own', 'N/A'),
                'Inst_Trans': data.get('Inst Trans', 'N/A'),
                'Insider_Trans': data.get('Insider Trans', 'N/A'),
                'Short_Float': data.get('Short Float', 'N/A'),
                'Market_Cap': data.get('Market Cap', 'N/A'),
                'P/E': data.get('P/E', 'N/A'),
                'Target_Price': data.get('Target Price', 'N/A')
            }
            return institutional_data
        except Exception as e:
            print(f"[ERROR] Erreur Finviz: {e}")
            return {}

    # ========== 4. SEC EDGAR - 13F FILINGS RÉELS ==========

    def search_cik_real(self, company_name: str):
        try:
            url = "https://www.sec.gov/cgi-bin/browse-edgar"
            params = {
                'company': company_name,
                'action': 'getcompany',
                'output': 'xml'
            }
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            cik_elem = root.find('.//CIK')
            if cik_elem is not None:
                return cik_elem.text.zfill(10)
            return None
        except Exception as e:
            print(f"[ERROR] Erreur recherche CIK: {e}")
            return None

    def get_latest_13f_holdings(self, cik: str, limit: int = 1) -> pd.DataFrame:
        try:
            cik_padded = cik.zfill(10)
            url = f"https://www.sec.gov/cgi-bin/browse-edgar"
            params = {
                'action': 'getcompany',
                'CIK': cik_padded,
                'type': '13F-HR',
                'dateb': '',
                'owner': 'exclude',
                'count': limit,
                'output': 'xml'
            }
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            filings = root.findall('.//filing')
            if not filings:
                return pd.DataFrame()

            filing = filings[0]
            filing_date = filing.find('filingDate')
            filing_href = filing.find('filingHREF')

            data = {
                'Filing_Date': [filing_date.text if filing_date is not None else 'N/A'],
                'Document_URL': [filing_href.text if filing_href is not None else 'N/A']
            }
            return pd.DataFrame(data)
        except Exception as e:
            print(f"[ERROR] Erreur 13F: {e}")
            return pd.DataFrame()

    # ========== 5. MÉTHODE D'ANALYSE COMPLÈTE ==========

    def analyze_stock_complete(self, ticker: str) -> dict:
        """
        Analyse COMPLÈTE d'une action avec données RÉELLES multi-sources
        """
        results = {'ticker': ticker.upper()}

        # Yahoo Finance - Détenteurs institutionnels
        yahoo_holders = self.get_institutional_holders(ticker)
        results['yahoo_holders'] = yahoo_holders

        # Populate F13 (Smart Money) from Yahoo Holders if available
        # Frontend expects: {Owner, Change_Pct, Date, Shares_Held}
        f13_data = []
        if yahoo_holders is not None:
             # If it's a dataframe, convert to records
            records = yahoo_holders
            if hasattr(yahoo_holders, 'to_dict'):
                records = yahoo_holders.to_dict(orient='records')

            for h in records:
                try:
                    pct_change = h.get('pctChange', 0)
                    # Handle if it's not a float
                    try:
                        pct_change = float(pct_change)
                    except:
                        pct_change = 0

                    f13_data.append({
                        'Owner': h.get('Holder', 'Unknown'),
                        'Change_Pct': f"{pct_change * 100:.2f}",
                        'Date': str(h.get('Date Reported', 'N/A')),
                        'Shares_Held': h.get('Shares', 0)
                    })
                except Exception as e:
                    print(f"Error parsing holder for F13: {e}")

        results['f13'] = f13_data

        # Yahoo Finance - Fonds Communs
        mutual_funds = self.get_mutual_fund_holders(ticker)
        results['mutual_funds'] = mutual_funds

        # Finviz - Données fondamentales
        finviz_data = self.get_finviz_data(ticker)
        results['finviz'] = finviz_data

        return results