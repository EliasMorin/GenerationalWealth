import re
import numpy as np
from datetime import datetime, timedelta
import pandas as pd

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


class CashAnalyzer:
    def __init__(self, transactions):
        self.transactions = transactions
        self.df = pd.DataFrame(transactions) if transactions else pd.DataFrame()

        self.services_statiques = {
            "streaming_musique": [
                {"nom": "Spotify", "categorie": "Musique", "pays": "Global"},
                {"nom": "Apple Music", "categorie": "Musique", "pays": "Global"},
                {"nom": "Deezer", "categorie": "Musique", "pays": "Global"},
                {"nom": "YouTube Music", "categorie": "Musique", "pays": "Global"},
                {"nom": "Amazon Music", "categorie": "Musique", "pays": "Global"},
                {"nom": "Tidal", "categorie": "Musique", "pays": "Global"},
            ],
            "streaming_video": [
                {"nom": "Netflix", "categorie": "Vidéo", "pays": "Global"},
                {"nom": "Disney+", "categorie": "Vidéo", "pays": "Global"},
                {"nom": "Amazon Prime Video", "categorie": "Vidéo", "pays": "Global"},
                {"nom": "Apple TV+", "categorie": "Vidéo", "pays": "Global"},
                {"nom": "HBO Max", "categorie": "Vidéo", "pays": "Global"},
                {"nom": "Paramount+", "categorie": "Vidéo", "pays": "Global"},
                {"nom": "Hulu", "categorie": "Vidéo", "pays": "USA"},
            ],
            "cloud_stockage": [
                {"nom": "Google One", "categorie": "Stockage", "pays": "Global"},
                {"nom": "Dropbox", "categorie": "Stockage", "pays": "Global"},
                {"nom": "Microsoft OneDrive", "categorie": "Stockage", "pays": "Global"},
                {"nom": "iCloud", "categorie": "Stockage", "pays": "Global"},
            ],
            "productivite": [
                {"nom": "Microsoft 365", "categorie": "Productivité", "pays": "Global"},
                {"nom": "Adobe Creative Cloud", "categorie": "Productivité", "pays": "Global"},
                {"nom": "Canva Pro", "categorie": "Productivité", "pays": "Global"},
            ]
        }

        # Build subscription keywords from static list
        self.subscription_keywords = []
        for cat, items in self.services_statiques.items():
            for item in items:
                self.subscription_keywords.append(item['nom'].lower())

        # Expanded Logo Map (Keyword -> Domain)
        self.logo_map = {
            # Streaming & Tech
            'uber': 'uber.com', 'netflix': 'netflix.com', 'spotify': 'spotify.com',
            'apple': 'apple.com', 'amazon': 'amazon.com', 'google': 'google.com',
            'starbucks': 'starbucks.com', 'mcdonalds': 'mcdonalds.com', 'burger king': 'burgerking.fr',
            'deliveroo': 'deliveroo.co.uk', 'ubereats': 'ubereats.com', 'youtube': 'youtube.com',
            'disney': 'disneyplus.com', 'adobe': 'adobe.com', 'microsoft': 'microsoft.com',
            'github': 'github.com', 'chatgpt': 'openai.com', 'openai': 'openai.com',
            'steam': 'steampowered.com', 'playstation': 'playstation.com', 'psn': 'playstation.com',
            'xbox': 'xbox.com', 'nintendo': 'nintendo.com', 'vinted': 'vinted.com',
            'prime': 'amazon.com', 'linkedin': 'linkedin.com', 'slack': 'slack.com',
            'zoom': 'zoom.us', 'dropbox': 'dropbox.com', 'canva': 'canva.com',
            'figma': 'figma.com', 'notion': 'notion.so', 'deezer': 'deezer.com',
            'dazn': 'dazn.com', 'canal': 'canalplus.com', 'beinsport': 'beinsports.com',
            # Grande distribution FR
            'leclerc': 'e-leclerc.com', 'intermarche': 'intermarche.com',
            'carrefour': 'carrefour.com', 'auchan': 'auchan.fr',
            'lidl': 'lidl.fr', 'aldi': 'aldi.fr', 'franprix': 'franprix.fr',
            'monoprix': 'monoprix.fr', 'picard': 'picard.fr', 'biocoop': 'biocoop.fr',
            'super u': 'magasins-u.com', 'systeme u': 'magasins-u.com',
            'casino': 'groupe-casino.fr', 'netto': 'netto.fr',
            'grand frais': 'granfrais.com',
            # Energie & Telecom
            'total': 'totalenergies.fr', 'totalenergies': 'totalenergies.fr',
            'shell': 'shell.com', 'bp': 'bp.com', 'esso': 'esso.fr',
            'engie': 'engie.com', 'edf': 'edf.fr',
            'orange': 'orange.fr', 'sfr': 'sfr.fr',
            'bouygues': 'bouygues-telecom.fr', 'free': 'free.fr', 'iliad': 'iliad.fr',
            # Transport
            'sncf': 'sncf.com', 'ratp': 'ratp.fr', 'blablacar': 'blablacar.fr',
            'airbnb': 'airbnb.com', 'booking': 'booking.com', 'expedia': 'expedia.com',
            'trainline': 'thetrainline.com', 'ouigo': 'ouigo.com', 'thalys': 'thalys.com',
            'eurostar': 'eurostar.com', 'easyjet': 'easyjet.com', 'ryanair': 'ryanair.com',
            'air france': 'airfrance.fr', 'transavia': 'transavia.com', 'volotea': 'volotea.com',
            # Retail & Mode
            'boulanger': 'boulanger.com', 'fnac': 'fnac.com', 'darty': 'darty.com',
            'decathlon': 'decathlon.fr', 'zara': 'zara.com', 'h&m': 'hm.com',
            'uniqlo': 'uniqlo.com', 'nike': 'nike.com', 'adidas': 'adidas.com',
            'foot locker': 'footlocker.fr', 'courir': 'courir.com', 'kiabi': 'kiabi.com',
            'la redoute': 'laredoute.fr', 'cdiscount': 'cdiscount.com', 'veepee': 'veepee.fr',
            # Maison
            'ikea': 'ikea.com', 'leroy': 'leroymerlin.fr', 'castorama': 'castorama.fr',
            'bricomarche': 'bricomarche.com', 'bricorama': 'bricorama.fr', 'brico depot': 'bricodepot.fr',
            'maisons du monde': 'maisonsdumonde.com', 'but': 'but.fr',
            # Sante & Finance
            'doctolib': 'doctolib.fr', 'alan': 'alan.com', 'qonto': 'qonto.com',
            'shine': 'shine.fr', 'revolut': 'revolut.com', 'n26': 'n26.com',
            'paypal': 'paypal.com', 'lydia': 'lydia-app.com', 'sumeria': 'sumeria.money',
            'fortuneo': 'fortuneo.fr', 'boursorama': 'boursorama.com', 'credit agricole': 'credit-agricole.fr',
            'societegenerale': 'societegenerale.fr', 'bnp': 'bnpparibas.fr', 'lcl': 'lcl.fr',
            # Restauration fast-food / delivery
            'dominos': 'dominos.fr', 'pizza hut': 'pizzahut.fr', 'subway': 'subway.com',
            'quick': 'quick.fr', 'kfc': 'kfc.fr', 'five guys': 'fiveguys.fr',
            'just eat': 'just-eat.fr', 'uber eats': 'ubereats.com',
        }

        # Known Subscription Services List (for immediate detection)
        self.subscription_keywords = [
            'netflix', 'spotify', 'youtube', 'disney', 'prime video', 'prime member', 'apple', 'icloud', 'google one', 'google storage',
            'adobe', 'microsoft', 'chatgpt', 'openai', 'github', 'linkedin',
            'canva', 'figma', 'notion', 'slack', 'zoom', 'dropbox',
            'edf', 'engie', 'totalenergies', 'sfr', 'orange', 'bouygues', 'free mobile', 'free telecom',
            'alan', 'doctolib', 'fitbit', 'strava', 'zwift', 'gym', 'fitness',
            'le monde', 'mediapart', 'nyt', 'wsj', 'ft', 'les echos',
            'canal+', 'beinsport', 'rmc sport', 'dazn', 'deezer', 'tidal', 'audible',
            'ovh', 'aws', 'heroku', 'digitalocean', 'hetzner'
        ]

    def _get_domain(self, merchant_name):
        """Match merchant name against logo_map using raw title too (handles E.LECLERC, LIDL 0123, etc.)"""
        merchant_lower = merchant_name.lower()
        # Try longest key first to avoid 'bp' matching 'burger king'
        for key in sorted(self.logo_map, key=len, reverse=True):
            if key in merchant_lower:
                return self.logo_map[key]
        return None

    def _get_domain_from_raw(self, raw_title):
        """Match against raw transaction title directly for better coverage."""
        if not raw_title:
            return None
        raw_lower = str(raw_title).lower()
        for key in sorted(self.logo_map, key=len, reverse=True):
            if key in raw_lower:
                return self.logo_map[key]
        return None

    def analyze(self):
        if self.df.empty:
            return {"subscriptions": [], "cash_flow": [], "transactions": [], "stats": {}}

        df = self.df.copy()

        # 1. Date Parsing
        if 'timestamp' in df.columns:
             try:
                # Handle hybrid formats
                df['date'] = pd.to_datetime(df['timestamp'])
             except:
                df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        elif 'date' in df.columns:
             df['date'] = pd.to_datetime(df['date'])
        else:
             return {"error": "Date field missing in transactions"}

        df = df.sort_values('date')

        # 2. Value Normalization
        def get_amount(row):
            if 'amount' in row:
                if isinstance(row['amount'], (int, float)): return float(row['amount'])
                if isinstance(row['amount'], dict): return float(row['amount'].get('value', 0))
            return 0.0
        df['val'] = df.apply(get_amount, axis=1)

        # 3. Clean Merchant Name
        raw_col = 'title' if 'title' in df.columns else 'name' if 'name' in df.columns else 'description'
        sub_col = 'subTitle' if 'subTitle' in df.columns else 'subtitle' if 'subtitle' in df.columns else None

        def clean_merchant_name(row):
            s = str(row.get(raw_col, '')).lower()
            s = re.sub(r'[\d\-.,]', ' ', s)
            s = re.sub(r'\s[a-z]{2,3}$', '', s)

            words = s.split()
            junk = ['payment', 'carte', 'cb', 'vir', 'prlv', 'paiement', 'fac', 'bill', 'sepa', 'debit', 'date', 'value', 'arl']
            words = [w for w in words if w not in junk and len(w) > 1]
            if not words: return "Inconnu"

            name_str = " ".join(words)
            for key in self.logo_map:
                if key in name_str: return key.capitalize()

            return " ".join(w.capitalize() for w in words[:2])

        df['merchant'] = df.apply(clean_merchant_name, axis=1)

        # 4. Classification
        category_rules = {
            'Shopping': ['amazon', 'fnac', 'darty', 'boulanger', 'zara', 'h&m', 'uniqlo', 'nike', 'adidas', 'vinted', 'paypal', 'apple store'],
            'Groceries': ['auchan', 'leclerc', 'carrefour', 'intermarche', 'lidl', 'aldi', 'franprix', 'monoprix', 'biocoop', 'market', 'super U'],
            'Transport': ['uber', 'sncf', 'ratp', 'trainline', 'total', 'shell', 'bp', 'esso', 'blablacar', 'scooter', 'lime', 'bird', 'bolt'],
            'Food & Drink': ['mcdonalds', 'burger king', 'starbucks', 'deliveroo', 'uber eats', 'restaurant', 'bistro', 'cafe', 'bar', 'sushi', 'pizza'],
            'Entertainment': ['cinema', 'ugc', 'gaumont', 'steam', 'playstation', 'xbox', 'nintendo'],
            'Travel': ['airbnb', 'booking', 'expedia', 'hotels', 'easyjet', 'ryanair', 'air france', 'transavia'],
            'Utilities': ['edf', 'engie', 'orange', 'sfr', 'bouygues', 'free', 'internet', 'mobile', 'water', 'electric'],
            'Tech': ['google', 'microsoft', 'adobe', 'github', 'openai', 'ovh', 'aws', 'apple'],
            'Health': ['pharmacie', 'doctolib', 'alan', 'mutuelle', 'doctor', 'dentist'],
            'Home': ['ikea', 'leroy merlin', 'castorama', 'habitat', 'maison'],
            'Finance': ['bank', 'frais', 'cotisation', 'qonto', 'shine', 'revolut', 'n26', 'lydia']
        }

        # Merge static services into rules
        for svc_type, items in self.services_statiques.items():
            for item in items:
                cat_name = item['categorie']
                if cat_name not in category_rules:
                    category_rules[cat_name] = []
                category_rules[cat_name].append(item['nom'].lower())

        def classify_row(row):
            evt = str(row.get('eventType', '')).lower()
            if evt in ['trade', 'savings_plan']: return 'savings', 'Épargne'

            nm = str(row.get(raw_col, '')).lower()
            sub = str(row.get(sub_col, '')).lower() if sub_col else ''

            invest_ind = ['(adr)', ' inc.', ' corp.', ' ag ', ' se ', ' plc ', 'nv', 'gmbh', 'ishares', 'vanguard', 'xtrackers', 'amundi', 'spdr', 'lyxor', 'etf', 'wisdomtree']
            invest_act = ['sparplan', 'savings plan', 'order', 'kauf', 'buy', 'invest', 'achat', 'titre', 'souscription']

            if any(x in nm for x in invest_ind) or any(x in sub for x in invest_ind) or any(x in sub for x in invest_act):
                return 'savings', 'Épargne'

            if row['val'] >= 0: return 'income', 'Revenus'

            m_lower = row['merchant'].lower()
            for cat, keywords in category_rules.items():
                if any(k in m_lower or k in nm for k in keywords):
                    return 'expense', cat

            return 'expense', 'Autre'

        df[['cat', 'category']] = df.apply(lambda x: pd.Series(classify_row(x)), axis=1)

        # 5. Advanced Subscription Detection (Frequency Analysis + Known List)
        subscriptions = []
        expenses = df[df['cat'] == 'expense'].copy()

        # A. Known List Detection
        for merchant, group in expenses.groupby('merchant'):
            m_lower = merchant.lower()
            if any(k in m_lower for k in self.subscription_keywords):
                last_row = group.sort_values('date').iloc[-1]
                domain = self._get_domain(merchant)
                logo_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128" if domain else ""

                subscriptions.append({
                    "name": merchant,
                    "amount": float(abs(last_row['val'])),
                    "frequency": 'Mensuel (Est.)',
                    "last_payment": last_row['date'].strftime('%Y-%m-%d'),
                    "next_payment": (last_row['date'] + timedelta(days=30)).strftime('%Y-%m-%d'),
                    "confidence": 90,
                    "logo": logo_url,
                    "domain": domain
                })

        # B. Frequency Detection
        # Normalize date to start of day for cleaner diffs
        expenses['date_norm'] = expenses['date'].dt.normalize()
        expenses['amount_approx'] = expenses['val'].round(0)

        for (merchant, amount), group in expenses.groupby(['merchant', 'amount_approx']):
            if len(group) < 2: continue # Need at least 2 occurrences

            group = group.sort_values('date')
            dates = group['date'].values

            intervals = []
            for i in range(1, len(dates)):
                diff = (dates[i] - dates[i-1]) / np.timedelta64(1, 'D')
                intervals.append(diff)

            if not intervals: continue

            avg_interval = np.mean(intervals)
            std_dev = np.std(intervals)

            # Detect periodicity
            freq = None
            if 25 <= avg_interval <= 35 and std_dev < 5: freq = 'Monthly'
            elif 350 <= avg_interval <= 380 and std_dev < 10: freq = 'Annuel'

            if freq:
                last_tx_date = pd.to_datetime(dates[-1])
                confidence = max(0, min(100, int(100 - (std_dev * 5))))

                days_since_last = (datetime.now() - last_tx_date).days
                is_active = (freq == 'Monthly' and days_since_last < 45) or (freq == 'Annuel' and days_since_last < 380)

                if is_active:
                    domain = self._get_domain(merchant)
                    logo_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128" if domain else ""

                    subscriptions.append({
                        "name": merchant,
                        "amount": float(abs(group['val'].mean())),
                        "frequency": freq,
                        "last_payment": last_tx_date.strftime('%Y-%m-%d'),
                        "next_payment": (last_tx_date + timedelta(days=avg_interval)).strftime('%Y-%m-%d'),
                        "confidence": confidence,
                        "logo": logo_url,
                        "domain": domain
                    })

        # Remove duplicates (keep highest confidence)
        unique_subs = {}
        for sub in subscriptions:
            key = sub['name']
            if key not in unique_subs or sub['confidence'] > unique_subs[key]['confidence']:
                unique_subs[key] = sub
        subscriptions = sorted(list(unique_subs.values()), key=lambda x: x['amount'])

        # 6. Monthly Cash Flow Stats
        df['month_str'] = df['date'].dt.strftime('%Y-%m')
        cash_flow = []
        for name, group in df.groupby('month_str'):
            inc = group[(group['cat'] == 'income')]['val'].sum()
            exp = group[(group['cat'] == 'expense')]['val'].sum()
            inv = group[(group['cat'] == 'investment') | (group['cat'] == 'savings')]['val'].sum()

            # Savings = (Income + Expenses (neg)) + Investments (neg->pos)
            # This represents Net Change in Wealth excluding market variation
            savings_val = (inc + exp) + abs(inv)

            cash_flow.append({
                "month": name,
                "income": round(inc, 2),
                "expense": round(abs(exp), 2),
                "investment": round(abs(inv), 2),
                "net": round(inc + exp + inv, 2), # Net flow
                "savings": round(savings_val, 2) # Total Savings (Cash + Investment)
            })

        # 7. Spending Breakdown
        breakdown = []
        recent_expenses = df[(df['cat'] == 'expense')].tail(100) # Analyze last 100 txns for breakdown
        if not recent_expenses.empty:
            by_cat = recent_expenses.groupby('category')['val'].sum().abs().sort_values(ascending=False)
            total = by_cat.sum()
            for cat, val in by_cat.items():
                breakdown.append({
                    "category": cat,
                    "amount": round(val, 2),
                    "percentage": round((val/total)*100, 1) if total > 0 else 0
                })

        # 8. Recent formatted transactions with logos
        recent_txns = []
        # Return ALL transactions for full history analysis
        for _, row in df.sort_values('date', ascending=False).iterrows():
            logo = ""
            # Priority 1: TR CDN logo via ISIN (stock/ETF transactions)
            icon_field = str(row.get('icon', ''))
            isin_match = re.search(r'logos/([A-Z0-9]{12})', icon_field)
            if isin_match:
                isin = isin_match.group(1)
                logo = f"https://assets.traderepublic.com/img/logos/{isin}/v2/dark.min.svg"
            else:
                # Priority 2: match on raw title first, then cleaned merchant name
                raw_title = str(row.get(raw_col, ''))
                domain = self._get_domain_from_raw(raw_title) or self._get_domain(row['merchant'])
                if domain:
                    logo = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"

            recent_txns.append({
                "date": row['date'].strftime('%Y-%m-%d'),
                "merchant": row['merchant'],
                "amount": round(row['val'], 2),
                "category": row['category'],
                "logo": logo,
                "isin": isin_match.group(1) if isin_match else ""
            })

        stats = {
            "total_subscriptions_monthly": sum([abs(s['amount']) for s in subscriptions if s['frequency'] == 'Monthly']) + (sum([abs(s['amount']) for s in subscriptions if s['frequency'] == 'Annuel'])/12),
            "monthly_burn_rate": cash_flow[-1]['expense'] if cash_flow else 0, # Last month
            "projected_annual_savings": (cash_flow[-1]['savings'] * 12) if cash_flow else 0
        }

        return {
            "recurring_subscriptions": subscriptions,
            "cash_flow": cash_flow,
            "spending_breakdown": breakdown,
            "transactions": recent_txns,
            "summary": stats
        }