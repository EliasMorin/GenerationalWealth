import json
import re
import requests
from typing import List, Dict, Any, Optional

# Assuming these will be imported from utils or defined locally if not available
try:
    from ..utils.http import create_retry_session
    from ..utils.token_bucket import call_groq_api
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

    def call_groq_api(messages, max_tokens=600, temperature=0.0):
        import os
        import requests
        GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
        GROQ_MODEL = "llama-3.3-70b-versatile"
        GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

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


class PolymarketService:
    def __init__(self):
        self.base_url = "https://gamma-api.polymarket.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        }

    def scrape_predictions_page(self, slug: str) -> List[Dict[str, Any]]:
        """
        Scrape directement https://polymarket.com/predictions/<slug>
        en parsant __NEXT_DATA__ — MÊME données que le site officiel.
        Retourne la liste des events avec markets, volume, liquidity, endDate.
        """
        url = f"https://polymarket.com/predictions/{slug}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=12)
            resp.raise_for_status()
        except Exception as e:
            print(f"Polymarket scrape error ({url}): {e}")
            return []

        try:
            from bs4 import BeautifulSoup as _BS
            soup = _BS(resp.text, 'html.parser')
            nd_tag = soup.find('script', id='__NEXT_DATA__')
            if not nd_tag:
                return []
            nd = json.loads(nd_tag.string)
            pages = (nd['props']['pageProps']
                       ['dehydratedState']['queries'][0]
                       ['state']['data']['pages'])
        except Exception as e:
            print(f"Polymarket parse error ({url}): {e}")
            return []

        results = []
        seen_slugs = set()

        for page in pages:
            for event in page.get('results', []):
                event_slug = event.get('slug', '')
                if event_slug in seen_slugs:
                    continue
                seen_slugs.add(event_slug)

                event_title = event.get('title', '')
                event_vol   = float(event.get('volume', 0) or 0)
                event_liq   = float(event.get('liquidity', 0) or 0)
                event_end   = event.get('endDate')
                event_url   = f"https://polymarket.com/event/{event_slug}"

                sub_markets = event.get('markets', [])

                # Build outcomes from sub-markets for multi-outcome events
                # For simple Yes/No events there's usually 1 market
                # For range events ("what price will MSFT hit?") there are many sub-markets
                if len(sub_markets) == 1:
                    m = sub_markets[0]
                    try:
                        prices = json.loads(m.get('outcomePrices', '[]') or '[]') if isinstance(m.get('outcomePrices'), str) else (m.get('outcomePrices') or [])
                        names  = json.loads(m.get('outcomes', '[]') or '[]') if isinstance(m.get('outcomes'), str) else (m.get('outcomes') or [])
                    except Exception:
                        prices, names = [], []
                    formatted_outcomes = [{'name': names[i], 'price': prices[i]} for i in range(min(len(prices), len(names)))]
                    question = m.get('question') or event_title
                    proba = prices[0] if prices else '0'
                else:
                    # Multi-outcome: each sub-market is an option (e.g. "reach $450?")
                    # Build outcome list from sub-markets — show all options
                    formatted_outcomes = []
                    question = event_title
                    proba = '0'
                    for m in sub_markets:
                        try:
                            prices = json.loads(m.get('outcomePrices', '[]') or '[]') if isinstance(m.get('outcomePrices'), str) else (m.get('outcomePrices') or [])
                        except Exception:
                            prices = []
                        label = m.get('groupItemTitle') or m.get('question') or ''
                        yes_price = prices[0] if prices else '0'
                        formatted_outcomes.append({'name': label, 'price': yes_price})
                    # Sort by probability desc to surface most likely outcome
                    formatted_outcomes.sort(key=lambda x: float(x['price'] or 0), reverse=True)
                    if formatted_outcomes:
                        proba = formatted_outcomes[0]['price']

                results.append({
                    'question': question,
                    'probability': proba,
                    'outcomes': formatted_outcomes,
                    'volume_usd': event_vol,
                    'liquidity': event_liq,
                    'end_date': event_end,
                    'url': event_url,
                    'event_slug': event_slug,
                    'relevance_score': None,
                })

        # Sort by volume desc
        results.sort(key=lambda x: x['volume_usd'], reverse=True)
        return results

    def search_by_entity(self, entity_name: str, search_terms: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Recherche TOUS les marchés actifs liés à une entité (entreprise, ticker...).
        Utilise plusieurs requêtes textuelles et filtre UNIQUEMENT sur le titre de la question.
        Equivalent à ce qu'affiche polymarket.com/predictions/<slug>.
        """
        # Build the list of terms to search for
        if search_terms is None:
            search_terms = [entity_name]
        # Deduplicate, preserve order
        all_terms = list(dict.fromkeys([entity_name] + list(search_terms)))
        # Normalised for title matching
        match_tokens = [t.lower() for t in all_terms]

        seen_slugs = set()
        results = []

        for term in all_terms:
            try:
                response = requests.get(
                    f"{self.base_url}/events",
                    headers=self.headers,
                    params={'q': term, 'closed': 'false', 'limit': 100,
                            'order': 'volume24hr', 'ascending': 'false'},
                    timeout=8
                )
                response.raise_for_status()
                data = response.json() or []
            except Exception as e:
                print(f"Polymarket entity search error ({term}): {e}")
                continue

            for event in data:
                slug = event.get('slug', '')
                if slug in seen_slugs:
                    continue

                markets_list = event.get('markets', [])
                if not markets_list:
                    continue

                # --- Collect valid markets whose QUESTION TITLE contains the entity ---
                valid = []
                for market in markets_list:
                    question_lower = (market.get('question') or '').lower()
                    # STRICT: at least one search token must appear in the question title
                    if not any(tok in question_lower for tok in match_tokens):
                        continue
                    vol = float(market.get('volume', 0))
                    if vol < 0:  # keep even 0-volume (liquidity may still be there)
                        continue
                    try:
                        prices = json.loads(market.get('outcomePrices', '[]'))
                        names = json.loads(market.get('outcomes', '[]'))
                    except Exception:
                        prices, names = [], []
                    formatted_outcomes = [
                        {'name': names[i], 'price': prices[i]}
                        for i in range(min(len(prices), len(names)))
                    ]
                    valid.append({
                        'question': market.get('question'),
                        'probability': prices[0] if prices else '0',
                        'outcomes': formatted_outcomes,
                        'volume_usd': vol,
                        'liquidity': float(market.get('liquidity', 0)),
                        'end_date': market.get('endDate'),
                        'url': f"https://polymarket.com/event/{slug}",
                        'event_slug': slug,
                        'relevance_score': None
                    })

                if not valid:
                    continue

                # Keep ALL valid markets per event (user wants to see every bet type)
                # but deduplicate same event slug across term loops
                seen_slugs.add(slug)
                # Sort by volume desc within event
                valid.sort(key=lambda x: x['volume_usd'], reverse=True)
                results.extend(valid)

        # Global dedup on question text, sort by volume
        seen_q = set()
        deduped = []
        for m in sorted(results, key=lambda x: x['volume_usd'], reverse=True):
            if m['question'] not in seen_q:
                seen_q.add(m['question'])
                deduped.append(m)

        return deduped

    def search_by_tag(self, tag_slug: str) -> List[Dict[str, Any]]:
        """Kept for backwards compat. Delegates to search_by_entity."""
        return self.search_by_entity(tag_slug, search_terms=[tag_slug])

    def score_markets_with_groq(self, markets: List[Dict[str, Any]], asset_context: str) -> List[Dict[str, Any]]:
        """
        Soumet les titres des marchés à Groq (LLM) pour scorer leur pertinence financière (0-10).
        Retourne la liste avec 'relevance_score' rempli, triée par score desc.
        """
        if not markets:
            return markets
        titles = [{'id': i, 'title': m['question']} for i, m in enumerate(markets)]
        prompt = (
            f'You are a financial analyst. The user holds "{asset_context}" in their portfolio.\n'
            f'Below are prediction market titles from Polymarket. Score each one\'s FINANCIAL RELEVANCE '
            f'for someone holding {asset_context} stock (0-10):\n'
            f'- 9-10: Direct stock price impact (earnings, CEO change, major acquisition)\n'
            f'- 7-8: Significant indirect impact (regulatory, macro competitor)\n'
            f'- 4-6: Related but minor\n'
            f'- 0-3: Tangential or noise\n\n'
            f'Markets:\n{json.dumps(titles, ensure_ascii=False)}\n\n'
            f'Return ONLY a JSON array: [{{"id": 0, "score": 8}},...] with no explanation.'
        )
        try:
            raw = call_groq_api([{"role": "user", "content": prompt}], max_tokens=600, temperature=0.0)
            raw = raw.replace('```json', '').replace('```', '').strip()
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                scored = json.loads(match.group(0))
                score_map = {s['id']: s['score'] for s in scored if 'id' in s and 'score' in s}
                for i, m in enumerate(markets):
                    m['relevance_score'] = score_map.get(i, 0)
            markets.sort(key=lambda x: x.get('relevance_score') or 0, reverse=True)
        except Exception as e:
            print(f"Groq scoring error: {e}")
        return markets

    def search_markets(self, query: str) -> List[Dict[str, Any]]:
        """
        Recherche des marchés sur Polymarket via l'API Gamma.
        Fallback sur /events avec filtrage client strict car /markets?q renvoie 422.
        """
        # print(f"\n? Recherche Polymarket pour: '{query}'...")

        # On repasse sur /events qui répond 200, mais on va filtrer nous-même
        endpoint = f"{self.base_url}/events"

        params = {
            'q': query,           # On laisse le q pour l'API (fuzzy search)
            'limit': 100,         # AUGMENTE à 100 pour trouver les items enfouis
            'closed': 'false',    # Actifs
            'order': 'volume24hr', # Les plus actifs
            'ascending': 'false'
        }

        try:
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=6)
            response.raise_for_status()
            data = response.json()

            if not data:
                # print("   -> Aucun resultat trouve (API vide).")
                return []

            results = []
            query_words = query.lower().split()

            for event in data:
                # --- GROUPING LOGIC FOR EVENT ---
                # To avoid duplicates like "Will Fed Hike 25?" "Will Fed Hike 50?",
                # we group all valid markets for this event and pick only the HIGHEST VOLUME one.

                event_matches = []
                markets = event.get('markets', [])
                event_description = event.get('description', '').lower()
                event_title = event.get('title', '').lower()

                for market in markets:
                    question = market.get('question', '').lower()
                    market_desc = market.get('description', '').lower()

                    # 1. FILTRE SEMANTIQUE STRICT
                    # On cherche dans Question ou Titre Event SEULEMENT pour la validation principale
                    primary_search_text = f"{question} {event_title}"
                    full_search_text = f"{question} {event_title} {event_description} {market_desc}"

                    match_count = 0
                    primary_match = False

                    for w in query_words:
                        if w in full_search_text:
                            match_count += 1
                        if w in primary_search_text:
                            primary_match = True

                    # Si on n'a aucun match global, c'est mort
                    if match_count == 0: continue

                    # STRICT: Au moins un mot clé doit être dans le Titre ou la Question
                    if not primary_match: continue

                    # Filtre strict multi-mots (ex: "Air Liquide")
                    if len(query_words) > 1 and match_count < len(query_words):
                        continue

                    # BLACKLIST ANTI-BRUIT (Logan Paul, etc.)
                    # Si la question contient des termes "poubelle" et la query ne les ciblait pas
                    garbage_terms = ["logan paul", "charizard", "pokemon", "boxing", "jake paul", "mikaylah", "demi lovato"]
                    if any(bad in question for bad in garbage_terms) and not any(bad in query.lower() for bad in garbage_terms):
                        print(f"[BLOCK] [FILTERED] Garbage content: {question}")
                        continue

                    # 2. FILTRE VOLUME
                    volume = float(market.get('volume', 0))
                    if volume < 10: continue # Minimum noise filter

                    try:
                        prices = json.loads(market.get('outcomePrices', '[]'))
                        names = json.loads(market.get('outcomes', '[]'))
                    except:
                        prices = []
                        names = []

                    # Construct specific outcomes list
                    formatted_outcomes = []
                    # Ensure we handle cases where lists might not match length, though API usually consistent
                    limit = min(len(prices), len(names))
                    for i in range(limit):
                        formatted_outcomes.append({
                            'name': names[i],
                            'price': prices[i]
                        })

                    # Fallback probability (usually the first one, or the highest?)
                    # For binary Yes/No, usually we want the 'Yes' price which is often first, but let's just pass the list
                    proba = prices[0] if prices else '0'

                    event_matches.append({
                        'question': market.get('question'),
                        'probability': proba, # Legacy field for sorting/primary display if needed
                        'outcomes': formatted_outcomes, # NEW: Full outcomes list
                        'volume_usd': volume,
                        'end_date': market.get('endDate'),
                        'url': f"https://polymarket.com/event/{event.get('slug')}",
                        'event_slug': event.get('slug')
                    })

                # Pick ONLY the best market from this event (Highest Volume)
                if event_matches:
                    event_matches.sort(key=lambda x: x['volume_usd'], reverse=True)
                    best_market = event_matches[0]
                    # Clean up question? No, use raw question.
                    results.append(best_market)

            # Tri final par volume
            results.sort(key=lambda x: x['volume_usd'], reverse=True)
            return results
        except Exception as e:
            print(f"Polymarket search error: {e}")
            return []