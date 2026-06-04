import requests
import cloudscraper
from bs4 import BeautifulSoup
import time
import socket
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


class TruthSocialScraper:
    """
    Scraper pour récupérer les posts de Truth Social avec gestion de Cloudflare
    """

    def __init__(self):
        # Créer un scraper qui gère automatiquement Cloudflare
        try:
            self.scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False
                }
            )
        except Exception:
            print("Cloudscraper not available, falling back to requests (might fail)")
            self.scraper = requests.Session()

        # Headers réalistes
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }

        self.base_url = "https://truthsocial.com"

        # Known account IDs to skip the lookup step (avoids extra request that may fail)
        self.KNOWN_ACCOUNT_IDS = {
            'realDonaldTrump': '107780257626128497',
            'realdonald trump': '107780257626128497',
        }

    def get_user_posts(self, username: str, max_posts: int = 20) -> List[Dict[str, Any]]:
        """
        Récupère les posts via l'API JSON publique de Truth Social (sans authentification).
        Utilise l'ID de compte connu pour éviter le step lookup.
        """
        username = username.replace('@', '').strip()
        print(f"TRUTH SOCIAL: Récupération des posts de @{username}...")

        # Resolve account ID: use known map first, then try lookup
        account_id = self.KNOWN_ACCOUNT_IDS.get(username) or self.KNOWN_ACCOUNT_IDS.get(username.lower())

        if not account_id:
            print(f"TRUTH SOCIAL: ID inconnu pour @{username}, tentative de lookup...")
            try:
                lookup_url = f"{self.base_url}/api/v1/accounts/lookup"
                r = requests.get(
                    lookup_url,
                    params={'acct': username},
                    headers={**self.headers, 'Accept': 'application/json'},
                    timeout=20
                )
                print(f"TRUTH SOCIAL lookup: HTTP {r.status_code}")
                if r.status_code == 200:
                    account_id = r.json().get('id')
                    print(f"TRUTH SOCIAL: ID trouvé via lookup: {account_id}")
                else:
                    print(f"TRUTH SOCIAL lookup body: {r.text[:200]}")
            except Exception as e:
                print(f"TRUTH SOCIAL lookup error: {e}")

        if not account_id:
            print(f"TRUTH SOCIAL: Impossible de résoudre l'ID pour @{username}.")
            return []

        # Strategy 1: cloudscraper / requests
        api_headers = {
            **self.headers,
            'Accept': 'application/json',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Referer': 'https://truthsocial.com/',
        }
        statuses_url = f"{self.base_url}/api/v1/accounts/{account_id}/statuses"
        print(f"TRUTH SOCIAL: Requête statuses -> {statuses_url}")
        for attempt, client in enumerate([self.scraper, requests.Session()]):
            try:
                r = client.get(statuses_url, params={'limit': max_posts}, headers=api_headers, timeout=30)
                print(f"TRUTH SOCIAL statuses (attempt {attempt+1}): HTTP {r.status_code}, taille={len(r.content)} octets")
                if r.status_code == 200:
                    data = r.json()
                    posts = self._parse_posts(data)
                    print(f"TRUTH SOCIAL: {len(posts)} posts récupérés (requests).")
                    return posts
            except Exception as e:
                print(f"TRUTH SOCIAL statuses exception (attempt {attempt+1}): {e}")

        # Strategy 2: requests via Tor SOCKS5 (change d'IP de sortie)
        print("TRUTH SOCIAL: Tentative via Tor (SOCKS5)...")
        tor_raw = self._get_posts_via_tor(account_id, max_posts, playwright=False)
        if tor_raw:
            return self._parse_posts(tor_raw)

        # Strategy 3: Playwright via Tor (passe aussi le challenge JS Cloudflare)
        print("TRUTH SOCIAL: Tentative via Playwright+Tor...")
        tor_raw = self._get_posts_via_tor(account_id, max_posts, playwright=True)
        if tor_raw:
            return self._parse_posts(tor_raw)

        return []

    def _tor_available(self) -> bool:
        """Vérifie que le daemon Tor écoute sur 127.0.0.1:9050."""
        try:
            s = socket.create_connection(('127.0.0.1', 9050), timeout=2)
            s.close()
            return True
        except Exception:
            return False

    def _new_tor_circuit(self) -> bool:
        """Demande un nouvel exit node Tor via le control port (9051)."""
        try:
            s = socket.socket()
            s.settimeout(3)
            s.connect(('127.0.0.1', 9051))
            # Authentification vide (CookieAuthentication 0 ou HashedControlPassword vide)
            s.sendall(b'AUTHENTICATE ""\r\nSIGNAL NEWNYM\r\nQUIT\r\n')
            resp = s.recv(256)
            s.close()
            ok = b'250' in resp
            print(f"TRUTH SOCIAL Tor NEWNYM: {'OK' if ok else 'FAIL'} ({resp[:40]})")
            if ok:
                time.sleep(3)  # attendre que le nouveau circuit soit établi
            return ok
        except Exception as e:
            print(f"TRUTH SOCIAL Tor NEWNYM error: {e}")
            return False

    def _get_posts_via_tor(self, account_id: str, max_posts: int, playwright: bool = False):
        """Requête vers Truth Social via Tor SOCKS5 (change l'IP de sortie).
        Rotation de circuit si 403 (jusqu'à 4 tentatives).
        Si playwright=True, lance Chromium headless via Tor pour passer le challenge JS.
        """
        if not self._tor_available():
            print("TRUTH SOCIAL Tor: daemon Tor non disponible (installe-le: apt install tor)")
            return []

        statuses_url = f"https://truthsocial.com/api/v1/accounts/{account_id}/statuses"
        tor_proxy = 'socks5h://127.0.0.1:9050'

        if not playwright:
            proxies = {'http': tor_proxy, 'https': tor_proxy}
            headers = {**self.headers, 'Accept': 'application/json'}
            for attempt in range(4):
                try:
                    r = requests.get(statuses_url, params={'limit': max_posts},
                                     headers=headers, proxies=proxies, timeout=60)
                    print(f"TRUTH SOCIAL Tor requests (essai {attempt+1}): HTTP {r.status_code}")
                    if r.status_code == 200:
                        data = r.json()
                        print(f"TRUTH SOCIAL Tor: {len(data)} posts OK")
                        return data
                    # Mauvais exit node -- on en demande un autre
                    if attempt < 3:
                        self._new_tor_circuit()
                except Exception as e:
                    print(f"TRUTH SOCIAL Tor requests error (essai {attempt+1}): {e}")
                    if attempt < 3:
                        self._new_tor_circuit()
            return []

        # Playwright via Tor proxy
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("TRUTH SOCIAL Playwright+Tor: Playwright non disponible.")
            return []

        collected = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    proxy={'server': tor_proxy},
                    args=['--no-sandbox', '--disable-dev-shm-usage',
                          '--disable-blink-features=AutomationControlled']
                )
                ctx = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                    extra_http_headers={'Accept-Language': 'en-US,en;q=0.9'}
                )
                page = ctx.new_page()

                def on_response(response):
                    try:
                        if '/api/v1/accounts/' in response.url and 'statuses' in response.url:
                            body = response.json()
                            if isinstance(body, list):
                                collected.extend(body)
                                print(f"TRUTH SOCIAL Playwright+Tor XHR: {len(body)} posts")
                    except Exception:
                        pass

                page.on('response', on_response)
                print("TRUTH SOCIAL Playwright+Tor: chargement profil...")
                try:
                    page.goto('https://truthsocial.com/@realDonaldTrump',
                              timeout=60000, wait_until='networkidle')
                except Exception:
                    pass
                page.wait_for_timeout(4000)
                browser.close()

                if collected:
                    print(f"TRUTH SOCIAL Playwright+Tor: {len(collected)} posts interceptés OK")
                    return collected[:max_posts]
                print("TRUTH SOCIAL Playwright+Tor: aucun post intercepté")
        except Exception as e:
            print(f"TRUTH SOCIAL Playwright+Tor error: {e}")
        return []

    def _parse_posts(self, posts_data: List[Dict]) -> List[Dict[str, Any]]:
        """Parse les données JSON des posts"""
        parsed_posts = []
        for post in posts_data:
            # Extract plain text from HTML content
            content_html = post.get('content', '')
            try:
                soup = BeautifulSoup(content_html, 'html.parser')
                text_content = soup.get_text().strip()
            except Exception:
                text_content = content_html

            media_urls = [m.get('url') for m in post.get('media_attachments', [])]

            # Fallback pour les posts sans texte (images uniquement)
            if not text_content:
                media_types = [m.get('type', 'image') for m in post.get('media_attachments', [])]
                if 'video' in media_types or 'gifv' in media_types:
                    text_content = '\U0001f3a5'  # 🎥
                elif media_urls:
                    text_content = ''  # laisse vide, l'image s'affiche
                else:
                    text_content = '[Post sans texte]'

            parsed_post = {
                'id': post.get('id'),
                'created_at': post.get('created_at'),
                'content': text_content,
                'url': post.get('url'),
                'reblogs_count': post.get('reblogs_count', 0),
                'favourites_count': post.get('favourites_count', 0),
                'replies_count': post.get('replies_count', 0),
                'media': media_urls,
                'source': 'truth_social',
                'author': 'Donald J. Trump',  # This should ideally come from the post data
                'avatar': post.get('account', {}).get('avatar')
            }
            parsed_posts.append(parsed_post)

        return parsed_posts