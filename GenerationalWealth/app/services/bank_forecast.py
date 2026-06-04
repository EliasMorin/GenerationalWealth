import json
import time
from datetime import datetime
from typing import List, Dict, Any

# Assuming these will be imported from utils or defined locally if not available
try:
    from ..utils.http import create_retry_session
    from ..utils.token_bucket import groq_rate_limiter, call_groq_api
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

    # Fallback token bucket and Groq call
    class TokenBucket:
        def __init__(self, capacity, refill_rate):
            self.capacity = capacity
            self.tokens = capacity
            self.refill_rate = refill_rate
            self.last_refill = time.time()
            import threading
            self.lock = threading.Lock()

        def consume(self, tokens_needed):
            with self.lock:
                now = time.time()
                elapsed = now - self.last_refill
                self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
                self.last_refill = now
                if self.tokens >= tokens_needed:
                    self.tokens -= tokens_needed
                    return True
                return False

    groq_rate_limiter = TokenBucket(capacity=2500, refill_rate=50)

    def call_groq_api(messages, temperature=0.7, max_tokens=1500, retries=3):
        import os
        import requests
        GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
        GROQ_MODEL = "llama-3.3-70b-versatile"
        GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

        # Simplified fallback - in reality would have proper rate limiting and retries
        try:
            response = requests.post(
                GROQ_API_URL,
                headers={
                    'Authorization': f'Bearer {GROQ_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': GROQ_MODEL,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens
                },
                timeout=15
            )
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                return f"Erreur API: {response.status_code}"
        except Exception as e:
            return f"Erreur: {str(e)}"

from bs4 import BeautifulSoup as _BS


