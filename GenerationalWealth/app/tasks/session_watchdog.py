import time
import threading
import configparser
import requests
from datetime import datetime
from ..utils.auth import _jwt_expiry
from ..services.trade_republic import TradeRepublicAPI

# Global state for HTTP keepalive
_last_http_keepalive_ts = 0
tr_api = None  # Will be initialized when the function starts

def _tr_http_keepalive():
    """Send HTTP keepalive to maintain TR session cookie server-side"""
    global _last_http_keepalive_ts, tr_api
    try:
        if tr_api is None:
            tr_api = TradeRepublicAPI()

        # Read current config to get session token
        tr_api.config.read(tr_api.config_path)
        session_tok = tr_api.config.get("secret", "tr_session", fallback="") or ""

        if not session_tok:
            return False

        url = "https://app.traderepublic.com/"
        headers = {
            'User-Agent': tr_api.device_info,
            'Accept': '*/*',
        }
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=False)
        _last_http_keepalive_ts = time.time()
        if resp.status_code == 200:
            print(f"[Keepalive] Ping TR HTTP OK ({resp.status_code}) — session prolongée.")
            return True
        else:
            print(f"[Keepalive] Ping TR HTTP {resp.status_code} — session peut-être expirée.")
            return False
    except Exception as e:
        print(f"[Keepalive] Erreur ping TR : {e}")
        return False


def run_session_watchdog(app):
    """Background session watchdog thread"""
    global tr_api

    with app.app_context():
        # Initialize TR API
        tr_api = TradeRepublicAPI()
        print("[Watchdog] Démarrage du watchdog de session Trade Republic.")

        while True:
            try:
                # Read current config
                cfg = configparser.ConfigParser()
                cfg.read("config.ini")
                session_tok = cfg.get("secret", "tr_session", fallback=None) or ""
                refresh_tok = cfg.get("secret", "tr_refresh", fallback=None) or ""
                now = time.time()

                if session_tok:
                    session_exp = _jwt_expiry(session_tok)
                    # Renouveler si expiré ou expire dans moins de 30 min (proactif)
                    if refresh_tok and session_exp and (session_exp - now) < 1800:
                        remaining = max(0, int(session_exp - now))
                        print(f"[Watchdog] tr_session expire dans {remaining}s - renouvellement silencieux via tr_refresh...")
                        if tr_api.refresh_session():
                            print("[Watchdog] Session renouvelée avec succès.")
                        else:
                            print("[Watchdog] Renouvellement échoué - l'utilisateur devra se reconnecter manuellement si nécessaire.")

                    # Ping HTTP toutes les 10 minutes pour maintenir le cookie serveur TR
                    if (now - _last_http_keepalive_ts) >= 600:
                        _tr_http_keepalive()

            except Exception as e:
                print(f"[Watchdog] Erreur : {e}")
            time.sleep(60)  # Vérification toutes les minutes


def start_session_watchdog_thread(app):
    """Start the session watchdog thread"""
    thread = threading.Thread(target=run_session_watchdog, args=(app,), daemon=True)
    thread.start()
    print("[OK] Session watchdog thread started")
    return thread