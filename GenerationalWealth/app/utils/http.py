import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading

# Thread-local storage for HTTP sessions to avoid conflicts
_thread_local = threading.local()


def create_retry_session(retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 504)):
    """
    Create a requests Session with retry logic.

    Args:
        retries: Number of retries for failed requests
        backoff_factor: Backoff factor for Retry-After header
        status_forcelist: HTTP status codes that should trigger a retry

    Returns:
        requests.Session: Configured session with retry adapters
    """
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def get_thread_local_session():
    """
    Get or create a thread-local HTTP session with standard headers.

    Returns:
        requests.Session: Thread-local session with common headers
    """
    if not hasattr(_thread_local, 'session'):
        _thread_local.session = create_retry_session()
        # Set common headers
        _thread_local.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Origin': 'https://finance.yahoo.com',
            'Referer': 'https://finance.yahoo.com/',
        })
    return _thread_local.session


def get_fresh_session():
    """
    Get a fresh HTTP session (not thread-local) with standard headers.

    Returns:
        requests.Session: Fresh session with common headers
    """
    session = create_retry_session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        'Origin': 'https://finance.yahoo.com',
        'Referer': 'https://finance.yahoo.com/',
    })
    return session


# For backward compatibility, create a global session instance
# Note: This is not thread-safe for concurrent use, prefer get_thread_local_session()
_http_session = create_retry_session()
_http_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    'Origin': 'https://finance.yahoo.com',
    'Referer': 'https://finance.yahoo.com/',
})


def get_global_session():
    """Get the global HTTP session (for backward compatibility)."""
    return _http_session


# IP utility functions (moved from backend.py)
def _get_client_ip() -> str:
    """Get real client IP considering proxies."""
    # This function will need to be adapted to work within Flask request context
    # For now, returning a placeholder - should be called within route handlers
    return "127.0.0.1"  # Placeholder


# These IP session functions would need access to Flask app/db context
# They'll be stubbed here and should be called within proper context
def _store_ip_session(ip: str, token: str, phone: str = ''):
    """Store IP session - placeholder, needs Flask context."""
    pass


def _get_ip_session(ip: str) -> str | None:
    """Get IP session - placeholder, needs Flask context."""
    return None


def _clear_ip_session(ip: str):
    """Clear IP session - placeholder, needs Flask context."""
    pass


def _load_ip_sessions_from_db():
    """Load IP sessions from DB - placeholder, needs Flask context."""
    pass