class BankForecastScraper:
    def __init__(self):
        self.results = []

    def _scrape_page(self, page, url, title_selectors, link_selectors):
        """Helper générique avec Playwright"""
        try:
            print(f"   Getting {url}...")
            # Reduced timeout and domcontentloaded logic might be too strict for some SPAs
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
            except Exception as nav_e:
                print(f"   Navigation Warning for {url}: {nav_e}")

            time.sleep(5) # Wait for hydration/modals

            # Dismiss cookies modal if possible (generic)
            try:
                page.locator("button:has-text('Accept'), button:has-text('Allow'), button:has-text('Agree')").first.click(timeout=2000)
            except: pass

            # Extract Titles
            titles = []
            for sel in title_selectors:
                try:
                    elements = page.locator(sel).all()
                    for el in elements[:15]: # Increased limit
                        txt = el.inner_text().strip()
                        if txt and len(txt) > 10 and txt not in titles:
                            titles.append(txt)
                except: continue

            if not titles:
                # Fallbck generic H2/H3
                try:
                    for tag in ['h2', 'h3', 'h4']:
                         elements = page.locator(tag).all()
                         for el in elements[:5]:
                             txt = el.inner_text().strip()
                             if txt and len(txt) > 10 and txt not in titles:
                                 titles.append(txt)
                except: pass

            return titles, []
        except Exception as e:
            print(f"   Error scraping {url}: {e}")
            return [], []

    def analyze_articles(self):
        """Simple heuristic analysis of titles"""
        analyses = []

        # Simple keywords (English + French based on context)
        bullish_terms = ['growth', 'croissance', 'opportunity', 'opportunité', 'bull', 'rally', 'strong', 'fort', 'buy', 'achat', 'positive', 'improving', 'upside']
        bearish_terms = ['recession', 'récession', 'risk', 'risque', 'bear', 'crash', 'downside', 'baissier', 'inflation', 'crisis', 'crise', 'weak', 'faible', 'slowdown']

        for res in self.results:
            titles = res.get('titles', [])
            if not titles:
                # Try to parse from summary if titles are missing but summary exists
                if 'summary' in res and res['summary'].startswith('\n- '):
                    titles = [t.strip() for t in res['summary'].split('\n- ') if t.strip()]

            if not titles:
                continue

            text = " ".join(titles).lower()
            bull_score = sum(1 for w in bullish_terms if w in text)
            bear_score = sum(1 for w in bearish_terms if w in text)

            sentiment = "Neutral"
            if bull_score > bear_score: sentiment = "Bullish"
            elif bear_score > bull_score: sentiment = "Bearish"

            interpretation = ""
            if sentiment == "Bullish":
                interpretation = "Focus sur la croissance et les opportunités d'investissement. Le narratif est positif."
            elif sentiment == "Bearish":
                interpretation = "Prudence recommandée face aux risques macroéconomiques et aux incertitudes."
            else:
                interpretation = "Approche équilibrée, surveillance des indicateurs clés sans biais marqué."

            analyses.append({
                'bank': res.get('bank'),
                'sentiment': sentiment,
                'summary': f"Analyse basée sur {len(titles)} articles.",
                'interpretation': interpretation,
                'analysis_text': f"Le ton général relevé est {sentiment.lower()} ({bull_score} vs {bear_score}). {interpretation}"
            })

        return analyses

    def scrape_all(self):
        # Configuration des cibles
        targets = [
            {
                'bank': 'JPMorgan',
                'url': 'https://www.jpmorgan.com/insights/global-research/outlook',
                'selectors': ['h2', 'h3', '.article-title', '.card-title']
            },
            {
                'bank': 'BNP Paribas',
                'url': 'https://globalmarkets.cib.bnpparibas/markets-360/',
                'selectors': ['h2', 'h3', '.post-title', '.article-title']
            },
            {
                'bank': 'Société Générale',
                'url': 'https://insight-public.sgmarkets.com/insights',
                'selectors': ['h2', 'h3', '.insight-title', '.card-title']
            },
            {
                'bank': 'Deloitte',
                'url': 'https://www.deloitte.com/us/en/insights/industry/financial-services/financial-services-industry-outlooks.html',
                'selectors': ['h2', 'h3', '.promo-title', '.article-title']
            },
            {
                'bank': 'McKinsey',
                'url': 'https://www.mckinsey.com/industries/financial-services/our-insights',
                'selectors': ['h2', 'h3', '.article-title', '.content-card h3', '.item-title']
            },
            {
                'bank': 'Barclays',
                'url': 'https://www.ib.barclays/research/global-outlook.html',
                'selectors': ['h2', 'h3', '.title', '.card-title']
            },
            {
                'bank': 'BlackRock',
                'url': 'https://www.blackrock.com/us/individual/insights/blackrock-investment-institute',
                'selectors': ['h2', 'h3', '.card-title', '.article-title', 'h4']
            },
            {
                'bank': 'Goldman Sachs',
                'url': 'https://www.goldmansachs.com/insights',
                'selectors': ['h2', 'h3', '.ti-card-title', 'span.h3', '.card__title']
            },
            {
                'bank': 'Morgan Stanley',
                'url': 'https://www.morganstanley.com/insights',
                'selectors': ['h2', 'h3', '.article-title', '.title']
            },
            {
                'bank': 'UBS',
                'url': 'https://www.ubs.com/global/en/wealth-management/chief-investment-office.html',
                'selectors': ['h2', 'h3', '.feature-title', '.teaser-title']
            }
        ]

        # Lancement Playwright
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )

                print("[START] Starting Bank Scrape (Playwright Mode)...")

                for t in targets:
                    print(f"Scraping {t['bank']}...")
                    titles, _ = self._scrape_page(page, t['url'], t['selectors'], [])

                    if titles:
                        self.results.append({
                            'bank': t['bank'],
                            'url': t['url'],
                            'titles': titles,
                            'timestamp': datetime.now().isoformat()
                        })
                    else:
                        print(f"[WARN] No titles found for {t['bank']}")

                browser.close()
        except Exception as e:
            print(f"[HOT] Critical Playwright Error: {e}")
            return []

        print(f"[DATA] Bank Scrape complete. Found {len(self.results)} articles.")

        # Sauvegarde
        try:
            # Import here to avoid circular imports
            from ..utils.db import db_save_generic
            db_save_generic('bank_raw_scrape', self.results)
        except ImportError:
            print("[WARN] Could not save bank raw scrape to DB")

        # Enregistrement "Best Effort"
        formatted_for_db = []
        for res in self.results:
            summary = "\n- " + "\n- ".join(res.get('titles', []))

            formatted_for_db.append({
                'bank': res.get('bank'),
                'url': res.get('url'),
                'date': res.get('timestamp'),
                'summary': summary,
                'sentiment': 'Neutral',
                'recommendation': 'Voir Détails',
                'ticker': None,
                'target_price': None
            })

        # Save to DB
        try:
            from ..utils.db import db_save_bank_forecasts
            db_save_bank_forecasts(formatted_for_db)
        except ImportError:
            print("[WARN] Could not save bank forecasts to DB")

        return self.results