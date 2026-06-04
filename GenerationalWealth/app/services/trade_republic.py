import json
import base64
import threading
import time
import websockets
import asyncio
import hashlib
import hmac
from urllib.parse import urljoin
import requests
import cloudscraper
from bs4 import BeautifulSoup

# Assuming these are imported from utils or will be passed in
# For now, I'll include placeholder imports and note what needs to be resolved
try:
    from ..utils.http import create_retry_session
    from ..utils.tr import generate_device_info, get_waf_token_with_selenium
    from ..utils.auth import _load_groq_key, _load_github_tokens
except ImportError:
    # Fallback definitions if utils not yet created
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

    def generate_device_info():
        import uuid
        import string
        import random
        # Simplified version - should be moved to utils.tr
        android_versions = ['10', '11', '12']
        device_models = ['SM-G973F', 'SM-G981B', 'Pixel 4', 'Pixel 5']
        return f"Android {random.choice(android_versions)}; {random.choice(device_models)} Build/{''.join(random.choices(string.ascii_uppercase + string.digits, k=3))}"

    def get_waf_token_with_selenium():
        # Placeholder - should be moved to utils.tr
        return ""

    def _load_groq_key():
        import os
        return os.environ.get('GROQ_API_KEY', '')

    def _load_github_tokens():
        import os
        return os.environ.get('GITHUB_TOKEN', '')


class TradeRepublicAPI:
    def __init__(self, config_path="config.ini"):
        import configparser
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        self.config_path = config_path

        # General settings
        self.output_format = self.config.get("general", "output_format", fallback="json")
        self.output_folder = self.config.get("general", "output_folder", fallback="./out")
        self.extract_details = self.config.getboolean("general", "extract_details", fallback=False)

        # Credentials
        self.phone_number = self.config.get("secret", "phone_number", fallback=None)
        self.pin = self.config.get("secret", "pin", fallback=None)
        self.first_name = self.config.get("secret", "first_name", fallback="")
        self.last_name = self.config.get("secret", "last_name", fallback="")
        self.session_token = self.config.get("secret", "tr_session", fallback=None)
        self.refresh_token = self.config.get("secret", "tr_refresh", fallback=None)

        # WAF & device (auto-générés si absents du config.ini)
        self.waf_token = self.config.get("secret", "waf_token", fallback="")
        self.device_info = self.config.get("secret", "device_info", fallback="")
        if not self.device_info:
            self.device_info = generate_device_info()

        self.websocket = None
        self.message_id = 0

        # Cache pour optimiser le mode Live
        self.cached_sec_acc = None
        self.cached_exchanges = {}

    def get_sec_acc_no(self):
        """Extract Securities Account Number from Session Token (JWT)."""
        if not self.session_token: return None
        if self.cached_sec_acc: return self.cached_sec_acc

        try:
            # Simple JWT Decode (Payload is middle part)
            parts = self.session_token.split('.')
            if len(parts) != 3: return None

            # Base64 Decode (handle padding)
            payload_b64 = parts[1]
            padding = len(payload_b64) % 4
            if padding: payload_b64 += '=' * (4 - padding)

            payload_str = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
            payload = json.loads(payload_str)

            # Extract secAccNo: payload -> act -> acc -> owner -> default -> sec -> [0]
            act = payload.get('act', {})
            acc = act.get('acc', {})
            owner = acc.get('owner', {})
            default_acc = owner.get('default', {})
            sec = default_acc.get('sec', [])
            if sec and len(sec) > 0:
                self.cached_sec_acc = sec[0]
                return self.cached_sec_acc
            return None
        except Exception as e:
            print(f"[ERROR] Failed to extract secAccNo from token: {e}")
            return None

    def refresh_session(self):
        """Refresh the session using refresh token."""
        if not self.refresh_token:
            print("[ERROR] No refresh token available")
            return False

        try:
            # Import here to avoid circular dependencies
            from ..utils.tr import get_waf_token_with_selenium

            url = "https://api.trade-republic.com/session"
            headers = {
                "Content-Type": "application/json",
                "User-Agent": self.device_info,
                "x-waf-token": self.waf_token or get_waf_token_with_selenium(),
            }
            data = {
                "refreshToken": self.refresh_token
            }

            session = create_retry_session()
            response = session.post(url, json=data, headers=headers, timeout=30)

            if response.status_code == 200:
                response_data = response.json()
                self.session_token = response_data.get("sessionToken")
                self.refresh_token = response_data.get("refreshToken")

                # Update config file
                self.config.set("secret", "tr_session", self.session_token)
                self.config.set("secret", "tr_refresh", self.refresh_token)
                with open(self.config_path, "w") as f:
                    self.config.write(f)

                print("[OK] Session refreshed successfully")
                return True
            else:
                print(f"[ERROR] Failed to refresh session: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"[ERROR] Exception during session refresh: {e}")
            return False

    def login(self):
        """Login to Trade Republic and obtain session tokens."""
        if not self.phone_number or not self.pin:
            print("[ERROR] Phone number or PIN not configured")
            return False

        try:
            from ..utils.tr import get_waf_token_with_selenium

            url = "https://api.trade-republic.com/session"
            headers = {
                "Content-Type": "application/json",
                "User-Agent": self.device_info,
                "x-waf-token": self.waf_token or get_waf_token_with_selenium(),
            }
            data = {
                "username": self.phone_number,
                "password": self.pin
            }

            session = create_retry_session()
            response = session.post(url, json=data, headers=headers, timeout=30)

            if response.status_code == 200:
                response_data = response.json()
                self.session_token = response_data.get("sessionToken")
                self.refresh_token = response_data.get("refreshToken")

                # Save to config
                self.config.set("secret", "phone_number", self.phone_number)
                self.config.set("secret", "pin", self.pin)
                self.config.set("secret", "first_name", self.first_name)
                self.config.set("secret", "last_name", self.last_name)
                self.config.set("secret", "tr_session", self.session_token)
                self.config.set("secret", "tr_refresh", self.refresh_token)
                self.config.set("secret", "device_info", self.device_info)
                if self.waf_token:
                    self.config.set("secret", "waf_token", self.waf_token)

                with open(self.config_path, "w") as f:
                    self.config.write(f)

                print("[OK] Login successful")
                return True
            else:
                print(f"[ERROR] Login failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"[ERROR] Exception during login: {e}")
            return False

    def get_ws_url(self):
        """Get WebSocket URL for real-time updates."""
        if not self.session_token:
            print("[ERROR] No session token available")
            return None

        sec_acc_no = self.get_sec_acc_no()
        if not sec_acc_no:
            print("[ERROR] Could not determine securities account number")
            return None

        return f"wss://websocket.trade-republic.com/{sec_acc_no}?v=3"

    def connect_websocket(self):
        """Connect to Trade Republic WebSocket."""
        import threading

        def run_websocket():
            import asyncio
            import websockets

            async def websocket_handler():
                ws_url = self.get_ws_url()
                if not ws_url:
                    return

                try:
                    async with websockets.connect(ws_url) as websocket:
                        self.websocket = websocket
                        print("[OK] WebSocket connected")

                        # Keep connection alive and handle messages
                        while True:
                            try:
                                message = await websocket.recv()
                                # Process message here - for now just acknowledge
                                # In a real implementation, you'd parse and handle different message types
                                print(f"[WS] Received: {message[:100]}...")
                            except websockets.exceptions.ConnectionClosed:
                                print("[WS] Connection closed")
                                break
                            except Exception as e:
                                print(f"[WS] Error receiving message: {e}")
                                break
                except Exception as e:
                    print(f"[WS] Connection error: {e}")

        # Run in a separate thread with its own event loop
        def start_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(websocket_handler())

        ws_thread = threading.Thread(target=start_loop, daemon=True)
        ws_thread.start()
        return ws_thread

    def close_websocket(self):
        """Close WebSocket connection."""
        if self.websocket:
            # Note: Properly closing websockets requires accessing the internal connection
            # This is a simplified version
            self.websocket = None
            print("[WS] WebSocket connection marked for closure")

    def fetch_portfolio(self):
        """Fetch portfolio data from Trade Republic API."""
        if not self.session_token:
            print("[ERROR] No session token available")
            return None

        try:
            sec_acc_no = self.get_sec_acc_no()
            if not sec_acc_no:
                print("[ERROR] Could not determine securities account number")
                return None

            url = f"https://api.trade-republic.com/securities-accounts/{sec_acc_no}/positions"
            headers = {
                "Authorization": f"Bearer {self.session_token}",
                "User-Agent": self.device_info,
                "x-waf-token": self.waf_token,
            }

            session = create_retry_session()
            response = session.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"[ERROR] Failed to fetch portfolio: {response.status_code} - {response.text}")
                # Try to refresh session on 401
                if response.status_code == 401:
                    if self.refresh_session():
                        # Retry once with new token
                        return self.fetch_portfolio()
                return None
        except Exception as e:
            print(f"[ERROR] Exception fetching portfolio: {e}")
            return None

    def fetch_order_history(self, limit=100):
        """Fetch order history from Trade Republic API."""
        if not self.session_token:
            print("[ERROR] No session token available")
            return None

        try:
            sec_acc_no = self.get_sec_acc_no()
            if not sec_acc_no:
                print("[ERROR] Could not determine securities account number")
                return None

            url = f"https://api.trade-republic.com/securities-accounts/{sec_acc_no}/orders"
            headers = {
                "Authorization": f"Bearer {self.session_token}",
                "User-Agent": self.device_info,
                "x-waf-token": self.waf_token,
            }
            params = {"limit": limit}

            session = create_retry_session()
            response = session.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"[ERROR] Failed to fetch order history: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"[ERROR] Exception fetching order history: {e}")
            return None

    def place_order(self, instrument_id, side, quantity, order_type="market", price=None, validity="day"):
        """Place an order with Trade Republic."""
        if not self.session_token:
            print("[ERROR] No session token available")
            return None

        try:
            sec_acc_no = self.get_sec_acc_no()
            if not sec_acc_no:
                print("[ERROR] Could not determine securities account number")
                return None

            url = f"https://api.trade-republic.com/securities-accounts/{sec_acc_no}/orders"
            headers = {
                "Authorization": f"Bearer {self.session_token}",
                "Content-Type": "application/json",
                "User-Agent": self.device_info,
                "x-waf-token": self.waf_token,
            }

            order_data = {
                "instrumentId": instrument_id,
                "side": side,  # "BUY" or "SELL"
                "quantity": str(quantity),
                "type": order_type,  # "market", "limit", "stop"
                "validity": validity,  # "day", "good-till-cancelled"
            }

            if price and order_type in ["limit", "stop"]:
                order_data["price"] = str(price)

            session = create_retry_session()
            response = session.post(url, json=order_data, headers=headers, timeout=30)

            if response.status_code in [200, 201]:
                return response.json()
            else:
                print(f"[ERROR] Failed to place order: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"[ERROR] Exception placing order: {e}")
            return None