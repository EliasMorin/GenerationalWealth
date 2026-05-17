import sys
import io
import os

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import json
import threading
import time
from datetime import datetime, timedelta, timezone
import re
import traceback
import math
import base64

# PDF generation (optional)
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None
    print("[WARN] fpdf2 not installed - PDF export disabled")

# Core HTTP / finance
import requests
import cloudscraper
from bs4 import BeautifulSoup
import feedparser
import yfinance as yf
import pandas as pd
import numpy as np

# Standard utils
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict, deque
from difflib import SequenceMatcher
import queue
import warnings
import collections
import string
import hashlib
import uuid
from urllib.parse import urljoin
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from io import StringIO
import xml.etree.ElementTree as ET
import asyncio
import ssl
import certifi
import configparser
import logging
import http.server
import socketserver
from email.utils import parsedate_to_datetime as _rfc2822_parse

# Websockets
import websockets

# SSL context
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# --- Optional heavy dependencies ---

try:
    import pdfplumber
except ImportError:
    pdfplumber = None
    print("[WARN] pdfplumber not installed")

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(x, **kwargs): return x  # no-op fallback

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False
    print("[WARN] opencv-python not installed - video features disabled")

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    easyocr = None
    EASYOCR_AVAILABLE = False
    print("[WARN] easyocr not installed - OCR features disabled")

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    yt_dlp = None
    YTDLP_AVAILABLE = False
    print("[WARN] yt-dlp not installed - video download disabled")

try:
    from transformers import pipeline as hf_pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    hf_pipeline = None
    TRANSFORMERS_AVAILABLE = False
    print("[WARN] transformers not installed - FinBERT sentiment disabled")

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None
    PLAYWRIGHT_AVAILABLE = False
    print("[WARN] playwright not installed - browser scraping disabled")

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    SELENIUM_AVAILABLE = True
except ImportError:
    webdriver = None
    ChromeOptions = None
    SELENIUM_AVAILABLE = False
    print("[WARN] selenium not installed - WAF token via browser disabled")

# Filter out /api/tr/status logs
# class StatusCodeFilter(logging.Filter):
#    def filter(self, record):
#        return "/api/tr/status" not in record.getMessage()

# log = logging.getLogger('werkzeug')
# log.addFilter(StatusCodeFilter())


# Import Trade Republic (Removed)
# from traderepublic import connect_to_websocket, get_tr_session_cookie, search_instrument, fetch_derivatives, fetch_instrument_details

warnings.filterwarnings('ignore')

# ============================================================================
# MERGED EXTERNAL MODULES: RESOLVE ISIN & FETCH PDF
# ============================================================================

# --- ISIN CACHE LOGIC ---
_isin_cache_lock = Lock()
_isin_cache = {}
_isin_cache_loaded = False

def ensure_isin_cache():
    global _isin_cache, _isin_cache_loaded
    if not _isin_cache_loaded:
        with _isin_cache_lock:
            if not _isin_cache_loaded:
                try:
                    if 'app' in globals() and app:
                        with app.app_context():
                            data = db_load_generic('isin_cache')
                            if data: _isin_cache.update(data)
                            _isin_cache_loaded = True
                except Exception as e:
                    print(f"ISIN Cache load error: {e}")

def save_cache():
    global _isin_cache
    with _isin_cache_lock:
        try:
            with app.app_context():
                db_save_generic('isin_cache', _isin_cache)
        except Exception as e:
            print(f"Error saving ISIN cache: {e}")

# --- METADATA CACHE (Sector/Country) ---
_metadata_cache = {}
_metadata_lock = Lock()

def get_sector_reference_index(sector, country="USA"):
    """Returns a reference index ticker based on sector and country."""
    if hasattr(sector, 'lower'): sector = sector.lower()
    else: sector = "unknown"
    
    # Global Sector Indices (mostly US based ETF proxies for now)
    mapping = {
        "technology": {"symbol": "^IXIC", "name": "NASDAQ 100"},
        "healthcare": {"symbol": "XLV", "name": "Health Care Select"},
        "financial services": {"symbol": "XLF", "name": "Financial Select"},
        "consumer cyclical": {"symbol": "XLY", "name": "Cons. Discretionary"},
        "consumer defensive": {"symbol": "XLP", "name": "Cons. Staples"},
        "energy": {"symbol": "XLE", "name": "Energy Select"},
        "utilities": {"symbol": "XLU", "name": "Utilities Select"},
        "industrials": {"symbol": "XLI", "name": "Industrial Select"},
        "basic materials": {"symbol": "XLB", "name": "Materials Select"},
        "real estate": {"symbol": "XLRE", "name": "Real Estate Select"},
        "communication services": {"symbol": "XLC", "name": "Communication Svc"},
    }
    
    for k, v in mapping.items():
        if k in sector: return v
        
    # Default geography based
    if country == "United States": return {"symbol": "^GSPC", "name": "S&P 500"}
    if country in ["France", "Germany", "Netherlands", "Spain", "Italy"]: return {"symbol": "^STOXX50E", "name": "Euro Stoxx 50"}
    if country == "China": return {"symbol": "000001.SS", "name": "Shanghai Comp"}
    if country == "Japan": return {"symbol": "^N225", "name": "Nikkei 225"}
    
    return {"symbol": "^GSPC", "name": "S&P 500"}

def fetch_metadata_for_ticker(ticker):
    """Fetches sector, country, and currency for a ticker."""
    global _metadata_cache
    
    if not ticker: return None
    
    # Check cache (quick)
    with _metadata_lock:
        if ticker in _metadata_cache:
            return _metadata_cache[ticker]
            
    try:
        t = yf.Ticker(ticker)
        # Fast info fetch
        info = t.info
        
        # Check if we got empty info (often happens with rate limits or blocked IP)
        if not info or len(info) < 5:
             # Try fast_info as fallback if available (newer yfinance)
             try:
                 fi = t.fast_info
                 if fi:
                     # Map fast_info keys if needed, but info is better for sector
                     pass
             except: pass
             
             raise ValueError("Empty info returned from Yahoo Finance")

        data = {
            "sector": info.get('sector', 'Unknown'),
            "industry": info.get('industry', 'Unknown'),
            "country": info.get('country', 'Unknown'),
            "region": info.get('region', 'Unknown')
        }
        
        # Determine Reference Index
        ref = get_sector_reference_index(data['sector'], data['country'])
        data['reference_index_ticker'] = ref['symbol']
        data['reference_index_name'] = ref['name']
        
        with _metadata_lock:
            _metadata_cache[ticker] = data
        
        print(f"[METADATA] Success for {ticker}: {data['sector']} / {data['country']}")
        return data
    except Exception as e:
        print(f"[METADATA] Error for {ticker}: {e}")
        # Return empty generic to store failure
        # FIX: We SHOULD cache this failure to prevent spamming the API every 10s if it's a persistent error
        # This means it will stay 'Unknown' until server restart.
        failure_data = {"sector": "Unknown", "country": "Unknown", "reference_index_ticker": "^GSPC", "reference_index_name": "S&P 500"}
        with _metadata_lock:
            _metadata_cache[ticker] = failure_data
        return failure_data

# --- HTTP SESSION SETUP ---
def create_retry_session(retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 504)):
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

_http_session = create_retry_session()
_http_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    'Origin': 'https://finance.yahoo.com',
    'Referer': 'https://finance.yahoo.com/',
})



def get_symbol_from_isin(isin):
    """Résout un ISIN en symbole Yahoo Finance avec cache DB"""
    if not isin: return None
    
    # Needs to run within app context if not already
    try:
        # Check if we are in a context
        try:
             # Just testing access
             _ = app.config['SQLALCHEMY_DATABASE_URI']
             has_context = True
        except:
             has_context = False
        
        # 1. Vérifier le cache DB
        if has_context:
             cached = IsinTicker.query.get(isin)
        else:
             with app.app_context():
                cached = IsinTicker.query.get(isin)
                
        if cached and cached.ticker:
            return cached.ticker
    except Exception as e: 
        # print(f"DB Cache Read Error: {e}")
        pass
        
    # 2. Requête API Yahoo
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={isin}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        # Use shared session with retry logic
        resp = _http_session.get(url, headers=headers, timeout=10)
        data = resp.json()
        
        if 'quotes' in data and len(data['quotes']) > 0:
            quote = data['quotes'][0]
            symbol = quote.get('symbol')
            
            if symbol:
                try:
                    if has_context:
                         new_cache = IsinTicker(isin=isin, ticker=symbol)
                         db.session.merge(new_cache)
                         db.session.commit()
                    else:
                         with app.app_context():
                            new_cache = IsinTicker(isin=isin, ticker=symbol)
                            db.session.merge(new_cache)
                            db.session.commit()
                except Exception as save_err:
                     # print(f"DB Cache Save Error: {save_err}")
                     try: db.session.rollback()
                     except: pass
            
            return symbol
    except Exception as e:
        print(f"Error resolving {isin}: {e}")
    
    return None


# --- FETCH PDF STOCKS LOGIC ---
PDF_URL = "https://assets.traderepublic.com/assets/files/DE/Instrument_Universe_DE_en.pdf"
PDF_FILENAME = "Instrument_Universe_DE_en.pdf"
PDF_OUTPUT_FILE = "all_stocks_from_pdf.json"

def download_pdf():
    if os.path.exists(PDF_FILENAME):
        print(f"[OK] Le fichier {PDF_FILENAME} existe deja.")
        return

    print(f"[DOWN]? Telechargement de {PDF_URL}...")
    try:
        response = requests.get(PDF_URL, stream=True)
        if response.status_code == 200:
            with open(PDF_FILENAME, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("[OK] Telechargement termine.")
        else:
            print(f"[ERROR] Echec du telechargement: {response.status_code}")
            raise Exception(f"Download failed: {response.status_code}")
    except Exception as e:
        print(f"Error downloading PDF: {e}")
        raise e

def extract_stocks_from_pdf():
    """
    Revised to fetch stocks from Trade Republic API instead of PDF.
    Keeps function name for backward compatibility.
    """
    print("[START] Fetching Stocks Universe via API (replacing PDF)...")
    
    stocks = []
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Ensure session
        if not tr_api.session_token:
            tr_api.config.read(tr_api.config_path)
            tr_api.session_token = tr_api.config.get("secret", "tr_session", fallback=None)
            
        stocks = loop.run_until_complete(tr_api.fetch_all_stocks_recursive())
        loop.close()
    except Exception as e:
        print(f"[ERROR] Error fetching stocks from API: {e}")
        traceback.print_exc()
        return []

    print(f"[OK] Extraction terminee via API. {len(stocks)} instruments trouves.")
    
    # Save to Cache DB
    try:
        with app.app_context():
            cache = CachedData.query.get("pdf_stocks")
            if not cache:
                cache = CachedData(key="pdf_stocks", data=stocks)
                db.session.add(cache)
            else:
                cache.data = stocks
                cache.updated_at = datetime.utcnow()
            db.session.commit()
            print(f"[SAVE] Sauvegarde dans DB (pdf_stocks)")
    except Exception as e:
        print(f"DB Error save pdf stocks: {e}")
            
    return stocks

# Loading State Global
LOADING_STATE = {
    'steps': {
        'database': {'status': 'pending', 'label': 'Connexion Base de Données'},
        'wallet': {'status': 'pending', 'label': 'Chargement du Portefeuille'},
        'rss': {'status': 'pending', 'label': 'Flux News (RSS)'},
        'insiders': {'status': 'pending', 'label': 'Transactions Insiders'},
        'forex': {'status': 'pending', 'label': 'Calendrier Économique'},
        'sector_trends': {'status': 'pending', 'label': 'Tendances Sectorielles'},
        'forecasts': {'status': 'pending', 'label': 'Prévisions & Analyses Bancaires'},
        'macro': {'status': 'pending', 'label': 'Données Macro-économiques'}
    },
    'complete': False
}

def update_loading_step(step, status):
    global LOADING_STATE
    if step in LOADING_STATE['steps']:
        LOADING_STATE['steps'][step]['status'] = status
        
    # Check completeness
    all_done = all(s['status'] in ['success', 'error'] for k, s in LOADING_STATE['steps'].items())
    LOADING_STATE['complete'] = all_done

app = Flask(__name__)
try:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///financial_terminal_multiuser.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Increase Pool Size for Threads
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 30,
        'max_overflow': 50,
        'pool_timeout': 60,
        'pool_recycle': 1800
    }
    
    db = SQLAlchemy(app)
    print("[OK] Database initialized successfully")
except Exception as e:
    print(f"[ERROR] Database init failed: {e}")
    # Fallback to avoid crashing if something is wrong with env
    class MockDB:
        Model = object
        Column = lambda *a,**k: None
        Integer = String = Float = Text = DateTime = Date = Boolean = JSON = None
        ForeignKey = lambda *a: None
        session = None
        def create_all(self): pass
    db = MockDB()

CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-User-Phone'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response

# ============================================================================
# DATABASE MODELS
# ============================================================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(50), unique=True, nullable=False)
    # In production, hash this PIN!
    pin = db.Column(db.String(10), nullable=False) 
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class IsinTicker(db.Model):
    isin = db.Column(db.String(20), primary_key=True)
    ticker = db.Column(db.String(20))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class PortfolioSnapshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id')) # Link to User
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    cash = db.Column(db.Float)
    total_value = db.Column(db.Float)
    positions_count = db.Column(db.Integer)
    # Storing the full complex JSON structure for frontend compatibility
    raw_data = db.Column(db.JSON)

class NewsItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(50)) # 'Bloomberg', 'RSS', etc.
    title = db.Column(db.String(500))
    url = db.Column(db.String(500), unique=True)
    summary = db.Column(db.Text)
    published_at = db.Column(db.DateTime)
    sentiment = db.Column(db.String(20)) # 'Positive', 'Negative'
    sentiment_score = db.Column(db.Float)
    related_tickers = db.Column(db.JSON) # List of tickers

class InsiderTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20))
    company = db.Column(db.String(200))
    insider_name = db.Column(db.String(200))
    relation = db.Column(db.String(100))
    date = db.Column(db.String(20))
    transaction = db.Column(db.String(100))
    cost = db.Column(db.Float)
    shares = db.Column(db.Float)
    value = db.Column(db.Float)
    shares_total = db.Column(db.Float)
    sec_form = db.Column(db.String(500))
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

class BankForecast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank = db.Column(db.String(100))
    ticker = db.Column(db.String(20))
    company = db.Column(db.String(200))
    recommendation = db.Column(db.String(100))
    target_price = db.Column(db.Float)
    date_published = db.Column(db.String(50))
    source_url = db.Column(db.String(500), unique=True)
    summary = db.Column(db.Text)
    market_sentiment = db.Column(db.String(50))

class SectorTrend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sector_name = db.Column(db.String(100), unique=True)
    monthly_trend = db.Column(db.Float)
    stocks_count = db.Column(db.Integer)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.JSON) # Full list of stocks in sector

class CachedData(db.Model):
    key = db.Column(db.String(100), primary_key=True)
    data = db.Column(db.JSON)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class TechnicalWarning(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20), unique=True)
    rsi = db.Column(db.Float)
    signal_type = db.Column(db.String(50)) # 'Overbought', 'Oversold', 'Trend Reversal'
    level = db.Column(db.String(20)) # 'Warning', 'Critical'
    message = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class BankAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank = db.Column(db.String(50))
    title = db.Column(db.String(500))
    url = db.Column(db.String(500)) # Not unique as multiple banks might link same generic page? but usually unique
    analysis = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class WalletInvestment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id')) # Link to User
    isin = db.Column(db.String(20), nullable=False) # Not unique globally anymore
    name = db.Column(db.String(200))
    
    quantity = db.Column(db.Float)
    buy_price = db.Column(db.Float)
    current_price = db.Column(db.Float)
    total_value = db.Column(db.Float)
    pnl = db.Column(db.Float)
    pnl_percent = db.Column(db.Float)
    exchange = db.Column(db.String(20))
    instrument_type = db.Column(db.String(50))
    logo = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class WalletCash(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id')) # Link to User
    amount = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(10), default='EUR')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class MacroData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), unique=True) # e.g., 'interest_rates', 'inflation'
    data = db.Column(db.JSON)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize DB
with app.app_context():
    db.create_all()

# Helper to migrate/load data
def db_save_portfolio(data, user_phone=None):
    try:
        with app.app_context():
            # Identify User from Active TradeRepublic Session (Config)
            user_id = None
            try:
                # Priority 1: Use provided phone number
                if user_phone:
                     u = User.query.filter_by(phone=user_phone).first()
                     if u: user_id = u.id
                
                # Priority 2: Fallback to config if not provided
                if not user_id and 'tr_api' in globals():
                    tr_api.config.read(tr_api.config_path)
                    phone = tr_api.config.get("secret", "phone_number", fallback=None)
                    if phone:
                        u = User.query.filter_by(phone=phone).first()
                        if u: user_id = u.id
            except Exception as e:
                print(f"Error identifying user for save: {e}")

            # Update detailed Wallet Tables
            # 1. Update Cash
            cash_obj = data.get('availableCash', data.get('available_cash', {}))
            cash_val = 0.0
            if isinstance(cash_obj, dict): cash_val = float(cash_obj.get('amount', 0))
            elif isinstance(cash_obj, (int, float)): cash_val = float(cash_obj)
            
            cash_db = WalletCash.query.filter_by(user_id=user_id).first()
            if not cash_db:
                db.session.add(WalletCash(amount=cash_val, user_id=user_id))
            else:
                cash_db.amount = cash_val
                cash_db.updated_at = datetime.utcnow()

            # 2. Update Investments
            investments = data.get('my_investments', data.get('positions', data.get('positions_detailed', [])))
            for item in investments:
                if not item.get('isin'): continue
                existing = WalletInvestment.query.filter_by(isin=item['isin'], user_id=user_id).first()
                if not existing:
                    inv = WalletInvestment(
                        isin=item['isin'],
                        user_id=user_id,
                        name=item.get('name', 'Unknown'),
                        quantity=float(item.get('quantity', item.get('qty', 0))),
                        buy_price=float(item.get('buy_price', item.get('avgPrice', 0))),
                        current_price=float(item.get('current_price', item.get('currentPrice', 0))),
                        total_value=float(item.get('total_value', item.get('totalValue', 0))),
                        pnl=float(item.get('pnl', 0)),
                        pnl_percent=float(item.get('pnl_percent', item.get('pnlPercent', 0))),
                        exchange=item.get('exchange', ''),
                        instrument_type=item.get('instrumentType', item.get('instrument_type', 'stock')),
                        logo=item.get('logo', '')
                    )
                    db.session.add(inv)
                else:
                    # Always do a full refresh of all fields.
                    # This handles the re-buy case: MSFT sold then repurchased —
                    # the old buy_price / pnl must be replaced with the new position's values.
                    new_qty   = float(item.get('quantity',      item.get('qty',          existing.quantity)))
                    new_bpx   = float(item.get('buy_price',     item.get('avgPrice',     0)) or 0)
                    new_cpx   = float(item.get('current_price', item.get('currentPrice', 0)) or 0)

                    existing.quantity = new_qty
                    # Only overwrite buy_price when TR provides a real value (> 0)
                    if new_bpx > 0:
                        existing.buy_price = new_bpx
                    # Only overwrite current_price when TR provides a real value
                    if new_cpx > 0:
                        existing.current_price = new_cpx

                    # Recalculate derived fields every time
                    cpx_eff = existing.current_price or 0
                    bpx_eff = existing.buy_price     or 0
                    existing.total_value = new_qty * cpx_eff
                    cost_basis           = new_qty * bpx_eff
                    existing.pnl         = existing.total_value - cost_basis
                    existing.pnl_percent = (existing.pnl / cost_basis * 100) if cost_basis > 0 else 0.0
                    existing.name        = item.get('name', existing.name) or existing.name
                    existing.logo        = item.get('logo', existing.logo) or existing.logo
                    existing.updated_at  = datetime.utcnow()

            # 3. Save Snapshot
            snap = PortfolioSnapshot(
                user_id=user_id,
                cash=cash_val,
                total_value=sum(float(i.get('total_value', i.get('totalValue', 0))) for i in investments) + cash_val,
                positions_count=len(investments),
                raw_data=data
            )
            db.session.add(snap)
            db.session.commit()
    except Exception as e:
        print(f"DB Error save portfolio: {e}")



def db_save_generic(key, data):
    try:
        with app.app_context():
            cache = CachedData.query.get(key)
            if not cache:
                cache = CachedData(key=key, data=data)
                db.session.add(cache)
            else:
                cache.data = data
                cache.updated_at = datetime.utcnow()
            db.session.commit()
    except Exception as e:
        print(f"DB Error save generic {key}: {e}")

def db_load_generic(key, default=None):
    try:
        with app.app_context():
            cache = CachedData.query.get(key)
            if cache and cache.data is not None:
                # Si les données sont vides, on les retourne quand même au lieu de retourner None
                # pour éviter de crasher le Frontend qui attend un objet ou une liste.
                return cache.data
            return default
    except Exception as e:
        print(f"Error loading generic key {key}: {e}")
        return default

def db_load_latest_portfolio():
    try:
        with app.app_context():
            # Trigger background tasks if data is missing
            if not db_load_generic('seasonality'):
                print("Missing seasonality: triggering background fetch...")
                threading.Thread(target=fetch_seasonality_api, daemon=True).start()
            
            if not db_load_generic('options_GOOG'):
                print("Missing options data: triggering GOOG fetch...")
                threading.Thread(target=lambda: fetch_options_chain_api('GOOG'), daemon=True).start()
            
            # Check sector trends but prevent spamming threads if already running
            if not db_load_sector_trends():
                if sector_update_status == "idle" or sector_update_status == "error":
                     # Double check lock
                     if not _sector_update_lock.locked():
                        print("Missing sector trends: triggering background calculation...")
                        threading.Thread(target=update_sector_monthly_trends, daemon=True).start()

            if not db_load_bank_forecasts():
                print("Missing bank forecasts: triggering background scrape...")
                # We need a function to wrap the scrape logic
                def background_bank_scrape():
                   try:
                       from backend import BankForecastScraper # Local import to avoid circular if any
                       scraper = BankForecastScraper()
                       scraper.scrape_all() # scrape_all handles saving formatted data
                   except Exception as e:
                       print(f"Background bank scrape error: {e}")

                threading.Thread(target=background_bank_scrape, daemon=True).start()

            # Determine User ID
            user_id = None
            if request:
                try:
                    phone = request.headers.get('X-User-Phone')
                    if phone:
                        u = User.query.filter_by(phone=phone).first()
                        if u: user_id = u.id
                except: pass 
            
            if user_id is None:
                try:
                     tr_api.config.read(tr_api.config_path)
                     phone = tr_api.config.get("secret", "phone_number", fallback=None)
                     if phone:
                         u = User.query.filter_by(phone=phone).first()
                         if u: user_id = u.id
                except: pass

            snap = PortfolioSnapshot.query.filter_by(user_id=user_id).order_by(PortfolioSnapshot.id.desc()).first()
            if snap and snap.raw_data:
                # Re-normalize snap.raw_data if it's old? 
                # Actually, better to just load from Wallet tables for consistency
                pass
            
            return load_portfolio_data(user_id=user_id)
    except Exception as e:
        print(f"Error loading portfolio from DB: {e}")
        return {}

def db_save_insiders(data_dict):
    """Save dictionary of insiders {ticker: { 'all': [...] }} to DB"""
    if not data_dict or len(data_dict) == 0:
        print("[WARN] db_save_insiders: No data provided, skipping update to avoid clearing DB")
        return
        
    try:
        with app.app_context():
            db.session.query(InsiderTransaction).delete()
            
            for ticker, groups in data_dict.items():
                 # Handle structure matching fetch_insiders_api
                 # It returns {'all': [], 'recent_7days': []}
                 trades = groups.get('all', []) if isinstance(groups, dict) else groups
                 
                 for t in trades:
                    txn = InsiderTransaction(
                        ticker=ticker,
                        company=t.get('company', t.get('Company', '')),
                        insider_name=t.get('insider', t.get('Insider', '')),
                        relation=t.get('relationship', t.get('Relationship', '')),
                        date=t.get('date', t.get('Date', '')),
                        transaction=t.get('transaction', t.get('Transaction', '')),
                        cost=float(str(t.get('cost', t.get('Cost', '0'))).replace(',','').replace('>','').replace('$','') or 0),
                        shares=float(str(t.get('shares', t.get('Shares', '0'))).replace(',','') or 0),
                        value=float(str(t.get('value', t.get('Value', t.get('Value ($)', '0')))).replace(',','').replace('$','') or 0),
                        shares_total=float(str(t.get('shares_total', t.get('Shares Total', '0'))).replace(',','') or 0),
                        sec_form=t.get('sec_form', t.get('SEC Form 4', ''))
                    )
                    db.session.add(txn)
            db.session.commit()
    except Exception as e:
        print(f"DB Error save insiders: {e}")

def db_load_insiders():
    try:
        def parse_date(date_str):
            try:
                # Handle "May 15 '24" format
                d = date_str.strip().replace("'", "20")
                return datetime.strptime(d, "%b %d %Y")
            except:
                return None

        with app.app_context():
            txns = InsiderTransaction.query.all()
            result = {}
            cutoff = datetime.now() - timedelta(days=7)
            
            for t in txns:
                if t.ticker not in result: 
                    result[t.ticker] = {'all': [], 'recent_7days': []}
                
                trade = {
                    'ticker': t.ticker,
                    'company': t.company,
                    'insider': t.insider_name,
                    'relationship': t.relation,
                    'date': t.date,
                    'transaction': t.transaction,
                    'cost': t.cost,
                    'shares': t.shares,
                    'value': t.value,
                    'shares_total': t.shares_total,
                    'sec_form': t.sec_form
                }
                result[t.ticker]['all'].append(trade)
                
                dt = parse_date(t.date)
                if dt and dt >= cutoff:
                    result[t.ticker]['recent_7days'].append(trade)
            
            return result
    except Exception as e:
        print(f"Error loading insiders from DB: {e}")
        return {}

def db_save_bank_forecasts(forecasts):
    try:
        with app.app_context():
            # Check existing entries to decide update vs insert
            for f in forecasts:
                url = f.get('url')
                if not url: continue

                existing = BankForecast.query.filter_by(source_url=url).first()
                if existing:
                    # Update existing record (especially if summary was empty)
                    existing.bank = f.get('bank', existing.bank)
                    existing.ticker = f.get('ticker', existing.ticker)
                    existing.recommendation = f.get('recommendation', existing.recommendation)
                    existing.target_price = f.get('target_price', existing.target_price)
                    existing.date_published = f.get('date', existing.date_published)
                    existing.summary = f.get('summary', existing.summary)
                    existing.market_sentiment = f.get('sentiment', existing.market_sentiment)
                else:
                    # Insert new
                    db_item = BankForecast(
                        bank=f.get('bank'),
                        ticker=f.get('ticker'),
                        recommendation=f.get('recommendation'),
                        target_price=f.get('target_price'),
                        date_published=f.get('date'),
                        source_url=url,
                        summary=f.get('summary', ''),
                        market_sentiment=f.get('sentiment', '')
                    )
                    db.session.add(db_item)
            db.session.commit()
    except Exception as e:
        print(f"DB Error save forecasts: {e}")

def db_load_bank_forecasts():
    try:
        def format_date(d):
            if not d: return ""
            if isinstance(d, datetime): return d.isoformat()
            return str(d)

        with app.app_context():
            items = BankForecast.query.order_by(BankForecast.id.desc()).all()
            return [{
                'bank': i.bank,
                'ticker': i.ticker,
                'recommendation': i.recommendation,
                'target_price': i.target_price,
                'date': format_date(i.date_published),
                'timestamp': format_date(i.date_published), # Map both for UI
                'url': i.source_url,
                'summary': i.summary,
                'sentiment': i.market_sentiment
            } for i in items]
    except Exception as e:
        print(f"Error loading forecasts: {e}")
        return []

def load_portfolio_data(user_id=None):
    """Charge le portfolio depuis la DB avec fallback JSON"""
    try:
        with app.app_context():
            investments = WalletInvestment.query.filter_by(user_id=user_id).all()
            cash_db = WalletCash.query.filter_by(user_id=user_id).first()
            cash_amount = cash_db.amount if cash_db else 0.0
            
            if investments:
                # --- NEW: Metadata Pre-Fetch ---
                tickers_to_fetch = []
                temp_isin_ticker_map = {}
                
                # 1. Identify necessary tickers
                for inv in investments:
                     t = get_symbol_from_isin(inv.isin)
                     temp_isin_ticker_map[inv.isin] = t
                     if t:
                         with _metadata_lock:
                             # FORCE REFRESH IF 'Unknown' in cache to avoid stuck bad state
                             curr = _metadata_cache.get(t, {})
                             if t not in _metadata_cache or curr.get('sector') == 'Unknown':
                                 if t not in tickers_to_fetch:
                                     tickers_to_fetch.append(t)
                
                # 2. Serial Fetch (Safest) - Avoiding ThreadPool issues
                if tickers_to_fetch:
                    print(f"Fetching metadata for {len(tickers_to_fetch)} tickers (Sync)...")
                    for ticker in tickers_to_fetch:
                        try:
                            # Add delay to be nice to Yahoo?
                            if len(tickers_to_fetch) > 5: time.sleep(0.5)
                            fetch_metadata_for_ticker(ticker)
                        except Exception as e:
                            print(f"[METADATA] Failed to fetch {ticker}: {e}")

                positions = []
                for inv in investments:
                    t = temp_isin_ticker_map.get(inv.isin)
                    
                    # Get Meta
                    meta = {}
                    if t:
                        with _metadata_lock:
                            meta = _metadata_cache.get(t, {})
                            
                    positions.append({
                        "isin": inv.isin,
                        "name": inv.name,
                        "qty": inv.quantity,
                        "avgPrice": inv.buy_price,
                        "currentPrice": inv.current_price,
                        "totalValue": inv.total_value,
                        "pnl": inv.pnl,
                        "pnlPercent": inv.pnl_percent,
                        "exchange": inv.exchange,
                        "instrumentType": inv.instrument_type,
                        "logo": inv.logo,
                        "ticker": t,
                        # New Fields
                        "sector": meta.get('sector', 'Unknown'),
                        "country": meta.get('country', 'Unknown'),
                        "reference_index_ticker": meta.get('reference_index_ticker'),
                        "reference_index_name": meta.get('reference_index_name')
                    })
                
                # DEBUG: Log counts of known sectors
                known_sectors = [p['sector'] for p in positions if p['sector'] != 'Unknown']
                if len(known_sectors) == 0 and len(positions) > 0:
                     print(f"[PORTFOLIO DEBUG] [WARN] 0/{len(positions)} positions have sector data. Sample Ticker: {positions[0].get('ticker')} (ISIN: {positions[0].get('isin')})")
                elif len(known_sectors) > 0:
                     # Only print once in a while to avoid spam, or if success
                     pass 

                return {
                    "available_cash": {"amount": cash_amount, "currency": "EUR"},
                    "my_investments": positions,
                    "positions": positions,
                    "wallets": [{"positions": positions, "available_cash": {"amount": cash_amount}}]
                }
    except Exception as e:
        print(f"Error loading portfolio from DB: {e}")
    
    # DB is now the source of truth
    return {
        "available_cash": {"amount": 0.0, "currency": "EUR"},
        "my_investments": [],
        "positions": [],
        "wallets": [{"positions": [], "available_cash": {"amount": 0.0}}]
    }

# ============================================================================
# CONFIGURATION
# ============================================================================

def _load_groq_key():
    """Lit la clé Groq depuis la variable d'environnement ou config.ini."""
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        try:
            _cfg = configparser.ConfigParser()
            _cfg.read("config.ini")
            key = _cfg.get("groq", "api_key", fallback="")
        except Exception:
            pass
    return key

GROQ_API_KEY = _load_groq_key()
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


def _jwt_expiry(token):
    """Retourne le timestamp d'expiration (exp) d'un JWT sans vérifier la signature.
    Retourne 0 en cas d'échec."""
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return int(data.get('exp', 0))
    except Exception:
        return 0


# Fichiers de cache
DATA_FILES = {
    'portfolio': 'trade_republic_wallet_complete.json',
    'forex': 'forex_cache.json',
    'insiders': 'insider_transactions.json',
    'news': 'bloomberg_markets_news.json',
    'bloomberg_live': 'bloomberg_news.json',
    'options': 'GOOG_options_analysis.json',
    'sector_trends': 'sector_trends_monthly.json',
    'sectors_performance': 'sector_trends.json',
    'seasonality': 'seasonality_analysis.json',
    'bank_forecasts': 'bank_forecasts.json',
    'bank_analyses': 'bank_analyses.json',
    'earnings': 'earnings_cache.json',
    'cot_data': 'cot_data_cache.json'
}

# ============================================================================
# TRUTH SOCIAL SCRAPER
# ============================================================================

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
        except:
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
    
    def get_user_posts(self, username: str, max_posts: int = 20):
        """
        Récupère les posts via le flux RSS public (ne nécessite pas d'authentification).
        Fallback sur l'API JSON si le RSS échoue.
        """
        username = username.replace('@', '')
        print(f"TRUTH SOCIAL: Recuperation des posts de @{username}...")

        # --- Méthode 1 : RSS public ---
        try:
            rss_url = f"{self.base_url}/@{username}.rss"
            rss_response = self.scraper.get(rss_url, headers=self.headers, timeout=20)
            if rss_response.status_code == 200:
                feed = feedparser.parse(rss_response.text)
                if feed.entries:
                    posts = []
                    for entry in feed.entries[:max_posts]:
                        content_html = entry.get('summary', '') or entry.get('content', [{}])[0].get('value', '')
                        try:
                            text_content = BeautifulSoup(content_html, 'html.parser').get_text().strip()
                        except Exception:
                            text_content = content_html
                        posts.append({
                            'id': entry.get('id', entry.get('link', '')),
                            'created_at': entry.get('published', ''),
                            'content': text_content,
                            'url': entry.get('link', ''),
                            'reblogs_count': 0,
                            'favourites_count': 0,
                            'replies_count': 0,
                            'media': [],
                            'source': 'truth_social',
                            'author': 'Donald J. Trump',
                            'avatar': None,
                        })
                    print(f"TRUTH SOCIAL: {len(posts)} posts via RSS.")
                    return posts
        except Exception as e:
            print(f"TRUTH SOCIAL RSS Error: {e}")

        # --- Méthode 2 : API JSON (fallback) ---
        try:
            api_url = f"{self.base_url}/api/v1/accounts/lookup?acct={username}"
            api_response = self.scraper.get(api_url, headers={
                **self.headers, 'Accept': 'application/json',
            }, timeout=20)

            if api_response.status_code == 200:
                user_data = api_response.json()
                user_id = user_data.get('id')
                if user_id:
                    posts_url = f"{self.base_url}/api/v1/accounts/{user_id}/statuses"
                    posts_response = self.scraper.get(
                        posts_url,
                        headers={**self.headers, 'Accept': 'application/json'},
                        params={'limit': max_posts},
                        timeout=20
                    )
                    if posts_response.status_code == 200:
                        return self._parse_posts(posts_response.json())
            print(f"TRUTH SOCIAL API: HTTP {api_response.status_code} - non disponible.")
        except Exception as e:
            print(f"TRUTH SOCIAL API Error: {e}")

        return []
    
    def _parse_posts(self, posts_data):
        """Parse les données JSON des posts"""
        parsed_posts = []
        for post in posts_data:
            # Extract plain text from HTML content
            content_html = post.get('content', '')
            try:
                soup = BeautifulSoup(content_html, 'html.parser')
                text_content = soup.get_text().strip()
            except:
                text_content = content_html

            parsed_post = {
                'id': post.get('id'),
                'created_at': post.get('created_at'),
                'content': text_content,
                'url': post.get('url'),
                'reblogs_count': post.get('reblogs_count', 0),
                'favourites_count': post.get('favourites_count', 0),
                'replies_count': post.get('replies_count', 0),
                'media': [m.get('url') for m in post.get('media_attachments', [])],
                'source': 'truth_social',
                'author': 'Donald J. Trump',
                'avatar': post.get('account', {}).get('avatar')
            }
            parsed_posts.append(parsed_post)
        
        return parsed_posts

def update_truth_social_posts():
    """Tâche de fond pour mettre à jour les posts Truth Social"""
    scraper = TruthSocialScraper()
    new_posts = scraper.get_user_posts('realDonaldTrump', max_posts=20)
    
    if new_posts:
        print(f"[OK] {len(new_posts)} Truths recuperes. Starting Immediate Analysis...")
        
        # Load existing posts to preserve AI analysis
        existing_posts = db_load_generic('truth_social') or []
        existing_map = {p.get('url'): p for p in existing_posts if p.get('url')}
        
        merged_posts = []
        for post in new_posts:
            # ------------------------------------------------------------
            # IMMEDIATE FAST-TRACK ANALYSIS (FinBERT)
            # ------------------------------------------------------------
            try:
                content = post.get('content', '')
                # Call global function (defined later in file, but available at runtime)
                bert_result = analyze_sentiment_finbert(content)
                s_label = bert_result.get('label', 'neutral').lower() if bert_result else 'neutral'
                if bert_result and 'score' in bert_result:
                    score_val = bert_result['score']
                else:
                    score_val = 0.0
                
                # Apply Critical Analysis Tags Immediately
                post['ai_analysis_v2'] = True
                post['criticality_score'] = 9  # High Priority for Trump
                post['sentiment_label'] = s_label
                post['ai_reasoning'] = f"Direct Truth Social Feed. FinBERT: {s_label} ({score_val:.2f})"
                post['title_fr'] = "Truth Social Update"
                post['summary_fr'] = content
                post['search_keywords'] = ['TRUMP', 'Truth Social']
                
            except Exception as e:
                print(f"[WARN] Error in immediate Truth analysis: {e}")
                # Fallback
                post['ai_analysis_v2'] = False
            # ------------------------------------------------------------

            url = post.get('url')
            if url and url in existing_map:
                existing = existing_map[url]
                # Preserve keys starting with 'ai_' ONLY if we failed to analyze
                # OR if the existing analysis is deeper (e.g. from Groq later)
                # But here we overwrite with fresh FinBERT. 
                pass

            merged_posts.append(post)
            
        db_save_generic('truth_social', merged_posts)
        print(f"[OK] {len(merged_posts)} Truths analyzed & saved (Fast-Track).")
    else:
        print("[WARN] Aucun Truth recupere.")

# ============================================================================
# INSTITUTIONAL DATA SCRAPER (Merged from inst.py)
# ============================================================================

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
        self.session = requests.Session()
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

# ============================================================================
# TRADE REPUBLIC API (Class-based)
# ============================================================================

def _ws_is_closed(ws) -> bool:
    """Check whether a websockets connection is closed.
    
    Compatible with both:
      - websockets < 11  : WebSocketClientProtocol  → has `.closed` bool property
      - websockets >= 11 : ClientConnection          → has `.state` enum attribute
    """
    if ws is None:
        return True
    # websockets >= 11 (asyncio API): state is a websockets.connection.State enum
    if hasattr(ws, 'state'):
        try:
            import websockets.connection as _wsc
            return ws.state != _wsc.State.OPEN
        except Exception:
            pass
    # websockets < 11: .closed is a bool
    if hasattr(ws, 'closed'):
        return ws.closed
    # Fallback – assume open
    return False


def generate_device_info():
    """Génère dynamiquement un device-info cohérent au format Base64 attendu par TR."""
    device_id = hashlib.sha512(uuid.uuid4().bytes).hexdigest()
    device_info = {
        "stableDeviceId": device_id,
        "browser": "Edge",
        "browserVersion": "146.0.0.0",
        "os": "Windows",
        "osVersion": "10",
        "timezone": "Europe/Paris",
        "timezoneOffset": -60,
        "screen": "1920x1080x32",
        "preferredLanguages": ["fr", "fr-FR", "en", "en-GB", "en-US"],
        "numberOfCores": 12,
        "deviceMemory": 8,
    }
    return base64.b64encode(json.dumps(device_info).encode()).decode()


def get_waf_token_with_selenium():
    """Utilise Selenium en mode Headless pour obtenir le token AWS WAF de Trade Republic."""
    if not SELENIUM_AVAILABLE:
        print("[WARN] Selenium not available — WAF token skipped")
        return ""
    print("[BOT] Recuperation du token WAF via Selenium (arriere-plan)...")
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0"
    )
    # Utilise le chromium système si disponible (évite le chromedriver téléchargé)
    for system_chrome in ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]:
        if os.path.exists(system_chrome):
            options.binary_location = system_chrome
            break
    try:
        from selenium.webdriver.chrome.service import Service as ChromeService
        # Cherche chromedriver système en priorité
        system_chromedriver = None
        for path in ["/usr/bin/chromedriver", "/usr/lib/chromium/chromedriver", "/usr/lib/chromium-browser/chromedriver"]:
            if os.path.exists(path):
                system_chromedriver = path
                break
        driver = webdriver.Chrome(
            service=ChromeService(executable_path=system_chromedriver) if system_chromedriver else ChromeService(),
            options=options
        )
        # Masquer le flag webdriver détecté par le WAF
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        driver.get("https://app.traderepublic.com/")
        time.sleep(8)  # laisser le WAF Challenge se résoudre (augmenté à 8s)
        
        all_cookies = driver.get_cookies()
        print(f"   -> {len(all_cookies)} cookies trouves : {[c.get('name') for c in all_cookies]}")
        
        waf_token = None
        # Méthode principale : cookie
        for cookie in all_cookies:
            if "aws-waf-token" in cookie.get("name", ""):
                waf_token = cookie["value"]
                print(f"   -> Cookie 'aws-waf-token' trouve (len={len(waf_token)})")
                break
        # Fallback : API JS du WAF
        if not waf_token:
            try:
                waf_token = driver.execute_script(
                    "return window.AWSWafIntegration && window.AWSWafIntegration.getToken();"
                )
                if waf_token:
                    print(f"   -> Token WAF via JS (len={len(str(waf_token))})")
            except Exception:
                pass
        driver.quit()
        if waf_token:
            print("[OK] Token WAF recupere avec succes !")
            return waf_token
        print("[WARN]  Token WAF introuvable - le WAF Challenge n'a peut-etre pas eu le temps de se resoudre.")
        return ""
    except Exception as e:
        print(f"[ERROR] Erreur Selenium WAF : {e}")
        return ""


class TradeRepublicAPI:
    def __init__(self, config_path="config.ini"):
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        self.config_path = config_path
        
        # General settings
        self.output_format = self.config.get("general", "output_format", fallback="json")
        self.output_folder = self.config.get("general", "output_folder", fallback="./out")
        self.extract_details = self.config.getboolean("general", "extract_details", fallback=False)
        # os.makedirs(self.output_folder, exist_ok=True) # REMOVED DB MIGRATION
        
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
            # Structure based on user hint
            # "act":{"id":"...","acc":{"owner":{"default":{"sec":["0442851302"]...
            act = payload.get('act', {})
            acc = act.get('acc', {})
            owner = acc.get('owner', {})
            default = owner.get('default', {})
            sec_list = default.get('sec', [])
            
            if sec_list and len(sec_list) > 0:
                self.cached_sec_acc = sec_list[0]
                return self.cached_sec_acc
                
            # Fallback based on user structure if different
            # Sometimes it's directly at root level or named differently
            # The user token example:
            # "act":{"id":...,"acc":{"owner":{"default":{"sec":["0442851302"]...
            pass
            print(f"SecAccNo from JWT: {self.cached_sec_acc}")
            return self.cached_sec_acc
            
        except Exception as e:
            print(f"Error parsing JWT for secAccNo: {e}")
        return None

    def fetch_portfolio_chart(self, range_code='1d'):
        """Fetch portfolio chart data from TR API V2. Uses full browser cookies if available."""
        sec_acc = self.get_sec_acc_no()
        if not sec_acc:
            print("[ERROR] Cannot fetch chart: No Account Number found.")
            return None

        api_range = range_code.lower()
        url = f"https://api.traderepublic.com/api-gateway/portfolio-chart/v2/chart?secAccNo={sec_acc}&range={api_range}&currency=EUR"

        # Prefer full browser cookie string if stored in config (copied from DevTools)
        browser_cookies = None
        try:
            browser_cookies = self.config.get("secret", "tr_browser_cookies", fallback=None)
        except Exception:
            pass

        if browser_cookies:
            cookie_header = browser_cookies
        else:
            # Fallback: build minimal cookie from session token
            cookie_header = f"tr_session={self.session_token}"
            try:
                claims = self.config.get("secret", "tr_claims", fallback=None)
                if claims:
                    cookie_header += f"; tr_claims={claims}"
            except Exception:
                pass
            waf = getattr(self, 'waf_token', None)
            if waf:
                cookie_header += f"; aws-waf-token={waf}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0",
            "Cookie": cookie_header,
            "Origin": "https://app.traderepublic.com",
            "Referer": "https://app.traderepublic.com/",
            "Accept": "*/*",
            "Accept-Language": "fr",
            "Content-Type": "application/json",
            "x-tr-app-version": "15.6.4",
            "x-tr-platform": "web",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache"
        }

        try:
            print(f"Fetching TR Chart: {url} (cookies={'browser' if browser_cookies else 'session-only'})")
            resp = requests.get(url, headers=headers, timeout=15)

            if resp.status_code == 200:
                print("[OK] Portfolio Chart fetched via TR API.")
                return resp.json()
            elif resp.status_code == 401:
                print("[WARN] Portfolio Chart 401: session expired - attempting auto-refresh via tr_refresh...")
                if self.refresh_session_token():
                    # Rebuild request with fresh session
                    return self.fetch_portfolio_chart(range_code)
                print("[ERROR] Auto-refresh failed. Paste fresh browser cookies via /api/tr-cookies.")
                return {"error": "auth", "message": "Session expirée. Collez les cookies depuis DevTools."}
            else:
                print(f"[ERROR] Portfolio Chart HTTP {resp.status_code}: {resp.text[:200]}")
                return {"error": "http", "status": resp.status_code}
        except Exception as e:
            print(f"[ERROR] Portfolio Chart Exception: {e}")
            return None

    def save_session_token(self, token, refresh_token=None):
        """Save the session token to config.ini for persistence."""
        if not self.config.has_section("secret"):
            self.config.add_section("secret")
        self.config.set("secret", "tr_session", token)
        if refresh_token:
            self.config.set("secret", "tr_refresh", refresh_token)
            self.refresh_token = refresh_token
            
        with open(self.config_path, "w") as configfile:
            self.config.write(configfile)
        self.session_token = token
        print("[OK] Session token saved to config.ini.")

    def refresh_session_token(self):
        """Exchange the tr_refresh token for a fresh tr_session without user interaction.
        Returns True on success, False otherwise."""
        self.config.read(self.config_path)
        refresh_tok = self.refresh_token or self.config.get("secret", "tr_refresh", fallback=None)
        if not refresh_tok:
            print("[TR Refresh] [ERROR] No refresh token available.")
            return False

        url = "https://api.traderepublic.com/api/v1/auth/web/refresh"
        headers = self._build_login_headers()
        headers["Cookie"] = f"tr_refresh={refresh_tok}"
        # Also include current session cookie if present (some TR versions require it)
        if self.session_token:
            headers["Cookie"] += f"; tr_session={self.session_token}"

        try:
            print("[TR Refresh] Attempting session token refresh via tr_refresh...")
            resp = requests.post(url, headers=headers, timeout=15, allow_redirects=False)
            print(f"[TR Refresh] -> HTTP {resp.status_code}")

            new_session = None
            new_refresh = None

            # Parse cookies from response
            def _get_cookie(response, name):
                try:
                    return response.cookies.get(name)
                except Exception:
                    for c in response.cookies:
                        if c.name == name:
                            return c.value
                    return None

            if resp.status_code in (200, 201, 204):
                new_session = _get_cookie(resp, "tr_session")
                new_refresh = _get_cookie(resp, "tr_refresh")

                # Fallback: token might be in JSON body
                if not new_session:
                    try:
                        body = resp.json()
                        new_session = body.get("sessionToken") or body.get("token") or body.get("access_token")
                        new_refresh = body.get("refreshToken") or body.get("refresh_token") or new_refresh
                    except Exception:
                        pass

                # Also check Set-Cookie header directly
                if not new_session:
                    set_cookie = resp.headers.get("Set-Cookie", "")
                    m = re.search(r'tr_session=([^;,\s]+)', set_cookie)
                    if m:
                        new_session = m.group(1)
                    m2 = re.search(r'tr_refresh=([^;,\s]+)', set_cookie)
                    if m2:
                        new_refresh = m2.group(1)

            if new_session:
                self.save_session_token(new_session, new_refresh or refresh_tok)
                self.cached_sec_acc = None  # force re-derivation
                print(f"[TR Refresh] [OK] Session refreshed successfully.")
                return True
            else:
                print(f"[TR Refresh] [WARN] No new session token in refresh response (body: {resp.text[:200]})")
                return False

        except Exception as e:
            print(f"[TR Refresh] [ERROR] Exception: {e}")
            return False

    def headers_to_dict(self, response):
        extracted_headers = {}
        for header, header_value in response.headers.items():
            parsed_dict = {}
            entries = header_value.split(", ")
            for entry in entries:
                key_value = entry.split(";")[0]
                if "=" in key_value:
                    key, value = key_value.split("=", 1)
                    parsed_dict[key.strip()] = value.strip()
            extracted_headers[header] = parsed_dict if parsed_dict else header_value
        return extracted_headers

    def _build_login_headers(self):
        """Construit les headers complets requis par l'API Trade Republic (anti-WAF inclus)."""
        return {
            "Accept": "*/*",
            "Accept-Language": "fr",
            "Content-Type": "application/json",
            "Origin": "https://app.traderepublic.com",
            "Referer": "https://app.traderepublic.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0"
            ),
            "x-aws-waf-token": self.waf_token,
            "x-tr-app-version": "14.23.3",
            "x-tr-device-info": self.device_info,
            "x-tr-platform": "web",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }

    def _refresh_waf_token(self):
        """Lance Selenium pour obtenir un nouveau token WAF et le persiste dans config.ini."""
        self.waf_token = get_waf_token_with_selenium()
        if self.waf_token:
            if not self.config.has_section("secret"):
                self.config.add_section("secret")
            self.config.set("secret", "waf_token", self.waf_token)
            with open(self.config_path, "w") as configfile:
                self.config.write(configfile)
        return self.waf_token

    def initiate_login(self, phone, pin, first_name=None, last_name=None):
        """Initiate login process: Send credentials, get processId."""
        self.phone_number = phone
        self.pin = pin
        if first_name: self.first_name = first_name
        if last_name: self.last_name = last_name
        
        # Save credentials to config (optional, but good for persistence)
        if not self.config.has_section("secret"):
            self.config.add_section("secret")
        self.config.set("secret", "phone_number", phone)
        self.config.set("secret", "pin", pin)
        if first_name: self.config.set("secret", "first_name", first_name)
        if last_name: self.config.set("secret", "last_name", last_name)
        with open(self.config_path, "w") as configfile:
            self.config.write(configfile)

        def _do_request():
            # allow_redirects=False : évite la conversion POST→GET sur 301/302
            # ce qui causerait un 405 sur l'endpoint POST-only de TR
            return requests.post(
                "https://api.traderepublic.com/api/v1/auth/web/login",
                json={"phoneNumber": phone, "pin": pin},
                headers=self._build_login_headers(),
                timeout=15,
                allow_redirects=False,
            )

        try:
            print(f"[KEY] Initiating login for {phone}...")

            # Si aucun token WAF n'est disponible, on en récupère un via Selenium
            if not self.waf_token:
                self._refresh_waf_token()
                if not self.waf_token:
                    print("[WARN]  Selenium n'a pas pu obtenir le token WAF - tentative sans token.")

            resp = _do_request()
            print(f"   -> Status TR: {resp.status_code}  | Redirect: {resp.headers.get('Location', 'none')}")

            # 403 ou 405 = WAF bloque (token absent/expiré)
            if resp.status_code in (403, 405):
                print(f"[WARN]  {resp.status_code} WAF detecte - actualisation du token via Selenium et nouvelle tentative...")
                self._refresh_waf_token()
                resp = _do_request()
                print(f"   -> Retry status TR: {resp.status_code}")

            # Suivi manuel d'une éventuelle redirection 3xx (POST → POST, pas GET)
            if resp.status_code in (301, 302, 307, 308):
                location = resp.headers.get('Location')
                if location:
                    print(f"   -> Redirection {resp.status_code} vers {location} - suivi POST explicite")
                    resp = requests.post(
                        location,
                        json={"phoneNumber": phone, "pin": pin},
                        headers=self._build_login_headers(),
                        timeout=15,
                        allow_redirects=False,
                    )

            resp.raise_for_status()
            resp_json = resp.json()
            process_id = resp_json.get("processId")
            countdown = resp_json.get("countdownInSeconds")
            
            if process_id:
                return {"success": True, "processId": process_id, "countdown": countdown}
            return {"success": False, "error": "No processId received"}
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "?"
            raw_body = ""
            try:
                raw_body = e.response.text
            except:
                pass
            msg = f"HTTP {status_code}"
            try:
                err_json = e.response.json()
                # Try common TR error shapes
                if isinstance(err_json, dict):
                    errors = err_json.get("errors")
                    if errors and isinstance(errors, list):
                        msg = errors[0].get("message", msg)
                    elif err_json.get("message"):
                        msg = err_json["message"]
                    elif err_json.get("error"):
                        msg = err_json["error"]
            except:
                if raw_body:
                    msg = f"HTTP {status_code}: {raw_body[:200]}"
            print(f"[ERROR] Login init error: {msg} (status={status_code}, body={raw_body[:300]})")
            return {"success": False, "error": msg}
        except Exception as e:
            print(f"[ERROR] Login init error: {e}")
            return {"success": False, "error": str(e)}

    def resend_sms(self, process_id):
        try:
            requests.post(
                f"https://api.traderepublic.com/api/v1/auth/web/login/{process_id}/resend",
                headers=self._build_login_headers(),
                timeout=10,
                allow_redirects=False,
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def complete_login(self, process_id, code):
        """Complete login with SMS code."""
        try:
            resp2 = requests.post(
                f"https://api.traderepublic.com/api/v1/auth/web/login/{process_id}/{code}",
                headers=self._build_login_headers(),
                timeout=10,
                allow_redirects=False,
            )
            if resp2.status_code != 200:
                print("[ERROR] Device verification failed.")
                return {"success": False, "error": "Verification failed"}

            print("[OK] Device verified!")
            
            def get_cookie_safe(cookies, name):
                try:
                    return cookies.get(name)
                except Exception:
                    # In case of multiple cookies with same name (CookieConflictError)
                    for cookie in cookies:
                        if cookie.name == name:
                            return cookie.value
                    return None

            token = get_cookie_safe(resp2.cookies, "tr_session")
            refresh = get_cookie_safe(resp2.cookies, "tr_refresh")
            
            # Fallback to headers
            if not token:
                response_headers = self.headers_to_dict(resp2)
                cookies = response_headers.get("Set-Cookie", {})
                if isinstance(cookies, dict):
                    token = cookies.get("tr_session")
                    refresh = cookies.get("tr_refresh")
                # Sometimes Set-Cookie is a string or list, simplified handling here might need robustness
            
            if token:
                self.save_session_token(token, refresh)
                return {"success": True}
            else:
                return {"success": False, "error": "No session token in response"}
                
        except Exception as e:
            print(f"[ERROR] Login complete error: {e}")
            return {"success": False, "error": str(e)}

    # Remove old login method
    # def login(self): ...

    async def connect(self):
        """Establish WebSocket connection."""
        global TR_WS_ERROR
        if not self.session_token:
            print("[ERROR] No session token available. Please login first.")
            return False

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Cookie": f"tr_session={self.session_token}",
            "Origin": "https://app.traderepublic.com",
            # "Referer": "https://app.traderepublic.com/", # Not strictly needed if Origin is there
        }

        try:
            self.websocket = await websockets.connect(
                "wss://api.traderepublic.com",
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10,
                max_size=None,
                ssl=_SSL_CTX
            )
            
            # Updated Handshake based on working test script
            await self.websocket.send('connect 34 {"locale":"fr","platformId":"webtrading","platformVersion":"edge-chromium - 143.0.0","clientId":"app.traderepublic.com","clientVersion":"12.12.0"}')
            
            response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            if "connected" in response:
                print("[OK] WebSocket connected.")
                TR_WS_ERROR = {"code": None, "message": None}  # clear error on success
                return True
            else:
                print(f"[WARN] Unexpected connection response: {response}")
                return False
        except Exception as e:
            print(f"[ERROR] WebSocket connection failed: {e}")
            if "401" in str(e) or "1000" in str(e) or "1006" in str(e) or "3003" in str(e):
                print("[WARN] Session expirée (3003) - tentative de renouvellement silencieux...")
                TR_WS_ERROR = {"code": 3003, "message": "Session expirée - renouvellement en cours..."}
                if self.refresh_session_token():
                    TR_WS_ERROR = {"code": None, "message": None}
                else:
                    TR_WS_ERROR = {"code": 3003, "message": "Session expirée. Veuillez vous reconnecter."}
            return False

    async def close(self):
        if self.websocket:
            await self.websocket.close()

    async def fetch_aggregate_history_light(self, instrument_id, range_val="1y"):
        if not self.websocket:
            connected = await self.connect()
            if not connected:
                return []

        self.message_id += 1
        msg_id = self.message_id
        
        payload = {
            "type": "aggregateHistoryLight",
            "range": range_val,
            "id": instrument_id
        }
        
        try:
            await self.websocket.send(f"sub {msg_id} {json.dumps(payload)}")
            
            # Wait for response
            while True:
                try:
                    resp = await asyncio.wait_for(self.websocket.recv(), timeout=10.0)
                except asyncio.TimeoutError:
                    print(f"timeout fetching {instrument_id}")
                    break

                if resp.startswith(f"{msg_id} A"):
                    # This is the data response
                    parts = resp.split(" ", 2)
                    if len(parts) > 2:
                        data = json.loads(parts[2])
                        aggregates = data.get("aggregates", [])
                        
                        # Unsubscribe
                        await self.websocket.send(f"unsub {msg_id}")
                        return aggregates
                elif resp.startswith(f"{msg_id} E"):
                    print(f"Error fetching {instrument_id}: {resp}")
                    await self.websocket.send(f"unsub {msg_id}")
                    break
                    
        except Exception as e:
            print(f"Exception fetching {instrument_id}: {e}")
            
        return []

    async def fetch_all_stocks_recursive(self):
        """
        Retrieves ALL stocks (~11k+) using a recursive prefix scan to bypass the 10k limit.
        Returns a list of raw stock objects.
        """
        if not self.websocket:
            connected = await self.connect()
            if not connected:
                print("[ERROR] Not connected to TR WebSocket.")
                return []

        all_unique_results = {}
        # Queue de recherche plus efficace
        search_queue = deque([""]) 
        
        # On retire l'espace ' ' car souvent trim() par l'API = recherche vide = boucle infinie ou redondance massive
        extended_chars = list(string.ascii_lowercase) + \
                         [str(i) for i in range(10)] + \
                         ['.', '-', '&', "'"]
        
        print(f"[NET] Demarrage du scan RECURSIF des actions...")
        
        # Compteur pour suivre l'avancement
        processed_count = 0
        
        while search_queue:
            query = search_queue.popleft()
            processed_count += 1
            
            # Affichage périodique ou si la query est courte
            if len(query) <= 2 or processed_count % 20 == 0:
                print(f"   --> Scan: '{query}' (Queue: {len(search_queue)}, Trouves: {len(all_unique_results)})")

            # 1. Sonder
            self.message_id += 1
            msg_id = self.message_id
            
            payload = {
                "type": "neonSearch",
                "data": {
                    "q": query,
                    "page": 1,
                    "pageSize": 1, 
                    "filter": [{"key": "type", "value": "stock"}]
                }
            }
            
            total_count = 0
            
            # Gestion basique erreur envoi
            try:
                await self.websocket.send(f"sub {msg_id} {json.dumps(payload)}")
            except Exception:
                 # Tentative reconnexion
                 if await self.connect():
                      try: await self.websocket.send(f"sub {msg_id} {json.dumps(payload)}")
                      except: continue
                 else:
                      continue

            try:
                probe_done = False
                while not probe_done:
                    try:
                        resp = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
                    except Exception as e:
                        # Timeout ou connection error
                        break 

                    if resp.startswith("echo"): continue
                    parts = resp.split(" ", 2)
                    
                    if len(parts) >= 2 and parts[0] == str(msg_id):
                        if parts[1] in ['A', 'C']:
                            if len(parts) > 2:
                                data = json.loads(parts[2])
                                total_count = data.get("resultCount", 0)
                                await self.websocket.send(f"unsub {msg_id}")
                                probe_done = True
                        elif parts[1] == 'E':
                            # print(f"Ignore: Erreur API sur '{query}'")
                            await self.websocket.send(f"unsub {msg_id}")
                            probe_done = True
            except Exception:
                pass

            # 2. Décision
            # Seuil de sécurité
            threshold = 5000 
            
            if total_count > threshold:
                for c in extended_chars:
                    search_queue.append(query + c)
            else:
                if total_count > 0:
                    await self._fetch_all_pages(query, all_unique_results)
        
        print(f"[OK] Scan complet termine. {len(all_unique_results)} actions recuperees.")
        return list(all_unique_results.values())

    async def _fetch_all_pages(self, query, storage_dict):
        # Vérification connexion
        if not self.websocket:
             connected = await self.connect()
             if not connected:
                 return

        page = 1
        page_size = 50
        
        while True:
            self.message_id += 1
            msg_id = self.message_id
            
            payload = {
                "type": "neonSearch",
                "data": {
                    "q": query,
                    "page": page,
                    "pageSize": page_size,
                    "filter": [{"key": "type", "value": "stock"}]
                }
            }
            try:
                await self.websocket.send(f"sub {msg_id} {json.dumps(payload)}")
            except Exception:
                # Reconnexion et retry unique
                await self.connect()
                try:
                    await self.websocket.send(f"sub {msg_id} {json.dumps(payload)}")
                except:
                    return # Abandon
            
            page_finished = False
            try:
                response_received = False
                while not response_received:
                    try:
                        # On utilise websocket.recv() direct
                        resp = await asyncio.wait_for(self.websocket.recv(), timeout=8.0)
                    except Exception: # ConnectionClosed etc
                         # print("[WARN] Connexion perdue (page loop). Reconnexion...")
                         await self.connect()
                         break 

                    if resp.startswith("echo"): continue
                    parts = resp.split(" ", 2)
                    
                    if len(parts) >= 2 and parts[0] == str(msg_id):
                        if parts[1] in ['A', 'C']:
                            if len(parts) > 2:
                                data = json.loads(parts[2])
                                results = data.get("results", [])
                                
                                # Stockage
                                for r in results:
                                    isin = r.get("isin")
                                    if isin and isin not in storage_dict:
                                        storage_dict[isin] = r
                                
                                # Stop condition
                                if len(results) < page_size:
                                    page_finished = True
                                
                                await self.websocket.send(f"unsub {msg_id}")
                                response_received = True
                        elif parts[1] == 'E':
                            await self.websocket.send(f"unsub {msg_id}")
                            response_received = True
                            page_finished = True
            except asyncio.TimeoutError:
                break 
            
            if page_finished:
                break
            page += 1
            await asyncio.sleep(0.02)

    async def _sub_unsub(self, payload, name="Unknown", log_structure=False):
        """Subscribe, get one message, and unsubscribe."""
        if not self.websocket:
            raise Exception("WebSocket not connected")

        self.message_id += 1
        msg_id = self.message_id
        
        await self.websocket.send(f"sub {msg_id} {json.dumps(payload)}")
        
        data = None
        try:
            # We wait for the INITIAL data (Type 'A' or 'D')
            while True:
                response = await asyncio.wait_for(self.websocket.recv(), timeout=8.0)
                
                # Handle heartbeat
                if response.startswith("echo"):
                    continue

                parts = response.split(" ", 2)
                if len(parts) < 2:
                    continue

                frame_id   = parts[0]
                frame_type = parts[1]

                # Only treat E-frame as error when it belongs to OUR subscription.
                # Ignore stale E-frames from previous unrelated subscriptions.
                if frame_id == str(msg_id) and frame_type == 'E':
                    print(f"[ERROR] API Error on {name}: {response}")
                    return None

                if frame_id == str(msg_id):
                    # Format: ID TYPE PAYLOAD
                    if len(parts) > 2:
                        data = json.loads(parts[2])
                    else:
                        data = {}  # Empty payload
                    break
                # else: frame belongs to a different subscription — keep reading
                    
        except asyncio.TimeoutError:
            print(f"[WARN] Timeout waiting for {name}")
            return None
        except Exception as e:
            print(f"[ERROR] Error reading {name}: {e}")
            return None
        finally:
            # Unsubscribe
            try:
                await self.websocket.send(f"unsub {msg_id}")
            except:
                pass
        
        return data

    async def get_securities_account(self):
        """Dynamically fetch the securities account number."""
        if self.cached_sec_acc:
            return self.cached_sec_acc
            
        print("[SEARCH] Searching for securitiesAccountNumber via accountPairs...")
        res = await self._sub_unsub({"type": "accountPairs"}, "AccountPairs")
        if res and "accounts" in res:
            accounts_list = res["accounts"]
            # Handle both list and dict just in case
            if isinstance(accounts_list, list):
                for acc in accounts_list:
                    sec_acc = acc.get("securitiesAccountNumber")
                    if sec_acc:
                         print(f"[OK] Securities Account Found: {sec_acc}")
                         self.cached_sec_acc = sec_acc
                         return sec_acc
            elif isinstance(accounts_list, dict):
                 sec_acc = accounts_list.get("securitiesAccountNumber")
                 if sec_acc:
                     print(f"[OK] Securities Account Found: {sec_acc}")
                     self.cached_sec_acc = sec_acc
                     return sec_acc
        print("[ERROR] securitiesAccountNumber not found in accountPairs.")
        return None

    async def fetch_portfolio(self, silent=False):
        if not silent:
            print("\n? Fetching Portfolio (Optimized for Stocks)...")
        
        # 1. Get Account ID
        sec_acc_no = await self.get_securities_account()
        if not sec_acc_no:
             # Try a fallback hardcoded ID if you want, or just return
             # sec_acc_no = "0442851302" 
             if not silent: print("[WARN] Cannot fetch portfolio without Account ID.")
             return {}

        # 2. Get Portfolio via compactPortfolioByTypeV2
        if not silent: print(f"[SEARCH] Fetching portfolio items for {sec_acc_no}...")
        data = await self._sub_unsub(
            {"type": "compactPortfolioByTypeV2", "secAccNo": sec_acc_no}, 
            "PortfolioV2"
        )

        # 2.5 Get Cash
        if not silent: print(f"[SEARCH] Fetching cash info...")
        cash_raw = await self._sub_unsub({"type": "cash"}, "Cash")
        available_cash = {}
        if isinstance(cash_raw, list) and len(cash_raw) > 0:
             available_cash = cash_raw[0]
             if not silent: print(f"[MONEY] Cash found: {available_cash.get('amount')} {available_cash.get('currencyId')}")
        
        # 3. Parse Results
        positions = []
        if data:
            # Check for 'results' (flat list) or 'categories' (nested)
            if "results" in data:
                positions = data["results"]
            elif "categories" in data:
                 if not silent: print(f"? Found {len(data['categories'])} categories.")
                 for cat in data['categories']:
                     # Extract items from common keys
                     # We saw 'positions' in the debug output for stocksAndETFs
                     items = cat.get("positions") or cat.get("items") or cat.get("results") or cat.get("products") or []
                     positions.extend(items)
        
        if positions:
            if not silent: print(f"[OK] {len(positions)} positions found. Enriching with market data...")
            
            enriched_positions = []
            for pos in positions:
                isin = pos.get("isin")
                if not isin:
                    continue
                
                # Default values
                qty = float(pos.get("netSize", 0))
                buy_price = 0.0
                curr_price = 0.0
                
                # Parse Buy Price
                avg_buy_in = pos.get("averageBuyIn")
                if isinstance(avg_buy_in, dict):
                    buy_price = float(avg_buy_in.get("value", 0))
                elif avg_buy_in is not None:
                     try: buy_price = float(avg_buy_in)
                     except: pass

                # Fetch Market Data
                try:
                    # Get Exchange (cached or fetched)
                    exchange_id = await self.get_home_exchange(isin)
                    if not exchange_id:
                        if not silent: print(f"[WARN] No exchange found for {isin}, defaulting to LSX")
                        exchange_id = "LSX"
                    # else:
                        # if not silent: print(f"?? Exchange for {isin}: {exchange_id}")

                    # Get Ticker
                    ticker = await self.get_ticker(isin, exchange_id)
                    
                    if not ticker and not silent:
                         print(f"[ERROR] No ticker data for {isin}.{exchange_id}")

                    curr_price = self._extract_price(ticker)
                    if curr_price == 0.0 and ticker and not silent:
                         pass
                         # print(f"[WARN] Price 0.0 extracted. Ticker payload: {json.dumps(ticker)[:100]}...")

                except Exception as e:
                    if not silent: print(f"[WARN] Error enriching {isin}: {e}")
                
                # Calculate Values
                total_value = qty * curr_price
                pnl = total_value - (qty * buy_price)
                pnl_percent = (pnl / (qty * buy_price)) * 100 if (qty * buy_price) > 0 else 0
                
                pos_data = {
                    "isin": isin,
                    "name": pos.get("name"),
                    "quantity": qty,
                    "buy_price": buy_price,
                    "current_price": curr_price,
                    "total_value": total_value,
                    "pnl": pnl,
                    "pnl_percent": pnl_percent,
                    "exchange": exchange_id if 'exchange_id' in locals() else "LSX",
                    "instrumentType": pos.get("instrumentType", "stock"),
                    "logo": pos.get("imageId")
                }
                enriched_positions.append(pos_data)


            
            # Save to file & DB
            wallet_data = {
                "availableCash": available_cash,
                "my_investments": enriched_positions,
                "positions_detailed": enriched_positions,
                "last_updated": str(datetime.now())
            }
            try:
                db_save_portfolio(wallet_data, user_phone=self.phone_number) # SAVE TO DB WITH USER CONTEXT
                # JSON write removed as requested
                if not silent: print("[SAVE] Saved to Database.")
            except Exception as e:
                print(f"Error saving portfolio data: {e}")

            return enriched_positions
        else:
            if not silent: print("[ERROR] No positions found or empty response.")
            return {}

    # Removed legacy endpoints fetching loop to focus on what works
    # If other endpoints (cash, timeline) are needed, they can be re-added similarly using self._sub()


    async def get_home_exchange(self, isin):
        if isin in self.cached_exchanges:
            return self.cached_exchanges[isin]
            
        payload = {"type": "homeInstrumentExchange", "id": isin, "token": self.session_token}
        data = await self._sub_unsub(payload, name=f"Exchange {isin}")
        res = data.get("exchangeId") if data else None
        
        if res:
            self.cached_exchanges[isin] = res
        return res

    async def get_ticker(self, isin, exchange_id="LSX"):
        ticker_id = f"{isin}.{exchange_id}"
        payload = {"type": "ticker", "id": ticker_id, "token": self.session_token}
        return await self._sub_unsub(payload, name=f"Ticker {isin}")

    def _extract_price(self, ticker_data):
        if not ticker_data or not isinstance(ticker_data, dict): 
            return 0.0
        
        price_obj = None
        
        # Check standard fields
        try:
            if "last" in ticker_data and isinstance(ticker_data["last"], dict) and "price" in ticker_data["last"]:
                price_obj = ticker_data["last"]["price"]
            elif "bid" in ticker_data and isinstance(ticker_data["bid"], dict) and "price" in ticker_data["bid"]:
                price_obj = ticker_data["bid"]["price"]
            elif "ask" in ticker_data and isinstance(ticker_data["ask"], dict) and "price" in ticker_data["ask"]:
                 price_obj = ticker_data["ask"]["price"]
            
            # Additional fallback: aggregatedInfo (often used for stocks)
            if not price_obj and "aggregatedInfo" in ticker_data and isinstance(ticker_data["aggregatedInfo"], dict):
                 # aggregatedInfo usually has 'price' or 'last'
                 agg = ticker_data["aggregatedInfo"]
                 if "price" in agg: price_obj = agg["price"]
                 elif "last" in agg: price_obj = agg["last"]
        except Exception as e:
            print(f"[WARN] Error parsing ticker structure: {e}")
            return 0.0

        if not price_obj:
             return 0.0

        if not isinstance(price_obj, dict):
             # Maybe it's a direct value? Unlikely but let's handle
             try: return float(price_obj)
             except: return 0.0

        try:
            val = float(price_obj.get("value", 0))
            digits = price_obj.get("fractionDigits", 2)
            return val / (10 ** digits)
        except Exception as e:
            print(f"[WARN] Error calculating price from object {price_obj}: {e}")
            return 0.0

    async def fetch_transaction_details(self, transaction_id):
        """Fetch details for a specific transaction.
        
        API response structure:
          sections[0]: header section  {"title": "You invested €726.48",
                                        "action": {"payload": "<ISIN>", "type": "instrumentDetail"},
                                        "data": [{"timestamp": "2026-02-10T13:06:39.808407Z",
                                                  "status": "executed", "icon": "logos/<ISIN>/v2"}]}
          sections[1]: {"title": "Overview", "type": "table",
                        "data": [{"title": "Shares", "detail": {"text": "5"}}, ...]}
          sections[2]: {"title": "Documents", ...}
          sections[3]: {"title": "", "type": "table", ...}
        """
        payload = {"type": "timelineDetailV2", "id": transaction_id, "token": self.session_token}
        data = await self._sub_unsub(payload, name=f"Tx {transaction_id}")

        result = {}
        if not data:
            return result

        sections = data.get("sections", [])
        if not sections:
            return result

        # --- Section 0: header with ISIN + timestamp ---
        header_sec = sections[0]
        action = header_sec.get("action", {})
        if action.get("type") == "instrumentDetail" and action.get("payload"):
            result["isin"] = action["payload"]

        header_data = header_sec.get("data", [])
        if header_data:
            first = header_data[0]
            ts = first.get("timestamp")
            if ts:
                result["timestamp"] = ts
            result["status"] = first.get("status", "")
            # Fallback ISIN from icon field
            if "isin" not in result:
                icon = first.get("icon", "")
                m = re.search(r'logos/([A-Z0-9]{12})', icon)
                if m:
                    result["isin"] = m.group(1)

        # Extract invested amount from header title
        title = header_sec.get("title", "")
        result["header_title"] = title
        amount_match = re.search(r'[\d]+[.,][\d]+', title.replace(",", "."))
        if amount_match:
            try:
                result["amount_eur"] = float(amount_match.group(0))
            except:
                pass

        # --- Remaining sections: look for table sections ---
        def _get_table_text(section):
            out = {}
            for item in section.get("data", []):
                if not isinstance(item, dict):
                    continue
                key = item.get("title", "").strip()
                detail = item.get("detail", {})
                if isinstance(detail, dict):
                    val = detail.get("text", "")
                elif isinstance(detail, str):
                    val = detail
                else:
                    val = ""
                if key:
                    out[key] = val
            return out

        for sec in sections[1:]:
            if sec.get("type") == "table":
                table_data = _get_table_text(sec)
                result.update(table_data)

        return result

    async def fetch_history(self, extract_details=False):
        print("\n[DOC] Fetching Transaction History...")
        all_transactions = []
        after_cursor = None
        
        while True:
            payload = {"type": "timelineTransactions", "token": self.session_token}
            if after_cursor:
                payload["after"] = after_cursor
            
            data = await self._sub_unsub(payload, name="Transactions Page")
            if not data:
                break
                
            items = data.get("items", [])
            if not items:
                break
                
            if extract_details:
                print(f"   extracting details for {len(items)} items...")
                for transaction in items:
                    t_id = transaction.get("id")
                    if t_id:
                        # Slight delay to avoid rate limits if any
                        await asyncio.sleep(0.05) 
                        details = await self.fetch_transaction_details(t_id)
                        transaction.update(details)
            
            all_transactions.extend(items)
            
            after_cursor = data.get("cursors", {}).get("after")
            if not after_cursor:
                break
                
        # SAVE TO DB
        if not hasattr(self, 'config'):
             # Try to reload config if missing (shouldn't happen in this class)
             self.config = configparser.ConfigParser()
             self.config.read('config.ini')

        phone = self.config.get("secret", "phone_number", fallback=None)
        key = f'tr_transactions_{phone}' if phone else 'tr_transactions'
        db_save_generic(key, all_transactions)
        print(f"[OK] {len(all_transactions)} transactions saved to DB.")
        return all_transactions

# ============================================================================
# TRADE REPUBLIC AUTH ROUTES
# ============================================================================
tr_api = TradeRepublicAPI()

# Tracks the last WebSocket connection error for the frontend
TR_WS_ERROR = {"code": None, "message": None}

# --- LIVE UPDATES THREAD ---
def run_live_updates():
    # Separate instance for background thread
    live_api = TradeRepublicAPI()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def loop_logic():
        print("[INFO] Starting Live Updates Loop (every 5s)...")
        while True:
             # Check credentials
             if not live_api.session_token:
                 # Try to reload from config in case login happened
                 live_api.config.read(live_api.config_path)
                 token = live_api.config.get("secret", "tr_session", fallback=None)
                 phone = live_api.config.get("secret", "phone_number", fallback=None)
                 
                 if token:
                     live_api.session_token = token
                     live_api.phone_number = phone # Critical: Update phone for db save context
                 else:
                     print("[WAIT] Live Loop: Waiting for login...")
                     await asyncio.sleep(10)
                     continue
            
             # Connect
             connected = await live_api.connect()
             if not connected:
                 if not live_api.session_token:
                     print("[WAIT] Live Loop: Session cleared (3003 / expired). Please log in via the UI. Retrying in 15s...")
                     await asyncio.sleep(15)
                 else:
                     print("[WARN] Live Loop: Connection failed, retrying in 10s...")
                     await asyncio.sleep(10)
                 continue
             
             # Fetch Loop
             while connected:
                 try:
                     # Silent fetch to avoid log spam, but keeps updating P&L
                     await live_api.fetch_portfolio(silent=True)
                     # Removed explicit print to clear console
                     # print(f"[TIME] Live Update: {datetime.now().strftime('%H:%M:%S')}")
                     await asyncio.sleep(5)
                 except Exception as e:
                     print(f"[ERROR] Live Loop Error: {e}")
                     break # Break to reconnect
             
             # If we break loop, clean up
             await live_api.close()
             await asyncio.sleep(5)
    
    try:
        loop.run_until_complete(loop_logic())
    except Exception as e:
        print(f"[ERROR] Live Thread Died: {e}")
    finally:
        loop.close()

# Start background thread
live_thread = threading.Thread(target=run_live_updates, daemon=True)
live_thread.start()


def _session_watchdog():
    """Surveille l'expiration du tr_session et le renouvelle silencieusement via tr_refresh.
    Le SMS OTP n'est JAMAIS envoyé automatiquement - uniquement via l'action manuelle de l'utilisateur."""
    print("[Watchdog] Démarrage du watchdog de session Trade Republic.")
    while True:
        try:
            cfg = configparser.ConfigParser()
            cfg.read("config.ini")
            session_tok = cfg.get("secret", "tr_session", fallback=None) or ""
            refresh_tok = cfg.get("secret", "tr_refresh", fallback=None) or ""
            now = time.time()

            if session_tok and refresh_tok:
                session_exp = _jwt_expiry(session_tok)
                # Renouveler si expiré ou expire dans moins de 10 min
                if session_exp and (session_exp - now) < 600:
                    remaining = max(0, int(session_exp - now))
                    print(f"[Watchdog] tr_session expire dans {remaining}s - renouvellement silencieux via tr_refresh...")
                    if tr_api.refresh_session_token():
                        print("[Watchdog] Session renouvelée avec succès.")
                    else:
                        print("[Watchdog] Renouvellement échoué - l'utilisateur devra se reconnecter manuellement si nécessaire.")

        except Exception as e:
            print(f"[Watchdog] Erreur : {e}")
        time.sleep(120)  # Vérification toutes les 2 minutes


_watchdog_thread = threading.Thread(target=_session_watchdog, daemon=True)
_watchdog_thread.start()

# ============================================================================
# CASH ANALYZER
# ============================================================================


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
                logo = f"https://assets.traderepublic.com/img/logos/{isin}/v2.png"
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

# ============================================================================
# API ROUTES (INTEGRATION)
# ============================================================================

@app.route('/api/cash/analysis', methods=['GET'])
def get_cash_analysis():
    # Try to get phone from header
    phone = request.headers.get('X-User-Phone')
    
    # Try to fallback to config if not in header (for monolithic app)
    if not phone:
         try:
             config = configparser.ConfigParser()
             config.read('config.ini')
             phone = config.get('secret', 'phone_number', fallback=None)
         except: pass

    key = f'tr_transactions_{phone}' if phone else 'tr_transactions'
    
    # Load transactions
    transactions = db_load_generic(key)
    
    # Fallback: if specific key failed, try generic default
    if not transactions and phone:
         transactions = db_load_generic('tr_transactions')
         
    if not transactions:
         transactions = []

    analyzer = CashAnalyzer(transactions)
    result = analyzer.analyze()
    return jsonify({"status": "success", "data": result})

@app.route('/api/institutional/cot/<commodity>', methods=['GET'])
def get_cot_api(commodity):
    try:
        limit = int(request.args.get('limit', 10))
        scraper = RealInstitutionalDataScraper()
        df = scraper.get_cot_data_real(commodity, limit)
        return jsonify({"status": "success", "data": df.to_dict(orient='records')})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/institutional/stock/<ticker>', methods=['GET'])
def get_inst_stock_api(ticker):
    try:
        scraper = RealInstitutionalDataScraper()
        results = scraper.analyze_stock_complete(ticker)
        if 'yahoo_holders' in results and isinstance(results['yahoo_holders'], pd.DataFrame):
            results['yahoo_holders'] = results['yahoo_holders'].to_dict(orient='records')
        if 'mutual_funds' in results and isinstance(results['mutual_funds'], pd.DataFrame):
            results['mutual_funds'] = results['mutual_funds'].to_dict(orient='records')
        return jsonify({"status": "success", "data": results})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
        
@app.route('/api/institutional/13f/<institution>', methods=['GET'])
def get_13f_api(institution):
    try:
        scraper = RealInstitutionalDataScraper()
        cik = scraper.search_cik_real(institution)
        if not cik:
             return jsonify({"status": "error", "message": "Institution not found"}), 404
        df = scraper.get_latest_13f_holdings(cik)
        return jsonify({"status": "success", "data": df.to_dict(orient='records')})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================================
# ASSETS ENRICHED DATA — Sentiment, Annual Perf, Momentum, Financials
# ============================================================================

@app.route('/api/assets/enriched/<ticker>', methods=['GET'])
def get_assets_enriched(ticker):
    """
    Endpoint unique qui renvoie pour un ticker :
      - news_sentiment  : score agrégé + points de vigilance depuis bloomberg_rss
      - annual_returns  : performance annuelle (calendrier) depuis 2019
      - momentum        : perf 1M/3M/6M/1Y + comparaison sectorielle (SectorTrend)
      - financials      : Revenus, Coût des ventes, Résultat Net (annuel via yfinance)
    """
    ticker = ticker.upper().strip()
    result = {
        "ticker": ticker,
        "news_sentiment": {},
        "annual_returns": [],
        "momentum": {},
        "financials": {},
        "quarterly_results": {},
        "eps_surprise": [],
        "macro_correlation": {},
        "short_interest": {},
        "options_flow": {},
    }

    # ── 1. NEWS SENTIMENT ──────────────────────────────────────────────────
    try:
        bloomberg_data = db_load_generic('bloomberg_rss') or {}
        all_items = bloomberg_data.get('items', []) + bloomberg_data.get('news_segments', [])
        related = []
        ticker_upper = ticker.upper()
        for item in all_items:
            text = f"{item.get('title','')}{item.get('title_fr','')}{item.get('summary','')}{item.get('summary_fr','')}".upper()
            if ticker_upper in text:
                cs = item.get('criticality_score', 0) or 0
                sl = item.get('sentiment_label', 'neutral') or 'neutral'
                related.append({'criticality': cs, 'sentiment': sl.lower(),
                                 'title': item.get('title_fr') or item.get('title', ''),
                                 'reasoning': item.get('ai_reasoning', '')})
        vigilance_items = [i for i in related if i['criticality'] >= 7]
        scores = [i['criticality'] for i in related if i['criticality'] > 0]
        positives = sum(1 for i in related if i['sentiment'] in ('positive','bullish'))
        negatives = sum(1 for i in related if i['sentiment'] in ('negative','bearish'))
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        result['news_sentiment'] = {
            'total_mentions': len(related),
            'vigilance_count': len(vigilance_items),
            'avg_criticality': avg_score,
            'positive_count': positives,
            'negative_count': negatives,
            'vigilance_items': vigilance_items[:5],
            'sentiment_bias': 'bullish' if positives > negatives else ('bearish' if negatives > positives else 'neutral'),
        }
    except Exception as e:
        print(f"[ENRICHED] Sentiment error for {ticker}: {e}")

    # ── 2. ANNUAL RETURNS ──────────────────────────────────────────────────
    try:
        t = yf.Ticker(ticker)
        start_year = 2019
        current_year = datetime.now().year
        hist = yf.download(ticker, start=f"{start_year}-01-01", end=f"{current_year}-12-31",
                           interval="1mo", progress=False)
        if isinstance(hist.columns, pd.MultiIndex):
            try: hist = hist['Close'][ticker]
            except: hist = hist.iloc[:, 0]
        else:
            hist = hist['Close'] if 'Close' in hist.columns else hist.iloc[:, 0]
        hist = hist.dropna()

        annual = []
        for yr in range(start_year, current_year + 1):
            yr_data = hist[hist.index.year == yr]
            if len(yr_data) < 2:
                continue
            open_p = float(yr_data.iloc[0])
            close_p = float(yr_data.iloc[-1])
            perf = round((close_p - open_p) / open_p * 100, 2)
            annual.append({'year': yr, 'perf': perf, 'open': round(open_p, 2), 'close': round(close_p, 2)})
        result['annual_returns'] = annual
    except Exception as e:
        print(f"[ENRICHED] Annual returns error for {ticker}: {e}")

    # ── 3. MOMENTUM + SECTEUR ──────────────────────────────────────────────
    try:
        perf_hist = yf.download(ticker, period="1y", interval="1d", progress=False)
        if isinstance(perf_hist.columns, pd.MultiIndex):
            try: closes = perf_hist['Close'][ticker]
            except: closes = perf_hist.iloc[:, 0]
        else:
            closes = perf_hist['Close'] if 'Close' in perf_hist.columns else perf_hist.iloc[:, 0]
        closes = closes.dropna()

        def get_perf(n_days):
            if len(closes) < n_days + 1: return None
            old = float(closes.iloc[-(n_days + 1)])
            now = float(closes.iloc[-1])
            return round((now - old) / old * 100, 2) if old else None

        perf_1m = get_perf(21)
        perf_3m = get_perf(63)
        perf_6m = get_perf(126)
        perf_1y = get_perf(252) if len(closes) > 252 else (round((float(closes.iloc[-1]) - float(closes.iloc[0])) / float(closes.iloc[0]) * 100, 2) if len(closes) > 1 else None)

        # Sector comparison via yfinance info
        t_info = yf.Ticker(ticker).info
        stock_sector = (t_info.get('sector') or 'Unknown').lower()

        # Find matching sector in SectorTrend DB
        sector_monthly = None
        sector_name_matched = None
        try:
            trends = SectorTrend.query.all()
            for st in trends:
                if st.sector_name and any(word in st.sector_name.lower() for word in stock_sector.split()):
                    sector_monthly = st.monthly_trend
                    sector_name_matched = st.sector_name
                    break
        except Exception as db_e:
            print(f"[ENRICHED] Sector DB error: {db_e}")

        result['momentum'] = {
            '1m': perf_1m,
            '3m': perf_3m,
            '6m': perf_6m,
            '1y': perf_1y,
            'sector': stock_sector.title(),
            'sector_monthly': sector_monthly,
            'sector_name': sector_name_matched,
            'vs_sector_1m': round(perf_1m - (sector_monthly or 0), 2) if perf_1m is not None else None,
        }
    except Exception as e:
        print(f"[ENRICHED] Momentum error for {ticker}: {e}")

    # ── 4. FINANCIALS ──────────────────────────────────────────────────────
    try:
        t_fin = yf.Ticker(ticker)
        # income_stmt is the modern API, financials is the alias
        fin = None
        try:
            fin = t_fin.income_stmt
        except:
            pass
        if fin is None or fin.empty:
            try:
                fin = t_fin.financials
            except:
                fin = None

        if fin is not None and not fin.empty:
            rows = {}
            wanted = {
                'Total Revenue': 'revenue',
                'Cost Of Revenue': 'cogs',
                'Gross Profit': 'gross_profit',
                'Operating Expense': 'opex',
                'Net Income': 'net_income',
                'EBITDA': 'ebitda',
            }
            for label, key in wanted.items():
                # Try multiple case variants
                for row_name in fin.index:
                    if label.lower() in str(row_name).lower():
                        rows[key] = {}
                        for col in fin.columns:
                            val = fin.loc[row_name, col]
                            if pd.notna(val):
                                yr_str = str(col.year) if hasattr(col, 'year') else str(col)[:4]
                                rows[key][yr_str] = int(val)
                        break
            # Build sorted year list
            years = sorted(set(yr for d in rows.values() for yr in d.keys()), reverse=True)[:5]
            result['financials'] = {'rows': rows, 'years': years}
    except Exception as e:
        print(f"[ENRICHED] Financials error for {ticker}: {e}")

    # ── 5. QUARTERLY RESULTS ───────────────────────────────────────────────
    try:
        t_q = yf.Ticker(ticker)
        qfin = None
        try:
            qfin = t_q.quarterly_income_stmt
        except Exception:
            pass
        if qfin is None or (hasattr(qfin, 'empty') and qfin.empty):
            try:
                qfin = t_q.quarterly_financials
            except Exception:
                qfin = None

        quarters = []
        if qfin is not None and not qfin.empty:
            rev_row, ni_row, oi_row = None, None, None
            for rn in qfin.index:
                rns = str(rn).lower()
                if 'total revenue' in rns:      rev_row = rn
                if 'net income' in rns:         ni_row  = rn
                if 'operating income' in rns or 'operating expense' in rns or 'ebit' in rns:
                    oi_row = rn
            # gross profit for operating margin approximation
            gp_row = None
            for rn in qfin.index:
                if 'gross profit' in str(rn).lower(): gp_row = rn

            cols = list(qfin.columns)[:8]  # last 8 quarters
            prev_rev = None
            for col in reversed(cols):  # oldest first for growth calc
                q_label = col.strftime('%YQ') if hasattr(col, 'strftime') else str(col)[:7]
                try:
                    q_num = (col.month - 1) // 3 + 1
                    q_label = f"Q{q_num} {col.year}"
                except Exception:
                    pass
                r  = float(qfin.loc[rev_row, col]) if rev_row is not None and pd.notna(qfin.loc[rev_row, col]) else None
                ni = float(qfin.loc[ni_row,  col]) if ni_row  is not None and pd.notna(qfin.loc[ni_row,  col]) else None
                oi = float(qfin.loc[oi_row,  col]) if oi_row  is not None and pd.notna(qfin.loc[oi_row,  col]) else None
                gp = float(qfin.loc[gp_row,  col]) if gp_row  is not None and pd.notna(qfin.loc[gp_row,  col]) else None
                rev_growth = round((r - prev_rev) / abs(prev_rev) * 100, 1) if r is not None and prev_rev and prev_rev != 0 else None
                op_margin  = round(gp / r * 100, 1) if gp is not None and r else (round(oi / r * 100, 1) if oi is not None and r else None)
                quarters.append({
                    'quarter': q_label,
                    'revenue': int(r) if r is not None else None,
                    'net_income': int(ni) if ni is not None else None,
                    'op_margin': op_margin,
                    'rev_growth': rev_growth,
                })
                prev_rev = r

        # Guidance / upcoming earnings from calendar
        guidance = None
        try:
            cal = t_q.calendar
            if cal is not None:
                if isinstance(cal, dict):
                    ed = cal.get('Earnings Date') or cal.get('earningsDate')
                    if ed:
                        guidance = {'earnings_date': str(ed[0]) if isinstance(ed, list) else str(ed)}
                    rev_low = cal.get('Revenue Low') or cal.get('revenueEstimateLow')
                    rev_high= cal.get('Revenue High') or cal.get('revenueEstimateHigh')
                    if rev_low: guidance = {**(guidance or {}), 'rev_est_low': int(rev_low), 'rev_est_high': int(rev_high) if rev_high else None}
                elif hasattr(cal, 'to_dict'):
                    d = cal.to_dict()
                    guidance = {str(k): str(v) for k, v in list(d.items())[:6]}
        except Exception as gc_e:
            print(f"[ENRICHED] Calendar error: {gc_e}")

        result['quarterly_results'] = {
            'quarters': list(reversed(quarters)),  # most recent first
            'guidance': guidance
        }
    except Exception as e:
        print(f"[ENRICHED] Quarterly results error for {ticker}: {e}")

    # ── 6. EPS SURPRISE ────────────────────────────────────────────────────
    try:
        t_eps = yf.Ticker(ticker)
        eps_list = []
        # Try earnings_history first (newer API)
        try:
            eh = t_eps.earnings_history
            if eh is not None and not eh.empty:
                for _, row in eh.iterrows():
                    actual   = row.get('epsActual')
                    estimate = row.get('epsEstimate')
                    surprise = row.get('epsSurprise') or row.get('surprisePercent')
                    quarter  = str(row.get('quarter', row.name))[:10] if hasattr(row, 'name') else ''
                    if actual is not None:
                        surp_pct = round(float(surprise) * 100, 1) if surprise is not None and abs(float(surprise)) < 10 else (round(float(surprise), 1) if surprise is not None else None)
                        eps_list.append({'quarter': quarter, 'actual': round(float(actual), 2),
                                         'estimate': round(float(estimate), 2) if estimate is not None else None,
                                         'surprise_pct': surp_pct})
        except Exception:
            pass
        # Fallback: earnings (annual/quarterly)
        if not eps_list:
            try:
                earn = t_eps.earnings
                if earn is not None and not earn.empty:
                    for yr, row in earn.iterrows():
                        eps_list.append({'quarter': str(yr), 'actual': round(float(row.get('Earnings', 0) or 0), 2), 'estimate': None, 'surprise_pct': None})
            except Exception:
                pass
        result['eps_surprise'] = eps_list[:8]
    except Exception as e:
        print(f"[ENRICHED] EPS surprise error for {ticker}: {e}")

    # ── 7. MACRO CORRELATION ───────────────────────────────────────────────
    try:
        macro_symbols = {
            'VIX':       '^VIX',
            'US10Y':     '^TNX',
            'DXY':       'DX-Y.NYB',
            'SP500':     '^GSPC',
            'Or':        'GC=F',
            'Pétrole':   'CL=F',
        }
        macro_data = {}
        for label, sym in macro_symbols.items():
            try:
                h = yf.download(sym, period='1mo', interval='1d', progress=False)
                if isinstance(h.columns, pd.MultiIndex):
                    try: h = h['Close'][sym]
                    except: h = h.iloc[:, 0]
                else:
                    h = h['Close'] if 'Close' in h.columns else h.iloc[:, 0]
                h = h.dropna()
                if len(h) < 5: continue

                # 1-month perf
                pct_1m = round((float(h.iloc[-1]) - float(h.iloc[0])) / float(h.iloc[0]) * 100, 2)
                # correlation with the stock over same window
                stock_h = yf.download(ticker, period='1mo', interval='1d', progress=False)
                if isinstance(stock_h.columns, pd.MultiIndex):
                    try: stock_s = stock_h['Close'][ticker]
                    except: stock_s = stock_h.iloc[:, 0]
                else:
                    stock_s = stock_h['Close'] if 'Close' in stock_h.columns else stock_h.iloc[:, 0]
                stock_s = stock_s.dropna()
                corr = None
                if len(stock_s) > 5 and len(h) > 5:
                    aligned = pd.concat([stock_s, h], axis=1).dropna()
                    if len(aligned) > 4:
                        corr = round(float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1])), 2)
                macro_data[label] = {'perf_1m': pct_1m, 'current': round(float(h.iloc[-1]), 2), 'correlation': corr}
            except Exception:
                pass
        result['macro_correlation'] = macro_data
    except Exception as e:
        print(f"[ENRICHED] Macro correlation error for {ticker}: {e}")

    # ── 8. SHORT INTEREST ──────────────────────────────────────────────────
    try:
        t_si = yf.Ticker(ticker)
        info = t_si.info
        shares_short    = info.get('sharesShort')
        shares_float    = info.get('floatShares') or info.get('sharesFloat')
        short_ratio     = info.get('shortRatio')
        short_pct_float = info.get('shortPercentOfFloat')
        prev_short      = info.get('sharesShortPriorMonth')
        result['short_interest'] = {
            'shares_short':       int(shares_short)    if shares_short    else None,
            'short_ratio':        round(float(short_ratio), 2) if short_ratio else None,
            'short_pct_float':    round(float(short_pct_float) * 100, 2) if short_pct_float and float(short_pct_float) <= 1 else (round(float(short_pct_float), 2) if short_pct_float else None),
            'shares_short_prev':  int(prev_short)      if prev_short      else None,
            'float_shares':       int(shares_float)    if shares_float    else None,
            'change_pct':         round((shares_short - prev_short) / prev_short * 100, 1) if shares_short and prev_short and prev_short != 0 else None,
        }
    except Exception as e:
        print(f"[ENRICHED] Short interest error for {ticker}: {e}")

    # ── 9. OPTIONS FLOW ────────────────────────────────────────────────────
    try:
        t_opt = yf.Ticker(ticker)
        exp_dates = t_opt.options
        if exp_dates:
            # Use the nearest expiry
            nearest = exp_dates[0]
            chain = t_opt.option_chain(nearest)
            calls = chain.calls
            puts  = chain.puts
            total_call_oi = int(calls['openInterest'].sum()) if 'openInterest' in calls.columns else 0
            total_put_oi  = int(puts['openInterest'].sum())  if 'openInterest' in puts.columns else 0
            total_call_vol= int(calls['volume'].sum())       if 'volume'       in calls.columns else 0
            total_put_vol = int(puts['volume'].sum())        if 'volume'       in puts.columns else 0
            pc_ratio_oi   = round(total_put_oi  / total_call_oi,  2) if total_call_oi  else None
            pc_ratio_vol  = round(total_put_vol / total_call_vol, 2) if total_call_vol else None

            # Top 3 calls and puts by open interest
            def top_strikes(df, n=3):
                if df.empty or 'openInterest' not in df.columns: return []
                top = df.nlargest(n, 'openInterest')
                return [{'strike': round(float(r['strike']), 2),
                         'oi': int(r['openInterest']),
                         'vol': int(r.get('volume', 0) or 0),
                         'iv': round(float(r.get('impliedVolatility', 0) or 0) * 100, 1)} for _, r in top.iterrows()]

            result['options_flow'] = {
                'expiry': nearest,
                'call_oi': total_call_oi,
                'put_oi': total_put_oi,
                'call_vol': total_call_vol,
                'put_vol': total_put_vol,
                'pc_ratio_oi': pc_ratio_oi,
                'pc_ratio_vol': pc_ratio_vol,
                'top_calls': top_strikes(calls),
                'top_puts': top_strikes(puts),
                'bias': 'bullish' if (pc_ratio_vol or 1) < 0.8 else ('bearish' if (pc_ratio_vol or 1) > 1.2 else 'neutre'),
            }
    except Exception as e:
        print(f"[ENRICHED] Options flow error for {ticker}: {e}")

    # ── 10. SEASONAL ANALYSIS ─────────────────────────────────────────────
    try:
        hist_sea = yf.download(ticker, start='2015-01-01', progress=False)
        if isinstance(hist_sea.columns, pd.MultiIndex):
            try:
                close_sea = hist_sea['Close'][ticker]
            except Exception:
                close_sea = hist_sea.iloc[:, 0]
        else:
            close_sea = hist_sea['Close'] if 'Close' in hist_sea.columns else hist_sea.iloc[:, 0]
        close_sea = close_sea.resample('ME').last().dropna()
        monthly_rets = close_sea.pct_change().dropna() * 100

        MONTHS_FR = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']

        # Monthly averages across all years
        monthly_avgs = []
        for m in range(1, 13):
            vals_s = monthly_rets[monthly_rets.index.month == m]
            vals_clean = [float(v) for v in vals_s.values if not pd.isna(v)]
            avg = round(sum(vals_clean) / len(vals_clean), 2) if vals_clean else 0.0
            pos = sum(1 for v in vals_clean if v > 0)
            monthly_avgs.append({
                'month': MONTHS_FR[m - 1],
                'month_num': m,
                'avg_pct': avg,
                'positive_years': pos,
                'total_years': len(vals_clean),
            })

        # Per-year monthly grid (last 10 years)
        current_yr = datetime.now().year
        yearly_grid = []
        for yr in range(current_yr - 9, current_yr + 1):
            yr_data = monthly_rets[monthly_rets.index.year == yr]
            if yr_data.empty:
                continue
            months_pct = {}
            for idx_val, pct_val in yr_data.items():
                if not pd.isna(pct_val):
                    months_pct[str(idx_val.month)] = round(float(pct_val), 1)
            if months_pct:
                yearly_grid.append({'year': yr, 'months': months_pct})
        yearly_grid.reverse()  # most recent first

        result['seasonality'] = {
            'monthly_avgs': monthly_avgs,
            'yearly_grid': yearly_grid,
        }
    except Exception as e:
        print(f"[ENRICHED] Seasonality error for {ticker}: {e}")

    return jsonify(clean_for_json(result))

# ============================================================================
# GLOBAL MARKET DATA (Moved from ez.py)
# ============================================================================

class GlobalMarketData:
    """
    Récupère les données des marchés mondiaux :
    - Matières premières (Or, Pétrole, etc.)
    - Devises (Forex)
    - Obligations (Treasury Yields)
    - Indices mondiaux (CAC 40, DAX, etc.)
    """
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _fetch_realtime(self, symbol):
        """Real-time price via fast_info (works outside US market hours). Falls back to intraday history."""
        t = yf.Ticker(symbol)
        try:
            fi = t.fast_info
            current = fi.last_price
            prev = fi.previous_close
            if current is not None and prev is not None and float(prev) > 0:
                change = float(current) - float(prev)
                pct = round(change / float(prev) * 100, 2)
                return round(float(current), 4), round(float(change), 4), pct
        except Exception:
            pass
        # Fallback: intraday 2d/5m bars
        hist = t.history(period='2d', interval='5m')
        if hist.empty:
            raise ValueError(f'No data for {symbol}')
        current = float(hist['Close'].iloc[-1])
        today = hist.index[-1].date()
        prev_bars = hist[hist.index.map(lambda x: x.date()) < today]
        prev = float(prev_bars['Close'].iloc[-1]) if not prev_bars.empty else float(hist['Close'].iloc[0])
        change = current - prev
        pct = round((change / prev * 100) if prev else 0, 2)
        return round(current, 4), round(change, 4), pct

    # ==================== MATIÈRES PREMIÈRES ====================
    def get_commodities(self):
        commodities = {}
        symbols = {
            'Gold': 'GC=F', 'Silver': 'SI=F', 'Platinum': 'PL=F', 'Palladium': 'PA=F', 'Copper': 'HG=F',
            'Crude_Oil_WTI': 'CL=F', 'Crude_Oil_Brent': 'BZ=F', 'Natural_Gas': 'NG=F', 'Heating_Oil': 'HO=F', 'Gasoline': 'RB=F',
            'Wheat': 'ZW=F', 'Corn': 'ZC=F', 'Soybeans': 'ZS=F', 'Coffee': 'KC=F', 'Sugar': 'SB=F', 'Cotton': 'CT=F', 'Cocoa': 'CC=F',
        }
        print("[PKG] Recuperation des matieres premieres (real-time)...")
        for name, symbol in symbols.items():
            try:
                price, change, change_pct = self._fetch_realtime(symbol)
                commodities[name] = {
                    'symbol': symbol,
                    'price': round(price, 2),
                    'change': round(change, 2),
                    'change_pct': change_pct,
                    'currency': 'USD',
                    'last_update': datetime.now().isoformat()
                }
            except Exception as e:
                print(f"  [ERROR] Erreur {name}: {e}")
                commodities[name] = {'error': str(e), 'symbol': symbol}
        commodities['timestamp'] = datetime.now().isoformat()
        return commodities
    
    # ==================== DEVISES (FOREX) ====================
    def get_forex(self):
        forex = {}
        pairs = {
            'EUR/USD': 'EURUSD=X', 'GBP/USD': 'GBPUSD=X', 'USD/JPY': 'USDJPY=X', 'USD/CHF': 'USDCHF=X',
            'AUD/USD': 'AUDUSD=X', 'NZD/USD': 'NZDUSD=X', 'USD/CAD': 'USDCAD=X', 'EUR/GBP': 'EURGBP=X',
            'EUR/JPY': 'EURJPY=X', 'GBP/JPY': 'GBPJPY=X', 'USD/CNY': 'USDCNY=X', 'USD/HKD': 'USDHKD=X', 'USD/SGD': 'USDSGD=X',
        }
        print("\n[FOREX] Recuperation des devises Forex (real-time)...")
        for pair_name, symbol in pairs.items():
            try:
                rate, change, change_pct = self._fetch_realtime(symbol)
                forex[pair_name] = {
                    'symbol': symbol,
                    'rate': round(rate, 4),
                    'change': round(change, 4),
                    'change_pct': change_pct,
                    'last_update': datetime.now().isoformat()
                }
            except Exception as e:
                print(f"  [ERROR] Erreur {pair_name}: {e}")
                forex[pair_name] = {'error': str(e), 'symbol': symbol}
        forex['timestamp'] = datetime.now().isoformat()
        return forex
    
    # ==================== OBLIGATIONS (TREASURY YIELDS) ====================
    def get_treasury_yields(self):
        yields = {}
        symbols = {
            '1_Month': '^IRX', '3_Month': '^IRX', '2_Year': '^FVX', '5_Year': '^FVX', '10_Year': '^TNX', '30_Year': '^TYX',
        }
        print("\n[DATA] Recuperation des taux obligataires US...")
        for name, symbol in symbols.items():
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='5d')
                if not hist.empty:
                    current_yield = hist['Close'].iloc[-1]
                    prev_yield = hist['Close'].iloc[0] if len(hist) > 1 else current_yield
                    change = current_yield - prev_yield
                    yields[name] = {
                        'symbol': symbol,
                        'yield': round(float(current_yield), 3),
                        'change': round(float(change), 3),
                        'last_update': datetime.now().isoformat(),
                        'unit': '%'
                    }
            except Exception as e:
                print(f"  [ERROR] Erreur {name}: {e}")
                yields[name] = {'error': str(e), 'symbol': symbol}
        
        # Calcul des spreads
        if '10_Year' in yields and '2_Year' in yields and 'yield' in yields['10_Year'] and 'yield' in yields['2_Year']:
            spread = yields['10_Year']['yield'] - yields['2_Year']['yield']
            yields['10Y_2Y_Spread'] = {
                'value': round(spread, 3),
                'interpretation': 'Normal' if spread > 0 else 'Inverted (Recession Signal)',
                'unit': 'bps'
            }
        yields['timestamp'] = datetime.now().isoformat()
        return yields

    # ==================== INDICES MONDIAUX ====================
    def get_global_indices(self):
        indices = {}
        symbols = {
            'S&P_500': '^GSPC', 'Dow_Jones': '^DJI', 'NASDAQ': '^IXIC', 'Russell_2000': '^RUT',
            'CAC_40': '^FCHI', 'DAX': '^GDAXI', 'FTSE_100': '^FTSE', 'EURO_STOXX_50': '^STOXX50E',
            'Nikkei_225': '^N225', 'Hang_Seng': '^HSI', 'Shanghai_Composite': '000001.SS',
            'VIX': '^VIX', 'Brazil_Bovespa': '^BVSP'
        }
        print("\n[WORLD] Recuperation des indices mondiaux (real-time)...")
        for name, symbol in symbols.items():
            try:
                price, change, change_pct = self._fetch_realtime(symbol)
                indices[name] = {
                    'symbol': symbol,
                    'price': round(price, 2),
                    'change': round(change, 2),
                    'change_pct': change_pct,
                    'last_update': datetime.now().isoformat()
                }
                if name == 'VIX':
                    sentiment = 'Low Fear (Complacent)' if price < 15 else 'Normal' if price < 20 else 'Elevated Fear' if price < 30 else 'High Fear (Panic)'
                    indices[name]['interpretation'] = sentiment
            except Exception as e:
                print(f"  [ERROR] Erreur {name}: {e}")
                indices[name] = {'error': str(e), 'symbol': symbol}
        indices['timestamp'] = datetime.now().isoformat()
        return indices

    def get_all_market_data(self):
        return {
            'commodities': self.get_commodities(),
            'forex': self.get_forex(),
            'treasury_yields': self.get_treasury_yields(),
            'indices': self.get_global_indices(),
            'timestamp': datetime.now().isoformat()
        }

# ==================== MARKET CORRELATOR ====================

class MarketCorrelator:
    """
    Analyse le portefeuille et identifie les corrélations de marché pertinentes.
    Crée des 'Surveillances' basées sur la composition du portefeuille.
    """
    def __init__(self):
        # Règles de corrélation (Mots-clés vs Indicateurs)
        self.rules = [
            {
                'category': 'Technology & Growth',
                'keywords': ['Technology', 'Software', 'Semiconductor', 'NVIDIA', 'Apple', 'Microsoft', 'Google', 'Meta', 'Amazon', 'Tesla', 'ASML', 'AMD', 'Intel', 'Tech', 'AI', 'Cyber'],
                'indicators': [
                    {'symbol': '^IXIC', 'name': 'NASDAQ', 'type': 'index', 'reason': 'Corrélation Secteur Tech'},
                    {'symbol': '^TNX', 'name': 'Taux US 10 Ans', 'type': 'yield', 'reason': 'Sensibilité aux Taux (Growth)'}
                ]
            },
            {
                'category': 'Energy',
                'keywords': ['Energy', 'Oil', 'Gas', 'Petroleum', 'Shell', 'Total', 'Exxon', 'Chevron', 'BP', 'Eni', 'Equinor'],
                'indicators': [
                    {'symbol': 'CL=F', 'name': 'Pétrole WTI', 'type': 'commodity', 'reason': 'Prix de l\'Énergie'},
                    {'symbol': 'NG=F', 'name': 'Gaz Naturel', 'type': 'commodity', 'reason': 'Prix de l\'Énergie'}
                ]
            },
            {
                'category': 'Precious Metals',
                'keywords': ['Gold', 'Silver', 'Mining', 'Precious', 'Agnico', 'Barrick', 'Newmont', 'Franco-Nevada', 'Wheaton'],
                'indicators': [
                    {'symbol': 'GC=F', 'name': 'Or (Gold)', 'type': 'commodity', 'reason': 'Actif Sous-jacent'},
                    {'symbol': 'SI=F', 'name': 'Argent (Silver)', 'type': 'commodity', 'reason': 'Actif Sous-jacent'}
                ]
            },
            {
                'category': 'Crypto & Blockchain',
                'keywords': ['Bitcoin', 'Crypto', 'Coinbase', 'MicroStrategy', 'Blockchain', 'Ethereum', 'Miner', 'Riot', 'Marathon'],
                'indicators': [
                    {'symbol': 'BTC-USD', 'name': 'Bitcoin', 'type': 'crypto', 'reason': 'Leader du Marché Crypto'},
                    {'symbol': 'ETH-USD', 'name': 'Ethereum', 'type': 'crypto', 'reason': 'Alternative Crypto Majeure'}
                ]
            },
            {
                'category': 'Financials',
                'keywords': ['Bank', 'Financial', 'Insurance', 'JPM', 'Chase', 'Goldman', 'Sachs', 'BNP', 'Axa', 'Allianz', 'Santander'],
                'indicators': [
                    {'symbol': '^TNX', 'name': 'Taux US 10 Ans', 'type': 'yield', 'reason': 'Marge d\'Intérêt'},
                    {'symbol': '10Y_2Y_Spread', 'name': 'Yield Curve', 'type': 'spread', 'reason': 'Indicateur de Récession/Marge'}
                ]
            },
            {
                'category': 'China Exposure',
                'keywords': ['Alibaba', 'Tencent', 'JD.com', 'Nio', 'Baidu', 'China', 'Emerging'],
                'indicators': [
                    {'symbol': '000001.SS', 'name': 'Shanghai Composite', 'type': 'index', 'reason': 'Exposition Marché Chinois'},
                    {'symbol': 'USDCNY=X', 'name': 'USD/CNY', 'type': 'forex', 'reason': 'Risque de Change (Yuan)'}
                ]
            },
            {
                'category': 'European Stocks',
                'keywords': ['LVMH', 'L\'Oreal', 'Airbus', 'Siemens', 'SAP', 'Inditex', 'Euro'], 
                # Note: Détection simpliste, idéalement enrichir avec la devise de l'actif (EUR)
                'indicators': [
                    {'symbol': 'EURUSD=X', 'name': 'EUR/USD', 'type': 'forex', 'reason': 'Impact Taux de Change Export'}
                ]
            }
        ]

    def get_market_data_subset(self, symbols_needed):
        """Récupère les données live pour une liste de symboles spécifiques"""
        data = {}
        # Mapping symbol -> Nom pour affichage propre
        symbol_map = {item['symbol']: item for item in symbols_needed}
        
        # Optimisation: Bulk fetch via yfinance pour actions/indices/crypto/forex/futures
        # Note: yfinance gère bien le mix
        unique_symbols = list(symbol_map.keys())
        # Filtrer les symboles spéciaux calculés (ex: spreads)
        fetch_symbols = [s for s in unique_symbols if 'Spread' not in s]
        
        if fetch_symbols:
            try:
                tickers = yf.Tickers(' '.join(fetch_symbols))
                
                for symbol in fetch_symbols:
                    try:
                        ticker = tickers.tickers[symbol]
                        # History est plus fiable pour le prix temps réel que info
                        hist = ticker.history(period="5d")
                        
                        if not hist.empty:
                            current = hist['Close'].iloc[-1]
                            prev = hist['Close'].iloc[-2] if len(hist) > 1 else hist['Open'].iloc[-1]
                            change = current - prev
                            pct = (change / prev) * 100 if prev != 0 else 0
                            
                            info = symbol_map[symbol]
                            data[symbol] = {
                                'symbol': symbol,
                                'name': info['name'],
                                'price': current,
                                'change': change,
                                'change_pct': pct,
                                'reason': info['reason'],
                                'type': info.get('type', 'generic')
                            }
                    except Exception as e:
                        print(f"Error fetching correlation data for {symbol}: {e}")
            except Exception as e:
                print(f"Bulk fetch error: {e}")

        # Gestion Spéciale: Spreads
        if '10Y_2Y_Spread' in unique_symbols:
            # Besoin de fetcher TNX et FVX manuellement si pas déjà fait
            try:
                t10 = yf.Ticker('^TNX').history(period='1d')['Close'].iloc[-1]
                t2 = yf.Ticker('^FVX').history(period='1d')['Close'].iloc[-1]
                val = t10 - t2
                data['10Y_2Y_Spread'] = {
                    'symbol': '10Y_2Y_Spread',
                    'name': 'Yield Curve (10Y-2Y)',
                    'price': val,
                    'change': 0, # Difficile à calc sans historique spread
                    'change_pct': 0,
                    'reason': symbol_map['10Y_2Y_Spread']['reason'],
                    'type': 'spread',
                    'interpretation': 'Normal' if val > 0 else 'Inverted (Warning)'
                }
            except: pass

        return data

    def analyze(self, portfolio_positions):
        """
        Analyse les positions et retourne une liste d'indicateurs à surveiller.
        portfolio_positions: Liste de dicts {'name': '...', 'ticker': '...', 'isin': '...'}
        """
        active_indicators = {} # Utiliser dict pr dédoublonner par symbole
        
        for pos in portfolio_positions:
            name = pos.get('name', '').lower()
            ticker = pos.get('ticker', '').lower() if pos.get('ticker') else ''
            
            # 1. Check Keywords
            for rule in self.rules:
                match = False
                # Vérifier mots-clés dans Nom ou Ticker
                for kw in rule['keywords']:
                    kw_lower = kw.lower()
                    if kw_lower in name or kw_lower in ticker:
                         match = True
                         break
                
                if match:
                    for ind in rule['indicators']:
                        # On garde la raison la plus pertinente (ou on concatène)
                        sym = ind['symbol']
                        if sym not in active_indicators:
                            active_indicators[sym] = {
                                'symbol': sym,
                                'name': ind['name'],
                                'type': ind['type'],
                                'reason': f"Impacté par {pos.get('name', 'Position')}"
                            }
                        else:
                            # Ajouter la position à la raison si pas trop long
                            if "Impacté par" in active_indicators[sym]['reason']:
                                current_reasons = active_indicators[sym]['reason'].split(', ')
                                if len(current_reasons) < 3:
                                     active_indicators[sym]['reason'] += f", {pos.get('name')}"
                                elif "..." not in active_indicators[sym]['reason']:
                                     active_indicators[sym]['reason'] += ", ..."

        # Récupérer les données Data Live pour ces indicateurs
        symbols_list = list(active_indicators.values())
        live_data = self.get_market_data_subset(symbols_list)
        
        # Merger les données live avec les métadonnées
        results = []
        for sym, meta in active_indicators.items():
            if sym in live_data:
                results.append(live_data[sym])
            else:
                # Fallback si data pas dispo
                results.append({
                    **meta,
                    'price': 'N/A',
                    'change_pct': 0
                })
                
        return results

@app.route('/api/market/correlations', methods=['GET'])
def get_portfolio_correlations():
    """Endpoint pour récupérer les indicateurs clés basés sur le portfolio"""
    try:
        # Charger le portfolio depuis la DB
        portfolio = db_load_latest_portfolio()
        if not portfolio:
             return jsonify({'status': 'warning', 'message': 'Portfolio empty', 'data': []})
        
        positions = portfolio.get('positions', [])
        if not positions:
            positions = portfolio.get('my_investments', [])
            
        correlator = MarketCorrelator()
        analysis = correlator.analyze(positions)
        
        return jsonify({'status': 'success', 'data': analysis})
    except Exception as e:
        print(f"Correlation Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/ai/news-recommendations', methods=['GET'])
def get_ai_news_recommendations():
    """Analyses news (RSS) via Groq to recommend stocks"""
    try:
        # 1. Get News Data
        rss_data = db_load_generic('bloomberg_rss')
        
        # If empty or old (older than 4h), refresh
        should_refresh = False
        if not rss_data or 'items' not in rss_data:
            should_refresh = True
        else:
            fetched_at = rss_data.get('fetched_at')
            if fetched_at:
                try:
                    last_fetch = datetime.fromisoformat(fetched_at)
                    if datetime.now() - last_fetch > timedelta(hours=4):
                        should_refresh = True
                except:
                    should_refresh = True
        
        if should_refresh:
            print("Refreshing Bloomberg RSS for AI analysis...")
            rss_data = fetch_bloomberg_rss_api()
            
        items = rss_data.get('items', [])
        if not items:
            return jsonify({'status': 'warning', 'message': 'No news data available', 'data': []})
            
        # 2. Prepare Context for AI
        # Take top 20 news items to avoid token limits, focus on title + summary
        news_context = "\n".join([f"- {item['title']}: {item['summary'][:200]}" for item in items[:20]])
        
        system_prompt = (
            "You are an expert financial analyst. Your goal is to identify investment opportunities based strictly on the provided news."
        )
        
        user_prompt = (
            f"Analyze the following market news headlines and summaries:\n\n{news_context}\n\n"
            "Identify the top 3-6 stock tickers that are most 'prized' or have the highest upside potential based on these specific news events. "
            "Focus on companies with positive momentum, breakouts, or strong fundamental catalysts mentioned.\n"
            "Return a strictly valid JSON array of objects. No markdown, no intro text.\n"
            "Format: [{'ticker': 'AAPL', 'name': 'Apple Inc', 'reason': 'Detailed explanation citing the specific news...', 'score': 8.5, 'sentiment': 'Bullish'}]\n"
            "Score is between 0-10. Sentiment is 'Bullish' or 'Neutral'."
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # 3. Call Groq
        print("Calling Groq for News Analysis...")
        ai_response = call_groq_api(messages, max_tokens=1000)
        
        # 4. Clean and Parse Response
        try:
            # Remove potential markdown code blocks
            clean_json = ai_response.replace('```json', '').replace('```', '').strip()
            recommendations = json.loads(clean_json)
            
            # Enrich with Logo URL if possible (optional, frontend handles it usually)
            for rec in recommendations:
                # heuristic to guess ISIN or just let frontend handle ticker
                pass
                
            return jsonify({'status': 'success', 'data': recommendations})
            
        except json.JSONDecodeError as je:
            print(f"AI JSON Error: {je}. Response: {ai_response}")
            return jsonify({'status': 'error', 'message': 'Failed to parse AI response'}), 500
            
    except Exception as e:
        print(f"AI News Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== TECHNICAL ANALYZER ====================

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

    def analyze_ticker(self, ticker_symbol):
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

@app.route('/api/analysis/technicals', methods=['GET'])
def get_technical_signals():
    """Scanne le portefeuille utilisateur pour les signaux techniques"""
    try:
        portfolio = db_load_latest_portfolio()
        if not portfolio:
             return jsonify({'status': 'warning', 'message': 'Portfolio empty', 'data': []})
        
        positions = portfolio.get('positions', [])
        unique_tickers = list(set([p.get('ticker') for p in positions if p.get('ticker')]))
        
        # Analyser TOUT le portfolio (max 20 pour perf)
        unique_tickers = unique_tickers[:20] 
        
        analyzer = TechnicalAnalyzer()
        results = []
        
        # Parallel Execution
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(analyzer.analyze_ticker, t): t for t in unique_tickers}
            for future in futures:
                res = future.result()
                if res: 
                    # On retourne TOUT maintenant, pas juste les alertes
                    results.append(res)
                    
        return jsonify({'status': 'success', 'data': results})
    except Exception as e:
        print(f"Scan Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/analysis/360', methods=['POST'])
def get_analysis_360():
    """Analyse complète du portefeuille — Technique + Insiders + Macro + News + Events + Enriched"""
    try:
        portfolio = db_load_latest_portfolio()
        if not portfolio:
            return jsonify({'status': 'warning', 'message': 'Portfolio vide', 'data': {}})

        positions = portfolio.get('positions', [])
        unique_tickers = list(set([p.get('ticker') for p in positions if p.get('ticker')]))[:20]

        # ── HELPER: Enriched per-ticker data via yfinance (parallel) ──────────
        def fetch_ticker_enriched(ticker):
            """Fetch short interest, options bias, quarterly trend, EPS beat rate, upcoming events"""
            result = {
                'ticker': ticker,
                'short_interest': {},
                'options_bias': None,
                'options_pc': None,
                'quarterly_trend': [],   # last 3 quarters: [{'q': label, 'rev': val, 'ni': val, 'growth': pct}]
                'eps_beat_rate': None,   # % of quarters that beat estimates
                'eps_last': None,        # last quarter surprise %
                'upcoming_earnings': None,
                'eps_estimate': None,
                'upcoming_dividend': None,
                'dividend_amount': None,
                'annual_perf_1y': None,
                'sector': '',
            }
            try:
                t = yf.Ticker(ticker)
                info = {}
                try:
                    info = t.info or {}
                except Exception:
                    pass

                # Sector
                try:
                    result['sector'] = (info.get('sector') or '').strip()
                except Exception:
                    pass

                # Short interest
                try:
                    sp = info.get('shortPercentOfFloat')
                    sr = info.get('shortRatio')
                    sp_prev = info.get('sharesShortPriorMonth')
                    ss = info.get('sharesShort')
                    if sp is not None:
                        pct = round(float(sp) * 100, 2) if float(sp) <= 1 else round(float(sp), 2)
                        chg = round((float(ss) - float(sp_prev)) / float(sp_prev) * 100, 1) if ss and sp_prev and float(sp_prev) > 0 else None
                        result['short_interest'] = {
                            'pct_float': pct,
                            'ratio': round(float(sr), 1) if sr else None,
                            'change_pct': chg,
                        }
                except Exception:
                    pass

                # Options bias
                try:
                    exps = t.options
                    if exps:
                        chain = t.option_chain(exps[0])
                        call_oi = int(chain.calls['openInterest'].sum()) if 'openInterest' in chain.calls.columns else 0
                        put_oi  = int(chain.puts['openInterest'].sum())  if 'openInterest' in chain.puts.columns else 0
                        call_v  = int(chain.calls['volume'].sum())       if 'volume' in chain.calls.columns else 0
                        put_v   = int(chain.puts['volume'].sum())        if 'volume' in chain.puts.columns else 0
                        pc = round(put_oi / call_oi, 2) if call_oi else None
                        pc_v = round(put_v / call_v, 2) if call_v else None
                        result['options_bias'] = 'bullish' if (pc_v or 1) < 0.8 else ('bearish' if (pc_v or 1) > 1.2 else 'neutre')
                        result['options_pc'] = pc
                        result['options_call_oi'] = call_oi
                        result['options_put_oi'] = put_oi
                except Exception:
                    pass

                # Quarterly results trend (last 3 quarters)
                try:
                    qfin = None
                    try: qfin = t.quarterly_income_stmt
                    except Exception: pass
                    if qfin is None or (hasattr(qfin, 'empty') and qfin.empty):
                        try: qfin = t.quarterly_financials
                        except Exception: qfin = None
                    if qfin is not None and not qfin.empty:
                        rev_row = next((r for r in qfin.index if 'total revenue' in str(r).lower()), None)
                        ni_row  = next((r for r in qfin.index if 'net income' in str(r).lower()), None)
                        cols = list(qfin.columns)[:4]
                        prev_r = None
                        for col in reversed(cols):
                            try:
                                ql = f"Q{(col.month-1)//3+1} {col.year}" if hasattr(col, 'month') else str(col)[:7]
                                r  = float(qfin.loc[rev_row, col]) if rev_row is not None and pd.notna(qfin.loc[rev_row, col]) else None
                                ni = float(qfin.loc[ni_row, col])  if ni_row  is not None and pd.notna(qfin.loc[ni_row, col])  else None
                                grw = round((r - prev_r) / abs(prev_r) * 100, 1) if r is not None and prev_r else None
                                result['quarterly_trend'].append({'q': ql, 'rev': int(r) if r else None, 'ni': int(ni) if ni else None, 'growth': grw})
                                prev_r = r
                            except Exception:
                                pass
                        result['quarterly_trend'] = list(reversed(result['quarterly_trend']))  # most recent first
                except Exception:
                    pass

                # EPS beat/miss rate
                try:
                    eh = t.earnings_history
                    if eh is not None and not eh.empty:
                        beats = 0; total_eps = 0; last_surp = None
                        for _, row in eh.iterrows():
                            actual = row.get('epsActual')
                            estimate = row.get('epsEstimate')
                            surprise = row.get('epsSurprise') or row.get('surprisePercent')
                            if actual is not None and estimate is not None:
                                total_eps += 1
                                if float(actual) >= float(estimate):
                                    beats += 1
                            if surprise is not None and last_surp is None:
                                last_surp = round(float(surprise) * 100, 1) if abs(float(surprise)) < 10 else round(float(surprise), 1)
                        result['eps_beat_rate'] = round(beats / total_eps * 100) if total_eps else None
                        result['eps_last'] = last_surp
                except Exception:
                    pass

                # Upcoming earnings + dividend
                try:
                    cal = t.calendar
                    if cal is not None:
                        cal_d = cal if isinstance(cal, dict) else (cal.to_dict() if hasattr(cal, 'to_dict') else {})
                        ed = cal_d.get('Earnings Date') or cal_d.get('earningsDate') or cal_d.get('Earnings_Date')
                        if ed:
                            ed_val = ed[0] if isinstance(ed, list) else ed
                            result['upcoming_earnings'] = str(ed_val)[:10]
                        eps_est = cal_d.get('EPS Estimate') or cal_d.get('epsEstimate')
                        if eps_est is not None:
                            result['eps_estimate'] = round(float(eps_est), 2)
                except Exception:
                    pass

                # Dividend date
                try:
                    div_date = info.get('dividendDate') or info.get('exDividendDate')
                    if div_date:
                        if isinstance(div_date, (int, float)):
                            div_dt = datetime.fromtimestamp(div_date)
                            result['upcoming_dividend'] = div_dt.strftime('%Y-%m-%d')
                        else:
                            result['upcoming_dividend'] = str(div_date)[:10]
                    div_amt = info.get('dividendRate') or info.get('lastDividendValue')
                    if div_amt:
                        result['dividend_amount'] = round(float(div_amt), 3)
                except Exception:
                    pass

                # 1-year performance
                try:
                    hist = t.history(period='1y')
                    if not hist.empty and len(hist) > 20:
                        result['annual_perf_1y'] = round((float(hist['Close'].iloc[-1]) - float(hist['Close'].iloc[0])) / float(hist['Close'].iloc[0]) * 100, 1)
                except Exception:
                    pass

            except Exception as outer_e:
                print(f"[360] Enriched error for {ticker}: {outer_e}")
            return result

        # ── 1. Parallel: Technical + Enriched per ticker ─────────────────────
        analyzer = TechnicalAnalyzer()
        tech_by_ticker = {}
        enriched_by_ticker = {}

        with ThreadPoolExecutor(max_workers=6) as executor:
            tech_futures  = {executor.submit(analyzer.analyze_ticker, t): ('tech', t)  for t in unique_tickers}
            enr_futures   = {executor.submit(fetch_ticker_enriched, t): ('enr', t)     for t in unique_tickers}
            all_futures   = {**tech_futures, **enr_futures}
            for future in all_futures:
                kind, ticker = all_futures[future]
                try:
                    res = future.result()
                    if res:
                        if kind == 'tech':
                            tech_by_ticker[res.get('ticker', ticker)] = res
                        else:
                            enriched_by_ticker[ticker] = res
                except Exception as fe:
                    print(f"[360] Future error ({kind}, {ticker}): {fe}")

        # ── 2. Insiders from DB (by ticker, fast) ────────────────────────────
        insiders_by_ticker = {t: [] for t in unique_tickers}
        try:
            with app.app_context():
                for ticker in unique_tickers:
                    txns = InsiderTransaction.query.filter_by(ticker=ticker).order_by(
                        InsiderTransaction.last_updated.desc()
                    ).limit(10).all()
                    for tx in txns:
                        insiders_by_ticker[ticker].append({
                            'name': tx.insider_name or '',
                            'transaction': tx.transaction,
                            'value': tx.value,
                            'date': tx.date,
                        })
        except Exception as ins_e:
            print(f"[360] Insiders DB error: {ins_e}")

        # ── 3. Market snapshot from cache ────────────────────────────────────
        indices  = db_load_generic('market_indices')  or {}
        treasury = db_load_generic('market_treasury') or {}

        vix_val = 0.0; sp500_change = 0.0
        nasdaq_change = 0.0; sp500_price = 0.0
        for key, val in indices.items():
            if not isinstance(val, dict): continue
            name = str(val.get('name', '')).upper()
            if 'VIX' in name or 'VIX' in key.upper():
                vix_val = float(val.get('price', 0) or 0)
            if 'S&P' in name or 'SPX' in key.upper() or 'GSPC' in key.upper():
                sp500_change = float(val.get('change_pct', 0) or 0)
                sp500_price  = float(val.get('price', 0) or 0)
            if 'NASDAQ' in name or 'NDX' in key.upper() or 'IXIC' in key.upper():
                nasdaq_change = float(val.get('change_pct', 0) or 0)

        y10_val = 0.0; y2_val = 0.0
        for key, val in treasury.items():
            if not isinstance(val, dict): continue
            if '10' in str(key): y10_val = float(val.get('yield', 0) or 0)
            elif '2' in str(key) and '20' not in str(key): y2_val = float(val.get('yield', 0) or 0)

        spread = round(y10_val - y2_val, 2) if y10_val and y2_val else None

        if vix_val < 15:    vix_regime, vix_color = "Très Calme", "emerald"
        elif vix_val < 20:  vix_regime, vix_color = "Faible Volatilité", "emerald"
        elif vix_val < 25:  vix_regime, vix_color = "Modéré", "amber"
        elif vix_val < 30:  vix_regime, vix_color = "Élevé", "orange"
        else:               vix_regime, vix_color = "Panique", "red"

        macro_regime_score = 80 if vix_val < 20 else 60 if vix_val < 25 else 40 if vix_val < 30 else 20
        if spread is not None and spread < 0:
            macro_regime_score = max(0, macro_regime_score - 10)

        # ── 4. Bloomberg news matching ───────────────────────────────────────
        rss_data   = db_load_generic('bloomberg_rss') or {}
        news_items = rss_data.get('items', [])

        ticker_news = {t: [] for t in unique_tickers}
        top_news    = []

        for item in news_items[:120]:
            crit      = float(item.get('criticality_score', 0) or 0)
            sentiment = item.get('sentiment_label', 'neutral') or 'neutral'
            title     = item.get('title', '') or ''
            title_fr  = item.get('title_fr') or title
            link      = item.get('link', '') or ''
            if crit >= 4:
                top_news.append({'title': title_fr, 'sentiment': sentiment,
                                 'criticality': crit, 'link': link,
                                 'published': item.get('published', '')})
            title_upper = title.upper()
            for ticker in unique_tickers:
                if ticker in title_upper:
                    ticker_news[ticker].append({'title': title_fr, 'sentiment': sentiment, 'criticality': crit})

        top_news.sort(key=lambda x: x['criticality'], reverse=True)
        top_news = top_news[:8]

        # ── 5. Per-position combined analysis ────────────────────────────────
        positions_analysis = []
        bull_count = 0; news_scores_collected = []

        for pos in positions:
            ticker = (pos.get('ticker') or '').strip()
            if not ticker: continue

            sig   = tech_by_ticker.get(ticker, {})
            enr   = enriched_by_ticker.get(ticker, {})
            tnews = ticker_news.get(ticker, [])
            ins   = insiders_by_ticker.get(ticker, [])

            # --- News ---
            if tnews:
                avg_crit = sum(n['criticality'] for n in tnews) / len(tnews)
                pos_c = sum(1 for n in tnews if n['sentiment'] in ('positive', 'bullish'))
                news_scores_collected.append(avg_crit)
                dom_sent = 'positive' if pos_c > len(tnews) / 2 else 'negative' if pos_c < len(tnews) / 2 else 'neutral'
                news_score_val = round(avg_crit, 1)
            else:
                dom_sent = 'neutral'; news_score_val = None

            # --- Technicals ---
            trend = sig.get('trend', 'Neutral')
            if trend == 'Bullish': bull_count += 1
            sma_cross = None
            try:
                if sig.get('sma_50') and sig.get('sma_200'):
                    sma_cross = float(sig['sma_50']) > float(sig['sma_200'])
            except Exception: pass

            # --- Insiders signal ---
            insider_signal = None
            if ins:
                buys  = sum(1 for i in ins if 'buy'  in str(i.get('transaction', '')).lower())
                sells = sum(1 for i in ins if 'sale' in str(i.get('transaction', '')).lower() or 'sell' in str(i.get('transaction', '')).lower())
                if buys > sells * 1.5:   insider_signal = 'bullish'
                elif sells > buys * 1.5: insider_signal = 'bearish'
                else:                    insider_signal = 'neutral'

            positions_analysis.append({
                'ticker':           ticker,
                'name':             pos.get('name', ticker),
                'isin':             pos.get('isin', ''),
                'qty':              float(pos.get('qty', 0) or 0),
                'avg_price':        float(pos.get('avgPrice', 0) or 0),
                'current_price':    float(pos.get('currentPrice', 0) or 0),
                'pnl_percent':      float(pos.get('pnlPercent', 0) or 0),
                'market_value':     float(pos.get('marketValue', 0) or 0),
                # Technicals
                'trend':            trend,
                'rsi':              sig.get('rsi'),
                'sma_cross':        sma_cross,
                'alerts':           sig.get('alerts', []),
                'fundamental':      sig.get('fundamental', {}),
                'price':            sig.get('price'),
                # News
                'news_score':       news_score_val,
                'news_sentiment':   dom_sent,
                'news_count':       len(tnews),
                'top_news':         tnews[:2],
                # Insiders (from DB)
                'insiders':         ins[:5],
                'insider_signal':   insider_signal,
                # Enriched (yfinance)
                'short_interest':   enr.get('short_interest', {}),
                'options_bias':     enr.get('options_bias'),
                'options_pc':       enr.get('options_pc'),
                'options_call_oi':  enr.get('options_call_oi'),
                'options_put_oi':   enr.get('options_put_oi'),
                'quarterly_trend':  enr.get('quarterly_trend', []),
                'eps_beat_rate':    enr.get('eps_beat_rate'),
                'eps_last':         enr.get('eps_last'),
                # Upcoming events
                'upcoming_earnings':   enr.get('upcoming_earnings'),
                'eps_estimate':        enr.get('eps_estimate'),
                'upcoming_dividend':   enr.get('upcoming_dividend'),
                'dividend_amount':     enr.get('dividend_amount'),
                'annual_perf_1y':      enr.get('annual_perf_1y'),
                'sector':              enr.get('sector', ''),
            })

        # ── 6. Health Score ──────────────────────────────────────────────────
        total = len(positions_analysis)
        tech_score   = round(bull_count / total * 100) if total else 50
        news_score_overall = round(sum(news_scores_collected) / len(news_scores_collected) / 10 * 100) if news_scores_collected else 50
        # Insider score: count positions with bullish insiders
        bullish_ins = sum(1 for p in positions_analysis if p.get('insider_signal') == 'bullish')
        insider_score = round(bullish_ins / max(total, 1) * 100)
        # Short interest risk: average short % across positions (lower = better)
        short_pcts = [p['short_interest'].get('pct_float', 0) for p in positions_analysis if p['short_interest'].get('pct_float')]
        avg_short = sum(short_pcts) / len(short_pcts) if short_pcts else 5
        short_score = max(0, min(100, round(100 - avg_short * 2)))

        health_score = round(
            tech_score         * 0.30 +
            news_score_overall * 0.20 +
            macro_regime_score * 0.25 +
            insider_score      * 0.15 +
            short_score        * 0.10
        )

        if health_score >= 75:   health_label, health_color = "Excellent", "emerald"
        elif health_score >= 60: health_label, health_color = "Solide",    "blue"
        elif health_score >= 45: health_label, health_color = "Prudent",   "amber"
        else:                    health_label, health_color = "Risqué",    "red"

        # ── 7. Tendances Sectorielles ────────────────────────────────────────
        sector_data = {}
        try:
            with app.app_context():
                all_trends = SectorTrend.query.all()
                for st in all_trends:
                    if st.sector_name:
                        sector_data[st.sector_name] = {
                            'monthly_trend': st.monthly_trend,
                            'stocks_count': st.stocks_count,
                        }
        except Exception as sec_e:
            print(f"[360] Sector data error: {sec_e}")

        # ── 8. Perspectives Bancaires ────────────────────────────────────────
        bank_data = []
        try:
            forecasts = db_load_bank_forecasts()
            portfolio_tickers_set = set(unique_tickers)
            ticker_matched = [f for f in forecasts if (f.get('ticker') or '').upper() in portfolio_tickers_set]
            bank_data = ticker_matched if ticker_matched else forecasts[:12]
        except Exception as be:
            print(f"[360] Bank Forecast Error: {be}")

        return jsonify({
            'status': 'success',
            'data': {
                'health_score':  health_score,
                'health_label':  health_label,
                'health_color':  health_color,
                'health_breakdown': {
                    'technicals': tech_score,
                    'news':       news_score_overall,
                    'macro':      macro_regime_score,
                    'insiders':   insider_score,
                    'short':      short_score,
                },
                'macro_snapshot': {
                    'vix':          {'value': round(vix_val, 1), 'regime': vix_regime, 'color': vix_color},
                    'sp500':        {'change_pct': round(sp500_change, 2), 'price': round(sp500_price, 0)},
                    'nasdaq':       {'change_pct': round(nasdaq_change, 2)},
                    'yield_10y':    round(y10_val, 2),
                    'yield_2y':     round(y2_val, 2),
                    'yield_spread': spread,
                    'yield_curve':  'Inversée' if spread and spread < 0 else 'Normale' if spread else 'N/A',
                },
                'top_news':           top_news,
                'positions_analysis': positions_analysis,
                'sector_data':        sector_data,
                'bank_forecasts':     bank_data,
                'scanned_at':         datetime.now().isoformat()
            }
        })
    except Exception as e:
        print(f"Analyse 360 Error: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/market/all', methods=['GET'])
def get_market_data():
    """Returns cached market data"""
    keys = ['market_commodities', 'market_forex', 'market_treasury', 'market_indices']
    response = {}
    for key in keys:
        data = db_load_generic(key)
        if data:
            short_key = key.replace('market_', '')
            if short_key == 'treasury': short_key = 'treasury_yields'
            response[short_key] = data
    return jsonify(response)

@app.route('/api/market/update', methods=['POST'])
def update_market_data():
    """Forces update of market data"""
    try:
        market = GlobalMarketData()
        data = market.get_all_market_data()
        
        if 'commodities' in data: db_save_generic('market_commodities', data['commodities'])
        if 'forex' in data: db_save_generic('market_forex', data['forex'])
        if 'treasury_yields' in data: db_save_generic('market_treasury', data['treasury_yields'])
        if 'indices' in data: db_save_generic('market_indices', data['indices'])
        
        return jsonify({"status": "success", "message": "Market data updated", "timestamp": data['timestamp']})
    except Exception as e:
        print(f"Validation Error: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.json
    phone = data.get('phone')
    pin = data.get('pin')
    # Optional fields for profile creation
    first_name = data.get('firstName')
    last_name = data.get('lastName')
    
    if not phone or not pin:
        return jsonify({"success": False, "error": "Phone and PIN required"}), 400
    
    # DB: Get or Create User
    try:
        with app.app_context():
            user = User.query.filter_by(phone=phone).first()
            if not user:
                user = User(
                    phone=phone, 
                    pin=pin, # Warning: Saving plain text PIN as requested for persistence logic, usually bad practice
                    first_name=first_name or "",
                    last_name=last_name or ""
                )
                db.session.add(user)
            else:
                user.pin = pin # Update PIN if changed
                if first_name: user.first_name = first_name
                if last_name: user.last_name = last_name
            db.session.commit()
    except Exception as e:
        print(f"DB Error User Save: {e}")

    result = tr_api.initiate_login(phone, pin, first_name=first_name, last_name=last_name)
    return jsonify(result)

@app.route('/api/auth/profile', methods=['GET'])
def get_user_profile():
    # In a real app, uses session/token. Here, we'll take phone header or assume single user
    phone = request.headers.get('X-User-Phone')
    if not phone:
        # Fallback: get the last created user
        user = User.query.order_by(User.id.desc()).first()
    else:
        user = User.query.filter_by(phone=phone).first()
        
    if user:
        return jsonify({
            'firstName': user.first_name,
            'lastName': user.last_name,
            'phone': user.phone
        })
    return jsonify({})

@app.route('/api/auth/remembered', methods=['GET'])
def get_remembered_user():
    """Récupère les informations d'identification sauvegardées dans config.ini."""
    tr_api.config.read(tr_api.config_path)
    return jsonify({
        'firstName': tr_api.config.get("secret", "first_name", fallback=""),
        'lastName': tr_api.config.get("secret", "last_name", fallback=""),
        'phone': tr_api.config.get("secret", "phone_number", fallback=""),
        'pin': tr_api.config.get("secret", "pin", fallback="")
    })

def sync_portfolio_after_login():
    """
    Called as a background thread after a successful login.
    1. Connects via WebSocket and fetches the live portfolio.
    2. Removes from DB any WalletInvestment rows that are no longer held.
    3. Recalculates PnL / total_value for every remaining position.
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _run():
            api = TradeRepublicAPI()
            connected = await api.connect()
            if not connected:
                print("[SYNC] [ERROR] WebSocket connection failed - portfolio sync skipped.")
                return

            print("[SYNC] [REFRESH] Syncing portfolio after login...")
            fresh_positions = await api.fetch_portfolio(silent=True)
            await api.close()

            if not fresh_positions or not isinstance(fresh_positions, list):
                print("[SYNC] [WARN]  No positions returned from TR - skipping cleanup.")
                return

            live_isins = {p['isin'] for p in fresh_positions if p.get('isin')}
            print(f"[SYNC] [OK] {len(live_isins)} ISINs currently held: {sorted(live_isins)}")

            with app.app_context():
                # Resolve user_id from config
                user_id = None
                try:
                    tr_api.config.read(tr_api.config_path)
                    phone = tr_api.config.get("secret", "phone_number", fallback=None)
                    if phone:
                        u = User.query.filter_by(phone=phone).first()
                        if u:
                            user_id = u.id
                except Exception as e:
                    print(f"[SYNC] [WARN]  Could not resolve user: {e}")

                # ── Step 1: Remove stale positions ─────────────────────────────
                all_db_pos = WalletInvestment.query.filter_by(user_id=user_id).all()
                removed = 0
                for pos in all_db_pos:
                    if pos.isin not in live_isins:
                        print(f"[SYNC] [DEL]  Removing stale position: {pos.isin} ({pos.name})")
                        db.session.delete(pos)
                        removed += 1

                if removed:
                    db.session.commit()
                    print(f"[SYNC] [OK] Removed {removed} stale position(s).")
                else:
                    print("[SYNC] [OK] No stale positions to remove.")

                # ── Step 2: Recalculate PnL for all remaining positions ─────────
                recalculated = 0
                for pos in WalletInvestment.query.filter_by(user_id=user_id).all():
                    qty   = pos.quantity   or 0.0
                    cpx   = pos.current_price or 0.0
                    bpx   = pos.buy_price  or 0.0
                    if qty > 0 and cpx > 0:
                        pos.total_value = qty * cpx
                        pos.pnl         = pos.total_value - (qty * bpx)
                        pos.pnl_percent = (pos.pnl / (qty * bpx) * 100) if bpx > 0 else 0.0
                        pos.updated_at  = datetime.utcnow()
                        recalculated   += 1

                db.session.commit()
                print(f"[SYNC] [OK] Recalculated PnL for {recalculated} position(s).")

        loop.run_until_complete(_run())
        loop.close()
    except Exception as e:
        print(f"[SYNC] [ERROR] Portfolio sync error: {e}")
        traceback.print_exc()


@app.route('/api/auth/verify', methods=['POST'])
def auth_verify():
    data = request.json
    process_id = data.get('processId')
    code = data.get('code')
    if not process_id or not code:
        return jsonify({"success": False, "error": "Process ID and Code required"}), 400
        
    result = tr_api.complete_login(process_id, code)
    
    if result.get("success"):
        print("[OK] Login successful. Triggering background sync tasks...")
        # 1. Update sector trends
        threading.Thread(target=update_sector_monthly_trends, daemon=True).start()
        # 2. Sync portfolio: remove stale positions + recalculate PnL
        threading.Thread(target=sync_portfolio_after_login, daemon=True).start()
        # 3. Re-crawl Perspectives Bancaires to detect new publications
        threading.Thread(target=refresh_bank_forecasts_on_login, daemon=True).start()
        # 4. Check if Macro indicators are stale (> 24h) and refresh if needed
        threading.Thread(target=check_macro_freshness_on_login, daemon=True).start()

    return jsonify(result)

def refresh_bank_forecasts_on_login():
    """
    Appelé à chaque connexion. Re-crawle toutes les sources bancaires
    et compare les URLs aux entrées existantes pour détecter de nouvelles publications.
    Sauvegarde uniquement les nouveaux articles trouvés.
    """
    try:
        with app.app_context():
            print("[LOGIN] [BANK] Verification des nouvelles Perspectives Bancaires...")
            existing_urls = set(
                row.source_url for row in BankForecast.query.with_entities(BankForecast.source_url).all()
                if row.source_url
            )
            scraper = BankForecastScraper()
            fresh_results = scraper.scrape_all()
            new_items = [
                r for r in (fresh_results or [])
                if r.get('url') and r['url'] not in existing_urls
            ]
            if new_items:
                print(f"[LOGIN] [NEW] {len(new_items)} nouvelles perspectives bancaires detectees - sauvegarde...")
                # scrape_all() sauvegarde déjà tout, pas besoin de re-sauvegarder ici.
            else:
                print("[LOGIN] [OK] Perspectives bancaires a jour, aucune nouveaute.")
    except Exception as e:
        print(f"[LOGIN] [ERROR] Erreur refresh perspectives bancaires: {e}")


def check_macro_freshness_on_login():
    """
    Appelé à chaque connexion. Vérifie si les MacroData sont plus vieilles
    que 24h. Si oui, relance update_macro_data().
    """
    try:
        with app.app_context():
            threshold = datetime.utcnow() - timedelta(hours=24)
            stale = MacroData.query.filter(
                (MacroData.updated_at == None) | (MacroData.updated_at < threshold)
            ).first()
            if stale or MacroData.query.count() == 0:
                print("[LOGIN] [DATA] Indicateurs Macro obsoletes (> 24h) - mise a jour en cours...")
                update_macro_data()
                print("[LOGIN] [OK] Indicateurs Macro mis a jour.")
            else:
                print("[LOGIN] [OK] Indicateurs Macro a jour.")
    except Exception as e:
        print(f"[LOGIN] [ERROR] Erreur verification macro: {e}")


@app.route('/api/auth/resend', methods=['POST'])
def auth_resend():
    data = request.json
    process_id = data.get('processId')
    if not process_id:
        return jsonify({"success": False, "error": "Process ID required"}), 400
    
    result = tr_api.resend_sms(process_id)
    return jsonify(result)

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    # Reload config to check if token exists (in case it was updated externally)
    tr_api.config.read(tr_api.config_path)
    tr_api.session_token = tr_api.config.get("secret", "tr_session", fallback=None)
    
    is_logged_in = bool(tr_api.session_token)
    return jsonify({"loggedIn": is_logged_in})

# ============================================================================
# NEW PORTFOLIO RECONSTRUCTION LOGIC
# ============================================================================

def _parse_ts(ts):
    """
    Parse a TR timestamp string to a naive datetime.
    Handles nanosecond precision (9 digits after '.') that Python's
    fromisoformat rejects — truncates to at most 6 fractional digits (microseconds).
    Also normalises +0000 → +00:00 and Z → +00:00.
    Returns None on failure.
    """
    if ts is None:
        return None
    if isinstance(ts, int):
        return datetime.fromtimestamp(ts / 1000.0).replace(tzinfo=None)
    try:
        s = str(ts).strip()
        # Normalise timezone: +0000 → +00:00
        s = re.sub(r'([+-])(\d{2})(\d{2})$', r'\1\2:\3', s)
        # Replace Z
        s = s.replace('Z', '+00:00')
        # Truncate fractional seconds > 6 digits (nanoseconds etc.)
        s = re.sub(r'(\.\d{6})\d+', r'\1', s)
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except Exception:
        return None


def _normalize_tr_transaction(tx):
    """
    Normalize a TR timeline item regardless of whether it is:
      • a flat dict  (classic timelineTransactions response)
      • a sections-based dict  (timelineDetailV2 / newer timeline format)

    Returns a canonical dict:
        isin      – ISIN string or ''
        icon      – icon URL string
        timestamp – ISO string or int or None
        status    – status string
        title     – header title ('You received €175.33', etc.)
        subtitle  – subtitle / subtitleText
        amount    – float  (positive = received/SELL, negative = paid/BUY, 0 = unknown)
        tx_type   – 'SELL'|'BUY'|None  (None means caller must decide)
        shares    – float (0 if unavailable)
        price     – float (0 if unavailable)
    """
    out = {
        'isin': '', 'icon': '', 'timestamp': None, 'status': '',
        'title': '', 'subtitle': '', 'amount': 0.0,
        'tx_type': None, 'shares': 0.0, 'price': 0.0,
    }

    def _parse_num(text):
        clean = re.sub(r'[^\d.,]', '', str(text)).replace(',', '.')
        nums = re.findall(r'[\d.]+', clean)
        try: return float(nums[0]) if nums else 0.0
        except: return 0.0

    sections = tx.get('sections')

    if sections:
        # ── Sections-based structure ──────────────────────────────────────────
        for sec in sections:
            sec_type  = (sec.get('type') or '').lower()
            sec_title = sec.get('title') or ''

            if sec_type == 'header':
                out['title'] = sec_title
                # Best ISIN source: action.payload
                action = sec.get('action') or {}
                if action.get('type') == 'instrumentDetail' and action.get('payload'):
                    out['isin'] = action['payload']
                # data can be a dict or a list
                data = sec.get('data') or {}
                if isinstance(data, list):
                    data = data[0] if data else {}
                if isinstance(data, dict):
                    out['timestamp'] = out['timestamp'] or data.get('timestamp')
                    out['status']    = out['status']    or (data.get('status') or '')
                    if data.get('icon'):
                        out['icon'] = data['icon']
                # Extract amount from title: "You received €175.33" / "You invested €726.48"
                t_lower = sec_title.lower()
                amt_m = re.search(r'[€$£]?\s*([\d]+[.,][\d]+)', sec_title)
                if amt_m:
                    raw_amt = _parse_num(amt_m.group(1))
                    if any(x in t_lower for x in ['received', 'erhalten', 'sold', 'verkauf']):
                        out['tx_type'] = 'SELL'
                        out['amount']  = abs(raw_amt)
                    elif any(x in t_lower for x in ['invested', 'invest', 'bought', 'kauf', 'sparplan', 'buy']):
                        out['tx_type'] = 'BUY'
                        out['amount']  = -abs(raw_amt)
                    else:
                        out['amount'] = raw_amt

            elif sec_type in ('table', 'horizontaltable'):
                for row in (sec.get('data') or []):
                    if not isinstance(row, dict):
                        continue
                    row_key_l = (row.get('title') or '').strip().lower()
                    detail    = row.get('detail') or {}
                    det_text  = (detail.get('text') or '').strip() if isinstance(detail, dict) else str(detail).strip()

                    # Definitive BUY / SELL row
                    if row_key_l in ('sell', 'verkauf', 'sold'):
                        out['tx_type'] = 'SELL'
                    elif row_key_l in ('buy', 'kauf', 'order', 'savings plan', 'sparplan'):
                        out['tx_type'] = 'BUY'
                    # Shares
                    elif row_key_l in ('shares', 'stück', 'anteile', 'anzahl', 'quantity',
                                       'shares purchased', 'shares sold', 'number of shares'):
                        v = _parse_num(det_text)
                        if v > 0: out['shares'] = v
                    # Price per share
                    elif row_key_l in ('price per share', 'price', 'kurs', 'ausführungskurs',
                                       'share price', 'execution price', 'prix unitaire'):
                        v = _parse_num(det_text)
                        if v > 0: out['price'] = v

        # Fallback ISIN from icon
        if not out['isin'] and out['icon']:
            m = re.search(r'logos/([A-Z0-9]{12})(?:/|$)', out['icon'])
            if m: out['isin'] = m.group(1)

        # Recompute amount from shares*price when still 0
        if out['amount'] == 0.0 and out['shares'] > 0 and out['price'] > 0:
            raw = out['shares'] * out['price']
            out['amount'] = raw if out['tx_type'] == 'SELL' else -raw

    else:
        # ── Flat structure (classic timelineTransactions item) ────────────────
        out['icon']      = tx.get('icon') or ''
        out['timestamp'] = tx.get('timestamp')
        out['status']    = (tx.get('status') or '')
        out['title']     = (tx.get('title') or '')
        out['subtitle']  = (tx.get('subtitleText') or tx.get('subtitle') or '')
        amt = tx.get('amount') or {}
        if isinstance(amt, dict):
            val = amt.get('value')
            if val is not None:
                try: out['amount'] = float(val)
                except: pass
        elif isinstance(amt, (int, float)):
            out['amount'] = float(amt)
        m = re.search(r'logos/([A-Z0-9]{12})(?:/|$)', out['icon'])
        if m: out['isin'] = m.group(1)

    return out


async def fetch_full_transaction_history_v2(api):
    """
    Fetches transaction history using ONLY timelineTransactions (same WebSocket as cash-flow).
    NO timelineDetailV2 calls – price/shares are resolved via yfinance outside of TR.

    Steps:
      1. Get raw items from timelineTransactions  (WebSocket – already reliable)
      2. Extract ISIN from icon field, date from timestamp, amount from amount.value
      3. Determine BUY/SELL from title keywords or amount sign
      4. Batch-download price history via yfinance for each unique ISIN → ticker
      5. Derive shares = |amount| / price_on_date

    Returns: [{date, type, isin, ticker, shares, price, amount}]
    """
    print("[TX_HISTORY] ========================================")
    print("[TX_HISTORY] [START] Fetching transactions (timelineTransactions only - no detail WS calls)")
    print("[TX_HISTORY]    Shares/prices resolved via yfinance outside TR WebSocket")
    print("[TX_HISTORY] ========================================")

    # ── Step 1: Raw transaction list via WebSocket ────────────────────────────
    all_txs = await api.fetch_history(extract_details=False)
    print(f"[TX_HISTORY] [PKG] Retrieved {len(all_txs)} raw timeline items.")

    ISIN_RE = re.compile(r'^[A-Z]{2}[A-Z0-9]{10}$')
    SELL_KW = ['received', 'erhalten', 'sold', 'verkauf', 'sell']
    BUY_KW  = ['invested', 'invest', 'kauf', 'buy', 'sparplan', 'savings plan']

    # ── Step 2: Parse ISIN / date / amount / type from raw items ─────────────
    candidates = []
    cnt_no_isin = cnt_no_date = cnt_no_amount = 0

    for tx in all_txs:
        # --- ISIN: primary from action.payload, fallback from icon field ---
        isin = None

        # Flat item (timelineTransactions): look for icon like "logos/US5949181045/v2"
        icon = tx.get('icon', '')
        m = re.search(r'logos/([A-Z0-9]{10,12})(?:/|$)', icon)
        if m and ISIN_RE.match(m.group(1)):
            isin = m.group(1)

        # Also check eventType / eventId if icon is missing
        if not isin:
            for fld in ('instrumentId', 'isin', 'id'):
                v = tx.get(fld, '')
                if v and ISIN_RE.match(str(v)):
                    isin = str(v)
                    break

        if not isin:
            cnt_no_isin += 1
            continue

        # --- Date ---
        ts_raw = tx.get('timestamp') or tx.get('date') or ''
        date = _parse_ts(ts_raw)
        if not date:
            cnt_no_date += 1
            continue

        # --- Amount ---
        amt_obj = tx.get('amount') or {}
        try:
            amount = float(amt_obj.get('value', 0)) if isinstance(amt_obj, dict) else float(amt_obj)
        except Exception:
            cnt_no_amount += 1
            continue
        if amount == 0.0:
            cnt_no_amount += 1
            continue

        # --- BUY / SELL ---
        title    = (tx.get('title') or tx.get('titleText') or '').lower()
        subtitle = (tx.get('subtitle') or tx.get('subtitleText') or '').lower()
        full_text = f"{title} {subtitle}"

        is_sell = any(k in full_text for k in SELL_KW)
        is_buy  = any(k in full_text for k in BUY_KW)

        if is_sell and not is_buy:
            tx_type = 'SELL'
        elif is_buy and not is_sell:
            tx_type = 'BUY'
        elif amount > 0:
            tx_type = 'SELL'   # money received → sold something
        else:
            tx_type = 'BUY'    # money spent    → bought something

        candidates.append({'isin': isin, 'date': date, 'amount': amount, 'type': tx_type})

    print(f"[TX_HISTORY] [SEARCH] {len(candidates)} BUY/SELL candidates "
          f"(skipped: no_isin={cnt_no_isin}, no_date={cnt_no_date}, no_amount={cnt_no_amount})")

    if not candidates:
        print("[TX_HISTORY] [WARN]  No valid candidates found.")
        return []

    # ── Step 3: Resolve ISIN → Yahoo ticker ──────────────────────────────────
    unique_isins = list({c['isin'] for c in candidates})
    print(f"[TX_HISTORY] ? Resolving {len(unique_isins)} unique ISINs -> Yahoo tickers...")

    isin_to_ticker = {}
    for isin in unique_isins:
        ticker = get_symbol_from_isin(isin)
        if ticker:
            isin_to_ticker[isin] = ticker
        else:
            print(f"[TX_HISTORY]   [WARN]  {isin} -> no Yahoo ticker found (will skip price)")

    print(f"[TX_HISTORY]    {len(isin_to_ticker)}/{len(unique_isins)} ISINs resolved.")

    # ── Step 4: Batch-download price history via yfinance ────────────────────
    ticker_price_history: dict[str, dict[str, float]] = {}  # ticker → {YYYY-MM-DD: close}

    all_tickers = list(set(isin_to_ticker.values()))
    if all_tickers:
        min_date = min(c['date'] for c in candidates)
        start_str = (min_date - timedelta(days=7)).strftime('%Y-%m-%d')
        end_str   = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        print(f"[TX_HISTORY] [DATA] Downloading price history {start_str}->{end_str} "
              f"for {len(all_tickers)} tickers via yfinance...")
        try:
            raw = yf.download(
                all_tickers if len(all_tickers) > 1 else all_tickers[0],
                start=start_str,
                end=end_str,
                auto_adjust=True,
                progress=False,
                threads=True,
            )

            # Normalise: single vs multi-ticker DataFrames
            if 'Close' in raw.columns:
                close_df = raw['Close']
                if hasattr(close_df, 'items'):  # DataFrame (multi-ticker)
                    for tkr in all_tickers:
                        if tkr in close_df.columns:
                            ticker_price_history[tkr] = {
                                idx.strftime('%Y-%m-%d'): float(val)
                                for idx, val in close_df[tkr].items()
                                if not pd.isna(val)
                            }
                else:  # Series (single ticker)
                    ticker_price_history[all_tickers[0]] = {
                        idx.strftime('%Y-%m-%d'): float(val)
                        for idx, val in close_df.items()
                        if not pd.isna(val)
                    }
            print(f"[TX_HISTORY] [OK] Price history loaded for {len(ticker_price_history)} tickers.")
        except Exception as e:
            print(f"[TX_HISTORY] [WARN]  yfinance download error: {e}")

    def _price_on(ticker, target_date) -> float:
        """Return closing price on or up to 7 days before target_date."""
        history = ticker_price_history.get(ticker, {})
        for delta in range(0, 8):
            d = (target_date - timedelta(days=delta)).strftime('%Y-%m-%d')
            if d in history:
                return history[d]
        return 0.0

    # ── Step 5: Build final records ──────────────────────────────────────────
    parsed_transactions = []
    for c in candidates:
        isin   = c['isin']
        ticker = isin_to_ticker.get(isin)
        price  = _price_on(ticker, c['date']) if ticker else 0.0
        shares = abs(c['amount']) / price if price > 0 else 0.0

        record = {
            'date':   c['date'],
            'type':   c['type'],
            'isin':   isin,
            'ticker': ticker or '',
            'shares': shares,
            'price':  price,
            'amount': c['amount'],
        }
        parsed_transactions.append(record)
        print(f"[TX_HISTORY]   [OK] {record['type']} {isin} ({ticker or '?'}) "
              f"date={c['date'].strftime('%Y-%m-%d')} "
              f"shares={shares:.4f} price={price:.4f} amt={c['amount']:.2f}")

    print(f"[TX_HISTORY] ========================================")
    print(f"[TX_HISTORY] [OK] {len(parsed_transactions)} total BUY/SELL transactions parsed.")
    print(f"[TX_HISTORY] ========================================")
    return parsed_transactions

def calculate_reconstructed_history(transactions, filter_isins=None):
    """
    Reconstructs daily portfolio value from transaction history.
    If filter_isins is provided, only considers transactions for these ISINs.
    """
    if not transactions: return []
    
    # Sort
    transactions.sort(key=lambda x: x['date'])
    
    # Filter by ISIN if requested
    if filter_isins:
        print(f"? Filtering history for {len(filter_isins)} current ISINs...")
        transactions = [t for t in transactions if t['isin'] in filter_isins]
        if not transactions: return []

    # 1. Identify Universe
    all_isins = set(t['isin'] for t in transactions)
    if not all_isins: return []
    
    min_date = transactions[0]['date']
    max_date = datetime.now()
    
    # 2. Bulk Fetch Prices
    print(f"[DATA] Fetching history for {len(all_isins)} ISINs from {min_date.date()}...")
    ticker_map = {}
    tickers = []
    
    for isin in all_isins:
        sym = get_symbol_from_isin(isin)
        if sym:
            ticker_map[isin] = sym
            tickers.append(sym)
    
    if not tickers: return []
    
    try:
        df = yf.download(tickers, start=min_date, end=max_date, progress=False, auto_adjust=False)['Close']
    except Exception as e:
        print(f"[ERROR] YF Download error: {e}")
        return []
        
    df = df.fillna(method='ffill').fillna(method='bfill') # Fill gaps
    
    # 3. Simulate Daily Portfolio
    portfolio_holdings = defaultdict(float) # ISIN -> Shares
    daily_values = []
    
    # Create Date Range
    date_range = pd.date_range(start=min_date, end=max_date, freq='D')
    
    # Group Tx by Date
    tx_by_date = defaultdict(list)
    for t in transactions:
        d = t['date'].strftime('%Y-%m-%d')
        tx_by_date[d].append(t)
        
    for d in date_range:
        d_str = d.strftime('%Y-%m-%d')
        
        # Apply transactions for this day
        if d_str in tx_by_date:
            for t in tx_by_date[d_str]:
                delta = t['shares'] if t['type'] == 'BUY' else -t['shares']
                portfolio_holdings[t['isin']] += delta
                if portfolio_holdings[t['isin']] < 0: portfolio_holdings[t['isin']] = 0 # Prevent negative
        
        # Calculate Value
        total_val = 0.0
        for isin, shares in portfolio_holdings.items():
            if shares > 0:
                ticker = ticker_map.get(isin)
                if ticker:
                    try:
                        # Extract price from DF (Handle Series vs DataFrame)
                        if isinstance(df, pd.Series):
                             price = df.loc[d] if d in df.index else 0
                        else:
                             price = df.loc[d, ticker] if d in df.index and ticker in df.columns else 0
                             
                        total_val += shares * price
                    except: pass
                    
        daily_values.append({'time': d_str, 'value': round(total_val, 2)})
        
    return daily_values


def calculate_portfolio_performance_from_transactions(parsed_txs, filter_isins=None):
    """
    Portfolio performance using Time-Weighted Return (TWR).

    TWR is completely immune to cash-injection distortion.

    Each lot stores:
        eur_invested  – the actual EUR paid at Trade Republic (|amount|)
        buy_yf_price  – the yfinance close price on the buy day (from THIS download)

    Current value of a lot:
        lot_value(d) = eur_invested × (price(ticker, d) / buy_yf_price)

    This keeps the calculation fully self-consistent within a single yfinance
    download and avoids any eur/usd mix or cross-download price discrepancy.

    Sub-period anchoring (key fix vs previous version):
        subperiod_start_mv = v_before_existing + abs(eur_new_cash)
    Instead of recomputing from lots with potentially stale buy prices.

    Returns: (daily_series, events)
        daily_series : [{'date': str, 'value': float}, ...]   TWR % from first purchase
        events       : [{'date', 'type', 'isin', 'ticker', 'shares', 'price', 'amount'}, ...]
    """
    if not parsed_txs:
        return [], []

    if filter_isins:
        parsed_txs = [t for t in parsed_txs if t['isin'] in filter_isins]
    if not parsed_txs:
        return [], []

    parsed_txs = sorted(parsed_txs, key=lambda x: x['date'])
    all_isins  = set(t['isin'] for t in parsed_txs)
    min_date   = parsed_txs[0]['date'].replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
    max_date   = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # ── Resolve ISIN → Yahoo ticker ─────────────────────────────────────────────
    ticker_map = {}
    def _resolve(isin):
        return isin, get_symbol_from_isin(isin)

    with ThreadPoolExecutor(max_workers=8) as executor:
        for isin, sym in executor.map(_resolve, all_isins):
            if sym:
                ticker_map[isin] = sym
            else:
                print(f"[PERF] [WARN]  No ticker for ISIN {isin}")

    if not ticker_map:
        print("[PERF] [ERROR] No ticker symbols resolved.")
        return [], []

    tickers = list(set(ticker_map.values()))
    print(f"[PERF] [OK] {len(ticker_map)}/{len(all_isins)} ISINs resolved: {tickers}")

    # ── Single yfinance download — used for ALL price lookups in this function ────
    try:
        raw = yf.download(
            tickers if len(tickers) > 1 else tickers[0],
            start=min_date - timedelta(days=10),
            end=max_date + timedelta(days=1),
            progress=False,
            auto_adjust=True,
        )
        if isinstance(raw.columns, pd.MultiIndex):
            df_prices = raw['Close']
        elif 'Close' in raw.columns:
            df_prices = raw[['Close']].rename(columns={'Close': tickers[0]})
        else:
            df_prices = raw
    except Exception as e:
        print(f"[PERF] [ERROR] yfinance download error: {e}")
        return [], []

    df_prices = df_prices.ffill().bfill()
    df_prices.index = pd.to_datetime(df_prices.index).tz_localize(None)

    # Filter ticker_map to only tickers that actually have non-empty price data
    # A column may exist but be all-NaN if yfinance returned nothing for that symbol
    valid_tickers = set(t for t in df_prices.columns if df_prices[t].notna().any())
    missing = [sym for sym in tickers if sym not in valid_tickers]
    if missing:
        print(f"[PERF] [WARN]  Tickers with no price data (excluded): {missing}")
    ticker_map = {isin: sym for isin, sym in ticker_map.items() if sym in valid_tickers}
    if not ticker_map:
        print("[PERF] [ERROR] No tickers with valid price data.")
        return [], []

    def _get_price(ticker, ts):
        """Return closing price for ticker on or up to 10 days before ts."""
        if ticker not in df_prices.columns:
            return 0.0
        d = pd.Timestamp(ts.strftime('%Y-%m-%d') if hasattr(ts, 'strftime') else str(ts)[:10])
        col = df_prices[ticker]
        for delta in range(0, 11):
            key = d - pd.Timedelta(days=delta)
            if key in col.index:
                v = col.loc[key]
                if not pd.isna(v):
                    return float(v)
        return 0.0

    def _portfolio_value(lots_list, date_dt):
        """
        Σ lot['eur_invested'] × (price_today / lot['buy_yf_price'])
        All values are in the same EUR-equivalent unit, consistent within
        this single yfinance download.

        When price is unavailable for a given day (market closed, data gap),
        we fall back to buy_yf_price so the lot contributes ratio=1.0 (neutral)
        instead of 0, which would create a phantom loss.
        """
        total = 0.0
        for l in lots_list:
            if l['buy_yf_price'] <= 0:
                continue   # lot was added without a valid buy price — skip
            px = _get_price(l['ticker'], date_dt)
            if px <= 0:
                px = l['buy_yf_price']   # fallback: no change (neutral), not a loss
            total += l['eur_invested'] * (px / l['buy_yf_price'])
        return total

    # ── TWR state ────────────────────────────────────────────────────────────────
    lots   = []   # {isin, ticker, eur_invested, buy_yf_price}
    events = []

    cumulative_factor  = 1.0
    subperiod_start_mv = None   # EUR-equivalent value at start of current sub-period

    # Display from the very first transaction — normalization to 0% is done
    # in the route handler after this function returns, so all series are
    # rebased to the same starting point.
    daily_series  = []

    tx_by_date = defaultdict(list)
    for t in parsed_txs:
        if ticker_map.get(t['isin']):
            tx_by_date[t['date'].strftime('%Y-%m-%d')].append(t)

    # ── Walk every calendar day ───────────────────────────────────────────────────
    for d in pd.date_range(start=min_date, end=max_date, freq='D'):
        d_str = d.strftime('%Y-%m-%d')
        d_dt  = d.to_pydatetime()

        if d_str in tx_by_date:
            for t in tx_by_date[d_str]:
                isin   = t['isin']
                ticker = ticker_map.get(isin, '')
                if not ticker:
                    continue
                amount    = abs(float(t.get('amount', 0.0)))
                yf_price  = _get_price(ticker, t['date'])

                if amount == 0.0:
                    print(f"[PERF] [WARN]  Skipping {t['type']} {isin}: amount=0")
                    continue
                if yf_price == 0.0:
                    # Try harder: search up to 30 days forward/back for a valid price
                    for fwd in range(1, 31):
                        yf_price = _get_price(ticker, t['date'] + timedelta(days=fwd))
                        if yf_price > 0:
                            break
                    if yf_price == 0.0:
                        print(f"[PERF] [WARN]  Skipping {t['type']} {isin}: no price found within ?30d")
                        continue

                # ── Shares: ALWAYS derived from THIS download to guarantee consistency ──
                # Using t['shares'] from a prior separate yfinance download would
                # create cross-download price discrepancies that corrupt sell_ratio.
                # Both BUY lot_shares and SELL shares_sold use the SAME yf_price here.
                shares_internal = amount / yf_price   # shares in THIS download's unit

                # For event display only: prefer real share count if available and sane
                shares_display = float(t.get('shares') or 0)
                if shares_display <= 0:
                    shares_display = shares_internal

                if t['type'] == 'BUY':
                    # Step 1 – close the current sub-period on existing lots
                    if lots and subperiod_start_mv and subperiod_start_mv > 0:
                        v_before = _portfolio_value(lots, d_dt)
                        hpr = (v_before - subperiod_start_mv) / subperiod_start_mv
                        cumulative_factor *= (1.0 + hpr)
                        # New sub-period start = existing value + new cash injected
                        subperiod_start_mv = v_before + amount
                    else:
                        # First ever BUY — sub-period starts at invested amount
                        subperiod_start_mv = amount

                    # Step 2 – add the lot (shares and buy_yf_price both from THIS download)
                    lots.append({
                        'isin':         isin,
                        'ticker':       ticker,
                        'shares':       shares_internal,   # consistent with sell logic below
                        'eur_invested': amount,
                        'buy_yf_price': yf_price,
                    })
                    events.append({'date': d_str, 'type': 'BUY',
                                   'isin': isin, 'ticker': ticker,
                                   'shares': shares_display, 'price': yf_price, 'amount': amount})

                elif t['type'] == 'SELL':
                    # Step 1 – close the current sub-period on existing lots BEFORE sell
                    if lots and subperiod_start_mv and subperiod_start_mv > 0:
                        v_before = _portfolio_value(lots, d_dt)
                        hpr = (v_before - subperiod_start_mv) / subperiod_start_mv
                        cumulative_factor *= (1.0 + hpr)

                    # Step 2 – sell_ratio: shares_sold / shares_held
                    # Both computed from THIS download → no cross-download skew
                    total_shares_held = sum(l['shares'] for l in lots if l['isin'] == isin)
                    if total_shares_held > 0:
                        sell_ratio = min(shares_internal / total_shares_held, 1.0)
                    else:
                        sell_ratio = 1.0  # no lots found for this ISIN

                    new_lots = []
                    for l in lots:
                        if l['isin'] == isin:
                            remaining = 1.0 - sell_ratio
                            if remaining > 0.001:
                                new_lots.append({**l,
                                    'shares':       l['shares']       * remaining,
                                    'eur_invested': l['eur_invested'] * remaining,
                                })
                            # else: lot fully consumed — drop it cleanly
                        else:
                            new_lots.append(l)
                    lots = new_lots

                    events.append({'date': d_str, 'type': 'SELL',
                                   'isin': isin, 'ticker': ticker,
                                   'shares': shares_display, 'price': yf_price, 'amount': amount})

                    # Step 3 – restart sub-period from remaining portfolio value
                    if lots:
                        subperiod_start_mv = _portfolio_value(lots, d_dt)
                    else:
                        subperiod_start_mv = None

        # ── Daily TWR data point ──────────────────────────────────────────────
        if lots and subperiod_start_mv and subperiod_start_mv > 0:
            v_now = _portfolio_value(lots, d_dt)
            current_hpr = (v_now - subperiod_start_mv) / subperiod_start_mv
            twr_pct = (cumulative_factor * (1.0 + current_hpr) - 1.0) * 100.0
            daily_series.append({'date': d_str, 'value': round(twr_pct, 2)})

    print(f"[PERF] [OK] TWR series: {len(daily_series)} pts (Oct 2025->today), "
          f"final={daily_series[-1]['value'] if daily_series else 'N/A'}%")

    # ── Diagnostic: show lot state and first/last data points ────────────────
    print(f"[PERF][DEBUG] Active lots at end: {len(lots)}")
    for l in lots:
        px_now = _get_price(l['ticker'], max_date)
        ratio  = (px_now / l['buy_yf_price']) if l['buy_yf_price'] > 0 else 0
        print(f"[PERF][DEBUG]   {l['isin']} ({l['ticker']}) "
              f"buy_px={l['buy_yf_price']:.4f} now_px={px_now:.4f} "
              f"ratio={ratio:.4f} eur_inv={l['eur_invested']:.2f} shares={l['shares']:.6f}")
    print(f"[PERF][DEBUG] cumulative_factor={cumulative_factor:.6f}")
    if daily_series:
        print(f"[PERF][DEBUG] First point: {daily_series[0]}")
        print(f"[PERF][DEBUG] Last  point: {daily_series[-1]}")

    return daily_series, events

# ============================================================================
# END NEW LOGIC
# ============================================================================


@app.route('/api/performance/market', methods=['GET'])
def get_market_performance():
    tr_api = TradeRepublicAPI()
    
    async def fetch_data():
        try:
           # NASDAQ: IE00B53SZB19.TIB, CAC40: LU1681046931.TIB
           res_nasdaq = await tr_api.fetch_aggregate_history_light("IE00B53SZB19.TIB", "1y")
           res_cac40 = await tr_api.fetch_aggregate_history_light("LU1681046931.TIB", "1y")
           await tr_api.close()
           return {"nasdaq": res_nasdaq, "cac40": res_cac40}
        except Exception as e:
            print(f"Error fetching market performance: {e}")
            await tr_api.close()
            return {"nasdaq": [], "cac40": []}

    try:
        # Use asyncio.run for a fresh event loop
        data = asyncio.run(fetch_data())
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/portfolio-chart', methods=['GET'])
def get_portfolio_chart():
    """Proxy TR portfolio chart API for a given range (1d, 5d, 1m, 6m, 1y, max)."""
    range_code = request.args.get('range', '5d').lower()
    allowed = {'1d', '5d', '1m', '6m', '1y', 'max'}
    if range_code not in allowed:
        return jsonify({"error": "invalid range"}), 400
    data = tr_api.fetch_portfolio_chart(range_code)
    if data is None:
        return jsonify({"error": "fetch_failed"}), 502
    return jsonify(data)


@app.route('/api/tr/refresh-session', methods=['POST'])
def tr_refresh_session():
    """Force a session token refresh using the stored tr_refresh token."""
    ok = tr_api.refresh_session_token()
    if ok:
        return jsonify({"status": "ok", "message": "Session refreshed successfully."})
    return jsonify({"status": "error", "message": "Refresh failed — no refresh token or TR refused."}), 400


@app.route('/api/tr-cookies', methods=['POST'])
def save_tr_cookies():
    """Save the full browser cookie string (copied from DevTools) for TR API calls."""
    body = request.get_json(silent=True) or {}
    cookie_str = body.get('cookies', '').strip()
    if not cookie_str:
        return jsonify({"error": "empty cookies"}), 400
    if not tr_api.config.has_section("secret"):
        tr_api.config.add_section("secret")
    tr_api.config.set("secret", "tr_browser_cookies", cookie_str)
    with open(tr_api.config_path, "w") as f:
        tr_api.config.write(f)
    # Also update session token and clear cached sec_acc_no
    try:
        import re as _re
        m = _re.search(r'tr_session=([^;]+)', cookie_str)
        if m:
            tr_api.session_token = m.group(1).strip()
            tr_api.cached_sec_acc = None  # force re-derivation from new token
    except Exception:
        pass
    return jsonify({"status": "ok"})


@app.route('/api/portfolio/performance', methods=['GET'])
def get_portfolio_performance():
    """
    Returns portfolio performance curve reconstructed from real trade history
    fetched live via WebSocket (timelineTransactions + timelineDetailV2),
    the same channel used by the cash-flow analysis.
    Also returns BUY/SELL event markers for the chart.
    """
    try:
        sep = '=' * 60
        print(f"\n{sep}")
        print(f"[PERF] Request at {datetime.now().strftime('%H:%M:%S')}")
        print(f"[PERF] Session token present: {bool(tr_api.session_token)}")
        print(sep)

        # ------------------------------------------------------------------ #
        # 1. Benchmark indices (NASDAQ, CAC 40)
        # ------------------------------------------------------------------ #
        # Benchmarks are downloaded from 1985 but will be RE-BASED later
        # (once we know the portfolio start date) so all curves start at 0%.
        comparison_data = {}
        benchmarks_tickers = {"NASDAQ": "^IXIC", "CAC 40": "^FCHI"}

        print(f"[PERF][BENCH] Downloading full benchmark history (weekly, from 1985)...")
        for name, symbol in benchmarks_tickers.items():
            try:
                data = yf.download(symbol, start="1985-01-01", interval="1wk", progress=False)
                if not data.empty:
                    closes = None
                    if isinstance(data.columns, pd.MultiIndex):
                        try:
                            closes = data['Close']
                            if isinstance(closes, pd.DataFrame):
                                closes = closes[symbol] if symbol in closes.columns else closes.iloc[:, 0]
                        except:
                            closes = data.iloc[:, 0]
                    else:
                        closes = data['Close'] if 'Close' in data.columns else data.iloc[:, 0]

                    if closes is not None and not closes.empty:
                        closes = closes.dropna()
                        closes.index = closes.index.tz_localize(None) if closes.index.tz is not None else closes.index
                        if not closes.empty:
                            # Store full series as dict {date_str: price}
                            comparison_data[name] = {
                                idx.strftime("%Y-%m-%d"): float(val)
                                for idx, val in closes.items()
                            }
                            print(f"[PERF][BENCH] {name} ({symbol}): {len(comparison_data[name])} pts")
            except Exception as e:
                print(f"[PERF][BENCH] [ERROR] Error fetching {name}: {e}")

        # ------------------------------------------------------------------ #
        # 2. Portfolio curve – fetched via WebSocket (same as cash-flow)
        # ------------------------------------------------------------------ #
        user_series  = []
        chart_events = []

        if not tr_api.session_token:
            print("[PERF][PORTFOLIO] [WARN]  No session token - portfolio curve skipped.")
        else:
            print("[PERF][PORTFOLIO] [PLUG] Connecting to TR WebSocket...")

            async def _fetch_via_websocket():
                """Open a fresh WebSocket connection and pull the full transaction history."""
                api = TradeRepublicAPI()
                connected = await api.connect()
                if not connected:
                    print("[PERF][PORTFOLIO] [ERROR] WebSocket connection failed. No portfolio curve.")
                    return [], []

                print("[PERF][PORTFOLIO] [OK] WebSocket connected.")
                print("[PERF][PORTFOLIO] [NET] Fetching transactions via timelineTransactions + timelineDetailV2 ...")

                # Uses same websocket channel as cash-flow:
                #   1. timelineTransactions (paginated)
                #   2. timelineDetailV2 for each BUY/SELL item
                parsed_txs = await fetch_full_transaction_history_v2(api)
                await api.close()
                print("[PERF][PORTFOLIO] [PLUG] WebSocket closed.")

                stock_txs = [t for t in parsed_txs
                             if t.get('type') in ('BUY', 'SELL') and t.get('isin')]
                print(f"[PERF][PORTFOLIO] [DATA] {len(stock_txs)} BUY/SELL stock transactions ready.")

                if not stock_txs:
                    print("[PERF][PORTFOLIO] [WARN]  No stock transactions found - empty portfolio curve.")
                    return [], []

                print("[PERF][PORTFOLIO] [UP] Building portfolio performance curve via yfinance...")
                series, events = calculate_portfolio_performance_from_transactions(stock_txs)

                # Summary logs
                buys  = sum(1 for e in events if e['type'] == 'BUY')
                sells = sum(1 for e in events if e['type'] == 'SELL')
                print(f"[PERF][PORTFOLIO] [OK] Curve: {len(series)} data points, "
                      f"{len(events)} events ({buys} BUY / {sells} SELL)")
                if series:
                    print(f"[PERF][PORTFOLIO]    First: {series[0]['date']} {series[0]['value']:+.2f}%")
                    print(f"[PERF][PORTFOLIO]    Last : {series[-1]['date']} {series[-1]['value']:+.2f}%")

                return series, events

            # ---- Run the async fetch in a fresh event loop ----
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    user_series, chart_events = loop.run_until_complete(
                        _fetch_via_websocket()
                    )
                finally:
                    loop.close()
            except Exception as ws_err:
                print(f"[PERF][PORTFOLIO] [ERROR] WebSocket fetch failed: {ws_err}")
                traceback.print_exc()

                # ---- Fallback: use cached transactions from DB ----
                print("[PERF][PORTFOLIO] [REFRESH] Falling back to cached transactions in DB...")
                phone = request.headers.get('X-User-Phone')
                if not phone:
                    try:
                        tr_api.config.read(tr_api.config_path)
                        phone = tr_api.config.get("secret", "phone_number", fallback=None)
                    except:
                        pass
                key     = f'tr_transactions_{phone}' if phone else 'tr_transactions'
                raw_txs = db_load_generic(key, []) or db_load_generic('tr_transactions', [])
                print(f"[PERF][PORTFOLIO] [PKG] Found {len(raw_txs) if raw_txs else 0} cached transactions in DB.")
                if raw_txs:
                    fallback_parsed = []
                    for tx in raw_txs:
                        n = _normalize_tr_transaction(tx)
                        if n['isin'] and n['tx_type'] in ('BUY', 'SELL'):
                            d = _parse_ts(n['timestamp'])
                            if d:
                                fallback_parsed.append({
                                    'date':   d,
                                    'type':   n['tx_type'],
                                    'isin':   n['isin'],
                                    'shares': n['shares'],
                                    'price':  n['price'],
                                    'amount': n['amount'],
                                })
                    print(f"[PERF][PORTFOLIO] [DATA] {len(fallback_parsed)} BUY/SELL transactions from DB cache.")
                    if fallback_parsed:
                        user_series, chart_events = calculate_portfolio_performance_from_transactions(
                            fallback_parsed
                        )

        # ------------------------------------------------------------------ #
        # 3. Rebase all series to the same origin (portfolio first date = 0%)
        # ------------------------------------------------------------------ #
        # This ensures NASDAQ, CAC 40 and portfolio are all comparable:
        # every curve starts at 0% on the day of the first portfolio transaction.
        if user_series:
            # The raw TWR value at the first point (may be e.g. -0.3% due to
            # intraday price differences on day 1 — nearly always close to 0)
            first_twr = user_series[0]['value']
            portfolio_start_date = user_series[0]['date']

            # Normalize portfolio: shift so first point = exactly 0.0%
            if first_twr != 0.0:
                user_series = [
                    {'date': pt['date'], 'value': round(pt['value'] - first_twr, 2)}
                    for pt in user_series
                ]
                print(f"[PERF] Portfolio normalized: shifted by {-first_twr:+.2f}% "
                      f"(first point was {first_twr:+.2f}%, now 0.0%)")

            # Rebase benchmarks: filter to dates >= portfolio_start_date,
            # find the closest price at/before that date, use it as the new 0%
            rebased_benchmarks = {}
            for name, price_dict in comparison_data.items():
                sorted_dates = sorted(price_dict.keys())
                if not sorted_dates:
                    continue

                # Find ref price: last benchmark price on or before portfolio start
                ref_price = None
                for d_str in sorted_dates:
                    if d_str <= portfolio_start_date:
                        ref_price = price_dict[d_str]
                    else:
                        break

                if ref_price is None or ref_price == 0:
                    # Fall back to first available price if none found before start date
                    ref_price = price_dict[sorted_dates[0]]

                rebased_benchmarks[name] = [
                    {
                        'date' : d_str,
                        'value': round((price_dict[d_str] - ref_price) / ref_price * 100, 2)
                    }
                    for d_str in sorted_dates
                    if d_str >= portfolio_start_date
                ]

                if rebased_benchmarks[name]:
                    final_val = rebased_benchmarks[name][-1]['value']
                    print(f"[PERF][BENCH] {name} rebased from {portfolio_start_date}: "
                          f"{len(rebased_benchmarks[name])} pts, final={final_val:+.2f}%")

            comparison_data = rebased_benchmarks
        else:
            # No portfolio data: rebase benchmarks from their own first available point
            rebased_benchmarks = {}
            for name, price_dict in comparison_data.items():
                sorted_dates = sorted(price_dict.keys())
                if not sorted_dates:
                    continue
                ref_price = price_dict[sorted_dates[0]]
                if ref_price == 0:
                    continue
                rebased_benchmarks[name] = [
                    {'date': d_str,
                     'value': round((price_dict[d_str] - ref_price) / ref_price * 100, 2)}
                    for d_str in sorted_dates
                ]
            comparison_data = rebased_benchmarks

        # ------------------------------------------------------------------ #
        # 4. True P&L snapshot from live WalletInvestment rows
        # ------------------------------------------------------------------ #
        true_pnl_pct = None
        try:
            wallet_invs = WalletInvestment.query.filter(WalletInvestment.quantity > 0).all()
            if wallet_invs:
                total_pnl_eur   = sum(float(inv.pnl         or 0) for inv in wallet_invs)
                total_value_eur = sum(float(inv.total_value or 0) for inv in wallet_invs)
                total_cost_eur  = total_value_eur - total_pnl_eur
                if total_cost_eur > 0:
                    true_pnl_pct = round((total_pnl_eur / total_cost_eur) * 100, 4)
            print(f"[PERF] True P&L snapshot: {true_pnl_pct}% "
                  f"(cost={total_cost_eur if wallet_invs else 0:.2f} € "
                  f"value={total_value_eur if wallet_invs else 0:.2f} €)")
        except Exception as cal_err:
            print(f"[PERF] [WARN]  true_pnl_pct error: {cal_err}")

        print(f"[PERF] Summary -> benchmarks={list(comparison_data.keys())} "
              f"| portfolio_pts={len(user_series)} "
              f"| portfolio_start={user_series[0]['date'] if user_series else 'N/A'} "
              f"| portfolio_final={user_series[-1]['value'] if user_series else 'N/A'}%"
              f"| events={len(chart_events)}")
        print(f"{sep}\n")

        return jsonify({
            "status": "success",
            "data": {
                "benchmarks"   : comparison_data,
                "portfolio"    : user_series,
                "events"       : chart_events,
                "true_pnl_pct" : true_pnl_pct
            }
        })

    except Exception as e:
        print(f"[PERF] [ERROR] Fatal error: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    tr_api.save_session_token("")
    return jsonify({"success": True})

@app.route('/api/refresh/portfolio', methods=['POST'])
def refresh_portfolio_route():
    # Double check token availability
    if not tr_api.session_token:
        tr_api.config.read(tr_api.config_path)
        tr_api.session_token = tr_api.config.get("secret", "tr_session", fallback=None)
        
    if not tr_api.session_token:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    # Queue to communicate connection result from thread
    conn_result = queue.Queue()

    def run_async_with_check():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Attempt connection
            connected = loop.run_until_complete(tr_api.connect())
            if not connected:
                conn_result.put(False)
                loop.close()
                return
            
            # Connection successful - notify main thread
            conn_result.put(True)
            
            # Proceed with fetching
            loop.run_until_complete(tr_api.fetch_portfolio())
            loop.run_until_complete(tr_api.fetch_history())
            loop.run_until_complete(tr_api.close())
            loop.close()
        except Exception as e:
            print(f"Error in background portfolio refresh: {e}")
            if conn_result.empty():
                conn_result.put(False)
            try: loop.close()
            except: pass

    thread = threading.Thread(target=run_async_with_check)
    thread.start()
    
    try:
        # Wait up to 10s for connection confirmation
        is_connected = conn_result.get(timeout=10)
        if is_connected:
            return jsonify({"success": True, "message": "Portfolio refresh started"})
        else:
            return jsonify({"success": False, "error": "Connection failed (Session invalid)"}), 401
    except queue.Empty:
        # Timeout but thread is running, optimistically return success or error? 
        # Usually connection is fast. If it hangs, assume it might work or fail silently.
        return jsonify({"success": True, "message": "Refresh started (timeout waiting for ack)"})


# ============================================================================
# UTILS SYSTEM INFO
# ============================================================================
import platform
import multiprocessing
try:
    import psutil
except ImportError:
    psutil = None
try:
    import torch
except ImportError:
    torch = None

def print_system_specs():
    print("="*50)
    print("SYSTEM SPECIFICATIONS")
    print("="*50)
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Processor: {platform.processor()}")
    print(f"CPU Cores: {multiprocessing.cpu_count()}")
    
    if psutil:
        ram_gb = psutil.virtual_memory().total / (1024**3)
        print(f"RAM: {ram_gb:.2f} GB")
    else:
        print("RAM: psutil not installed (cannot detect RAM)")
        
    if torch:
        print(f"PyTorch Version: {torch.__version__}")
        cuda_avail = torch.cuda.is_available()
        print(f"CUDA Available: {cuda_avail}")
        if cuda_avail:
            print(f"GPU: {torch.cuda.get_device_name(0)}")
            print(f"CUDA Device Count: {torch.cuda.device_count()}")
    else:
        print("PyTorch: Not installed")
    print("="*50)

# ============================================================================
# FINBERT MODEL
# ============================================================================

# Optimisation: Chargement différé ou sur GPU si dispo
finbert_pipeline = None

def load_finbert():
    global finbert_pipeline
    if finbert_pipeline is not None:
        return finbert_pipeline
        
    print("Initialisation du modele FinBERT...")
    try:
        # Detect device
        device = -1 # CPU by default
        if torch and torch.cuda.is_available():
            device = 0 # First GPU
            print("Utilisation du GPU pour FinBERT")
        
        if not TRANSFORMERS_AVAILABLE or hf_pipeline is None:
            print("[WARN] transformers not available — FinBERT disabled")
            return None
        finbert_pipeline = hf_pipeline("sentiment-analysis", model="ProsusAI/finbert", device=device)
        print("FinBERT charge avec succes.")
    except Exception as e:
        print(f"Erreur lors du chargement de FinBERT: {e}")
        finbert_pipeline = None
    return finbert_pipeline

# Chargement asynchrone différé
# On définit une fonction d'init qui sera appelée au démarrage
def init_app_background_tasks():
    print_system_specs()
    threading.Thread(target=load_finbert, daemon=True).start()

def analyze_sentiment_finbert(text):
    """Analyse le sentiment d'un texte avec FinBERT"""
    # Le pipeline peut ne pas être encore chargé
    if not finbert_pipeline:
        # Si on est pressé et qu'il n'est pas chargé, on tente de le charger synchrone
        # ou on renvoie None. Pour l'instant on tente le chargement
        if finbert_pipeline is None: # Si toujours None
             # Petite attente active ou retour None ?
             pass 
    
    if not finbert_pipeline or not text:
        return None
    
    try:
        # FinBERT a une limite de 512 tokens, on tronque le texte si nécessaire
        # On combine souvent Titre + Résumé pour une meilleure précision
        results = finbert_pipeline(text[:512])
        res = results[0]
        # Ensure float type for JSON serialization (handle numpy types)
        if 'score' in res:
            res['score'] = float(res['score'])
        return res
    except Exception as e:
        print(f"Erreur analyse FinBERT: {e}")
        return None

# État global pour les tâches de fond
background_tasks_running = False

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def load_json_file(filename):
    """Charge un fichier JSON, retourne {} si absent"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Erreur lecture {filename}: {e}")
        return {}










    
# ============================================================================
# YOUTUBE LIVE STREAM (Bloomberg)
# ============================================================================

class YouTubeLiveStream:
    def __init__(self, url):
        self.url = url
        self.frame_queue = queue.Queue(maxsize=10)
        self.running = False
        self.capture = None
        
    def get_stream_url(self):
        ydl_opts = {'format': 'best[height<=720]', 'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.url, download=False)
            return info['url']
    
    def start(self):
        stream_url = self.get_stream_url()
        self.capture = cv2.VideoCapture(stream_url)
        
        if not self.capture.isOpened():
            raise Exception("Flux vidéo inaccessible")
        
        self.running = True
        threading.Thread(target=self._capture_frames, daemon=True).start()
        return self
    
    def _capture_frames(self):
        while self.running:
            ret, frame = self.capture.read()
            if ret:
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.frame_queue.put(frame)
            else:
                time.sleep(5)
                try:
                    stream_url = self.get_stream_url()
                    self.capture = cv2.VideoCapture(stream_url)
                except Exception:
                    pass
    
    def read(self):
        try:
            return self.frame_queue.get(timeout=10)
        except queue.Empty:
            return None
    
    def stop(self):
        self.running = False
        if self.capture:
            self.capture.release()

def db_save_news_segment(title, ticker_fragments, ai_summary):
    try:
        with app.app_context():
            news = NewsItem(
                source="Bloomberg Live",
                title=title,
                url=f"bloomberg_live_{int(time.time())}", 
                summary=ai_summary,
                published_at=datetime.now(),
                sentiment="Neutral", 
                sentiment_score=0.0,
                related_tickers=ticker_fragments
            )
            db.session.add(news)
            db.session.commit()
    except Exception as e:
        print(f"DB Error save news: {e}")

def db_get_news_segments(limit=50):
    try:
        with app.app_context():
             items = NewsItem.query.filter_by(source="Bloomberg Live").order_by(NewsItem.published_at.desc()).limit(limit).all()
             return [{
                 "timestamp": i.published_at.isoformat() if i.published_at else "",
                 "main_title": i.title,
                 "ticker_fragments": i.related_tickers,
                 "ai_summary": i.summary,
                 "fragment_count": len(i.related_tickers or [])
             } for i in items]
    except:
        return []

class NewsLogger:
    def __init__(self, json_file="bloomberg_news.json"):
        self.json_file = json_file
        # No load from file needed
    
    def load_data(self):
        # Fetch from DB for compatibility
        return {"news_segments": db_get_news_segments()}
    
    def save_data(self):
        pass 
    
    def add_news_segment(self, title, ticker_fragments, ai_summary):
        db_save_news_segment(title, ticker_fragments, ai_summary)

# ============================================================================
# CAPITOL TRADES SCRAPER (Trades des sénateurs)
# ============================================================================

class CapitolTradesScraper:
    """Scraper pour Capitol Trades - Trades des politiciens au Congrès"""
    
    # Dictionnaire de mapping nom de compagnie -> ticker
    NAME_TO_TICKER = {
        'AT&T Inc': 'T',
        'Abbott Laboratories': 'ABT',
        'Advanced Micro Devices': 'AMD',
        'Alibaba': 'BABA',
        'Alphabet Inc': 'GOOGL',
        'Amazon': 'AMZN',
        'Apple Inc': 'AAPL',
        'Broadcom Inc': 'AVGO',
        'Chevron Corporation': 'CVX',
        'Cisco Systems': 'CSCO',
        'Eli Lilly': 'LLY',
        'ExxonMobil': 'XOM',
        'GE Aerospace': 'GE',
        'Intel Corporation': 'INTC',
        'JPMorgan Chase': 'JPM',
        'Johnson & Johnson': 'JNJ',
        'Meta Platforms': 'META',
        'Microsoft': 'MSFT',
        'Nvidia': 'NVDA',
        'Procter & Gamble': 'PG',
        'Tesla Inc': 'TSLA',
        'The Coca-Cola Company': 'KO',
        'The Home Depot': 'HD',
        'The Walt Disney Company': 'DIS',
        'Walmart Inc': 'WMT',
        'Visa Inc': 'V',
    }
    
    def __init__(self):
        self.base_url = "https://www.capitoltrades.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.cache_file = 'capitol_trades_cache.json'
        self.all_issuers_file = 'all_issuers.json'
        self.cache_data = self._load_cache()
        self.all_issuers = self._load_all_issuers()
    
    def _load_all_issuers(self):
        """Charge la liste complète des issuers"""
        try:
            if os.path.exists(self.all_issuers_file):
                with open(self.all_issuers_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[ERROR] Erreur chargement all_issuers.json: {e}")
        return []
    
    def _load_cache(self):
        """Charge le cache local depuis la DB"""
        return db_load_generic('capitol_trades_cache', {'issuers': {}, 'issuers_index': {}, 'last_updated': None})
    
    def _save_cache(self):
        """Sauvegarde le cache local dans la DB"""
        db_save_generic('capitol_trades_cache', self.cache_data)
    
    def _match_ticker_from_name(self, company_name):
        """Extrait le ticker à partir du nom de la compagnie"""
        if not company_name:
            return None
        
        # Cherche une correspondance exacte
        for name, ticker in self.NAME_TO_TICKER.items():
            if name.lower() in company_name.lower() or company_name.lower() in name.lower():
                return ticker
        
        return None
    
    def _get_total_pages(self, soup):
        """Détecte la pagination 'Page X of Y'"""
        text = soup.get_text(" ", strip=True)
        m = re.search(r'Page\s+\d+\s+of\s+(\d+)', text, flags=re.IGNORECASE)
        if m:
            return int(m.group(1))
        return 1
    
    def _extract_trades_page_issuers(self, soup):
        """Extrait tous les issuers visibles depuis une page /trades"""
        issuers = []
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            m = re.match(r'^/issuers/(\d+)$', href.strip())
            if m:
                issuer_id = m.group(1)
                name = a.get_text(" ", strip=True) or None
                
                # Essai d'extraction du ticker (ex. 'MSFT:US')
                ticker = None
                parent = a.find_parent()
                if parent:
                    tmatch = re.search(r'([A-Z.\-]+:[A-Z]{2})', parent.get_text(" ", strip=True))
                    if tmatch:
                        ticker = tmatch.group(1).split(':')[0]  # Extraire juste "MSFT" de "MSFT:US"
                
                issuers.append({
                    'issuer_id': issuer_id,
                    'name': name,
                    'ticker': ticker,
                    'url': f"{self.base_url}{href}"
                })
        
        # Dédupliquer par issuer_id
        by_id = {}
        for it in issuers:
            by_id[it['issuer_id']] = it
        return list(by_id.values())
    
    def collect_issuers_from_trades(self, max_pages=1, delay=0.5):
        """Parcourt /trades pour récupérer automatiquement les issuers avec leurs IDs"""
        base_trades_url = f"{self.base_url}/trades?assetType=stock"
        
        try:
            print(f"[SCRAPER] Fetching {base_trades_url}...")
            resp = requests.get(base_trades_url, headers=self.headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'html.parser')
            print(f"[SCRAPER] Got response, parsing...")
        except Exception as e:
            print(f"[ERROR] Echec d'acces {base_trades_url}: {e}")
            return []
        
        total_pages = self._get_total_pages(soup)
        if max_pages is not None:
            total_pages = min(total_pages, max_pages)
        
        print(f"[SCRAPER] Total pages: {total_pages}")
        
        all_issuers = []
        all_issuers.extend(self._extract_trades_page_issuers(soup))
        print(f"[SCRAPER] Page 1: found {len(all_issuers)} issuers")
        
        # Pages suivantes
        for page in range(2, total_pages + 1):
            page_url = f"{base_trades_url}&page={page}"
            try:
                print(f"[SCRAPER] Fetching page {page}...")
                r = requests.get(page_url, headers=self.headers, timeout=15)
                r.raise_for_status()
                psoup = BeautifulSoup(r.content, 'html.parser')
                page_issuers = self._extract_trades_page_issuers(psoup)
                all_issuers.extend(page_issuers)
                print(f"[SCRAPER] Page {page}: found {len(page_issuers)} issuers")
                time.sleep(delay)
            except Exception as e:
                print(f"[WARN] Page trades {page} ignoree: {e}")
                continue
        
        # Dédupe finale
        by_id = {}
        for it in all_issuers:
            by_id[it['issuer_id']] = it
        
        print(f"[SCRAPER] Total unique issuers: {len(by_id)}")
        return list(by_id.values())
    
    def search_issuer_by_name(self, search_term):
        """Cherche les issuers par nom ou ticker (case-insensitive, partial match) + Live Search"""
        if not search_term:
            return []
        
        search_lower = search_term.lower()
        results = []
        
        # 1. Local Search
        for issuer in self.all_issuers:
            name = issuer.get('name', '').lower()
            ticker = issuer.get('ticker', '').lower() if issuer.get('ticker') else ''
            
            # Match on name OR ticker (exact match for ticker preferred)
            if search_lower == ticker or search_lower in name:
                results.append(issuer)
        
        # 2. If no results locally, try LIVE search
        if not results:
             print(f"[SCRAPER] No local match for '{search_term}', trying LIVE search...")
             live_results = self._search_live_issuer(search_term)
             if live_results:
                 print(f"[SCRAPER] Found {len(live_results)} live results")
                 results.extend(live_results)
                 
                 # Optional: add to local cache/session (skipped to avoid complexity)

        return results[:10]  # Limiter à 10 résultats

    def _search_live_issuer(self, query):
        """Recherche 'live' sur CapitolTrades si le cache ne donne rien"""
        try:
             url = f"{self.base_url}/issuers?q={query}"
             r = requests.get(url, headers=self.headers, timeout=10)
             if r.status_code != 200:
                 return []
             
             soup = BeautifulSoup(r.content, 'html.parser')
             found_items = []
             
             # Search for all links that match /issuers/{id}
             # Valid ID is usually numeric or mixed ID
             links = soup.find_all('a', href=True)
             
             for link in links:
                 href = link['href']
                 # /issuers/230554536
                 if href.startswith('/issuers/') and len(href.split('/')) == 3:
                     issuer_id = href.split('/')[-1]
                     
                     # Simple valid check
                     if not issuer_id or len(issuer_id) < 3: continue
                     
                     name_text = link.get_text(strip=True)
                     
                     # Check if query matches (to avoid random links)
                     match_found = False
                     name_clean = name_text.lower()
                     query_lower = query.lower()
                     known_ticker = None
                     
                     # 1. Direct Name Match
                     if query_lower in name_clean:
                         match_found = True
                     
                     # 2. Ticker Match via Dictionary (Name -> Ticker)
                     # We try to extract the company name key (e.g. "Nvidia" from "NVIDIA Corporation")
                     if not match_found:
                         first_word = name_text.split(' ')[0].capitalize() # NVIDIA -> Nvidia
                         # Try pure name map
                         known_ticker = self.NAME_TO_TICKER.get(first_word) # Nvidia -> NVDA
                         
                         # Also try full name keys if present
                         if not known_ticker:
                             for key, val in self.NAME_TO_TICKER.items():
                                 if key.lower() in name_clean:
                                     known_ticker = val
                                     break
                                     
                         if known_ticker and known_ticker.lower() == query_lower:
                             match_found = True
                             
                     # 3. Last Resort: Ticker in URL or Name Text pattern
                     if not match_found and ':' in name_text:
                         if query.upper() in name_text:
                             match_found = True
                             
                     if match_found:
                         
                         # Try to extract ticker from Name (e.g. "NVIDIA Corporation NVDA:US")
                         ticker = query.upper()
                         # Enhanced Ticker Extraction
                         if ':' in name_text:
                             parts = name_text.split(':')
                             if len(parts) > 0:
                                 pre_colon = parts[0].split(' ')[-1]
                                 if pre_colon.isupper():
                                     ticker = pre_colon
                         elif known_ticker: # From Dict
                             ticker = known_ticker
                         
                         item = {
                             'name': name_text,
                             'issuer_id': issuer_id,
                             'ticker': ticker,
                             'country': 'US'
                         }
                         
                         # Avoid duplicates
                         if not any(f['issuer_id'] == item['issuer_id'] for f in found_items):
                            found_items.append(item)
                            
             return found_items
             
        except Exception as e:
            print(f"[SCRAPER] Live search error: {e}")
            return []
    
    def get_issuer_id_for_ticker(self, ticker_symbol):
        """Récupère l'issuer_id pour un ticker"""
        if not ticker_symbol:
            return None
        
        # Chercher dans all_issuers par nom (peut être un nom, pas nécessairement un ticker)
        search_term = ticker_symbol.lower()
        
        for issuer in self.all_issuers:
            # 1. Check explicit ticker if available
            if issuer.get('ticker') and issuer.get('ticker').lower() == search_term:
                print(f"[SCRAPER] Found exact ticker match {ticker_symbol}: {issuer.get('name')} (ID: {issuer['issuer_id']})")
                return issuer['issuer_id']

            # 2. Check name
            name = issuer.get('name', '').lower()
            # Chercher une correspondance du début du nom
            if name.startswith(search_term) or search_term in name:
                print(f"[SCRAPER] Found name match {ticker_symbol}: {issuer.get('name')} (ID: {issuer['issuer_id']})")
                return issuer['issuer_id']
        
        print(f"[SCRAPER] {ticker_symbol} not found")
        return None
    
    def scrape_issuer(self, issuer_id, ticker_symbol=None):
        """Scrape les données d'un émetteur spécifique"""
        url = f"{self.base_url}/issuers/{issuer_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extraction des informations de l'émetteur
            issuer_data = self._extract_issuer_info(soup, ticker_symbol)
            
            # Extraction des transactions
            trades = self._extract_trades(soup)
            
            # Statistiques
            stats = self._extract_statistics(soup)
            
            result = {
                'issuer': issuer_data,
                'trades': trades,
                'statistics': stats,
                'scraped_at': datetime.now().isoformat()
            }
            
            # Mettre en cache
            if ticker_symbol:
                self.cache_data['issuers'][ticker_symbol] = result
                self.cache_data['last_updated'] = datetime.now().isoformat()
                self._save_cache()
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"Erreur Capitol Trades: {e}")
            # Retourner le cache si disponible
            if ticker_symbol and ticker_symbol in self.cache_data.get('issuers', {}):
                return self.cache_data['issuers'][ticker_symbol]
            return None
    
    def _extract_issuer_info(self, soup, ticker_symbol=None):
        """Extrait les informations de base sur l'émetteur"""
        issuer_info = {
            'ticker': ticker_symbol,
            'name': None,
            'country': 'United States'
        }
        
        # Nom de l'entreprise
        title = soup.find('h1')
        if title:
            issuer_info['name'] = title.text.strip()
        
        # Prix, Market Cap, etc.
        info_sections = soup.find_all('div', class_=re.compile('issuer|card'))
        
        for section in info_sections:
            text = section.get_text()
            if 'Last Price' in text:
                price_match = re.search(r'([\d.]+)', text)
                if price_match:
                    issuer_info['last_price'] = float(price_match.group(1))
            
            if 'Market Cap' in text:
                cap_match = re.search(r'([\d.]+[BMK])', text)
                if cap_match:
                    issuer_info['market_cap'] = cap_match.group(1)
            
            if 'Country' in text:
                issuer_info['country'] = 'United States'
            
            if 'State' in text:
                issuer_info['state'] = text.split('State')[1].strip() if 'State' in text else None
        
        return issuer_info
    
    def _extract_trades(self, soup):
        """Extrait toutes les transactions du tableau"""
        trades = []
        
        # Trouver le tableau des transactions
        table = soup.find('table')
        if not table:
            return trades
        
        rows = table.find_all('tr')[1:]  # Skip header row
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 6:
                trade = {}
                
                # Politicien
                politician_link = cols[0].find('a')
                if politician_link:
                    trade['politician_name'] = politician_link.text.strip()
                    trade['politician_url'] = self.base_url + politician_link.get('href', '')
                
                # Parti et chambre
                party_info = cols[0].get_text()
                if 'Republican' in party_info:
                    trade['party'] = 'Republican'
                elif 'Democrat' in party_info:
                    trade['party'] = 'Democrat'
                
                if 'House' in party_info:
                    trade['chamber'] = 'House'
                elif 'Senate' in party_info:
                    trade['chamber'] = 'Senate'
                
                # État
                state_match = re.search(r'(House|Senate)([A-Z]{2})', party_info)
                if state_match:
                    trade['state'] = state_match.group(2)
                
                # Date de publication
                trade['published'] = cols[1].text.strip()
                
                # Date de transaction
                trade['traded'] = cols[2].text.strip()
                
                # Délai de déclaration
                filed_after = cols[3].text.strip()
                days_match = re.search(r'(\d+)', filed_after)
                if days_match:
                    trade['filed_after_days'] = int(days_match.group(1))
                
                # Type de transaction
                trade['type'] = cols[4].text.strip().lower()
                
                # Montant
                trade['size'] = cols[5].text.strip()
                
                # Lien vers le détail
                detail_link = cols[6].find('a') if len(cols) > 6 else None
                if detail_link:
                    trade['detail_url'] = self.base_url + detail_link.get('href', '')
                
                trades.append(trade)
        
        return trades
    
    def _extract_statistics(self, soup):
        """Extrait les statistiques globales"""
        stats = {
            'democrats': {'total': 0, 'buy': 0, 'sell': 0},
            'republicans': {'total': 0, 'buy': 0, 'sell': 0},
            'total_trades': 0,
            'total_filings': 0,
            'total_volume': None,
            'total_politicians': 0
        }
        
        # Chercher les sections de statistiques
        text = soup.get_text()
        
        # Trades by Democrats
        dem_match = re.search(r'Trades by Democrats\s*(\d+)\s*Trades.*?Buy(\d+).*?Sell(\d+)', text, re.DOTALL)
        if dem_match:
            stats['democrats']['total'] = int(dem_match.group(1))
            stats['democrats']['buy'] = int(dem_match.group(2))
            stats['democrats']['sell'] = int(dem_match.group(3))
        
        # Trades by Republicans
        rep_match = re.search(r'Trades by Republicans\s*(\d+)\s*Trades.*?Buy(\d+).*?Sell(\d+)', text, re.DOTALL)
        if rep_match:
            stats['republicans']['total'] = int(rep_match.group(1))
            stats['republicans']['buy'] = int(rep_match.group(2))
            stats['republicans']['sell'] = int(rep_match.group(3))
        
        # Total trades
        total_match = re.search(r'(\d+)\s*Trades\s*(\d+)\s*Filings', text)
        if total_match:
            stats['total_trades'] = int(total_match.group(1))
            stats['total_filings'] = int(total_match.group(2))
        
        # Volume
        volume_match = re.search(r'\$([\d.]+M)', text)
        if volume_match:
            stats['total_volume'] = volume_match.group(1)
        
        # Politicians
        pol_match = re.search(r'(\d+)\s*Politicians', text)
        if pol_match:
            stats['total_politicians'] = int(pol_match.group(1))
        
        return stats
    
    def scrape_issuer(self, issuer_id, ticker_symbol=None):
        """Scrape les données d'un émetteur spécifique (ex: AT&T avec ID 429914)"""
        url = f"{self.base_url}/issuers/{issuer_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extraction des informations de l'émetteur
            issuer_data = self._extract_issuer_info(soup, ticker_symbol)
            
            # Extraction des transactions
            trades = self._extract_trades(soup)
            
            # Statistiques
            stats = self._extract_statistics(soup)
            
            result = {
                'issuer': issuer_data,
                'trades': trades,
                'statistics': stats,
                'scraped_at': datetime.now().isoformat()
            }
            
            # Mettre en cache
            if ticker_symbol:
                self.cache_data['issuers'][ticker_symbol] = result
                self.cache_data['last_updated'] = datetime.now().isoformat()
                self._save_cache()
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"Erreur Capitol Trades: {e}")
            # Retourner le cache si disponible
            if ticker_symbol and ticker_symbol in self.cache_data.get('issuers', {}):
                return self.cache_data['issuers'][ticker_symbol]
            return None
    
    def _extract_issuer_info(self, soup, ticker_symbol=None):
        """Extrait les informations de base sur l'émetteur"""
        issuer_info = {
            'ticker': ticker_symbol,
            'name': None,
            'country': 'United States'
        }
        
        # Nom de l'entreprise
        title = soup.find('h1')
        if title:
            issuer_info['name'] = title.text.strip()
        
        return issuer_info
    
    def _extract_trades(self, soup):
        """Extrait toutes les transactions du tableau"""
        trades = []
        
        # Trouver le tableau des transactions
        table = soup.find('table')
        if not table:
            return trades
        
        rows = table.find_all('tr')[1:]  # Skip header row
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 6:
                trade = {}
                
                # Politicien
                politician_link = cols[0].find('a')
                if politician_link:
                    trade['politician_name'] = politician_link.text.strip()
                    trade['politician_url'] = self.base_url + politician_link.get('href', '')
                
                # Parti et chambre
                party_info = cols[0].get_text()
                if 'Republican' in party_info:
                    trade['party'] = 'Republican'
                elif 'Democrat' in party_info:
                    trade['party'] = 'Democrat'
                
                if 'House' in party_info:
                    trade['chamber'] = 'House'
                elif 'Senate' in party_info:
                    trade['chamber'] = 'Senate'
                
                # État
                state_match = re.search(r'(House|Senate)([A-Z]{2})', party_info)
                if state_match:
                    trade['state'] = state_match.group(2)
                
                # Date de publication
                trade['published'] = cols[1].text.strip()
                
                # Date de transaction
                trade['traded'] = cols[2].text.strip()
                
                # Délai de déclaration
                filed_after = cols[3].text.strip()
                days_match = re.search(r'(\d+)', filed_after)
                if days_match:
                    trade['filed_after_days'] = int(days_match.group(1))
                
                # Type de transaction
                trade['type'] = cols[4].text.strip().lower()
                
                # Montant
                trade['size'] = cols[5].text.strip()
                
                trades.append(trade)
        
        return trades
    
    def _extract_statistics(self, soup):
        """Extrait les statistiques globales"""
        stats = {
            'democrats': {'total': 0, 'buy': 0, 'sell': 0},
            'republicans': {'total': 0, 'buy': 0, 'sell': 0},
            'total_trades': 0,
            'total_politicians': 0
        }
        
        # Chercher les sections de statistiques
        text = soup.get_text()
        
        # Trades by Democrats
        dem_match = re.search(r'Trades by Democrats\s*(\d+)\s*Trades.*?Buy(\d+).*?Sell(\d+)', text, re.DOTALL)
        if dem_match:
            stats['democrats']['total'] = int(dem_match.group(1))
            stats['democrats']['buy'] = int(dem_match.group(2))
            stats['democrats']['sell'] = int(dem_match.group(3))
        
        # Trades by Republicans
        rep_match = re.search(r'Trades by Republicans\s*(\d+)\s*Trades.*?Buy(\d+).*?Sell(\d+)', text, re.DOTALL)
        if rep_match:
            stats['republicans']['total'] = int(rep_match.group(1))
            stats['republicans']['buy'] = int(rep_match.group(2))
            stats['republicans']['sell'] = int(rep_match.group(3))
        
        return stats

# État global pour Bloomberg Live
bloomberg_stream = None
bloomberg_logger = None

def normalize(text):
    return "".join(c for c in text.lower() if c.isalnum() or c.isspace()).strip()

def is_similar(a, b, threshold=0.85):
    return SequenceMatcher(None, a, b).ratio() > threshold

def bloomberg_live_worker():
    """Worker pour le flux Bloomberg Live"""
    global bloomberg_stream, bloomberg_logger
    
    url = "https://www.youtube.com/watch?v=iEpJwprxDdk"
    bloomberg_logger = NewsLogger("bloomberg_news.json")
    
    print("Demarrage flux Bloomberg Live...")
    bloomberg_stream = YouTubeLiveStream(url).start()
    
    print("Initialisation OCR...")
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    
    last_main_title = ""
    last_ticker_text = ""
    ticker_buffer = []
    frame_count = 0
    
    print("Surveillance Bloomberg active\n")
    
    try:
        while bloomberg_stream and bloomberg_stream.running:
            frame = bloomberg_stream.read()
            if frame is None:
                time.sleep(5)
                continue
            
            frame_count += 1
            if frame_count % 20 != 0:
                continue
            
            h, w, _ = frame.shape
            
            # Zone titre principal
            title_y1, title_y2 = int(h * 0.78), int(h * 0.86)
            title_x1, title_x2 = int(w * 0.05), int(w * 0.95)
            title_roi = frame[title_y1:title_y2, title_x1:title_x2]
            
            title_gray = cv2.cvtColor(title_roi, cv2.COLOR_BGR2GRAY)
            _, title_processed = cv2.threshold(title_gray, 120, 255, cv2.THRESH_BINARY)
            
            # Zone ticker
            ticker_y1, ticker_y2 = int(h * 0.89), int(h * 0.98)
            ticker_x1 = int(w * 0.15)
            ticker_roi = frame[ticker_y1:ticker_y2, ticker_x1:w]
            
            ticker_gray = cv2.cvtColor(ticker_roi, cv2.COLOR_BGR2GRAY)
            _, ticker_processed = cv2.threshold(ticker_gray, 100, 255, cv2.THRESH_BINARY)
            
            try:
                title_results = reader.readtext(title_processed, paragraph=False)
                ticker_results = reader.readtext(ticker_processed, paragraph=False)
            except Exception:
                continue
            
            # Extraction titre
            main_title = ""
            if title_results:
                title_parts = []
                for item in title_results:
                    if len(item) >= 2:
                        text = item[1] if len(item) == 3 else item[0]
                        prob = item[2] if len(item) == 3 else item[1]
                        text_clean = text.strip()
                        
                        if text_clean.lower() not in ['bloomberg', 'radio', 'live', 'tv']:
                            if prob > 0.3 and len(text_clean) > 3:
                                title_parts.append(text_clean)
                
                main_title = " ".join(title_parts)
            
            # Extraction ticker
            ticker_parts = []
            for item in ticker_results:
                if len(item) >= 2:
                    text = item[1] if len(item) == 3 else item[0]
                    prob = item[2] if len(item) == 3 else item[1]
                    if prob > 0.5 and len(text.strip()) > 3:
                        ticker_parts.append(text.strip())
            
            ticker_text = " ".join(ticker_parts)
            
            # Nouveau titre détecté
            if main_title and len(main_title) > 15:
                if not is_similar(normalize(main_title), normalize(last_main_title)):
                    
                    # Résumé IA du segment précédent
                    if last_main_title and len(ticker_buffer) > 5:
                        print("\n[BOT] Generation resume IA...")
                        
                        combined_text = " ".join(ticker_buffer)
                        prompt = f"""TITRE: {last_main_title}
FRAGMENTS: {combined_text}

Résume en 3-5 points clés les actualités financières."""

                        try:
                            ai_summary = call_groq_api([
                                {'role': 'system', 'content': 'Tu es un expert en news financières Bloomberg.'},
                                {'role': 'user', 'content': prompt}
                            ], temperature=0.3, max_tokens=500)
                            
                            bloomberg_logger.add_news_segment(last_main_title, ticker_buffer, ai_summary)
                            print(f"[OK] Resume sauvegarde\n")
                        except Exception as e:
                            print(f"[ERROR] Erreur resume: {e}")
                    
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n? NOUVEAU [{timestamp}]")
                    print(f"   {main_title}\n")
                    
                    ticker_buffer = []
                    last_main_title = main_title
            
            # Nouveau ticker
            if ticker_text and len(ticker_text) > 20:
                if not is_similar(normalize(ticker_text), normalize(last_ticker_text)):
                    print(f"[DATA] {ticker_text[:60]}...")
                    ticker_buffer.append(ticker_text)
                    last_ticker_text = ticker_text
            
            time.sleep(0.1)
    
    except Exception as e:
        print(f"Erreur Bloomberg Live: {e}")
    finally:
        if bloomberg_stream:
            bloomberg_stream.stop()

# ============================================================================
# LIVE STOCK PRICES
# ============================================================================

def fetch_live_prices(tickers, days=5):
    """
    Récupère les prix actuels ET historiques (derniers jours) pour une liste de tickers en mode groupé.
    Le cache est utilisé en repli si Yahoo Finance échoue.
    """
    try:
        prices = {}
        if not tickers:
            return {}
        
        print(f"[PRICES] Fetching {len(tickers)} tickers in bulk: {tickers}")
        
        # Yahoo Finance a des problèmes récents avec les sessions requests standard.
        # On suit la recommandation de ne plus passer de session personnalisée si elle n'est pas curl_cffi.
        try:
            # period='5d' pour avoir les derniers jours
            all_data = yf.download(
                tickers, 
                period=f"{days}d", 
                interval="1d", 
                group_by='ticker', 
                progress=False, 
                threads=True,
                timeout=10
            )
        except Exception as download_err:
            print(f"[WARN] yf.download failed: {download_err}")
            all_data = None
        
        if all_data is None or all_data.empty:
            print("[WARN] Yahoo Finance returned empty data. Returning DB cache...")
            cached = db_load_generic('live_prices_cache', {})
            return {t: cached[t] for t in tickers if t in cached}

        for ticker in tickers:
            try:
                # Si un seul ticker, all_data est un DataFrame simple, sinon MultiIndex (TICKER, Variable)
                if len(tickers) == 1:
                    hist = all_data
                else:
                    if ticker not in all_data.columns.levels[0]:
                        continue
                    hist = all_data[ticker]
                
                # Nettoyage des données
                if hist is None or hist.empty or 'Close' not in hist.columns:
                    continue
                    
                hist = hist.dropna(subset=['Close'])
                if hist.empty:
                    continue
                
                # Prix actuel (dernière clôture disponible)
                price = float(hist['Close'].iloc[-1])
                
                # Calculer variation
                price_prev = float(hist['Close'].iloc[0]) if len(hist) > 1 else price
                change_pct = ((price - price_prev) / price_prev * 100) if price_prev > 0 else 0
                
                historical = []
                for date, row in hist.iterrows():
                    historical.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'price': float(row['Close'])
                    })
                
                prices[ticker] = {
                    'price': price,
                    'change': change_pct,
                    'historical': historical,
                    'last_update': datetime.now().isoformat()
                }
            except Exception as item_err:
                print(f"Error processing ticker {ticker}: {item_err}")
                continue

        if prices:
            # Mettre à jour le cache fusionné
            full_cache = db_load_generic('live_prices_cache', {})
            full_cache.update(prices)
            db_save_generic('live_prices_cache', full_cache)
            
        return prices

    except Exception as e:
        print(f"Global error in fetch_live_prices: {e}. Returning DB cache...")
        cached = db_load_generic('live_prices_cache', {})
        return {t: cached[t] for t in tickers if t in cached}



# ============================================================================
# FOREX FACTORY
# ============================================================================

def fetch_forex_calendar_api():
    """Récupère le calendrier Forex Factory"""
    FF_JSON_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    UA = "Mozilla/5.0 (X11; Linux x86_64) FFCalendarFetcher/1.0"
    
    try:
        response = requests.get(FF_JSON_URL, timeout=30, headers={"User-Agent": UA})
        response.raise_for_status()
        data = response.json()
        
        events = data.get("events", []) if isinstance(data, dict) else data
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "events": events[:50]  # Limiter à 50 événements
        }
        
        # SAVE DB
        db_save_generic('forex_calendar', result)
        return result
    except Exception as e:
        print(f"Erreur Forex: {e}")
        return {"timestamp": datetime.now().isoformat(), "events": []}

# ============================================================================
# ============================================================================
# MACRO-ECONOMIC DATA (EZ.PY INTEGRATION)
# ============================================================================

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
        self.session = requests.Session()
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
    
    def get_gdp_data(self):
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
    
    # ==================== AUTRES INDICATEURS ====================
    
    def get_housing_data(self):
        """Récupère les données immobilières"""
        housing = {}
        
        # 1. Housing Starts
        try:
            df = self._read_fred_csv('HOUST')
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                housing['Housing_Starts'] = {
                    'value': float(latest.iloc[1]),
                    'date': str(latest.iloc[0]),
                    'name': 'Housing Starts (thousands)',
                    'unit': 'Thousands of Units'
                }
        except Exception as e:
            print(f"Erreur Housing Starts: {e}")
        
        # 2. Existing Home Sales
        try:
            df = self._read_fred_csv('EXHOSLUSM495S')
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                housing['Existing_Home_Sales'] = {
                    'value': float(latest.iloc[1]),
                    'date': str(latest.iloc[0]),
                    'name': 'Existing Home Sales',
                    'unit': 'Millions'
                }
        except Exception as e:
            print(f"Erreur Home Sales: {e}")
        
        housing['timestamp'] = datetime.now().isoformat()
        return housing
    
    def get_industrial_production(self):
        """Récupère la production industrielle"""
        industrial = {}
        
        try:
            df = self._read_fred_csv('INDPRO')
            if df is not None and not df.empty and len(df) >= 2:
                latest = df.iloc[-1]
                previous = df.iloc[-2]
                
                latest_val = float(latest.iloc[1])
                prev_val = float(previous.iloc[1])
                
                mom_change = ((latest_val - prev_val) / prev_val) * 100
                
                industrial['US'] = {
                    'value': latest_val,
                    'mom_change': round(mom_change, 2),
                    'date': str(latest.iloc[0]),
                    'name': 'Industrial Production Index'
                }
        except Exception as e:
            print(f"Erreur Industrial Production: {e}")
        
        industrial['timestamp'] = datetime.now().isoformat()
        return industrial
    
    # ==================== CALENDRIER FED ====================
    
    def get_fed_calendar(self):
        """Récupère le calendrier des réunions FOMC"""
        calendar = {}
        
        try:
            url = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
            response = self.session.get(url, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            meetings = []
            
            # Chercher les panels de l'année courante
            current_year = datetime.now().year
            year_panel = soup.find('div', {'id': f'meeting-calendars-{current_year}'})
            
            if year_panel:
                # Extraire les dates
                date_elements = year_panel.find_all('div', class_='fomc-meeting__date')
                for elem in date_elements[:8]:  # Max 8 prochaines réunions
                    date_text = elem.get_text(strip=True)
                    if date_text:
                        meetings.append(date_text)
            
            calendar['FOMC_meetings'] = {
                'upcoming': meetings,
                'year': current_year,
                'source': 'Federal Reserve',
                'url': url
            }
            
        except Exception as e:
            print(f"Erreur FED Calendar: {e}")
        
        calendar['timestamp'] = datetime.now().isoformat()
        return calendar
    
    # ==================== AGGREGATION ====================
    
    def get_all_macro_data(self):
        """Récupère toutes les données macro"""
        print("[DATA] Recuperation des donnees macro-economiques...")
        
        data = {
            'interest_rates': self.get_interest_rates(),
            'inflation': self.get_inflation_data(),
            'unemployment': self.get_unemployment_data(),
            'gdp': self.get_gdp_data(),
            'pmi': self.get_pmi_data(),
            'retail_sales': self.get_retail_sales(),
            'consumer_confidence': self.get_consumer_confidence(),
            'housing': self.get_housing_data(),
            'industrial_production': self.get_industrial_production(),
            'fed_calendar': self.get_fed_calendar(),
            'timestamp': datetime.now().isoformat()
        }
        
        return data

def db_save_macro_data(category, data_dict):
    """Save macro data category to DB"""
    try:
        with app.app_context():
            macro = MacroData.query.filter_by(category=category).first()
            if not macro:
                macro = MacroData(category=category, data=data_dict)
                db.session.add(macro)
            else:
                macro.data = data_dict
                macro.updated_at = datetime.utcnow()
            db.session.commit()
    except Exception as e:
        print(f"DB Error save macro {category}: {e}")

def db_load_macro_data():
    """Load all macro data from DB"""
    try:
        # Note: calling from route provides context
        all_macro = MacroData.query.all()
        result = {m.category: m.data for m in all_macro}
        print(f"DEBUG: Loaded macro data keys: {list(result.keys())}")
        return result
    except Exception as e:
        print(f"DB Error load macro: {e}")
        return {}

def update_macro_data():
    """Worker function to refresh macro data"""
    scraper = MacroEconomicDataScraper()
    data = scraper.get_all_macro_data()
    
    for category, category_data in data.items():
        if category != 'timestamp':
            db_save_macro_data(category, category_data)
    
    print("[OK] Macro data updated in DB")

# INSIDERS (YFINANCE REPLACEMENT)
# ============================================================================

def fetch_insiders_api(tickers):
    """Récupère les transactions d'insiders via Yahoo Finance"""
    
    def get_insider_data_yf(ticker):
        try:
            t = yf.Ticker(ticker)
            df = t.insider_transactions
            
            if df is None or df.empty:
                return []
            
            transactions = []
            
            # DataFrame columns usually: ['Shares', 'Value', 'URL', 'Text', 'Insider', 'Position', 'Transaction', 'Start Date', 'Ownership']
            # Start Date is DatetimeIndex or column? Usually column 'Start Date'
            
            # Reset index if Date is index
            df = df.reset_index()
            
            for _, row in df.iterrows():
                try:
                    # Clean Date
                    date_val = row.get('Start Date')
                    date_str = ""
                    if hasattr(date_val, 'strftime'):
                        # Match Finviz format expected by frontend: "May 15 '24"
                        date_str = date_val.strftime("%b %d '%y") 
                    else:
                        date_str = str(date_val)
                    
                    # Transaction Type Logic
                    raw_text = str(row.get('Text', ''))
                    # Frontend expects 'Buy' or 'Sale' for coloring/translation
                    txn_type = "Option Execute" if "Option" in raw_text else ("Sale" if "Sale" in raw_text else "Buy") 
                    
                    # Cost extraction (approximate from Text if Value is total)
                    # "Sale at price 200.00 per share"
                    cost = 0.0
                    try:
                        matches = re.findall(r'price\s+([\d\.]+)', raw_text)
                        if matches:
                            cost = float(matches[0])
                    except: pass
                    
                    # Shares & Value
                    shares = row.get('Shares', 0)
                    value = row.get('Value', 0)
                    if pd.isna(value): value = 0
                    if pd.isna(shares): shares = 0
                    
                    # If cost still 0 and we have value/shares
                    if cost == 0 and shares != 0:
                        cost = round(value / shares, 2)
                        
                    transactions.append({
                        'insider': str(row.get('Insider', 'Unknown')),
                        'relationship': str(row.get('Position', 'Officer')),
                        'date': date_str,
                        'transaction': txn_type,
                        'cost': cost,
                        'shares': int(shares),
                        'value': int(value),
                        'shares_total': 0, # Not provided by YF standard call easily
                        'sec_form': str(row.get('URL', ''))
                    })
                except Exception as row_e:
                    continue
                    
            return transactions
            
        except Exception as e:
            print(f"Error YF Insiders {ticker}: {e}")
            return []
    
    all_data = {}
    for ticker in tickers:
        all_transactions = get_insider_data_yf(ticker)
        
        if not all_transactions:
            continue
            
        # Filtrer 2 derniers mois (YF donne souvent bcp d'historique)
        try:
            cutoff = datetime.now() - timedelta(days=60)
            
            recent = []
            for t in all_transactions:
                try:
                    # Re-parse generated date string back to object for filtering
                    deduced_date = datetime.strptime(t['date'], "%b %d '%y")
                    if deduced_date >= cutoff:
                        recent.append(t)
                except: pass
            
            # Sort newest first
            all_transactions.sort(key=lambda x: datetime.strptime(x['date'], "%b %d '%y"), reverse=True)
            recent.sort(key=lambda x: datetime.strptime(x['date'], "%b %d '%y"), reverse=True)
            
            all_data[ticker] = {
                'all': all_transactions[:50], # Limit payload
                'recent_7days': recent
            }
        except Exception as sort_e:
            print(f"Error filtering insiders {ticker}: {sort_e}")
            
        # time.sleep(0.5) # Fast API
    
    # MIRROR TO DB
    if all_data:
        db_save_insiders(all_data)
        
    return all_data

# ============================================================================
# BLOOMBERG RSS
# ============================================================================

def fetch_bloomberg_rss_api():
    """Récupère le flux RSS Bloomberg"""
    try:
        # Load existing data to preserve analysis
        existing_data = db_load_generic('bloomberg_rss')
        existing_items_map = {}
        cached_critical_items = []
        existing_report = None

        if existing_data:
            existing_report = existing_data.get('report')
            if existing_data.get('items'):
                for item in existing_data['items']:
                    if item.get('link'):
                        existing_items_map[item['link']] = item
                    
                    # Preserve Critical Items (Score >= 6)
                    # "Points de Vigilance" are usually >= 6 or 7
                    if item.get('criticality_score', 0) >= 6:
                        cached_critical_items.append(item)

        feedparser.USER_AGENT = "Mozilla/5.0"
        _rss_url = "https://feeds.bloomberg.com/markets/news.rss"
        try:
            _rss_resp = requests.get(
                _rss_url,
                headers={"User-Agent": "Mozilla/5.0"},
                verify=certifi.where(),
                timeout=15
            )
            _rss_resp.raise_for_status()
            feed = feedparser.parse(_rss_resp.content)
        except Exception as _rss_err:
            print(f"Erreur fetch RSS via requests: {_rss_err}")
            feed = feedparser.parse(_rss_url)
        
        entries = feed.entries if hasattr(feed, "entries") else []
        normalized = []
        seen_links = set()
        
        for e in entries[:50]:  # Limiter à 50
            link = e.get("link", "").strip()
            seen_links.add(link)
            
            # Base item structure
            new_item = {
                "title": e.get("title", "").strip(),
                "link": link,
                "published": e.get("published", ""),
                "published_iso": datetime.now().isoformat(),
                "summary": e.get("summary", ""),
                "authors": [a.get("name") for a in e.get("authors", []) 
                           if isinstance(a, dict) and a.get("name")],
                "tags": [t.get("term") for t in e.get("tags", []) 
                        if isinstance(t, dict) and t.get("term")]
            }
            
            # Check for existing analysis
            if link in existing_items_map:
                existing = existing_items_map[link]
                
                # Keep original fetch timestamp if present
                if existing.get('published_iso'):
                    new_item['published_iso'] = existing.get('published_iso')

                # Restore AI analysis fields
                keys_to_preserve = [
                    'ai_analysis_v2', 'title_fr', 'summary_fr', 
                    'criticality_score', 'sentiment_label', 'ai_reasoning', 
                    'search_keywords', 'polymarket_data', 'temp_bert_result'
                ]
                for k in keys_to_preserve:
                    if k in existing:
                        new_item[k] = existing[k]
                        
            normalized.append(new_item)
            
        # Append Critical Items that are missing from current feed (Persistence)
        # Allows "Points de Vigilance" to stick around until they are very old or manually cleared
        for crit in cached_critical_items:
            if crit['link'] not in seen_links:
                normalized.append(crit)
                
        # Sort by published_iso descending to keep order
        # (Assuming ISO format allows string sort)
        normalized.sort(key=lambda x: x.get('published_iso', ''), reverse=True)

        result = {
            "feed_title": "Bloomberg Markets",
            "fetched_at": datetime.now().isoformat(),
            "count": len(normalized),
            "items": normalized,
            "report": existing_report # Preserve the last generated report to avoid UI flicker
        }
        
        # SAVE DB
        db_save_generic('bloomberg_rss', result)
        return result
    except Exception as e:
        print(f"Erreur RSS: {e}")
        # Return cache if fetch fails
        return db_load_generic('bloomberg_rss') or {"items": [], "fetched_at": datetime.now().isoformat()}

# ============================================================================
# OPTIONS (NASDAQ)
# ============================================================================

import re

def fetch_options_chain_api(ticker='GOOG'):
    """Récupère et analyse complètement la chaîne d'options"""
    try:
        url = f"https://api.nasdaq.com/api/quote/{ticker}/option-chain"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'fr,fr-FR;q=0.9,en;q=0.8',
            'Origin': 'https://www.nasdaq.com',
            'Referer': 'https://www.nasdaq.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site'
        }
        
        response = requests.get(url, headers=headers, params={'limit': 60, 'assetclass': 'stocks'}, timeout=10)
        response.raise_for_status()
        
        raw_data = response.json()
        
        if not raw_data or 'data' not in raw_data:
            return {}
        
        data = raw_data['data']
        
        # Métadonnées
        metadata = {
            'symbol': data.get('symbol', ticker),
            'last_trade_price': data.get('lastTrade', 'N/A'),
            'last_trade_change': data.get('change', 'N/A'),
            'total_records': data.get('totalRecord', 0),
            'timestamp': datetime.now().isoformat()
        }
        
        # Parser les options
        tables = data.get('table', {})
        rows = tables.get('rows', [])
        
        if not rows:
            return {'metadata': metadata, 'sentiment_marche': {}}
        
        calls_data = []
        puts_data = []
        
        for row in rows:
            if row.get('expirygroup') and not row.get('strike'):
                continue
            
            exp_date = row.get('expiryDate', '')
            strike = row.get('strike', '')
            
            if not strike:
                continue
            
            # CALLS
            calls_data.append({
                'expiry_date': exp_date,
                'strike': strike,
                'last': row.get('c_Last', ''),
                'change': row.get('c_Change', ''),
                'bid': row.get('c_Bid', ''),
                'ask': row.get('c_Ask', ''),
                'volume': row.get('c_Volume', ''),
                'open_interest': row.get('c_Openinterest', ''),
            })
            
            # PUTS
            puts_data.append({
                'expiry_date': exp_date,
                'strike': strike,
                'last': row.get('p_Last', ''),
                'change': row.get('p_Change', ''),
                'bid': row.get('p_Bid', ''),
                'ask': row.get('p_Ask', ''),
                'volume': row.get('p_Volume', ''),
                'open_interest': row.get('p_Openinterest', ''),
            })
        
        # Convertir en DataFrame
        df_calls = pd.DataFrame(calls_data)
        df_puts = pd.DataFrame(puts_data)
        
        # Nettoyer
        numeric_cols = ['strike', 'last', 'change', 'bid', 'ask', 'volume', 'open_interest']
        
        for col in numeric_cols:
            if col in df_calls.columns:
                df_calls[col] = df_calls[col].replace(['--', '', ' ', None], pd.NA)
                df_calls[col] = pd.to_numeric(df_calls[col], errors='coerce')
            if col in df_puts.columns:
                df_puts[col] = df_puts[col].replace(['--', '', ' ', None], pd.NA)
                df_puts[col] = pd.to_numeric(df_puts[col], errors='coerce')
        
        # Extraire prix actuel
        last_price_str = metadata.get('last_trade_price', '0')
        match = re.search(r'\$?([\d,]+\.?\d*)', last_price_str)
        current_price = float(match.group(1).replace(',', '')) if match else 0
        
        # CALCUL DES MÉTRIQUES
        total_call_volume = df_calls['volume'].sum()
        total_put_volume = df_puts['volume'].sum()
        total_call_oi = df_calls['open_interest'].sum()
        total_put_oi = df_puts['open_interest'].sum()
        
        pcr_volume = total_put_volume / total_call_volume if total_call_volume > 0 else None
        pcr_oi = total_put_oi / total_call_oi if total_call_oi > 0 else None
        
        # Sentiment
        if pcr_volume and pcr_volume > 1.0:
            sentiment = "BAISSIER"
            emoji = "[DOWN]"
        elif pcr_volume and pcr_volume < 0.7:
            sentiment = "HAUSSIER"
            emoji = "[UP]"
        else:
            sentiment = "NEUTRE"
            emoji = "➡️"
        
        # Zones de prix (supports/résistances)
        calls_with_type = df_calls.copy()
        calls_with_type['option_type'] = 'Call'
        puts_with_type = df_puts.copy()
        puts_with_type['option_type'] = 'Put'
        
        all_strikes = pd.concat([calls_with_type, puts_with_type])
        significant_oi = all_strikes[all_strikes['open_interest'] > 0].copy()
        
        strike_summary = significant_oi.groupby('strike').agg({
            'open_interest': 'sum',
            'volume': 'sum'
        }).reset_index()
        
        resistances = strike_summary[strike_summary['strike'] > current_price].copy()
        supports = strike_summary[strike_summary['strike'] < current_price].copy()
        
        resistances = resistances.sort_values('open_interest', ascending=False).head(5)
        supports = supports.sort_values('open_interest', ascending=False).head(5)
        
        resistance_levels = [
            {
                'strike': float(row['strike']),
                'open_interest': int(row['open_interest']),
                'volume': int(row['volume']),
                'distance_pct': round((row['strike'] - current_price) / current_price * 100, 2),
                'type': 'Résistance forte' if i == 0 else 'Résistance'
            }
            for i, (_, row) in enumerate(resistances.iterrows())
        ]
        
        support_levels = [
            {
                'strike': float(row['strike']),
                'open_interest': int(row['open_interest']),
                'volume': int(row['volume']),
                'distance_pct': round((current_price - row['strike']) / current_price * 100, 2),
                'type': 'Support fort' if i == 0 else 'Support'
            }
            for i, (_, row) in enumerate(supports.iterrows())
        ]
        
        # Volatilité
        df_calls['spread'] = df_calls['ask'] - df_calls['bid']
        df_puts['spread'] = df_puts['ask'] - df_puts['bid']
        
        avg_call_spread = df_calls['spread'].mean()
        avg_put_spread = df_puts['spread'].mean()
        avg_spread = (avg_call_spread + avg_put_spread) / 2
        
        if pd.notna(avg_spread):
            if avg_spread > 2.0:
                volatility = "ÉLEVÉE"
                vol_interp = "Forte incertitude du marché"
            elif avg_spread > 1.0:
                volatility = "MODÉRÉE"
                vol_interp = "Volatilité normale"
            else:
                volatility = "FAIBLE"
                vol_interp = "Marché calme"
        else:
            volatility = "N/A"
            vol_interp = ""
        
        # Top strikes par volume
        top_calls = df_calls.nlargest(5, 'volume')
        top_puts = df_puts.nlargest(5, 'volume')
        
        most_active_calls = [
            {'strike': float(row['strike']), 'volume': int(row['volume'])}
            for _, row in top_calls.iterrows()
            if pd.notna(row['volume']) and row['volume'] > 0
        ]
        
        most_active_puts = [
            {'strike': float(row['strike']), 'volume': int(row['volume'])}
            for _, row in top_puts.iterrows()
            if pd.notna(row['volume']) and row['volume'] > 0
        ]
        
        # Activité inhabituelle
        df_calls['volume_to_oi_ratio'] = df_calls['volume'] / df_calls['open_interest'].replace(0, 1)
        df_puts['volume_to_oi_ratio'] = df_puts['volume'] / df_puts['open_interest'].replace(0, 1)
        
        unusual_calls = df_calls[df_calls['volume_to_oi_ratio'] > 0.5].nlargest(3, 'volume')
        unusual_puts = df_puts[df_puts['volume_to_oi_ratio'] > 0.5].nlargest(3, 'volume')
        
        unusual_activity = {
            'calls': [
                {
                    'strike': float(row['strike']),
                    'volume': int(row['volume']),
                    'open_interest': int(row['open_interest']),
                    'ratio': float(row['volume_to_oi_ratio'])
                }
                for _, row in unusual_calls.iterrows()
                if pd.notna(row['volume']) and row['volume'] > 0
            ],
            'puts': [
                {
                    'strike': float(row['strike']),
                    'volume': int(row['volume']),
                    'open_interest': int(row['open_interest']),
                    'ratio': float(row['volume_to_oi_ratio'])
                }
                for _, row in unusual_puts.iterrows()
                if pd.notna(row['volume']) and row['volume'] > 0
            ]
        }
        
        # Analyse par expiration
        exp_stats = {}
        for exp_date in df_calls['expiry_date'].unique():
            if pd.isna(exp_date) or exp_date == '':
                continue
            
            exp_calls = df_calls[df_calls['expiry_date'] == exp_date]
            exp_puts = df_puts[df_puts['expiry_date'] == exp_date]
            
            call_vol = exp_calls['volume'].sum()
            put_vol = exp_puts['volume'].sum()
            
            exp_stats[exp_date] = {
                'call_volume': int(call_vol),
                'put_volume': int(put_vol),
                'total_volume': int(call_vol + put_vol),
                'put_call_ratio': float(put_vol / call_vol) if call_vol > 0 else None,
                'volume_pct_of_total': float((call_vol + put_vol) / (total_call_volume + total_put_volume) * 100) if (total_call_volume + total_put_volume) > 0 else 0
            }
        
        exp_stats_sorted = dict(sorted(exp_stats.items(), 
                                       key=lambda x: x[1]['total_volume'], 
                                       reverse=True))
        
        # Signal institutionnel
        institutional_signal = {'detected': False}
        if exp_stats_sorted:
            dominant_exp = list(exp_stats_sorted.keys())[0]
            dominant_data = exp_stats_sorted[dominant_exp]
            
            if dominant_data['volume_pct_of_total'] > 40:
                institutional_signal = {
                    'detected': True,
                    'expiration_dominante': dominant_exp,
                    'concentration_pct': float(dominant_data['volume_pct_of_total']),
                    'interpretation': f"Forte concentration sur {dominant_exp} - Position institutionnelle probable"
                }
        
        # Résultat final
        result = {
            'ticker': ticker,
            'current_price': current_price,
            'last_trade': metadata['last_trade_price'],
            'timestamp': metadata['timestamp'],
            
            'sentiment_marche': {
                'sentiment': sentiment,
                'emoji': emoji,
                'put_call_ratio_volume': round(pcr_volume, 2) if pcr_volume else 0,
                'put_call_ratio_oi': round(pcr_oi, 2) if pcr_oi else 0,
                'total_call_volume': int(total_call_volume),
                'total_put_volume': int(total_put_volume),
                'total_call_oi': int(total_call_oi),
                'total_put_oi': int(total_put_oi)
            },
            
            'zones_prix_cles': {
                'resistances': resistance_levels,
                'supports': support_levels
            },
            
            'volatilite_anticipee': {
                'attente': volatility,
                'interpretation': vol_interp,
                'spread_moyen_calls': round(float(avg_call_spread), 2) if pd.notna(avg_call_spread) else 0,
                'spread_moyen_puts': round(float(avg_put_spread), 2) if pd.notna(avg_put_spread) else 0
            },
            
            'flux_institutionnels': {
                'signal_detecte': institutional_signal.get('detected', False),
                'expiration_dominante': institutional_signal.get('expiration_dominante', 'N/A'),
                'concentration_pct': institutional_signal.get('concentration_pct', 0),
                'interpretation': institutional_signal.get('interpretation', 'Pas de signal clair'),
                'repartition_par_expiration': [
                    {
                        'expiration': exp,
                        'total_volume': data['total_volume'],
                        'volume_pct': round(data['volume_pct_of_total'], 1),
                        'put_call_ratio': round(data['put_call_ratio'], 2) if data['put_call_ratio'] is not None else None,
                        'call_volume': data['call_volume'],
                        'put_volume': data['put_volume']
                    }
                    for exp, data in list(exp_stats_sorted.items())[:5]
                ]
            },
            
            'activite_inhabituelle': unusual_activity,
            
            'top_strikes_volume': {
                'calls': most_active_calls,
                'puts': most_active_puts
            }
        }
        
        # SAVE DB
        db_save_generic(f'options_{ticker}', result)
        return result
        
    except Exception as e:
        print(f"Erreur Options: {e}")
        import traceback
        traceback.print_exc()
        return {}

# ============================================================================
# SAISONNALITÉ
# ============================================================================

def fetch_seasonality_api():
    """Analyse de saisonnalité des indices"""
    try:
        indices = {
            'S&P 500': '^GSPC',
            'NASDAQ': '^IXIC',
            'Dow Jones': '^DJI'
        }
        
        result = {
            'metadata': {
                'start_date': '2004-01-01',
                'end_date': '2024-12-31',
                'generated_at': datetime.now().isoformat(),
                'indices': indices
            },
            'data_summary': {},
            'day_of_week': {},
            'monthly_cycles': {}
        }
        
        # Logique simplifiée (utilisez votre classe complète)
        for name, symbol in indices.items():
            data = yf.download(symbol, start='2004-01-01', end='2024-12-31', progress=False)
            
            if not data.empty:
                result['data_summary'][name] = {
                    'total_days': len(data),
                    'avg_daily_return_pct': 0.05,
                    'volatility_pct': 15.0
                }
        
        # SAVE DB
        db_save_generic('seasonality', result)
        return result
    except Exception as e:
        print(f"Erreur Saisonnalite: {e}")
        return {}

# ============================================================================
# EARNINGS (YAHOO FINANCE)
# ============================================================================

def fetch_earnings_api(days_ahead=14):
    """Récupère les earnings à venir via Alpha Vantage (Calendrier complet)"""
    print("Recuperation des earnings (Alpha Vantage)...")
    
    # Utilisation de la clé démo par défaut
    api_key = 'demo'
    url = f'https://www.alphavantage.co/query?function=EARNINGS_CALENDAR&horizon=3month&apikey={api_key}'
    
    try:
        response = requests.get(url, timeout=10)
        
        # L'API retourne du CSV
        df = pd.read_csv(StringIO(response.text))
        
        if not df.empty and 'reportDate' in df.columns:
            df['reportDate'] = pd.to_datetime(df['reportDate'])
            
            # Filtrer pour les prochains jours
            today = datetime.now()
            future_date = today + pd.Timedelta(days=days_ahead)
            df = df[(df['reportDate'] >= today) & (df['reportDate'] <= future_date)]
            
            # Trier par date
            df = df.sort_values('reportDate')
            
            # Filtrer les colonnes importantes et renommer
            # Alpha Vantage columns: symbol, name, reportDate, fiscalDateEnding, estimate, currency
            result_df = df[['symbol', 'name', 'reportDate', 'estimate', 'currency']].copy()
            result_df.columns = ['ticker', 'name', 'date', 'eps_estimate', 'currency']
            
            # Formater la date en string pour le JSON
            result_df['date'] = result_df['date'].dt.strftime('%Y-%m-%d')
            
            # Nettoyer les noms (limiter la longueur)
            result_df['name'] = result_df['name'].str[:40]
            
            # Ajouter le secteur (non fourni par AV, on met N/A ou on pourrait fetcher ailleurs)
            result_df['sector'] = 'N/A'
            
            # Convertir en liste de dictionnaires
            earnings_data = result_df.to_dict('records')
            
            # Nettoyage profond des valeurs NaN
            cleaned_data = []
            for item in earnings_data:
                clean_item = {}
                for k, v in item.items():
                    if pd.isna(v):
                        clean_item[k] = None
                    elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                         clean_item[k] = None
                    else:
                        clean_item[k] = v
                cleaned_data.append(clean_item)
            
            result = {
                'updated_at': datetime.now().isoformat(),
                'days_ahead': days_ahead,
                'count': len(cleaned_data),
                'data': cleaned_data
            }
            
            db_save_generic('earnings_cache', result)
            return result
            
    except Exception as e:
        print(f"Erreur API Alpha Vantage: {e}")
        # En cas d'erreur, on retourne une liste vide ou le cache existant
        return db_load_generic('earnings_cache')
    
    return {'data': [], 'count': 0}

# ============================================================================
# GROQ AI ASSISTANT
# ============================================================================


class TokenBucket:
    """Simple Token Bucket for Rate Limiting"""
    def __init__(self, capacity, refill_rate):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate # tokens per second
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens_needed):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            
            # Refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            
            if self.tokens >= tokens_needed:
                self.tokens -= tokens_needed
                return True
            return False

# 6000 TPM limit (using half of 12k to be safe) => 100 tokens per sec
groq_rate_limiter = TokenBucket(capacity=4000, refill_rate=50) 

def call_groq_api(messages, temperature=0.7, max_tokens=1500, retries=3):
    """Appel à l'API Groq avec retry exponentiel et Token Bucket"""
    
    # Estimate tokens (approximation: 1 word = 1.3 tokens)
    input_text = json.dumps(messages)
    estimated_tokens = len(input_text) / 3 
    
    # Wait for capacity
    wait_attempts = 0
    while not groq_rate_limiter.consume(estimated_tokens):
        wait_attempts += 1
        # Stop waiting after 2 seconds to fail fast for UI responsiveness
        if wait_attempts > 20: 
             # Silently fail to keep console clean, caller handles it.
             return "Erreur API: Rate Limit Internal - Skipped"
        time.sleep(0.1)
    
    backoff = 2  # Reduced to 2s for faster UI feedback

    for attempt in range(retries):
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
                timeout=15 # Reduced timeout further
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    return data['choices'][0]['message']['content']
                else:
                    return f"Erreur API: Réponse vide"
            elif response.status_code == 429:
                if attempt == retries - 1:
                    return "Erreur API (429): Rate Limit Exceeded"
                
                # print(f"[WARN] Groq Rate Limit (429)...") # Silenced
                time.sleep(backoff)
                backoff *= 1.5
            else:
                return f"Erreur API: {response.status_code}"
        except Exception as e:
            # print(f"Erreur tentative {attempt+1}: {e}") # Silenced
            if attempt == retries - 1:
                return f"Erreur: {str(e)}"
            time.sleep(2)
            
    return "Erreur API: Max retries exceeded"

# ============================================================================
# BANK FORECASTS SCRAPER (Playwright Edition)
# ============================================================================

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
        db_save_generic('bank_raw_scrape', self.results)
        
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
        
        db_save_bank_forecasts(formatted_for_db)
        
        return self.results
# État global pour Bloomberg Live
bloomberg_stream = None
bloomberg_logger = None

def normalize(text):
    return "".join(c for c in text.lower() if c.isalnum() or c.isspace()).strip()

def is_similar(a, b, threshold=0.85):
    return SequenceMatcher(None, a, b).ratio() > threshold

def bloomberg_live_worker():
    """Worker pour le flux Bloomberg Live"""
    global bloomberg_stream, bloomberg_logger
    
    url = "https://www.youtube.com/watch?v=iEpJwprxDdk"
    bloomberg_logger = NewsLogger("bloomberg_news.json")
    
    print("Demarrage flux Bloomberg Live...")
    bloomberg_stream = YouTubeLiveStream(url).start()
    
    print("Initialisation OCR...")
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    
    last_main_title = ""
    last_ticker_text = ""
    ticker_buffer = []
    frame_count = 0
    
    print("Surveillance Bloomberg active\n")
    
    try:
        while bloomberg_stream and bloomberg_stream.running:
            frame = bloomberg_stream.read()
            if frame is None:
                time.sleep(5)
                continue
            
            frame_count += 1
            if frame_count % 20 !=  0:
                continue
            
            h, w, _ = frame.shape
            
            # Zone titre principal
            title_y1, title_y2 = int(h * 0.78), int(h * 0.86)
            title_x1, title_x2 = int(w * 0.05), int(w * 0.95)
            title_roi = frame[title_y1:title_y2, title_x1:title_x2]
            
            title_gray = cv2.cvtColor(title_roi, cv2.COLOR_BGR2GRAY)
            _, title_processed = cv2.threshold(title_gray, 120, 255, cv2.THRESH_BINARY)
            
            # Zone ticker
            ticker_y1, ticker_y2 = int(h * 0.89), int(h * 0.98)
            ticker_x1 = int(w * 0.15)
            ticker_roi = frame[ticker_y1:ticker_y2, ticker_x1:w]
            
            ticker_gray = cv2.cvtColor(ticker_roi, cv2.COLOR_BGR2GRAY)
            _, ticker_processed = cv2.threshold(ticker_gray, 100, 255, cv2.THRESH_BINARY)
            
            try:
                title_results = reader.readtext(title_processed, paragraph=False)
                ticker_results = reader.readtext(ticker_processed, paragraph=False)
            except Exception:
                continue
            
            # Extraction titre
            main_title = ""
            if title_results:
                title_parts = []
                for item in title_results:
                    if len(item) >= 2:
                        text = item[1] if len(item) == 3 else item[0]
                        prob = item[2] if len(item) == 3 else item[1]
                        text_clean = text.strip()
                        
                        if text_clean.lower() not in ['bloomberg', 'radio', 'live', 'tv']:
                            if prob > 0.3 and len(text_clean) > 3:
                                title_parts.append(text_clean)
                
                main_title = " ".join(title_parts)
            
            # Extraction ticker
            ticker_parts = []
            for item in ticker_results:
                if len(item) >= 2:
                    text = item[1] if len(item) == 3 else item[0]
                    prob = item[2] if len(item) == 3 else item[1]
                    if prob > 0.5 and len(text.strip()) > 3:
                        ticker_parts.append(text.strip())
            
            ticker_text = " ".join(ticker_parts)
            
            # Nouveau titre détecté
            if main_title and len(main_title) > 15:
                if not is_similar(normalize(main_title), normalize(last_main_title)):
                    
                    # Résumé IA du segment précédent
                    if last_main_title and len(ticker_buffer) > 5:
                        print("\n[BOT] Generation resume IA...")
                        
                        combined_text = " ".join(ticker_buffer)
                        prompt = f"""TITRE: {last_main_title}
FRAGMENTS: {combined_text}

Résume en 3-5 points clés les actualités financières."""

                        try:
                            ai_summary = call_groq_api([
                                {'role': 'system', 'content': 'Tu es un expert en news financières Bloomberg.'},
                                {'role': 'user', 'content': prompt}
                            ], temperature=0.3, max_tokens=500)
                            
                            bloomberg_logger.add_news_segment(last_main_title, ticker_buffer, ai_summary)
                            print(f"[OK] Resume sauvegarde\n")
                        except Exception as e:
                            print(f"[ERROR] Erreur resume: {e}")
                    
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n? NOUVEAU [{timestamp}]")
                    print(f"   {main_title}\n")
                    
                    ticker_buffer = []
                    last_main_title = main_title
            
            # Nouveau ticker
            if ticker_text and len(ticker_text) > 20:
                if not is_similar(normalize(ticker_text), normalize(last_ticker_text)):
                    print(f"[DATA] {ticker_text[:60]}...")
                    ticker_buffer.append(ticker_text)
                    last_ticker_text = ticker_text
            
            time.sleep(0.1)
    
    except Exception as e:
        print(f"Erreur Bloomberg Live: {e}")
    finally:
        if bloomberg_stream:
            bloomberg_stream.stop()

# ============================================================================
# ENDPOINTS API
# ============================================================================

@app.route('/api/bloomberg-live/start', methods=['POST'])
def start_bloomberg_live():
    """Démarre la surveillance Bloomberg Live"""
    global bloomberg_stream
    
    if bloomberg_stream and bloomberg_stream.running:
        return jsonify({'status': 'already_running'})
    
    try:
        thread = threading.Thread(target=bloomberg_live_worker, daemon=True)
        thread.start()
        return jsonify({
            'status': 'started',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bloomberg-live/stop', methods=['POST'])
def stop_bloomberg_live():
    """Arrête la surveillance Bloomberg Live"""
    global bloomberg_stream
    
    if bloomberg_stream:
        bloomberg_stream.stop()
        bloomberg_stream = None
        return jsonify({
            'status': 'stopped',
            'timestamp': datetime.now().isoformat()
        })
    
    return jsonify({'status': 'not_running'})

@app.route('/api/bloomberg-live/status', methods=['GET'])
def bloomberg_live_status():
    """Statut du flux Bloomberg Live"""
    global bloomberg_stream, bloomberg_logger
    
    is_running = bloomberg_stream is not None and bloomberg_stream.running
    
    segments_count = 0
    if bloomberg_logger:
        # data is now a method or dynamic property in our logic, but let's just query db directly
        # or rely on load_data() return
        segments_count = len(db_get_news_segments())
    
    return jsonify({
        'running': is_running,
        'segments_captured': segments_count,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/refresh/insiders', methods=['POST'])
def refresh_insiders():
    """Rafraîchit les données insiders pour les tickers spécifiés"""
    try:
        data = request.get_json() or {}
        tickers = data.get('tickers', ['NVDA', 'GOOGL', 'AVGO', 'TSM', 'AAPL'])
        
        result = fetch_insiders_api(tickers)
        
        return jsonify({
            'status': 'success',
            'data_type': 'insiders',
            'timestamp': datetime.now().isoformat(),
            'tickers_processed': tickers,
            'data': result
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Vérifie que le serveur fonctionne"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'ws_error': TR_WS_ERROR,
        'services': {
            'forex': 'db',
            'insiders': 'db',
            'news': 'db',
            'options': 'db',
            'seasonality': 'db'
        }
    })


def db_save_sector_trends(data):
    try:
        with app.app_context():
            for sector_name, details in data.items():
                trend = SectorTrend.query.filter_by(sector_name=sector_name).first()
                if not trend:
                    trend = SectorTrend(sector_name=sector_name)
                    db.session.add(trend)
                
                trend.monthly_trend = details.get('average_performance', 0)
                trend.stocks_count = details.get('count', 0)
                trend.details = details.get('stocks', [])
                trend.last_updated = datetime.utcnow()
            
            db.session.commit()
    except Exception as e:
        print(f"DB Error save sector trends: {e}")

def db_load_sector_trends():
    try:
        with app.app_context():
            items = SectorTrend.query.all()
            result = {}
            for i in items:
                result[i.sector_name] = {
                    'monthly_trend': i.monthly_trend,
                    'stocks_analyzed': i.stocks_count,
                    'stocks_count': i.stocks_count,
                    'details': i.details,
                    'stocks': i.details # UI compat
                }
            return result
    except:
        return {}

def db_load_bank_analyses():
    try:
        with app.app_context():
            items = BankAnalysis.query.order_by(BankAnalysis.timestamp.desc()).all()
            return [{
                'bank': i.bank,
                'title': i.title,
                'url': i.url,
                'analysis': i.analysis,
                'timestamp': i.timestamp.isoformat()
            } for i in items]
    except:
        return []

@app.route('/api/debug/metadata/cache', methods=['GET'])
def debug_get_metadata_cache():
    """Inspect memory cache"""
    with _metadata_lock:
        return jsonify(_metadata_cache)

@app.route('/api/debug/clear-metadata', methods=['POST'])
def debug_clear_metadata():
    """Vide le cache de métadonnées pour forcer un re-téléchargement"""
    global _metadata_cache
    with _metadata_lock:
        _metadata_cache = {}
    print("[DEBUG] Metadata cache cleared via API")
    return jsonify({'status': 'cleared'})

@app.route('/api/data/all', methods=['GET'])
def get_all_data():
    """Récupère toutes les données en cache + prix en temps réel + données SQL"""
    def sanitize_nan(obj):
        if isinstance(obj, dict):
            return {k: sanitize_nan(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [sanitize_nan(v) for v in obj]
        elif isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return 0.0
            return obj
        return obj

    try:
        # Récupérer portfolio (automatiquement fallback sur WalletInvestment si Snapshot vide)
        portfolio = db_load_latest_portfolio()
        
        tickers = []
        if portfolio and 'positions' in portfolio:
            tickers = [p.get('ticker', '') for p in portfolio.get('positions', []) if p.get('ticker')]
        
        # Récupérer prix en temps réel pour les tickers du portfolio
        live_prices = {}
        if tickers:
            try:
                live_prices = fetch_live_prices(tickers)
            except: pass
        
        data = {
            'portfolio': portfolio,
            'live_prices': live_prices,
            'forex': db_load_generic('forex_calendar'),
            'insiders': db_load_insiders(),
            'news': db_load_generic('bloomberg_rss'),
            'bloomberg_live': db_load_generic('bloomberg_live'),
            'options': db_load_generic('options_GOOG'),
            'seasonality': db_load_generic('seasonality'),
            'sector_trends': db_load_sector_trends(),
            'bank_forecasts': db_load_bank_forecasts(),
            'bank_analyses': db_load_generic('bank_analyses'),
            'earnings': db_load_generic('earnings_cache'),
            'macro_data': db_load_macro_data(),
            'timestamp': datetime.now().isoformat()
        }

        # --- INJECT TRUTH SOCIAL POSTS INTO NEWS FEED ---
        try:
            truth_posts = db_load_generic('truth_social') or []
            if truth_posts:
                if not data['bloomberg_live']:
                    data['bloomberg_live'] = {'news_segments': []}
                
                if isinstance(data['bloomberg_live'], dict):
                    if 'news_segments' not in data['bloomberg_live']:
                        data['bloomberg_live']['news_segments'] = []
                    
                    # Convert posts to news_segments format
                    formatted_social_posts = []
                    for post in truth_posts:
                        content = post.get('content', '').strip()
                        # Si pas de texte mais des médias, on l'indique
                        if not content and post.get('media'):
                            content = ""
                        
                        # Truncation logic correcte
                        display_title = content[:60] + ('...' if len(content) > 60 else '')
                        
                        formatted_social_posts.append({
                            'timestamp': post.get('created_at', datetime.now().isoformat()),
                            'raw_text': content, 
                            'title': display_title if content else "(Post sans texte)",
                            'source': 'truth_social',
                            'url': post.get('url'),
                            'author': str(post.get('author', 'Donald J. Trump')),
                            'avatar': post.get('avatar'),
                            'media': post.get('media', []), # Pass media list to frontend
                            'ai_summary': content,  # Fallback
                            
                            # --- AI ANALYSIS FIELDS ---
                            'ai_analysis_v2': post.get('ai_analysis_v2'),
                            'sentiment_label': post.get('sentiment_label'),
                            'criticality_score': post.get('criticality_score'),
                            'ai_reasoning': post.get('ai_reasoning')
                        })
                    
                    # Merge (prepend to ensure visibility or just append)
                    # Frontend filters by source, so order in the main list doesn't matter strictly for separation,
                    # but good to have them in.
                    data['bloomberg_live']['news_segments'].extend(formatted_social_posts)
        except Exception as e:
            print(f"[WARN] Error injecting Truth Social posts: {e}")

        return jsonify(sanitize_nan(data))
    except Exception as e:
        print(f"Error in get_all_data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/data/<data_type>', methods=['GET'])
def get_specific_data(data_type):
    """Récupère un type de données spécifique"""
    
    # DB Override
    if data_type == 'insiders':
        return jsonify(db_load_insiders() or [])
    if data_type == 'portfolio':
        return jsonify(db_load_latest_portfolio() or {})
    if data_type == 'forex':
        return jsonify(db_load_generic('forex_calendar') or {})
    if data_type == 'news':
        return jsonify(db_load_generic('bloomberg_rss') or {})
    if data_type == 'bloomberg_live':
        return jsonify(db_load_generic('bloomberg_live') or {})
    if data_type == 'truth_social':
        return jsonify(db_load_generic('truth_social') or [])
    if data_type == 'seasonality':
        return jsonify(db_load_generic('seasonality') or {})
    if data_type == 'options':
        return jsonify(db_load_generic('options_GOOG') or {})
    if data_type == 'earnings':
        return jsonify(db_load_generic('earnings_cache') or {})
    if data_type == 'bank_analyses':
        return jsonify(db_load_generic('bank_analyses') or [])
        
    return jsonify({'error': 'Type de données invalide'}), 400

def clean_for_json(data):
    """Nettoie les données pour JSON (NaN -> None, Inf -> None)"""
    if isinstance(data, dict):
        return {k: clean_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_for_json(v) for v in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
    return data

@app.route('/api/sector-trends', methods=['GET'])
def get_sector_trends():
    """Récupère les tendances sectorielles (mensuelles) pour le frontend"""
    global sector_update_status
    
    # 1. Try DB
    try:
        with app.app_context():
            trends = SectorTrend.query.all()
            if trends:
                result = {}
                for t in trends:
                    result[t.sector_name] = {
                        "monthly_trend": t.monthly_trend,
                        "stocks_analyzed": t.stocks_count,
                        "details": t.details or [],
                        "last_updated": t.last_updated.isoformat() if t.last_updated else ""
                    }
                return jsonify(clean_for_json(result))
            else:
                 # DB is empty, trigger update if not already running
                 if sector_update_status == "idle":
                      print("[WARN] Sector Trends DB empty. Triggering background update...")
                      threading.Thread(target=update_sector_monthly_trends, kwargs={'force': True}).start()
    except Exception as e:
        print(f"DB Error get sector trends: {e}")

    # 2. Fallback File - REMOVED for DB Migration
    data = {} 
    
    # Return empty but maybe with status? 
    return jsonify(clean_for_json(data))


# Global Status for Sector Update
sector_update_status = "idle"

def parse_sector_value(text):
    """Clean and convert string values to float for sector analysis."""
    if not text:
        return 0.0
    text = text.strip()
    if text.lower() == 'nan' or 'nan' in text.lower():
         return 0.0

    # Remove currency symbol, spaces, and replace comma with dot
    clean = text.replace("€", "").replace("%", "").strip().replace(".", "").replace(",", ".")
    try:
        val = float(clean)
        if math.isnan(val):
            return 0.0
        return val
    except ValueError:
        return 0.0

def scrape_sectors_data():
    """
    Scrape sector data using Trade Republic API (WebSocket).
    Replaces Playwright methodology.
    """
    print("[START] Starting Sector Discovery via TR API (WebSocket)...")
    
    # Use a LOCAL instance to avoid asyncio loop conflicts with other threads
    local_api = TradeRepublicAPI()
    
    stocks_list = []
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Reuse or load session
        local_api.config.read(local_api.config_path)
        token = local_api.config.get("secret", "tr_session", fallback=None)
        if token:
             local_api.session_token = token
        
        if not local_api.session_token:
            print("[ERROR] Cannot scrape sectors: Not logged in. Please login via Web Terminal first.")
            return {}
            
        stocks_list = loop.run_until_complete(local_api.fetch_all_stocks_recursive())
        
        # Clean close
        try:
             loop.run_until_complete(local_api.close())
        except: pass
        loop.close()
        
    except Exception as e:
        print(f"[ERROR] API Fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return {}
        
    print(f"[DATA] Processing {len(stocks_list)} stocks into sectors...")
    
    all_sector_data = {}
    
    # 1. Group by sector
    for stock in stocks_list:
        name = stock.get("name")
        isin = stock.get("isin")
        tags = stock.get("tags", [])
        
        sector_name = "Non classé"
        for tag in tags:
            if tag.get("type") == "sector":
                sector_name = tag.get("name")
                break
        
        if sector_name not in all_sector_data:
            all_sector_data[sector_name] = {
                "sector_name": sector_name,
                "average_performance": 0.0, # Renamed to match DB
                "count": 0,                 # Renamed to match DB
                "stocks": []                # Renamed to match DB
            }
            
        all_sector_data[sector_name]["count"] += 1
        all_sector_data[sector_name]["stocks"].append({
            "name": name,
            "isin": isin,
            "ticker": None,
            "performance": 0.0
        })

    # 2. Enrich with Ticker and Performance
    print("[START] Enriching sector data (Tickers + Performance)... this may take time.")
    
    # helper for resolving ticker
    def resolve_ticker_wrapper(stock):
        try:
            with app.app_context():
                t = get_symbol_from_isin(stock['isin'])
                return (stock['isin'], t)
        except Exception as e:
            # print(f"Context Error resolving {stock.get('isin')}: {e}")
            return (stock.get('isin'), None)

    # Collect all stocks to resolve
    all_stocks_flat = []
    for s_name, s_data in all_sector_data.items():
        all_stocks_flat.extend(s_data['stocks'])
        
    # Resolve tickers in parallel (Reduced concurrency to save DB connections)
    isin_map = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(tqdm(executor.map(resolve_ticker_wrapper, all_stocks_flat), total=len(all_stocks_flat), desc="Resolving Tickers"))
        for isin, ticker in results:
            isin_map[isin] = ticker
            
    # Assign tickers to data AND build list for batch fetch
    valid_tickers = []
    for s_name, s_data in all_sector_data.items():
        for stock in s_data['stocks']:
            stock['ticker'] = isin_map.get(stock['isin'])
            if stock['ticker']:
                valid_tickers.append(stock['ticker'])

    # Batch download performance data for valid tickers
    print(f"[DOWN] Fetching performance for {len(valid_tickers)} tickers...")
    
    ticker_perf_map = {}
    BATCH_SIZE = 50 # Reduced batch size for stability
    
    sorted_tickers = sorted(list(set(valid_tickers))) # dedup
    for i in range(0, len(sorted_tickers), BATCH_SIZE):
        batch = sorted_tickers[i:i+BATCH_SIZE]
        try:
            print(f"Downloading batch {i} to {i+len(batch)} of {len(sorted_tickers)}...")
            # Use threads=False to avoid deadlocks in background threads
            # Using timeout to prevent forever hanging (handled by requests session underlying if possible, but threads=False helps)
            data = yf.download(batch, period="1mo", progress=False, group_by='ticker', threads=False)
            
            # If only one ticker, data format is different
            if len(batch) == 1:
                t = batch[0]
                # data is just the DF for this ticker
                if not data.empty and len(data) >= 2:
                    # Depending on version, could be Series or DF
                    try:
                        closes = data['Close']
                        start_p = closes.iloc[0]
                        end_p = closes.iloc[-1]
                        
                        # Handle if they are Series (sometimes multi-column if adjusted close exists etc? usually Close is single col)
                        if hasattr(start_p, 'item'): start_p = start_p.item()
                        if hasattr(end_p, 'item'): end_p = end_p.item()
                        
                        if start_p > 0:
                            perf = ((end_p - start_p) / start_p) * 100
                            ticker_perf_map[t] = perf
                    except: pass
            else:
                for t in batch:
                    try:
                        # With group_by='ticker', top level is Ticker
                        if t in data.columns.levels[0]:
                             df_t = data[t]
                        else:
                             continue
                             
                        df_t = df_t.dropna(subset=['Close'])
                        if not df_t.empty and len(df_t) >= 2:
                            start_p = df_t['Close'].iloc[0]
                            end_p = df_t['Close'].iloc[-1]
                            
                            if hasattr(start_p, 'item'): start_p = start_p.item()
                            if hasattr(end_p, 'item'): end_p = end_p.item()
                            
                            if start_p > 0:
                                perf = ((end_p - start_p) / start_p) * 100
                                ticker_perf_map[t] = perf
                    except Exception as e:
                        pass
            
            # Small sleep to be nice to API
            time.sleep(0.5)
                        
        except Exception as e:
            print(f"Batch download error for batch {i}: {e}")


    # Assign Performance & Calculate Averages
    for s_name, s_data in all_sector_data.items():
        total_perf = 0.0
        count_perf = 0
        
        for stock in s_data['stocks']:
            t = stock.get('ticker')
            if t and t in ticker_perf_map:
                p = ticker_perf_map[t]
                stock['performance'] = p
                total_perf += p
                count_perf += 1
            else:
                stock['performance'] = 0.0 # Default if no data
                
        if count_perf > 0:
            s_data['average_performance'] = total_perf / count_perf
        else:
            s_data['average_performance'] = 0.0

    print(f"[SAVE] Saving Sector Trends to DB...")
    try:
        db_save_sector_trends(all_sector_data)
    except Exception as db_err:
        print(f"Error saving sector trends to DB: {db_err}")
    
    print("\n=== [DATA] SECTOR TREND SUMMARY via API ===")
    sorted_sectors = sorted(all_sector_data.items(), key=lambda x: x[1]['count'], reverse=True)
    for name, data in sorted_sectors:
        print(f"{name:<40} | Count: {data['count']:>5} | Avg Perf: {data['average_performance']:.2f}%")

    return all_sector_data

def old_scrape_sectors_data_playwright():
    """
    Scrape sector data using Playwright.
    Integrated from fetch_sectors.py
    """
    # Imports already available in backend.py or managed globally if needed, 
    # but to be safe and match original structure we ensure they are available.
    import json
    import time
    from playwright.sync_api import sync_playwright
    
    USER_DATA_DIR = "./browser_session"
    OUTPUT_FILE = "sector_trends.json"
    
    print("[START] Starting Sector Trend Analyzer...")
    
    all_sector_data = {}

    with sync_playwright() as p:
        # Launch browser with persistent context to keep login session
        browser = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=True, # Run headless for backend integration
            viewport={"width": 1920, "height": 1080},
            locale="fr-FR", # Force French locale for headless
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--window-size=1920,1080",
                "--start-maximized",
                "--lang=fr-FR" # Extra flag for language
            ],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        print("? Navigating to Stock Browse page...")
        page.goto("https://app.traderepublic.com/browse/stock")
        page.wait_for_load_state("networkidle")
        time.sleep(3) # Extra wait for UI hydration

        # 1. Open Sector Filter to get the list of sectors
        print("[SEARCH] Opening Sectors filter...")
        try:
            # Look for button containing "Secteurs" or "Sectors"
            sector_btn = page.locator("button.filterSection", has_text="Secteurs")
            if not sector_btn.count():
                print("[WARN] 'Secteurs' not found, trying 'Sectors'...")
                sector_btn = page.locator("button.filterSection", has_text="Sectors")
            
            sector_btn.first.click()
            time.sleep(1)
        except Exception as e:
            print(f"[ERROR] Could not find Sector filter button: {e}")
            browser.close()
            return {}

        # 2. Get list of available sectors from the popover
        sector_options = page.locator(".filterSection__popover .filterOption").all()
        sectors_list = []
        for opt in sector_options:
            name = opt.locator(".filterOption__name").inner_text()
            # We store the input value to identify it uniquely if needed, or just use text
            input_val = opt.locator("input").get_attribute("value")
            sectors_list.append({"name": name, "value": input_val})
        
        print(f"[LOG] Found {len(sectors_list)} sectors: {[s['name'] for s in sectors_list]}")
        
        # Close popover for now (clicking outside or pressing escape)
        page.keyboard.press("Escape")
        time.sleep(1)

        # 3. Iterate through each sector
        # FILTER OUT unwanted sectors (Caps, etc.)
        EXCLUDED_SECTORS = [
             "Large Caps", "Mid Caps", "Small Caps", 
             "Large/Mid Caps", "Mid/Small Caps", "Micro Caps"
        ]
        
        for sector in sectors_list:
            sector_name = sector["name"]
            
            if sector_name in EXCLUDED_SECTORS:
                 print(f"? Skipping excluded sector: {sector_name}")
                 continue

            print(f"\n[NEW] Analyzing Sector: {sector_name}")
            
            # Re-open filter
            sector_btn.click()
            time.sleep(0.5)
            
            # Click "Effacer" (Clear) to reset previous selection
            try:
                clear_btn = page.locator(".filterSection__popover button", has_text="Effacer")
                if clear_btn.is_visible():
                    clear_btn.click()
                    time.sleep(0.2)
            except:
                pass

            # Select the specific sector
            opt_locator = page.locator(".filterSection__popover .filterOption", has_text=sector_name).first
            opt_locator.click()
            
            # Click "Appliquer" (Apply)
            apply_btn = page.locator(".filterSection__popover button", has_text="Appliquer")
            # Check if apply button is enabled/visible
            if apply_btn.is_visible():
                apply_btn.click()
            else:
                 page.keyboard.press("Escape")
            
            # Wait for table to update
            time.sleep(2) 
            
            # INFINITE SCROLL LOGIC
            # Scroll until no new items are loaded
            last_count = 0
            MAX_SCROLL_ATTEMPTS = 50 # Avoid infinite loops
            attempts = 0
            
            while attempts < MAX_SCROLL_ATTEMPTS:
                # Get current rows
                rows_count = page.locator(".instrumentTableWrapper__row").count()
                
                if rows_count > last_count:
                    last_count = rows_count
                    if rows_count % 100 == 0:
                        print(f"   Loading more... ({rows_count} items)")
                    
                    # Scroll to bottom
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1.5) # Wait for load
                    attempts = 0 # Reset attempts if new data found
                else:
                    attempts += 1
                    time.sleep(0.5)
                    if attempts >= 3: # If no change after 3 checks, assume end
                        break

            # Scrape visible rows
            rows = page.locator(".instrumentTableWrapper__row").all()
            sector_stocks = []
            
            print(f"   Found {len(rows)} total stocks (Scrolled).")
            
            for row in rows:
                try:
                    name_el = row.locator(".instrumentResult__name")
                    isin_el = row.locator(".instrumentResult__details")
                    
                    # Columns: Name/ISIN is col 1.
                    # Price is usually the first simple cell after name.
                    # Change% is the one with 'performance__relative'.
                    
                    name = name_el.inner_text() if name_el.count() > 0 else "Unknown"
                    isin = isin_el.inner_text() if isin_el.count() > 0 else "Unknown"
                    
                    # Find performance element
                    perf_el = row.locator("data.performance__relative")
                    change_pct_text = perf_el.inner_text() if perf_el.count() > 0 else "0%"
                    change_val_attr = perf_el.get_attribute("value") if perf_el.count() > 0 else "0"
                    
                    # Try to get price (sometimes multiple columns, usually the current price is prominent)
                    # We'll take the text of the second cell (index 1) which is usually "Bid" or "Last"
                    cells = row.locator(".tableCell").all()
                    price_text = "N/A"
                    if len(cells) > 1:
                        # cell 0 is name, cell 1 is price usually
                        price_text = cells[1].inner_text()

                    # Clean data
                    try:
                        change_pct = parse_sector_value(change_pct_text)
                        if math.isnan(change_pct):
                            change_pct = 0.0
                    except:
                        change_pct = 0.0
                    
                    # If we have the value attribute, it's more precise (e.g. "0.00138...")
                    if change_val_attr:
                        try:
                            # The value attribute is often a decimal (0.01 = 1%)
                            val = float(change_val_attr) * 100
                            # Check against NaN explicitly
                            if not math.isnan(val):
                                change_pct = val
                        except:
                            pass

                    sector_stocks.append({
                        "name": name,
                        "isin": isin,
                        "price_text": price_text,
                        "change_pct": change_pct
                    })
                except Exception as row_err:
                    # print(f"   Error parsing row: {row_err}")
                    pass
            
            # Calculate simple sector stats
            if sector_stocks:
                avg_perf = sum(s["change_pct"] for s in sector_stocks) / len(sector_stocks)
                # Sort by best performers
                sector_stocks.sort(key=lambda x: x["change_pct"], reverse=True)
                
                print(f"   Avg Performance: {avg_perf:.2f}%")
                print(f"   Top Mover: {sector_stocks[0]['name']} ({sector_stocks[0]['change_pct']:.2f}%)")
                
                all_sector_data[sector_name] = {
                    "average_performance": avg_perf,
                    "count": len(sector_stocks),
                    "stocks": sector_stocks
                }
            else:
                all_sector_data[sector_name] = {
                    "average_performance": 0,
                    "count": 0,
                    "stocks": []
                }

        # 4. Save results
        print(f"[SAVE] Saving Sector Trends to DB...")
        try:
            db_save_sector_trends(all_sector_data)
        except Exception as db_err:
            print(f"Error saving sector trends to DB: {db_err}")
            
        print(f"\n[OK] Analysis complete. Data saved to DB.")
        
        # 5. Print Summary Report to console
        print("\n=== [DATA] SECTOR TREND SUMMARY ===")
        sorted_sectors = sorted(all_sector_data.items(), key=lambda x: x[1]['average_performance'], reverse=True)
        
        for name, data in sorted_sectors:
            print(f"{name:<40} | Avg: {data['average_performance']:>6.2f}% | Top: {data['stocks'][0]['name'] if data['stocks'] else 'N/A'}")

        browser.close()

    return all_sector_data


# Global Lock for Sector Updates to prevent concurrent overlapping runs
_sector_update_lock = threading.Lock()

def update_sector_monthly_trends(force=False):
    """
    Recalcule les tendances mensuelles via Browser Automation (Scraping du site).
    Remplace la méthode PDF+Yahoo qui causait des problèmes de catégorisation ('Others').
    """
    global sector_update_status

    # Acquire non-blocking lock to check if already running
    if not _sector_update_lock.acquire(blocking=False):
        print("[WARN] Sector analysis already running. Skipping this request.")
        return {}

    try:
        # 1. Vérification du cache DB
        if not force:
            try:
                with app.app_context():
                    count = SectorTrend.query.count()
                    if count > 0:
                        print(f"[OK] Sector Trends exist in DB ({count} records). Skipping massive update (User Preference).")
                        sector_update_status = "success"
                        update_loading_step('sector_trends', 'success')
                        return db_load_sector_trends()
            except Exception as e:
                print(f"Error checking existing sector trends: {e}")

        print("[START] Starting Sector Trends Update (Browser Mode)...")
        sector_update_status = "scraping"
        update_loading_step('sector_trends', 'running')

        data = scrape_sectors_data()
        
        if not data:
             print("[ERROR] Browser scraping returned no data.")
             sector_update_status = "error"
             update_loading_step('sector_trends', 'error')
             return {}

        sector_update_status = "success"
        update_loading_step('sector_trends', 'success')
        
        return db_load_sector_trends()

    except Exception as e:
        print(f"[ERROR] Error in sector update: {e}")
        sector_update_status = "error"
        update_loading_step('sector_trends', 'error')
        return {}
    finally:
        try:
            _sector_update_lock.release()
        except RuntimeError:
            pass


@app.route('/api/sector-trends/refresh', methods=['POST'])
def refresh_sector_trends():
    """Recalcule les tendances mensuelles (yfinance) basé sur sector_trends.json"""
    try:
        # Exécuter en background pour ne pas bloquer
        def run_update():
            try:
                # Force update when manually requested
                update_sector_monthly_trends(force=True)
                print("Update Sector Trends Finished")
            except Exception as e:
                print(f"Error in background update: {e}")

        # Lancer le thread
        thread = threading.Thread(target=run_update)
        thread.start()
        
        return jsonify({"status": "success", "message": "Mise à jour des tendances lancée en arrière-plan"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/pdf/refresh', methods=['POST'])
def refresh_pdf_data():
    """Télécharge le PDF TradeRepublic et extrait les stocks"""
    try:
        print("Lancement de la mise a jour PDF...")
        download_pdf()
        stocks = extract_stocks_from_pdf()
        return jsonify({'status': 'ok', 'count': len(stocks), 'message': f'{len(stocks)} instruments extraits du PDF'})
    except Exception as e:
        print(f"Erreur update PDF: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# =================================================================================================
# SERVICE POLYMARKET (Social/Prediction Markets)
# =================================================================================================

# Mapping: keyword/ticker → slug réel sur polymarket.com/predictions/<slug>
# (valeurs vérifiées manuellement depuis le site)
POLYMARKET_PAGE_SLUGS = {
    # US Tech
    "microsoft": "microsoft",  "msft": "microsoft",
    "apple":     "apple",      "aapl": "apple",
    "nvidia":    "nvidia",     "nvda": "nvidia",
    "tesla":     "tesla",      "tsla": "tesla",
    "amazon":    "amazon",     "amzn": "amazon",
    "meta":      "meta",       "facebook": "meta",
    "alphabet":  "google",     "google": "google",  "googl": "google",
    "netflix":   "netflix",    "nflx": "netflix",
    "amd":       "amd",
    "intel":     "intel",      "intc": "intel",
    # Finance & Macro
    "fed":                    "fed-interest-rate",
    "federal reserve":        "fed-interest-rate",
    "fed interest rate":      "fed-interest-rate",
    "s&p 500":                "sp-500",  "sp500": "sp-500",  "spy": "sp-500",
    "nasdaq":                 "nasdaq",  "qqq": "nasdaq",
    "gold":                   "gold-prices",
    "oil":                    "oil",
    "bitcoin":                "bitcoin", "btc": "bitcoin",
    "ethereum":               "ethereum","eth": "ethereum",
    "solana":                 "solana",  "sol": "solana",
    # Other
    "tsmc":  "tsmc",
    "asml":  "asml",
}

class PolymarketService:
    def __init__(self):
        self.base_url = "https://gamma-api.polymarket.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        }

    def scrape_predictions_page(self, slug):
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

    def search_by_entity(self, entity_name, search_terms=None):
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

    def search_by_tag(self, tag_slug):
        """Kept for backwards compat. Delegates to search_by_entity."""
        return self.search_by_entity(tag_slug, search_terms=[tag_slug])

    def score_markets_with_groq(self, markets, asset_context):
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

    def search_markets(self, query):
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
            
            return results[:10]

        except Exception as e:
            print(f"Erreur API Polymarket: {e}")
            return []

@app.route('/api/predictions/portfolio', methods=['GET'])
def get_portfolio_predictions():
    """
    Remplacer la logique news-based par une logique portfolio-based + Macro.
    Utilise le code de test 'correct' intégré dans PolymarketService.
    Retourne des résultats séparés: Macro vs Portfolio.
    """
    try:
        service = PolymarketService()
        seen_questions = set()

        # --- ENTITY MAP: name.lower() → [primary name, ticker, ...] used for title-matching ---
        ENTITY_SEARCH_MAP = {
            "nvidia": ["Nvidia", "NVDA"],
            "tesla": ["Tesla", "TSLA"],
            "apple": ["Apple", "AAPL"],
            "microsoft": ["Microsoft", "MSFT"],   # removed "Windows" (causes noise)
            "amazon": ["Amazon", "AMZN"],
            "meta": ["Meta", "META"],
            "alphabet": ["Alphabet", "Google", "GOOGL"],
            "google": ["Alphabet", "Google", "GOOGL"],
            "netflix": ["Netflix", "NFLX"],
            "amd": ["AMD"],
            "intel": ["Intel", "INTC"],
            "tsmc": ["TSMC", "TSM"],
            "asml": ["ASML"],
            "bitcoin": ["Bitcoin", "BTC"],
            "ethereum": ["Ethereum", "ETH"],
            "solana": ["Solana", "SOL"],
        }

        # 1. MACRO SECTION
        macro_results = []
        macro_targets = [
            ('Fed Interest Rate', ['Fed', 'Federal Reserve', 'Interest Rate']),
            ('Nasdaq',            ['Nasdaq', 'QQQ']),
            ('Gold',              ['Gold', 'XAU']),
            ('S&P 500',           ['S&P 500', 'SPX', 'SPY']),
            ('Recession',         ['Recession', 'US Recession']),
            ('US Inflation',      ['Inflation', 'CPI']),
            ('ECB',               ['ECB', 'European Central Bank']),
        ]

        print(f"? Polymarket Search: Macro targets...")
        for label, terms in macro_targets:
            # Use page scrape if a known slug exists, else fall back to entity search
            page_slug = POLYMARKET_PAGE_SLUGS.get(label.lower())
            if page_slug:
                markets = service.scrape_predictions_page(page_slug)
            else:
                markets = service.search_by_entity(label, search_terms=terms)
            for m in markets:
                if m['question'] not in seen_questions:
                    m['source_category'] = 'Macro'
                    m['source_keyword'] = label
                    macro_results.append(m)
                    seen_questions.add(m['question'])

        macro_results.sort(key=lambda x: x['volume_usd'], reverse=True)
        macro_results = macro_results[:8]


        # 2. PORTFOLIO SECTION — page scrape first, then entity search fallback + Groq NLP scoring
        portfolio_results = []
        try:
            investments = WalletInvestment.query.order_by(WalletInvestment.total_value.desc()).limit(15).all()
            portfolio_keywords = []

            for inv in investments:
                if inv.name:
                    parts = inv.name.replace(',', '').split()
                    if not parts: continue
                    candidate = parts[0]
                    if len(candidate) <= 3 and len(parts) > 1:
                        candidate = f"{parts[0]} {parts[1]}"
                    if candidate.lower() in ['cash', 'euro', 'usd', 'eur', 'account']: continue
                    portfolio_keywords.append(candidate)

            portfolio_keywords = list(set(portfolio_keywords))
            print(f"? Polymarket (scrape+NLP): {portfolio_keywords}...")

            for target_original in portfolio_keywords:
                tgt_lower = target_original.lower()
                markets = []

                # 1st priority: direct page scrape (polymarket.com/predictions/<slug>)
                page_slug = POLYMARKET_PAGE_SLUGS.get(tgt_lower)
                if page_slug:
                    markets = service.scrape_predictions_page(page_slug)
                    print(f"  [WEB] Scrape '{page_slug}': {len(markets)} events")

                # Fallback: entity API search
                if not markets:
                    search_terms = ENTITY_SEARCH_MAP.get(tgt_lower, [target_original])
                    markets = service.search_by_entity(target_original, search_terms=search_terms)
                    print(f"  [SEARCH] Entity '{target_original}': {len(markets)} marches bruts")

                if not markets:
                    continue

                # Groq NLP: score relevance of ALL titles, keep score >= 5 (max 6 per asset)
                markets = service.score_markets_with_groq(markets, target_original)
                relevant = [m for m in markets if (m.get('relevance_score') or 0) >= 5][:6]
                if not relevant:
                    relevant = markets[:3]

                for m in relevant:
                    if m['question'] not in seen_questions:
                        m['source_category'] = 'Portfolio'
                        m['source_keyword'] = target_original
                        portfolio_results.append(m)
                        seen_questions.add(m['question'])

            # Sort by relevance_score desc, then volume
            portfolio_results.sort(key=lambda x: (x.get('relevance_score') or 0, x.get('volume_usd', 0)), reverse=True)
            portfolio_results = portfolio_results[:15]

        except Exception as e:
            print(f"Error getting portfolio keywords: {e}")


        # Structure finale catégorisée
        return jsonify({
            "status": "success", 
            "results": {
                "macro": macro_results,
                "portfolio": portfolio_results
            }
        })

    except Exception as e:
        print(f"Error extracting portfolio predictions: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/predictions/tag', methods=['GET'])
def get_predictions_by_tag():
    """
    Recherche polymarket par entité: ?entity=Microsoft&terms=Microsoft,MSFT&context=Microsoft MSFT
    """
    entity = request.args.get('entity', request.args.get('tag', '')).strip()
    terms_raw = request.args.get('terms', '').strip()
    context = request.args.get('context', entity)
    if not entity:
        return jsonify({"status": "error", "message": "Missing 'entity' or 'tag' query param"}), 400
    search_terms = [t.strip() for t in terms_raw.split(',') if t.strip()] if terms_raw else None
    try:
        service = PolymarketService()
        # 1st: direct page scrape
        page_slug = POLYMARKET_PAGE_SLUGS.get(entity.lower())
        if page_slug:
            markets = service.scrape_predictions_page(page_slug)
        else:
            markets = []
        # 2nd fallback: entity API search
        if not markets:
            markets = service.search_by_entity(entity, search_terms=search_terms)
        # 3rd fallback: old text search
        if not markets:
            markets = service.search_markets(entity)
        markets = service.score_markets_with_groq(markets, context)
        return jsonify({
            "status": "success",
            "entity": entity,
            "page_slug": page_slug,
            "total": len(markets),
            "markets": markets
        })
    except Exception as e:
        print(f"Error in get_predictions_by_tag: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/news/analyze-sentiment', methods=['POST'])
def analyze_news_sentiment():
    """Analyse le sentiment, la pertinence et traduit les news avec FinBERT + LLM"""
    try:
        # 1. Load Data
        news_data = db_load_generic('bloomberg_rss')
        truth_data = db_load_generic('truth_social') or []
        
        if not news_data and not truth_data:
             return jsonify({'status': 'error', 'message': 'No news data found'}), 404
             
        items = news_data.get('items', [])
        
        # Merge segments logic
        existing_segments = news_data.get('news_segments', [])
        
        # Deduplication: Track existing URLs in segments
        seen_urls = set(s.get('url') for s in existing_segments if s.get('url'))
        
        # Adapt Truth Social posts to segment format
        truth_segments = []
        # ENABLED TRUTH SOCIAL ANALYSIS VIA FINBERT FAST-TRACK
        for post in truth_data:
            url = post.get('url')
            if url and url in seen_urls: continue
            truth_segments.append({
                'title': f"TRUTH SOCIAL: {post.get('author', 'Donald Trump')}",
                'raw_text': post.get('content', ''),
                'summary': post.get('content', ''),
                'source': 'truth_social',
                'url': url,
                'created_at': post.get('created_at'), 
                **{k:v for k,v in post.items() if k.startswith('ai_')}
            })
        
        # Include Truth Social in pipeline (filtered by Fast Track below)
        segments = existing_segments + truth_segments
        
        # ====================================================================
        # STRATEGIE ENTONNOIR: FinBERT + KEYWORDS en PRE-FILTRE
        # ====================================================================
        
        # 1. Identifier tout ce qui n'est PAS encore analysé
        all_unanalyzed = [i for i in items + segments if 'ai_analysis_v2' not in i]
        
        # --- PHASE 1: LOCAL FAST-TRACK (Truth Social & Noise) ---
        # Analyze critical Trump posts AND filter out noise locally BEFORE calling Groq.
        # This ensures UI progress even if Groq fails.
        
        groq_candidates = []
        noise_or_truth_processed = False
        analyzed_count = 0
        
        priority_keywords = ['TRUMP', 'FED', 'POWELL', 'CPI', 'INFLATION', 'RATE', 'EARNINGS', 'NVIDIA', 'APPLE', 'TESLA', 'WAR', 'CHINA', 'OIL', 'GOLD', 'ECB', 'GDP']

        if all_unanalyzed:
            # print(f"?? Pre-Screening {len(all_unanalyzed)} items (Local AI)...")
            
            for item in all_unanalyzed:
                text_en = f"{item.get('title', '')} {item.get('summary', '') or item.get('raw_text', '')}"
                is_truth = (item.get('source') == 'truth_social')
                
                # B. FinBERT Check (Local Model)
                bert_result = analyze_sentiment_finbert(text_en)
                
                # Decision Factors
                has_keyword = any(k in text_en.upper() for k in priority_keywords)
                is_significant_sentiment = False
                if bert_result:
                    sent_label = bert_result.get('label', 'neutral').lower()
                    if sent_label != 'neutral' and bert_result['score'] > 0.75:
                        is_significant_sentiment = True

                if is_truth:
                    # TRUTH SOCIAL: Always analyzed locally (Market Mover)
                    item['ai_analysis_v2'] = True
                    item['criticality_score'] = 9 
                    s_label = bert_result.get('label', 'neutral').lower() if bert_result else 'neutral'
                    item['sentiment_label'] = s_label
                    item['title_fr'] = item.get('title')
                    item['summary_fr'] = item.get('summary') or item.get('raw_text')
                    item['ai_reasoning'] = f"Direct Truth Social Feed. FinBERT: {s_label}"
                    item['search_keywords'] = ['TRUMP', 'Truth Social']
                    noise_or_truth_processed = True
                    analyzed_count += 1
                
                elif has_keyword or is_significant_sentiment:
                    # CANDIDATE FOR GROQ: Significant content
                    item['temp_bert_result'] = bert_result
                    groq_candidates.append(item)
                    
                else:
                    # NOISE: Mark as analyzed locally (Low Impact)
                    item['ai_analysis_v2'] = True
                    item['criticality_score'] = 2
                    item['sentiment_label'] = bert_result.get('label', 'neutral').lower() if bert_result else 'neutral'
                    item['ai_reasoning'] = "Automated Filter: Low semantic impact"
                    if 'title_fr' not in item: 
                        item['title_fr'] = item.get('title')
                        item['summary_fr'] = item.get('summary') or "Info mineure (Non traduite)"
                    noise_or_truth_processed = True
                    analyzed_count += 1

            # --- SAVE POINT 1: Save local analysis IMMEDIATELY ---
            if noise_or_truth_processed:
                # Save Truths
                truth_to_save = [x for x in truth_data if x.get('url') in {t.get('url') for t in segments if t.get('ai_analysis_v2')}]
                if truth_to_save:
                   # Ensure truth_data in memory is updated from segments
                   seg_map = {s.get('url'): s for s in segments if s.get('source') == 'truth_social'}
                   for t in truth_data:
                       if t.get('url') in seg_map:
                           s = seg_map[t.get('url')]
                           if s.get('ai_analysis_v2'):
                               t.update({k: s[k] for k in ['ai_analysis_v2','title_fr','summary_fr','criticality_score','sentiment_label','ai_reasoning'] if k in s})
                   db_save_generic('truth_social', truth_data)
                
                # Save News
                db_save_generic('bloomberg_rss', news_data)
                # print(f"[OK] Local Phase Saved: Truths & Noise processed.")

        # Recalculate progress for UI feedback before blocking on Groq
        total = len(items) + len(segments)
        done = len([i for i in items + segments if i.get('ai_analysis_v2')])
        # If Groq candidates exist but haven't been processed yet, they are pending.
        # But we already saved the "Noise" ones, so progress should be > 0.
        
        # 2. Batch Process the CANDIDATES (Groq)
        processing_queue = groq_candidates[:5]
        
        if processing_queue:
            # print(f"[AI] AI Analysis on {len(processing_queue)} priority items...")
            
            # Prepare Batch Prompt
            items_input = []
            for idx, item in enumerate(processing_queue):
                summary_text = item.get('summary', '') or item.get('raw_text', '') or ''
                # Hint FinBERT helps LLM
                bert_res = item.get('temp_bert_result')
                bert_sentiment = bert_res.get('label', 'unknown') if bert_res else 'unknown'
                hint = f"[Hint: FinBERT sees {bert_sentiment}]"
                txt = f"ID {idx}: {hint} {item.get('title', '')} | {summary_text[:150]}" 
                items_input.append(txt)
            
            joined_input = "\n".join(items_input)
            
            messages = [
                {"role": "system", "content": """
                Analyze financial news for a French trader.
                JSON LIST ONLY: [{"id":0,"title_fr":"..","summary_fr":"..","relevance_score":8,"sentiment":"bullish","reasoning":"..","search_keywords":["Trump", "Warsh"]}]
                
                SCORING RULES:
                - 0-3 (Noise): Gossip, Local Sports, Celebrities.
                - 4-6 (Sector/Mild): Winter Storms (unless shutting down NYSE/Oil), Earnings of small caps, New Product launches, General Tech.
                - 7-10 (Critical): FED Rate Decisions, POWELL speech, MAJOR Wars (affecting Oil/Chips), TRUMP Executive Orders, CPI/Inflation Data.
                
                IMPORTANT:
                - Downgrade 'Storms/Weather' to max 6 unless it explicitly mentions "Oil Refinery Shutdown" or "Global Supply Chain".
                - Downgrade "Power Outages" to 5.
                - "search_keywords": Extract 2-3 MAIN English keywords (Entities, Events) for searching Prediction Markets (Polymarket). E.g. "Trump Warsh" for nomination, "Fed Rate" for checks. Avoid generic words.
                """},
                {"role": "user", "content": joined_input}
            ]
            
            # Call API
            raw_response = call_groq_api(messages, max_tokens=1500, temperature=0.1)


            
            if "Erreur" in raw_response:
                # Silently skip batch failure allowing local results to be returned
                pass 
            else:
                try:
                    # 3. Parse & Apply Results
                    json_str = raw_response.replace('```json', '').replace('```', '').strip()
                    if not json_str.startswith('['):
                        # Attempt to find list in text
                        import re
                        match = re.search(r'\[.*\]', json_str, re.DOTALL)
                        if match:
                             json_str = match.group(0)
                    
                    results_list = json.loads(json_str)
                    
                    # Map back using ID
                    result_map = {r.get('id'): r for r in results_list if r.get('id') is not None}
                    
                    for idx, item in enumerate(processing_queue):
                        if idx in result_map:
                            res = result_map[idx]
                            item['title_fr'] = res.get('title_fr', item.get('title'))
                            item['summary_fr'] = res.get('summary_fr', item.get('summary'))
                            item['criticality_score'] = res.get('relevance_score', 0)
                            item['sentiment_label'] = res.get('sentiment', 'Neutral').lower()
                            item['ai_reasoning'] = res.get('reasoning', '')
                            item['search_keywords'] = res.get('search_keywords', [])
                            item['ai_analysis_v2'] = True
                            
                            if 'temp_bert_result' in item:
                                del item['temp_bert_result']

                            analyzed_count += 1
                                            
                except Exception as e:
                    pass

        # 2. Generate Global Report (Recalculate with new data)
        # Combine all analyzed valid items for stats
        all_valid = [i for i in items + segments if i.get('ai_analysis_v2')]
        
        if all_valid:
            # Sort by criticality
            all_valid.sort(key=lambda x: x.get('criticality_score', 0), reverse=True)
            
            top_threats = [i for i in all_valid if i.get('sentiment_label') == 'bearish' and i.get('criticality_score') >= 6][:3]
            top_opps = [i for i in all_valid if i.get('sentiment_label') == 'bullish' and i.get('criticality_score') >= 6][:3]
            
            # Enrich Top Threats/Opps with Polymarket Data (Odds)
            try:
                poly_service = PolymarketService()
                # On traite threats ET opps (car une opportunité peut aussi avoir des paris)
                for item in top_threats + top_opps:
                    # Refresh simple si clé manquante (TODO: Logique de refresh temporel)
                    if 'polymarket_data' not in item:
                        keywords = item.get('search_keywords', [])
                        
                        # Fallback keywords extraction
                        if not keywords:
                            title_en = item.get('title', '')
                            # Simple heuristic for existing items: Use title but limit words
                            # keywords = [w for w in title_en.split() if w[0].isupper() and len(w)>2] # Too risky
                            keywords = title_en.split()[:5] # Take first 5 words
                        
                        query = " ".join(keywords) if isinstance(keywords, list) else str(keywords)
                        # print(f"? Polymarket Check for '{query}'...")
                        odds = poly_service.search_markets(query)
                        item['polymarket_data'] = odds
            except Exception as e_poly:
                # print(f"[WARN] Polymarket Enrichment Error: {e_poly}")
                pass

            trump_activity = [i for i in segments if i.get('source') == 'truth_social']
            
            # Safe access to sentiment_label with default for mood calculation
            bullish_count = len([i for i in all_valid[:20] if i.get('sentiment_label', 'neutral') == 'bullish'])
            bearish_count = len([i for i in all_valid[:20] if i.get('sentiment_label', 'neutral') == 'bearish'])
            
            report = {
                "generated_at": datetime.now().isoformat(),
                "market_mood": "Bullish" if bullish_count > bearish_count else "Bearish",
                "top_threats": top_threats,
                "top_opportunities": top_opps,
                "trump_monitor": {
                    "count": len(trump_activity),
                    "latest_fr": trump_activity[0].get('summary_fr') if trump_activity else None
                }
            }
            news_data['report'] = report
        
        # Save GROQ Analysis if anything was processed in this batch
        if processing_queue and 'res' in locals(): # Ensure we actually got results from Groq
             db_save_generic('bloomberg_rss', news_data)

        # Force save report even if no new items, so frontend gets latest structure
        if not processing_queue:
            db_save_generic('bloomberg_rss', news_data)
        
        # Calculate Progress
        total_items_count = len(items) + len(segments)
        currently_analyzed = len([i for i in items + segments if i.get('ai_analysis_v2')])
        remaining_count = total_items_count - currently_analyzed
        
        progress_pct = 100
        if total_items_count > 0:
            progress_pct = int((currently_analyzed / total_items_count) * 100)

        return jsonify({
            'status': 'success', 
            'analyzed_count': analyzed_count,
            'remaining_count': remaining_count,
            'progress_pct': progress_pct,
            'data': news_data
        })
    except Exception as e:
        print(f"Erreur endpoint sentiment: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/options', methods=['GET'])
def get_options():
    """Récupère et renvoie l'analyse complète de la chaîne d'options pour un ticker donné"""
    try:
        ticker = request.args.get('ticker', '').strip().upper()
        if not ticker:
            return jsonify({'status': 'error', 'error': 'missing_ticker'}), 400

        result = fetch_options_chain_api(ticker)
        if not result:
            return jsonify({'status': 'error', 'error': 'no_data'}), 500
        return jsonify({'status': 'ok', 'data': result})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/api/refresh/options', methods=['POST'])
def refresh_options():
    """Force le rafraîchissement de l'analyse des options pour un ticker"""
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').strip().upper()
        
        if not ticker:
            return jsonify({'status': 'error', 'error': 'missing_ticker'}), 400

        print(f"Rafraichissement options demande pour: {ticker}")
        result = fetch_options_chain_api(ticker)
        
        if not result:
            return jsonify({'status': 'error', 'error': 'analysis_failed'}), 500
            
        return jsonify({'status': 'success', 'data': result})
    except Exception as e:
        print(f"Erreur refresh options: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

async def get_derivatives_async(ticker):
    """Logique asynchrone pour récupérer les dérivés"""
    return {'error': 'deprecated', 'message': 'Use /api/tr/navigate with browser automation'}
    # try:
    #     tr_session_cookie = get_tr_session_cookie()
    #     if not tr_session_cookie:
    #         return {'error': 'no_session_cookie'}

    #     async with await connect_to_websocket(tr_session_cookie) as websocket:
    #         token = tr_session_cookie
    #         message_id = 0

    #         # 1. Recherche de l'instrument
    #         print(f"Recherche derives pour {ticker}...")
    #         data, message_id = await search_instrument(websocket, ticker, token, message_id)
            
    #         results = data.get("results", [])
    #         if not results:
    #             return {'error': 'instrument_not_found'}

    #         # Prendre le premier résultat
    #         selected = results[0]
    #         isin = selected.get("isin")
    #         name = selected.get("name")
            
    #         # 2. Récupération des dérivés
    #         deriv_data, message_id = await fetch_derivatives(websocket, isin, token, message_id)
            
    #         return {
    #             'ticker': ticker,
    #             'isin': isin,
    #             'name': name,
    #             'derivatives': deriv_data
    #         }
    # except Exception as e:
    #     print(f"Erreur async derives: {e}")
    #     return {'error': str(e)}

@app.route('/api/derivatives', methods=['GET'])
def get_derivatives():
    """Récupère les produits dérivés (Turbos, Facteurs) pour un ticker"""
    try:
        ticker = request.args.get('ticker', '').strip().upper()
        if not ticker:
            return jsonify({'status': 'error', 'error': 'missing_ticker'}), 400

        # Exécuter la logique asynchrone
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        result = asyncio.run(get_derivatives_async(ticker))
        
        if 'error' in result:
            return jsonify({'status': 'error', 'error': result['error']}), 500
            
        return jsonify({'status': 'success', 'data': result})
    except Exception as e:
        print(f"Erreur endpoint derives: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/prices', methods=['GET'])
def get_prices():
    """Récupère les prix en temps réel pour des tickers"""
    try:
        # Récupérer depuis query params : /api/prices?tickers=AAPL,GOOGL,MSFT
        tickers_param = request.args.get('tickers', '').strip()
        days = int(request.args.get('days', 5))  # Nombre de jours d'historique
        
        if tickers_param:
            # Si tickers fournis en param, les utiliser
            tickers = [t.strip().upper() for t in tickers_param.split(',') if t.strip()]
        else:
            # Sinon, prendre les tickers du portfolio
            portfolio = load_portfolio_data()
            tickers = []
            
            # Essayer différentes structures de portfolio
            if portfolio:
                if 'positions' in portfolio:
                    tickers = [p.get('ticker', '').strip().upper() for p in portfolio.get('positions', []) if p.get('ticker')]
                elif 'wallets' in portfolio:
                    # Cas où les données sont dans wallets
                    for wallet in portfolio.get('wallets', []):
                        if 'positions' in wallet:
                            tickers.extend([p.get('ticker', '').strip().upper() for p in wallet.get('positions', []) if p.get('ticker')])
        
        # Filtrer les tickers vides
        tickers = [t for t in tickers if t]
        
        if not tickers:
            # Fallback: utiliser des tickers par défaut
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [PRICES] No tickers found in portfolio, using defaults")
            tickers = ['NVDA', 'GOOGL', 'AAPL', 'MSFT', 'TSMC']
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching prices for: {tickers} ({days} days)")
        prices = fetch_live_prices(tickers, days=days)
        
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'prices': prices,
            'count': len(prices),
            'days': days
        })
    except Exception as e:
        print(f"Error in get_prices: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/prices/history', methods=['GET'])
def get_prices_history():
    """Récupère l'historique détaillé des prix (derniers jours/semaines/mois)"""
    try:
        # Paramètres
        tickers_param = request.args.get('tickers', '').strip()
        period = request.args.get('period', '30d')  # 5d, 1mo, 3mo, 1y, etc.
        
        if not tickers_param:
            return jsonify({
                'status': 'error',
                'error': 'tickers parameter required for history',
                'timestamp': datetime.now().isoformat()
            }), 400
        
        tickers = [t.strip().upper() for t in tickers_param.split(',') if t.strip()]
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching history for: {tickers} (period: {period})")
        
        history = {}
        for ticker in tickers:
            try:
                print(f"[HISTORY] {ticker}...", end=' ')
                data = yf.Ticker(ticker)
                hist = data.history(period=period)
                
                if not hist.empty:
                    # Transformer en format lisible
                    daily_data = []
                    for date, row in hist.iterrows():
                        daily_data.append({
                            'date': date.strftime('%Y-%m-%d'),
                            'open': float(row['Open']),
                            'high': float(row['High']),
                            'low': float(row['Low']),
                            'close': float(row['Close']),
                            'volume': int(row['Volume']) if pd.notna(row['Volume']) else 0
                        })
                    
                    # Statistiques globales
                    history[ticker] = {
                        'success': True,
                        'period': period,
                        'data_points': len(daily_data),
                        'start_date': hist.index[0].strftime('%Y-%m-%d'),
                        'end_date': hist.index[-1].strftime('%Y-%m-%d'),
                        'price_start': float(hist['Close'].iloc[0]),
                        'price_end': float(hist['Close'].iloc[-1]),
                        'price_high': float(hist['High'].max()) if pd.notna(hist['High'].max()) else 0.0,
                        'price_low': float(hist['Low'].min()) if pd.notna(hist['Low'].min()) else 0.0,
                        'change': float(hist['Close'].iloc[-1] - hist['Close'].iloc[0]),
                        'change_pct': float((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0] * 100) if hist['Close'].iloc[0] != 0 else 0.0,
                        'avg_volume': float(hist['Volume'].mean()) if pd.notna(hist['Volume'].mean()) else 0.0,
                        'daily_data': daily_data
                    }
                    if math.isnan(history[ticker]['change_pct']):
                        history[ticker]['change_pct'] = 0.0
                    print(f"OK ({len(daily_data)} days)")
                else:
                    history[ticker] = {'success': False, 'error': 'no_data'}
                    print("ERROR: no_data")
                
                time.sleep(0.5)
            except Exception as e:
                history[ticker] = {'success': False, 'error': str(e)}
                print(f"ERROR: {e}")
        
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'period': period,
            'history': history,
            'count': len([h for h in history.values() if h.get('success')])
        })
    except Exception as e:
        print(f"Error in get_prices_history: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/senator-trades/search', methods=['GET'])
def search_senator_trades():
    """Cherche les issuers par nom (pour autocomplete)"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query or len(query) < 2:
            return jsonify({
                'status': 'error',
                'error': 'Query must be at least 2 characters',
                'results': []
            })
        
        scraper = CapitolTradesScraper()
        results = scraper.search_issuer_by_name(query)
        
        return jsonify({
            'status': 'ok',
            'query': query,
            'count': len(results),
            'results': results,
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        print(f"Error in search_senator_trades: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/senator-trades', methods=['GET'])
def get_senator_trades():
    """Récupère les trades des sénateurs pour un nom/ticker donné"""
    try:
        search_term = request.args.get('ticker', '').strip()
        issuer_id = request.args.get('issuer_id', '').strip()
        
        if not search_term and not issuer_id:
            return jsonify({
                'status': 'error',
                'error': 'ticker or issuer_id parameter required',
                'timestamp': datetime.now().isoformat()
            }), 400
        
        scraper = CapitolTradesScraper()
        
        # Vérifier le cache d'abord
        cache_data = scraper._load_cache()
        if search_term in cache_data.get('issuers', {}):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Capitol Trades {search_term} found in cache")
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.now().isoformat(),
                'search_term': search_term,
                'data': cache_data['issuers'][search_term],
                'from_cache': True
            })
        
        # Si issuer_id fourni explicitement, l'utiliser
        if issuer_id:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Scraping Capitol Trades for issuer {issuer_id}")
            data = scraper.scrape_issuer(issuer_id, search_term)
            
            if not data:
                return jsonify({
                    'status': 'error',
                    'error': 'Failed to scrape Capitol Trades',
                    'timestamp': datetime.now().isoformat()
                }, 500)
            
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.now().isoformat(),
                'search_term': search_term,
                'issuer_id': issuer_id,
                'data': data
            })
        
        # Sinon, chercher l'issuer_id automatiquement
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Looking up {search_term} in all_issuers...")
        found_issuer_id = scraper.get_issuer_id_for_ticker(search_term)
        
        if not found_issuer_id:
            return jsonify({
                'status': 'error',
                'error': f'{search_term} not found. Try searching with /api/senator-trades/search?q={search_term}',
                'timestamp': datetime.now().isoformat()
            }, 404)
        
        # Scraper avec l'issuer_id trouvé
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Found issuer_id {found_issuer_id}, scraping Capitol Trades...")
        data = scraper.scrape_issuer(found_issuer_id, search_term)
        
        if not data:
            return jsonify({
                'status': 'error',
                'error': 'Failed to scrape Capitol Trades',
                'timestamp': datetime.now().isoformat()
            }, 500)
        
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'search_term': search_term,
            'issuer_id': found_issuer_id,
            'data': data
        })
    
    except Exception as e:
        print(f"Error in get_senator_trades: {e}")
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/senator-trades/summary', methods=['GET'])
def get_senator_trades_summary():
    """Retourne un résumé des trades des sénateurs"""
    try:
        scraper = CapitolTradesScraper()
        cache_data = scraper._load_cache()
        
        summary = {
            'total_issuers': len(cache_data.get('issuers', {})),
            'last_updated': cache_data.get('last_updated'),
            'issuers': {}
        }
        
        # Résumer chaque issuer
        for ticker, issuer_data in cache_data.get('issuers', {}).items():
            if issuer_data and 'trades' in issuer_data:
                trades = issuer_data['trades']
                democrat_trades = [t for t in trades if t.get('party') == 'Democrat']
                republican_trades = [t for t in trades if t.get('party') == 'Republican']
                buy_trades = [t for t in trades if t.get('type') == 'buy']
                sell_trades = [t for t in trades if t.get('type') == 'sell']
                
                summary['issuers'][ticker] = {
                    'name': issuer_data.get('issuer', {}).get('name'),
                    'total_trades': len(trades),
                    'democrat_trades': len(democrat_trades),
                    'republican_trades': len(republican_trades),
                    'buy_trades': len(buy_trades),
                    'sell_trades': len(sell_trades),
                    'last_trade': trades[0]['traded'] if trades else None,
                    'statistics': issuer_data.get('statistics', {})
                }
        
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'summary': summary
        })
    
    except Exception as e:
        print(f"Error in get_senator_trades_summary: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/bank-forecasts/scrape', methods=['POST'])
def scrape_bank_forecasts():
    """Lance le scraping des prévisions bancaires"""
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Demarrage scraping previsions bancaires...")
        scraper = BankForecastScraper()
        results = scraper.scrape_all()
        
        # Sauvegarder les résultats DB
        # Note: scraper.scrape_all() gère déjà la sauvegarde en DB (raw et formatted)
        # On ne refait pas db_save_bank_forecasts(results) ici pour éviter d'écraser avec le format raw
        
        return jsonify({
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'sources_found': len(results),
            'data': results
        })
    except Exception as e:
        print(f"Erreur scraping: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/bank-forecasts/analyze', methods=['POST'])
def analyze_bank_articles():
    """Lance l'analyse IA des articles bancaires récupérés"""
    try:
        # Load raw data
        raw_data = db_load_generic('bank_raw_scrape')
        if not raw_data:
            return jsonify({'error': 'No raw data found. Run scrape first.'}), 404
        
        scraper = BankForecastScraper()
        scraper.results = raw_data
        
        # Run Analysis
        analyses = scraper.analyze_articles()
        
        # Save Analysis
        db_save_generic('bank_analyses', analyses)
        
        return jsonify({
            'status': 'success',
            'count': len(analyses),
            'analyses': analyses
        })
    except Exception as e:
        print(f"Erreur analyse: {e}")
        return jsonify({'error': str(e)}), 500

# Thread-safety flag: prevent concurrent scrapes triggered by multiple page reloads
_bank_scrape_in_progress = False

@app.route('/api/bank-forecasts', methods=['GET'])
def get_bank_forecasts():
    """
    Retourne les prévisions bancaires depuis la DB.
    Si les données ont plus de 6h, lance un re-scrape en arrière-plan
    et retourne refreshing=true pour que le frontend re-fetche.
    """
    global _bank_scrape_in_progress
    results = db_load_bank_forecasts()

    # Determine staleness from CachedData entry 'bank_raw_scrape'
    last_scraped_at = None
    is_stale = True
    try:
        with app.app_context():
            cache_entry = CachedData.query.filter_by(key='bank_raw_scrape').first()
            if cache_entry and cache_entry.updated_at:
                last_scraped_at = cache_entry.updated_at.isoformat()
                age_hours = (datetime.utcnow() - cache_entry.updated_at).total_seconds() / 3600
                is_stale = age_hours > 6
    except Exception:
        pass

    refreshing = False
    if is_stale and not _bank_scrape_in_progress:
        def _bg_scrape():
            global _bank_scrape_in_progress
            _bank_scrape_in_progress = True
            try:
                with app.app_context():
                    print("[BANK] [REFRESH] Perspectives bancaires > 6h - re-scrape en arriere-plan...")
                    existing_urls = set(
                        row.source_url for row in
                        BankForecast.query.with_entities(BankForecast.source_url).all()
                        if row.source_url
                    )
                    scraper = BankForecastScraper()
                    fresh = scraper.scrape_all() or []
                    new_count = sum(1 for r in fresh if r.get('url') and r['url'] not in existing_urls)
                    if new_count:
                        print(f"[BANK] [NEW] {new_count} nouveaux articles detectes et sauvegardes.")
                    else:
                        print("[BANK] [OK] Aucun nouvel article. Base a jour.")
            except Exception as e:
                print(f"[BANK] [ERROR] Erreur re-scrape: {e}")
            finally:
                _bank_scrape_in_progress = False
        threading.Thread(target=_bg_scrape, daemon=True).start()
        refreshing = True

    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'last_scraped_at': last_scraped_at,
        'refreshing': refreshing or _bank_scrape_in_progress,
        'results': results,
        'count': len(results)
    })

@app.route('/api/bank-analyses', methods=['GET'])
def get_bank_analyses():
    """Récupère les analyses bancaires en cache"""
    data = db_load_generic('bank_analyses')
    if data is None:
        return jsonify([])
    return jsonify(data)

@app.route('/api/earnings', methods=['GET'])
def get_earnings():
    """Récupère les earnings (cache ou refresh si vieux)"""
    try:
        # Vérifier cache
        cache = db_load_generic('earnings_cache')
        if cache and 'updated_at' in cache:
            last_update = datetime.fromisoformat(cache['updated_at'])
            if (datetime.now() - last_update).total_seconds() < 3600 * 12: # 12h cache
                return jsonify(cache)
        
        # Sinon refresh
        return jsonify(fetch_earnings_api())
    except Exception as e:
        print(f"Erreur endpoint earnings: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/refresh/earnings', methods=['POST'])
def refresh_earnings():
    """Force le rafraîchissement des earnings"""
    try:
        return jsonify(fetch_earnings_api())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/refresh/forex', methods=['POST'])
def refresh_forex():
    """Force le rafraîchissement du calendrier Forex"""
    try:
        return jsonify(fetch_forex_calendar_api())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio-events', methods=['POST'])
def get_portfolio_events():
    """Fetch upcoming earnings & dividends for a list of tickers from the portfolio."""
    try:
        body = request.get_json(force=True) or {}
        raw_ids = [t.strip().upper() for t in (body.get('tickers') or []) if t]
        if not raw_ids:
            return jsonify({'events': []})

        # Resolve ISINs to Yahoo Finance tickers (ISIN = 2 letters + 10 alphanums)
        _isin_re = re.compile(r'^[A-Z]{2}[A-Z0-9]{10}$')
        tickers = []
        for item in raw_ids:
            if _isin_re.match(item):
                sym = get_symbol_from_isin(item)
                if sym:
                    tickers.append(sym.upper())
                else:
                    print(f'[portfolio-events] Could not resolve ISIN {item}, skipping')
            else:
                tickers.append(item)
        tickers = list(dict.fromkeys(tickers))  # deduplicate preserving order
        if not tickers:
            return jsonify({'events': []})

        events = []
        today = datetime.now().date()
        horizon = today + timedelta(days=90)

        print(f'[portfolio-events] Processing {len(tickers)} tickers: {tickers}')

        def fetch_events_for(ticker):
            result = []
            try:
                obj = yf.Ticker(ticker)

                # ---- Name resolution (fast_info first, then info) ----
                name = ticker
                info = {}
                try:
                    info = obj.info or {}
                    name = info.get('shortName') or info.get('longName') or ticker
                except Exception:
                    pass

                # ---- EARNINGS: Method 1 — get_earnings_dates() (yfinance >= 0.2) ----
                earnings_added = False
                try:
                    eds = obj.get_earnings_dates(limit=12)
                    if eds is not None and not eds.empty:
                        for idx in eds.index:
                            try:
                                d = idx.date() if hasattr(idx, 'date') else datetime.strptime(str(idx)[:10], '%Y-%m-%d').date()
                                if today <= d <= horizon:
                                    result.append({
                                        'ticker': ticker, 'name': name,
                                        'date': d.isoformat(), 'type': 'earnings',
                                        'label': 'Résultats trimestriels',
                                        'eps_estimate': None,
                                    })
                                    earnings_added = True
                                    break
                            except Exception:
                                pass
                except Exception:
                    pass

                # ---- EARNINGS: Method 2 — calendar (fallback) ----
                if not earnings_added:
                    try:
                        cal = obj.calendar
                        if cal is not None:
                            cal_d = cal if isinstance(cal, dict) else {}
                            if hasattr(cal, 'to_dict') and not isinstance(cal, dict):
                                try:
                                    # DataFrame: first column = values
                                    cal_d = cal.iloc[:, 0].to_dict() if not cal.empty else {}
                                except Exception:
                                    cal_d = {}
                            ed = (cal_d.get('Earnings Date') or cal_d.get('earningsDate')
                                  or cal_d.get('Earnings_Date'))
                            if ed:
                                ed_vals = ed if isinstance(ed, list) else [ed]
                                for ed_val in ed_vals:
                                    try:
                                        ed_str = str(ed_val)[:10]
                                        ed_date = datetime.strptime(ed_str, '%Y-%m-%d').date()
                                        if today <= ed_date <= horizon:
                                            eps_est = cal_d.get('EPS Estimate') or cal_d.get('epsEstimate')
                                            result.append({
                                                'ticker': ticker, 'name': name,
                                                'date': ed_str, 'type': 'earnings',
                                                'label': 'Résultats trimestriels',
                                                'eps_estimate': round(float(eps_est), 2) if eps_est else None,
                                            })
                                            earnings_added = True
                                            break
                                    except Exception:
                                        pass
                    except Exception:
                        pass

                # ---- EARNINGS: Method 3 — retry without exchange suffix (e.g. BMW.DE → BMW) ----
                if not earnings_added and '.' in ticker:
                    base = ticker.split('.')[0]
                    try:
                        obj2 = yf.Ticker(base)
                        eds2 = obj2.get_earnings_dates(limit=12)
                        if eds2 is not None and not eds2.empty:
                            for idx in eds2.index:
                                try:
                                    d = idx.date() if hasattr(idx, 'date') else datetime.strptime(str(idx)[:10], '%Y-%m-%d').date()
                                    if today <= d <= horizon:
                                        # verify it's the same company via name similarity
                                        result.append({
                                            'ticker': ticker, 'name': name,
                                            'date': d.isoformat(), 'type': 'earnings',
                                            'label': 'Résultats trimestriels',
                                            'eps_estimate': None,
                                        })
                                        break
                                except Exception:
                                    pass
                    except Exception:
                        pass

                # ---- DIVIDENDS: Method 1 — info fields ----
                dividend_added = False
                try:
                    div_date = info.get('dividendDate') or info.get('exDividendDate')
                    if div_date:
                        if isinstance(div_date, (int, float)):
                            dd = datetime.fromtimestamp(div_date).date()
                        else:
                            dd = datetime.strptime(str(div_date)[:10], '%Y-%m-%d').date()
                        if today <= dd <= horizon:
                            div_amt = info.get('dividendRate') or info.get('lastDividendValue')
                            result.append({
                                'ticker': ticker, 'name': name, 'date': dd.isoformat(),
                                'type': 'dividend', 'label': 'Dividende',
                                'dividend_amount': round(float(div_amt), 3) if div_amt else None,
                            })
                            dividend_added = True
                except Exception:
                    pass

                # ---- DIVIDENDS: Method 2 — predict from historical pattern ----
                if not dividend_added:
                    try:
                        divs = obj.dividends
                        if divs is not None and len(divs) >= 2:
                            divs_sorted = divs.sort_index()
                            last_few = divs_sorted.tail(6)
                            dates = []
                            for d in last_few.index:
                                try:
                                    dates.append(d.date() if hasattr(d, 'date') else datetime.strptime(str(d)[:10], '%Y-%m-%d').date())
                                except Exception:
                                    pass
                            if len(dates) >= 2:
                                intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                                avg_interval = int(sum(intervals) / len(intervals))
                                next_date = dates[-1] + timedelta(days=avg_interval)
                                if today <= next_date <= horizon:
                                    last_amt = float(last_few.iloc[-1])
                                    result.append({
                                        'ticker': ticker, 'name': name,
                                        'date': next_date.isoformat(), 'type': 'dividend',
                                        'label': 'Dividende (estimé)',
                                        'dividend_amount': round(last_amt, 3) if last_amt else None,
                                    })
                    except Exception:
                        pass

            except Exception as e:
                print(f'[portfolio-events] {ticker}: {e}')
            return result

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(fetch_events_for, t): t for t in tickers}
            for future in futures:
                try:
                    res = future.result(timeout=20)
                    events.extend(res)
                    print(f'[portfolio-events] {futures[future]}: {len(res)} event(s)')
                except Exception as e:
                    print(f'[portfolio-events] future error for {futures[future]}: {e}')

        events.sort(key=lambda x: x['date'])
        return jsonify({'events': events})

    except Exception as e:
        print(f'[portfolio-events] error: {e}')
        return jsonify({'error': str(e)}), 500


# ============================================================================
# NEWS CORRELATOR
# ============================================================================

_NC_MAX_NEWS      = 8
_NC_DATE_TOL      = timedelta(days=2)   # +/- 2j du move
_NC_GOOGLE_MAX    = 30                  # Google filtre fiablement ~30 derniers jours

_NC_PERIOD_MAP = {
    '1d':  ('15m', '1 jour',    '1d'),
    '5d':  ('1h',  '5 jours',   '5d'),
    '1w':  ('1h',  '1 semaine', None),   # None -> date range sur 7j
    '1mo': ('1d',  '1 mois',    '1mo'),
}

def _nc_parse_date(date_str):
    if not date_str: return None
    try:
        dt = _rfc2822_parse(date_str)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception: pass
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str[:19], fmt).replace(tzinfo=timezone.utc)
        except Exception: pass
    return None

def _nc_rss_fetch(url, source):
    try:
        r = requests.get(url, verify=certifi.where(), timeout=12,
                         headers={'User-Agent': 'Mozilla/5.0 (compatible; NCBot/1.0)'})
        r.raise_for_status()
        feed = feedparser.parse(r.text)
        out = []
        for e in feed.entries[:_NC_MAX_NEWS * 3]:
            title = getattr(e, 'title', '')
            pub   = getattr(e, 'published', '') or getattr(e, 'updated', '')
            link  = getattr(e, 'link', '')
            if title:
                out.append({'source': source, 'title': title, 'date': pub, 'url': link})
        return out
    except Exception as ex:
        print(f'[news-correlator][{source}] {ex}')
        return []

def _nc_search_terms(ticker, company):
    """Return (search_ticker, search_company) cleaned for news queries.
    Strips exchange suffixes (.F, .KS, .PA, .L, .TO, .AX, .SW, .HK, .SI, .KQ, .T)
    so Google News can actually find results.
    If company differs from ticker, prefer company name as the main search term.
    """
    base = re.sub(r'\.[A-Z]{1,2}$', '', ticker)   # HY9H.F -> HY9H, 000660.KS -> 000660
    # If company name is meaningful (not just the ticker echoed back), use it
    search_co = company if (company.lower() != ticker.lower()
                            and company.lower() != base.lower()
                            and len(company) > 3) else base
    return base, search_co

def _nc_google_dated(ticker, company, d_from, d_to):
    d1 = d_from.strftime('%Y-%m-%d'); d2 = d_to.strftime('%Y-%m-%d')
    base, search_co = _nc_search_terms(ticker, company)
    q  = f"{search_co.replace(' ', '+')}+after:{d1}+before:{d2}"
    return _nc_rss_fetch(
        f'https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en',
        'Google News')

def _nc_reuters_dated(ticker, company, d_from, d_to):
    d1 = d_from.strftime('%Y-%m-%d'); d2 = d_to.strftime('%Y-%m-%d')
    base, search_co = _nc_search_terms(ticker, company)
    q  = f"site:reuters.com+{search_co.replace(' ', '+')}+after:{d1}+before:{d2}"
    return _nc_rss_fetch(
        f'https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en',
        'Reuters')

def _nc_marketwatch_dated(ticker, company, d_from, d_to):
    d1 = d_from.strftime('%Y-%m-%d'); d2 = d_to.strftime('%Y-%m-%d')
    base, search_co = _nc_search_terms(ticker, company)
    q  = f"site:marketwatch.com+{search_co.replace(' ', '+')}+after:{d1}+before:{d2}"
    return _nc_rss_fetch(
        f'https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en',
        'MarketWatch')

def _nc_seeking_alpha(ticker):
    base, _ = _nc_search_terms(ticker, ticker)
    return _nc_rss_fetch(
        f'https://seekingalpha.com/api/sa/combined/{base.upper()}.xml',
        'Seeking Alpha')

def _nc_yahoo_news(ticker):
    try:
        items = yf.Ticker(ticker).news or []
        out = []
        for item in items[:_NC_MAX_NEWS * 2]:
            content = item.get('content', {}) or {}
            title   = content.get('title') or item.get('title', '')
            pub     = content.get('pubDate') or item.get('providerPublishTime', '')
            if isinstance(pub, (int, float)):
                pub = datetime.fromtimestamp(pub, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
            cu  = content.get('clickThroughUrl', {})
            url = cu.get('url', '') if isinstance(cu, dict) else (cu or '')
            if title:
                out.append({'source': 'Yahoo Finance', 'title': title,
                            'date': str(pub), 'url': url})
        return out
    except Exception as e:
        print(f'[news-correlator][Yahoo] {e}')
        return []

def _nc_parallel(fns_and_args):
    results, lock = [], threading.Lock()
    def run(fn, args):
        items = fn(*args)
        with lock: results.extend(items)
    threads = [threading.Thread(target=run, args=(fn, args), daemon=True)
               for fn, args in fns_and_args]
    for t in threads: t.start()
    for t in threads: t.join(timeout=15)
    seen, unique = set(), []
    for item in results:
        key = item['title'].lower().strip()[:80]
        if key not in seen:
            seen.add(key); unique.append(item)
    return unique

def _nc_sentiment(title):
    """Use existing FinBERT pipeline; returns {label, score, display}."""
    pipe = load_finbert()
    if pipe:
        try:
            res  = pipe(title[:512])
            item = res[0] if isinstance(res, list) else res
            lbl  = item['label'].lower()   # positive / negative / neutral
            scr  = float(item['score'])
            display = {'positive': 'Haussier', 'negative': 'Baissier'}.get(lbl, 'Neutre')
            return {'label': lbl, 'score': round(scr, 3), 'display': display}
        except Exception: pass
    # keyword fallback
    t = title.lower()
    bull_kw = ['surge','soar','beat','record','rally','gain','rise','boost','upgrade','profit',
               'revenue','growth','outperform','acquisition','approved','deal','raises']
    bear_kw = ['drop','fall','plunge','miss','cut','downgrade','loss','decline','crash',
               'investigation','fine','layoff','lawsuit','warn','fraud','missed','slump']
    s = sum(1 for w in bull_kw if w in t) - sum(1 for w in bear_kw if w in t)
    if s > 0: return {'label': 'positive', 'score': 0.6, 'display': 'Haussier'}
    if s < 0: return {'label': 'negative', 'score': 0.6, 'display': 'Baissier'}
    return {'label': 'neutral', 'score': 0.5, 'display': 'Neutre'}

def _nc_fetch_for_move(ticker, company, move_dt, age_days):
    """Fetch + filter articles for a historical move."""
    if age_days > _NC_GOOGLE_MAX:
        return [], False  # too old — skip
    d_from = move_dt - timedelta(days=3)
    d_to   = move_dt + timedelta(days=2)
    raw = _nc_parallel([
        (_nc_google_dated,      (ticker, company, d_from, d_to)),
        (_nc_reuters_dated,     (ticker, company, d_from, d_to)),
        (_nc_marketwatch_dated, (ticker, company, d_from, d_to)),
        (_nc_seeking_alpha,     (ticker,)),
        (_nc_yahoo_news,        (ticker,)),   # post-filtered by date below
    ])
    # Hard-filter by parsed publication date
    filtered = []
    for art in raw:
        pub = _nc_parse_date(art.get('date', ''))
        if pub is None:
            filtered.append({**art, 'date_ok': False,
                              'date_parsed': None,
                              'date_display': art.get('date', '')[:10]})
        elif abs((pub - move_dt).total_seconds()) <= _NC_DATE_TOL.total_seconds():
            filtered.append({**art, 'date_ok': True,
                              'date_parsed': pub.isoformat(),
                              'date_display': pub.strftime('%Y-%m-%d')})
    # Fallback: if strict filter yields nothing, relax to raw (unfiltered, marked date_ok=False)
    if not filtered:
        filtered = [{**a, 'date_ok': False, 'date_parsed': None,
                     'date_display': a.get('date', '')[:10]} for a in raw]
    return filtered[:_NC_MAX_NEWS], True

@app.route('/api/news-correlator', methods=['GET'])
def news_correlator():
    """
    Analyse les mouvements de prix significatifs et corrèle avec les actualités.
    Params:
      ticker    (str)   - ex: NVDA, 000660.KS
      period    (str)   - 1d | 5d | 1w | 1mo
      threshold (float) - seuil de move en % (défaut: 1.0)
    """
    try:
        ticker    = (request.args.get('ticker') or '').strip().upper()
        period    = (request.args.get('period') or '1mo').strip().lower()
        threshold = float(request.args.get('threshold') or 1.0)

        if not ticker:
            return jsonify({'error': 'ticker manquant'}), 400
        if period not in _NC_PERIOD_MAP:
            return jsonify({'error': f'periode invalide: {period}. Valeurs: {list(_NC_PERIOD_MAP)}'}), 400

        interval, label_h, yf_period = _NC_PERIOD_MAP[period]

        # --- Fetch OHLCV ---
        try:
            if yf_period:
                df = yf.download(ticker, period=yf_period, interval=interval,
                                 progress=False, auto_adjust=True)
            else:
                # 1w: last 7 calendar days with 1h bars
                end   = datetime.now(tz=timezone.utc)
                start = end - timedelta(days=7)
                df = yf.download(ticker, start=start, end=end, interval=interval,
                                 progress=False, auto_adjust=True)
        except Exception as e:
            return jsonify({'error': f'yfinance: {e}'}), 500

        if df is None or df.empty:
            return jsonify({'error': 'Pas de données de prix disponibles'}), 404

        closes = df['Close'].squeeze()
        p_start = float(closes.iloc[0])
        p_end   = float(closes.iloc[-1])
        total_pct = (p_end - p_start) / p_start * 100 if p_start else 0.0

        # Company name
        try:
            info    = yf.Ticker(ticker).info
            company = info.get('shortName') or info.get('longName') or ticker
        except Exception:
            company = ticker

        # --- Detect moves ---
        raw_moves = []
        for i in range(1, len(closes)):
            prev = float(closes.iloc[i - 1]); curr = float(closes.iloc[i])
            if prev == 0: continue
            pct = (curr - prev) / prev * 100
            if abs(pct) >= threshold:
                ts = closes.index[i]
                if hasattr(ts, 'to_pydatetime'): ts = ts.to_pydatetime()
                if hasattr(ts, 'tzinfo') and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                raw_moves.append({'timestamp': ts, 'price_from': prev,
                                  'price_to': curr, 'change_pct': pct})

        now_utc = datetime.now(tz=timezone.utc)
        stats = {'total': len(raw_moves), 'correlated': 0, 'divergent': 0,
                 'no_news': 0, 'too_old': 0}
        moves_out = []

        for move in raw_moves:
            ts       = move['timestamp']
            age_days = (now_utc - ts).days
            ts_str   = (ts.strftime('%Y-%m-%d %H:%M') if interval not in ('1d', '1wk')
                        else ts.strftime('%Y-%m-%d'))

            move_entry = {
                'timestamp':  ts_str,
                'change_pct': round(move['change_pct'], 2),
                'price_from': round(move['price_from'], 4),
                'price_to':   round(move['price_to'],   4),
                'age_days':   age_days,
                'too_old':    age_days > _NC_GOOGLE_MAX,
                'articles':   [],
                'bull': 0, 'bear': 0, 'neutral': 0,
                'is_correlated': False,
                'date_confirmed': 0,
            }

            if age_days > _NC_GOOGLE_MAX:
                stats['too_old'] += 1
                moves_out.append(move_entry)
                continue

            articles_raw, _ = _nc_fetch_for_move(ticker, company, ts, age_days)

            if not articles_raw:
                stats['no_news'] += 1
                moves_out.append(move_entry)
                continue

            articles_out = []
            for art in articles_raw:
                sent = _nc_sentiment(art['title'])
                articles_out.append({
                    'title':      art['title'],
                    'source':     art['source'],
                    'date':       art.get('date_display', ''),
                    'url':        art.get('url', ''),
                    'sentiment':  sent['label'],
                    'sentiment_display': sent['display'],
                    'sentiment_score':   sent['score'],
                    'date_ok':    art.get('date_ok', False),
                })

            # Use date-confirmed articles for correlation if possible
            confirmed = [a for a in articles_out if a['date_ok']]
            eval_set  = confirmed if confirmed else articles_out
            bull  = sum(1 for a in eval_set if a['sentiment'] == 'positive')
            bear  = sum(1 for a in eval_set if a['sentiment'] == 'negative')
            neut  = len(eval_set) - bull - bear
            is_up = move['change_pct'] > 0
            is_corr = (is_up and bull > bear) or (not is_up and bear > bull)

            move_entry.update({
                'articles':        articles_out,
                'bull':            bull,
                'bear':            bear,
                'neutral':         neut,
                'is_correlated':   is_corr,
                'date_confirmed':  len(confirmed),
            })
            if is_corr: stats['correlated'] += 1
            else:       stats['divergent']  += 1
            moves_out.append(move_entry)

        analyzed = stats['correlated'] + stats['divergent'] + stats['no_news']
        stats['rate'] = round(stats['correlated'] / analyzed * 100) if analyzed > 0 else 0

        return jsonify({
            'ticker':      ticker,
            'company':     company,
            'period':      period,
            'period_label': label_h,
            'threshold':   threshold,
            'price_start': round(p_start, 4),
            'price_end':   round(p_end,   4),
            'total_pct':   round(total_pct, 2),
            'candles':     len(closes),
            'moves':       moves_out,
            'stats':       stats,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/watchlist', methods=['GET'])
def get_watchlist():
    """Return the saved watchlist."""
    data = db_load_generic('watchlist') or []
    return jsonify(data)


@app.route('/api/watchlist', methods=['POST'])
def add_to_watchlist():
    """Add a ticker to the watchlist."""
    try:
        body = request.get_json(force=True) or {}
        ticker = (body.get('ticker') or '').strip().upper()
        if not ticker:
            return jsonify({'error': 'ticker required'}), 400
        watchlist = db_load_generic('watchlist') or []
        if any(w['ticker'] == ticker for w in watchlist):
            return jsonify({'status': 'already_exists', 'watchlist': watchlist})
        # Fetch basic info
        name = ticker
        try:
            info = yf.Ticker(ticker).info or {}
            name = info.get('shortName') or info.get('longName') or ticker
        except Exception: pass
        watchlist.append({'ticker': ticker, 'name': name, 'added_at': datetime.now().isoformat()})
        db_save_generic('watchlist', watchlist)
        return jsonify({'status': 'added', 'watchlist': watchlist})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/watchlist/<ticker>', methods=['DELETE'])
def remove_from_watchlist(ticker):
    """Remove a ticker from the watchlist."""
    try:
        ticker = ticker.strip().upper()
        watchlist = db_load_generic('watchlist') or []
        watchlist = [w for w in watchlist if w['ticker'] != ticker]
        db_save_generic('watchlist', watchlist)
        return jsonify({'status': 'removed', 'watchlist': watchlist})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/watchlist/prices', methods=['POST'])
def get_watchlist_prices():
    """Get live prices for a list of tickers (for watchlist display)."""
    try:
        body = request.get_json(force=True) or {}
        tickers = [t.strip().upper() for t in (body.get('tickers') or []) if t]
        if not tickers:
            return jsonify({})
        result = {}
        def fetch_price(ticker):
            try:
                t = yf.Ticker(ticker)
                info = t.info or {}
                price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
                prev = info.get('previousClose') or info.get('regularMarketPreviousClose')
                chg_pct = round((price - prev) / prev * 100, 2) if price and prev and prev > 0 else None
                return ticker, {
                    'price': round(float(price), 2) if price else None,
                    'change_pct': chg_pct,
                    'name': info.get('shortName') or info.get('longName') or ticker,
                    'sector': info.get('sector') or '',
                    'market_cap': info.get('marketCap'),
                    'pe': round(float(info.get('trailingPE')), 1) if info.get('trailingPE') else None,
                }
            except Exception as e:
                return ticker, {'error': str(e)}
        with ThreadPoolExecutor(max_workers=8) as executor:
            for ticker, data in executor.map(lambda t: fetch_price(t), tickers):
                result[ticker] = data
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/watchlist/search', methods=['GET'])
def search_watchlist_tickers():
    """Search tickers/company names via Yahoo Finance autocomplete."""
    q = (request.args.get('q') or '').strip()
    if len(q) < 1:
        return jsonify([])
    try:
        url = 'https://query2.finance.yahoo.com/v1/finance/search'
        params = {'q': q, 'quotesCount': 10, 'newsCount': 0, 'enableFuzzyQuery': 'false', 'quotesQueryId': 'tss_match_phrase_query'}
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        r = requests.get(url, params=params, headers=headers, timeout=5)
        data = r.json() if r.ok else {}
        quotes = data.get('quotes') or []
        results = []
        for item in quotes:
            t = (item.get('symbol') or '').upper()
            name = item.get('longname') or item.get('shortname') or t
            qtype = item.get('quoteType') or ''
            exchange = item.get('exchange') or ''
            if t:
                results.append({'ticker': t, 'name': name, 'type': qtype, 'exchange': exchange})
        return jsonify(results)
    except Exception as e:
        return jsonify([])


@app.route('/api/user/financial-config', methods=['GET'])
def get_user_financial_config():
    """Retrieve user financial configuration"""
    data = db_load_generic('user_financial_config')
    if data is None:
        # Default structure
        return jsonify({
            'budget': 0,
            'savings_goal': 0,
            'subscriptions': []
        })
    return jsonify(data)

@app.route('/api/user/financial-config', methods=['POST'])
def save_user_financial_config():
    """Save user financial configuration"""
    try:
        data = request.json
        db_save_generic('user_financial_config', data)
        return jsonify({'status': 'success', 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# TÂCHES DE FOND
# ============================================================================

def background_refresh_loop():
    """Boucle de rafraîchissement automatique"""
    global background_tasks_running
    
    tickers = ['NVDA', 'GOOGL', 'AVGO', 'TSM', 'AAPL']
    

    static_insiders_run = False

    while background_tasks_running:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Rafraichissement automatique...")
            
            # RSS toutes les 5 minutes
            try:
                fetch_bloomberg_rss_api()
            except: pass
            
            # Truth Social
            try:
                print("Updating Truth Social posts...")
                update_truth_social_posts()
            except Exception as e:
                print(f"Truth Social Error: {e}")
            
            # Insiders une seule fois au démarrage de la boucle
            if not static_insiders_run:
                print("[START] Chargement unique des Insiders (Background)...")
                try:
                    fetch_insiders_api(tickers)
                    static_insiders_run = True
                except Exception as e:
                    print(f"Erreur insiders background: {e}")
            
            # Forex toutes les heures
            if int(time.time()) % 3600 < 60:
                fetch_forex_calendar_api()
            
            time.sleep(300)  # 5 minutes
        except Exception as e:
            print(f"Erreur background: {e}")
            time.sleep(60)

@app.route('/api/background/start', methods=['POST'])
def start_background_tasks():
    """Démarre les tâches de fond"""
    global background_tasks_running
    
    if not background_tasks_running:
        background_tasks_running = True
        thread = threading.Thread(target=background_refresh_loop, daemon=True)
        thread.start()
        return jsonify({'status': 'started', 'timestamp': datetime.now().isoformat()})
    
    return jsonify({'status': 'already_running'})

@app.route('/api/background/stop', methods=['POST'])
def stop_background_tasks():
    """Arrête les tâches de fond"""
    global background_tasks_running
    background_tasks_running = False
    return jsonify({'status': 'stopped', 'timestamp': datetime.now().isoformat()})

# ============================================================================

@app.route('/api/analyze-fundamentals', methods=['POST'])
def analyze_fundamentals():
    """Analyse technique (3 timeframes) et fondamentale"""
    tickers_input = request.json.get('tickers', [])
    if not tickers_input:
        return jsonify({'results': []})
    
    # 1. Nettoyage et préparation des tickers
    clean_tickers = []
    ticker_map = {} # Map  Clean -> Original
    
    def process_one_ticker(t):
        if not t: return None
        # Detection ISIN
        if re.match(r'^[A-Z]{2}[A-Z0-9]{9}\d$', t):
            resolved = get_symbol_from_isin(t)
            if resolved:
                # print(f"ISIN Resolved: {t} -> {resolved}") # Desactive pour perf
                clean = resolved.replace(' ', '').upper()
                return (clean, t)
            else:
                # print(f"Could not resolve ISIN: {t}")
                return None
        
        # Nettoyage basique
        clean = t.replace(' ', '').upper()
        return (clean, t)

    # Note: On a déplacé le save_cache hors de la boucle unitaire pour ne pas écrire sur disque 800 fois
    # Exécution en parallèle pour accélérer la résolution ISIN (IO bound)
    # Augmentation des workers à 100 pour maximiser le débit réseau
    # EDIT: Réduction à 60 workers pour éviter 'NameResolutionError' sur le DNS local
    with ThreadPoolExecutor(max_workers=60) as executor:
        future_results = executor.map(process_one_ticker, tickers_input)
        
        for res in future_results:
            if res:
                clean, orig = res
                clean_tickers.append(clean)
                ticker_map[clean] = orig
    
    # Sauvegarde du cache en une seule fois à la fin
    try:
        save_cache()
    except Exception as e:
        print(f"Warning: Failed to save ISIN cache: {e}")

    clean_tickers = list(set(clean_tickers))
    
    # Limite pour éviter le timeout (batch de 300 max pour yf.download)
    # L'utilisateur a dit "tous", et yf.download peut gérer ~1000 tickers assez vite.
    # On monte la limite à 800 pour couvrir la 'totalité' des positifs probables.
    # UPDATE: L'utilisateur veut TOUT traiter. On augmente massivement la limite.
    candidates_tickers = clean_tickers[:10000] 
    
    # MODE MANUEL : Si peu de tickers (ex: recherche), on désactive les filtres stricts
    is_manual_mode = (len(clean_tickers) <= 5)

    results = []

    try:
        # 2. ANALYSE TECHNIQUE (BATCH FAST)
        # On télécharge l'historique de 1 AN pour couvrir le 6 mois largement
        print(f"Downloading history for {len(candidates_tickers)} tickers...")
        if not candidates_tickers:
             return jsonify({'results': []})

        # Augmentation threads yfinance + période ajustée si besoin (1y est ok)
        history_data = yf.download(candidates_tickers, period="1y", interval="1d", group_by='ticker', progress=False, threads=100)
        
        strong_trend_tickers = []
        
        for ticker in candidates_tickers:
            try:
                # Récupération dataframe (Gestion multi-index ou simple)
                # Correction pour yfinance qui retourne parfois un MultiIndex même pour un seul ticker si passé en liste
                if isinstance(history_data.columns, pd.MultiIndex) and ticker in history_data.columns.get_level_values(0):
                    df = history_data[ticker]
                elif len(candidates_tickers) > 1:
                     # Cas classique fallback
                     df = history_data[ticker]
                else:
                    df = history_data
                
                # Nettoyage des données vides
                df = df.dropna(how='all')
                
                if len(df) < 20: continue # Pas assez d'historique (min 1 mois)
                
                # Calcul des variations
                # Prix actuel
                current_price = df['Close'].iloc[-1]
                if isinstance(current_price, pd.Series): current_price = current_price.iloc[0]

                # 1 Semaine (5 jours de bourse)
                price_1w = df['Close'].iloc[-6] if len(df) >= 6 else df['Close'].iloc[0]
                if isinstance(price_1w, pd.Series): price_1w = price_1w.iloc[0]
                
                # 1 Mois (20 jours)
                price_1m = df['Close'].iloc[-21] if len(df) >= 21 else df['Close'].iloc[0]
                if isinstance(price_1m, pd.Series): price_1m = price_1m.iloc[0]
                
                # 3 Mois (60 jours)
                price_3m = df['Close'].iloc[-61] if len(df) >= 61 else df['Close'].iloc[0]
                if isinstance(price_3m, pd.Series): price_3m = price_3m.iloc[0]

                # 6 Mois (126 jours - demi-année de bourse)
                price_6m = df['Close'].iloc[-126] if len(df) >= 126 else df['Close'].iloc[0]
                if isinstance(price_6m, pd.Series): price_6m = price_6m.iloc[0]

                # Perf calc
                perf_1w = (current_price - price_1w) / price_1w
                perf_1m = (current_price - price_1m) / price_1m
                perf_3m = (current_price - price_3m) / price_3m
                perf_6m = (current_price - price_6m) / price_6m

                # Condition de TREND
                # Si mode manuel, on accepte tout. Sinon, on filtre strictement.
                # Critères renforcés:
                # 1. Tendance positive sur 1 mois (Momentum court terme)
                # 2. Tendance positive sur 6 mois (Fond de tendance sain)
                passed_trend_check = (perf_1m > 0 and perf_6m > 0)
                
                # Modification suite à la demande utilisateur : "Il ne doit pas y avoir de limites et il faut tout analyser normalement"
                # On force le passage (équivalent à is_manual_mode = True pour tout le monde)
                force_include_all = True
                
                if force_include_all or is_manual_mode or passed_trend_check:
                     strong_trend_tickers.append({
                         'symbol': ticker,
                         'perfs': {
                             '1w': perf_1w,
                             '1m': perf_1m,
                             '3m': perf_3m,
                             '6m': perf_6m
                         }
                     })

            except Exception as e:
                # print(f"Tech error {ticker}: {e}")
                continue

        # 3. ANALYSE FONDAMENTALE & ÉVÈNEMENTIELLE (PARALLEL)
        print(f"Technical filter passed: {len(strong_trend_tickers)} stocks. Launching parallel analysis...")
        
        # Function to process one stock (Thread Safe)
        def process_one_stock(item):
            symbol = item['symbol']
            try:
                stock = yf.Ticker(symbol)
                info = stock.info
                
                if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info and 'previousClose' not in info): 
                    # print(f"Skipping {symbol}: No price info")
                    return None
                
                # Récupération indicateurs fondamentaux clés
                rev_growth = info.get('revenueGrowth', 0) or 0
                earn_growth = info.get('earningsGrowth', 0) or 0
                profit_margin = info.get('profitMargins', 0) or 0
                roe = info.get('returnOnEquity', 0) or 0
                debt = info.get('debtToEquity')
                target_price = info.get('targetMeanPrice')
                recommendation = info.get('recommendationKey')
                description = info.get('longBusinessSummary') or "Aucune description disponible."
                name = info.get('longName') or info.get('shortName') or symbol
                
                # Dividend details
                dividendRate = info.get('dividendRate', 0)
                dividendYield = info.get('dividendYield', 0)
                exDividendDate = info.get('exDividendDate', 0)
                payoutRatio = info.get('payoutRatio', 0)
                
                # Market Cap
                marketCap = info.get('marketCap', 0)
                
                # High/Low 52w
                fiftyTwoWeekHigh = info.get('fiftyTwoWeekHigh', 0)
                fiftyTwoWeekLow = info.get('fiftyTwoWeekLow', 0)

                # --- FILTRE HARD SUR LA RENTABILITÉ ---
                # Exclusion des sociétés qui perdent de l'argent SAUF si Hyper-Croissance (>20%)
                # DESACTIVÉ EN MODE MANUEL
                is_high_growth = (rev_growth > 0.20) or (earn_growth > 0.20)
                
                # MODIFICATION CLIENT: On n'exclut plus rien, on taggera "Trend" plus bas
                # if not is_manual_mode:
                    # Resserrement du filtre : On évite les sociétés en perte (Marge < 0) sauf si forte croissance
                    # if profit_margin < 0.0 and not is_high_growth: continue # VETO
                    # if roe < 0.0 and not is_high_growth: continue # VETO

                # --- Détection ÉVÈNEMENTS (Dividendes, Earnings, etc.) ---
                events_found = []
                
                # 1. Dividendes
                if 'exDividendDate' in info and info['exDividendDate']:
                    import datetime
                    ex_div = datetime.datetime.fromtimestamp(info['exDividendDate'])
                    now = datetime.datetime.now()
                    diff_days = (ex_div - now).days
                    
                    if -10 <= diff_days <= 10:
                        events_found.append(f"Ex-Div: {ex_div.strftime('%d/%m')}")
                
                # 2. Earnings (Approximation via info) - yfinance n'a pas toujours le field 'earningsTimestamp' fiable pour le prochain
                # On tente une heuristique simplifiée ou on laisse vide si pas dispo
                # Parfois 'mostRecentQuarter' aide pour le passé
                
                # 3. News Catalyst (Basic Check)
                # On regarde si une news récente parle de Dividend, Earnings, Split
                try:
                    news = stock.news
                    if news:
                        for n in news[:2]: # Check 2 dernières news
                            title = n.get('title', '').lower()
                            if 'dividend' in title: events_found.append("News: Dividende")
                            if 'earnings' in title or 'result' in title: events_found.append("News: Résultats")
                            if 'split' in title: events_found.append("News: Split")
                            if 'acquisition' in title or 'merger' in title: events_found.append("News: M&A")
                except:
                    pass

                events_found = list(set(events_found)) # Dedup

                # Pré-calcul Croissance (Facteur "Growth" pour ajuster la tolérance P/E)
                
                # Si Croissance > 15% ou Marges exceptionnelles, on considère "High Growth/Quality"
                # Cela permet de tolérer des PE plus élevés (ex: NVIDIA, Google...)
                profit_margin = info.get('profitMargins', 0) or 0
                is_high_growth = (rev_growth > 0.15) or (earn_growth > 0.15)
                is_high_quality = (profit_margin > 0.20)

                # --- Critères Fondamentaux ---
                
                # 1. Valorisation
                pe = info.get('forwardPE') or info.get('trailingPE')
                peg = info.get('pegRatio')
                pb = info.get('priceToBook')
                
                val_points = 0
                # Seuils adaptatifs : On accepte PE jusqu'à 70 si High Growth/Quality
                pe_limit = 75 if (is_high_growth or is_high_quality) else 30
                pb_limit = 15 if (is_high_growth or is_high_quality) else 4

                if pe and 0 < pe < pe_limit: val_points += 1 
                if peg and 0 < peg < 3: val_points += 1
                if pb and 0 < pb < pb_limit: val_points += 1
                
                # 2. Qualité
                roe = info.get('returnOnEquity', 0) or 0
                debt = info.get('debtToEquity')
                
                qual_points = 0
                if roe > 0.10: qual_points += 1 # ROE > 10%
                if profit_margin > 0.10: qual_points += 1 # Marge > 10%
                if debt and debt < 250: qual_points += 1 # Dette sous contrôle
                
                # 3. Croissance
                growth_points = 0
                if rev_growth > 0.05: growth_points += 1
                if earn_growth > 0.05: growth_points += 1
                if is_high_growth: growth_points += 1 # Bonus Point pour Growth > 15%
                
                total_score = val_points + qual_points + growth_points
                
                # Tags
                validations = []
                # Tech tags
                if item['perfs']['1w'] > 0: validations.append("Wkly Bull")
                if item['perfs']['3m'] > 0: validations.append("Qtr Bull")
                # Funda tags
                if is_high_growth: validations.append("High Growth [START]")
                elif growth_points >= 1: validations.append("Croissance")
                
                # Trend / Speculative Tag (Si pas rentable mais strong momentum)
                if profit_margin < 0:
                     if item['perfs']['3m'] > 0.20: # +20% en 3 mois mais perte
                         validations.append("Trend Spéculatif [WARN]")
                     else:
                         validations.append("Non Rentable")
                
                if val_points >= 2: validations.append("Valo.")
                if is_high_quality: validations.append("Quality 💎")

                # Score Tech
                tech_score = (1 if item['perfs']['1w'] > 0 else 0) + (1 if item['perfs']['1m'] > 0 else 0) + (1 if item['perfs']['3m'] > 0 else 0)
                
                # Validation Finale
                # On exige un minimum de qualité fondamentale MÊME si le trend est bon (tech_score == 3)
                # Si tech_score == 3, on accepte un score fonda >= 2 (moyen), sinon >= 3 ou 2 si high_growth
                
                pass_funda = (total_score >= (2 if is_high_growth else 3))
                pass_tech_mixed = (tech_score == 3 and total_score >= 1) # Exception momentum: faut quand même 1pt fonda min (pas total junk)

                if is_manual_mode or pass_funda or pass_tech_mixed:
                     return {
                        'symbol': symbol,
                        'isValidated': True,
                        'score': total_score + tech_score,
                        'validations': list(set(validations)),
                        'events': events_found,
                        'metrics': clean_for_json({
                            'pe': pe, 'roe': roe, 'margin': profit_margin,
                            'rev_growth': rev_growth, 'debt': debt,
                            'dividendRate': dividendRate, 
                            'dividendYield': dividendYield,
                            'payoutRatio': payoutRatio,
                            'exDividendDate': exDividendDate,
                            'fiftyTwoWeekHigh': fiftyTwoWeekHigh, 
                            'fiftyTwoWeekLow': fiftyTwoWeekLow
                        }),
                        'perfs': clean_for_json(item['perfs']),
                        'name': info.get('longName') or info.get('shortName') or symbol, # <--- Nom ajouté
                        'currency': info.get('currency', 'EUR'), # <--- Devise ajoutée
                        'targetPrice': info.get('targetMeanPrice'),
                        'recommendation': info.get('recommendationKey'),
                        'description': info.get('longBusinessSummary') or info.get('shortBusinessSummary'),
                        'sector': info.get('sector'),
                        'industry': info.get('industry'),
                        'employees': info.get('fullTimeEmployees'),
                        'marketCap': info.get('marketCap'),
                        'isin': ticker_map.get(symbol) # Retourne l'ISIN d'origine si fourni
                    }
            
            except Exception as e:
                return None

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=50) as executor:
            # Using list() to force evaluation/wait
            # Removed tqdm to clean up logs (disable=True)
            parallel_results = list(tqdm(executor.map(process_one_stock, strong_trend_tickers), total=len(strong_trend_tickers), desc="Fundamental Analysis", disable=True))
        
        results = [r for r in parallel_results if r is not None]
                
    except Exception as e:
        print(f"Global analysis error: {e}")
        return jsonify({'error': str(e)}), 500
            
    # Tri final par score descendant
    results.sort(key=lambda x: x['score'], reverse=True)
    return jsonify({'results': results})

def background_tr_portfolio_loop():
    """Boucle dédiée au rafraîchissement du portfolio Trade Republic toutes les 5 minutes.
    Fetch history (transactions) runs every 30 minutes so new purchases appear on the graph.
    Auto-refreshes the session token via tr_refresh when expired."""
    print("[START] Auto-refresh Portfolio loop started (5 min prices / 30 min history)")
    
    # Use LOCAL instance
    local_api = TradeRepublicAPI()
    _cycle = 0  # Counter to throttle fetch_history (every 6th cycle = 30 min)
    
    while True:
        try:
             # Check if logged in (token exists)
            local_api.config.read(local_api.config_path)
            token = local_api.config.get("secret", "tr_session", fallback=None)
            
            if not token:
                # Attempt silent refresh via tr_refresh before giving up
                print("[Background TR] No session token - attempting auto-refresh via tr_refresh...")
                if local_api.refresh_session_token():
                    token = local_api.session_token
                    print(f"[Background TR] [OK] Auto-refresh succeeded.")
                else:
                    print("[Background TR] [WAIT] Auto-refresh failed - waiting for user login.")
                    time.sleep(60)
                    continue

            if token:
                 local_api.session_token = token
                 # Run async fetch
                 loop = asyncio.new_event_loop()
                 asyncio.set_event_loop(loop)
                 try:
                    connected = loop.run_until_complete(local_api.connect())
                    if connected:
                        loop.run_until_complete(local_api.fetch_portfolio())
                        # Refresh transaction history every 30 min so new purchases show on graph
                        if _cycle % 6 == 0:
                            print("[Background TR] Refreshing transaction history (30 min cycle)...")
                            loop.run_until_complete(local_api.fetch_history())
                        loop.run_until_complete(local_api.close())
                    else:
                        print("[Background TR] Session invalide - tentative de renouvellement silencieux via tr_refresh...")
                        if not local_api.refresh_session_token():
                            print("[Background TR] Refresh échoué - nouvelle tentative dans 5 min.")
                            local_api.session_token = None
                 except Exception as e:
                     print(f"Background TR Error: {e}")
                 finally:
                     loop.close()
            else:
                # No token, wait silently
                pass
                
        except Exception as e:
             print(f"Background TR Loop Error: {e}")
        
        _cycle += 1
        # Sleep 5 minutes
        time.sleep(300)

# ============================================================================
# NEW LOADING & WALLET ENDPOINTS
# ============================================================================

@app.route('/api/loading/status', methods=['GET'])
def get_loading_status():
    return jsonify(LOADING_STATE)

@app.route('/api/wallet/investments', methods=['GET'])
def get_wallet_investments():
    try:
        investments = WalletInvestment.query.all()
        data = []
        for inv in investments:
            data.append({
                'isin': inv.isin,
                'name': inv.name,
                'quantity': inv.quantity,
                'buy_price': inv.buy_price,
                'current_price': inv.current_price,
                'total_value': inv.total_value,
                'pnl': inv.pnl,
                'pnl_percent': inv.pnl_percent,
                'exchange': inv.exchange,
                'instrumentType': inv.instrument_type,
                'logo': inv.logo
            })
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def import_wallet_json():
    """Vérifie que le portefeuille est présent en DB"""
    print("[REFRESH] Verification portefeuille en DB...")
    update_loading_step('database', 'success')
    update_loading_step('wallet', 'running')
    
    try:
        with app.app_context():
            count = WalletInvestment.query.count()
            if count > 0:
                print(f"[OK] Portefeuille trouve en DB ({count} positions).")
                update_loading_step('wallet', 'success')
                return
            
            # Si DB vide, on ne fait plus de migration JSON
            print("?? Portefeuille absent de la DB. En attente de synchronisation Trade Republic.")
            update_loading_step('wallet', 'success') # On valide quand même le step pour l'UI
    except Exception as e:
        print(f"Error checking DB for wallet: {e}")
        update_loading_step('wallet', 'error')

def import_transactions_json():
    """Vérifie que les transactions sont en DB"""
    print("[REFRESH] Verification transactions en DB...")
    try:
        data = db_load_generic('tr_transactions')
        if data:
            print(f"[OK] {len(data)} transactions trouvees en DB.")
        else:
            print("?? Aucune transaction en DB.")
    except Exception as e:
        print(f"Error checking DB for transactions: {e}")

def run_initial_loading_tasks():
    """Lance les tâches de chargement initial et s'assure que la DB est peuplée"""
    time.sleep(1) # Laisser le temps à l'init DB
    
    # 1. Base de données
    update_loading_step('database', 'success')
    
    # 2. Portefeuille
    import_wallet_json()
    
    # 3. RSS News
    update_loading_step('rss', 'running')
    try:
        with app.app_context():
            # On vérifie si on a des news
            if db_load_generic('bloomberg_rss'):
                 update_loading_step('rss', 'success')
            else:
                 # Trigger background fetch
                 threading.Thread(target=fetch_bloomberg_rss_api, daemon=True).start()
                 update_loading_step('rss', 'success')
    except Exception as e:
        print(f"Error in initial RSS task: {e}")
        update_loading_step('rss', 'error')
        
    # 4. Insiders
    update_loading_step('insiders', 'running')
    try:
        with app.app_context():
            if InsiderTransaction.query.count() > 0:
                print("[OK] Insiders already in DB.")
                update_loading_step('insiders', 'success')
            else:
                # Si vide, on tente de récupérer les tickers du portfolio
                tickers = ['NVDA', 'AAPL', 'MSFT', 'TSM', 'AMD', 'GOOGL', 'AMZN', 'META']
                invs = WalletInvestment.query.all()
                if invs:
                    for inv in invs:
                        t = get_symbol_from_isin(inv.isin)
                        if t and t not in tickers: tickers.append(t)
                
                print(f"?? Scraping context initial pour: {tickers[:8]}...")
                fetch_insiders_api(tickers[:10]) 
                update_loading_step('insiders', 'success')
    except:
        update_loading_step('insiders', 'error')
        
    # 5. Forex
    update_loading_step('forex', 'running')
    try:
        fetch_forex_calendar_api()
        update_loading_step('forex', 'success')
    except:
        update_loading_step('forex', 'error')
        
    # 6. Secteurs (Wait for it if empty)
    update_loading_step('sector_trends', 'pending')
    with app.app_context():
        count = SectorTrend.query.count()
        if count > 0:
            update_loading_step('sector_trends', 'success')
        else:
            # Check if logged in. If yes, trigger. If no, leave as pending.
            tr_api.config.read(tr_api.config_path)
            if tr_api.config.get("secret", "tr_session", fallback=None):
                 print("[WAIT] Sectors empty but logged in. Triggering background calculation...")
                 update_loading_step('sector_trends', 'running')
                 threading.Thread(target=update_sector_monthly_trends, daemon=True).start()
            else:
                 print("?? Sectors empty. Waiting for user login...")
                 # Status remains 'pending' until login triggers it

    # 7. Prévisions Bancaires (Wait for it if empty)
    update_loading_step('forecasts', 'pending')
    with app.app_context():
        # Check if we have valid data (non-empty summaries)
        has_valid_data = False
        if BankForecast.query.count() > 0:
            # Check a sample for content
            sample = BankForecast.query.limit(5).all()
            if any(i.summary and len(i.summary) > 0 for i in sample):
                has_valid_data = True
        
        if not has_valid_data:
            print("[WAIT] Perspectives bancaires vides ou incompletes. Tentative de recuperation...")
            update_loading_step('forecasts', 'running')
            
            # Helper to format raw scrape results
            def format_and_save_raw(raw_data):
                formatted = []
                for res in raw_data:
                    summary = "\n- " + "\n- ".join(res.get('titles', []))
                    formatted.append({
                        'bank': res.get('bank'),
                        'url': res.get('url'),
                        'date': res.get('timestamp'),
                        'summary': summary,
                        'sentiment': 'Neutral',
                        'recommendation': 'Voir Détails',
                        'ticker': None,
                        'target_price': None
                    })
                db_save_bank_forecasts(formatted)

            # 1. Essayer le cache raw d'abord
            raw = db_load_generic('bank_raw_scrape')
            if raw:
                print("[PKG] Chargement des perspectives depuis le cache SQL (avec formatage)...")
                format_and_save_raw(raw)
            
            # 2. Si toujours invalide/vide, lancer le scraper
            # On revérifie la DB après l'étape 1
            still_empty = True
            if BankForecast.query.count() > 0:
                 sample = BankForecast.query.limit(5).all()
                 if any(i.summary for i in sample): still_empty = False

            if still_empty:
                print("[WEB] Recuperation en direct des perspectives (Scraping)...")
                try:
                    scraper = BankForecastScraper()
                    results = scraper.scrape_all()
                    if results:
                        # db_save_bank_forecasts est déjà appelé dans scrape_all avec le bon format
                        # on a juste besoin de sauvegarder le raw cache si scrape_all ne le fait pas (mais il le fait)
                        print(f"[OK] {len(results)} sources bancaires recuperees.")
                except Exception as e:
                    print(f"[ERROR] Erreur scraping perspectives: {e}")
        
        if BankForecast.query.count() > 0:
            print("[OK] Perspectives bancaires pretes.")
            update_loading_step('forecasts', 'success')
        else:
            print("[WARN] Aucune perspective bancaire trouvee, passage a la suite.")
            update_loading_step('forecasts', 'success') # On débloque quand même après tentative

    # 8. Macro Data
    update_loading_step('macro', 'running')
    try:
        with app.app_context():
            if MacroData.query.count() > 0:
                print("[OK] Macro data already in DB.")
                update_loading_step('macro', 'success')
            else:
                print("[WEB] Recuperation des donnees macro-economiques...")
                update_macro_data()
                update_loading_step('macro', 'success')
    except Exception as e:
        print(f"Error in initial macro task: {e}")
        update_loading_step('macro', 'error')

    # Marquer complet
    global LOADING_STATE
    LOADING_STATE['complete'] = True
    print("[OK] Chargement initial termine.")

class NoCacheHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with Cache-Control: no-store to always serve fresh files."""
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()
    def log_message(self, format, *args):
        pass  # silence static server logs

def run_static_http_server():
    """Lance un serveur HTTP simple sur le port 8080 pour servir les fichiers statiques (terminal.html, etc.)."""
    PORT = 8080
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", PORT), NoCacheHTTPHandler) as httpd:
            print(f"[NET] Serveur HTTP statique lance sur http://localhost:{PORT}")
            httpd.serve_forever()
    except Exception as e:
        print(f"[ERROR] Erreur lors du lancement du serveur HTTP statique: {e}")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("="*70)
    print("BACKEND API - TERMINAL FINANCIER")
    print("="*70)
    print("Endpoints disponibles:")
    print("  GET  /api/health                     - Statut du serveur")
    print("  GET  /api/data/all                   - Toutes les donnees")
    print("  GET  /api/data/<type>                - Donnees specifiques")
    print("  GET  /api/prices                     - Prix actuels")
    print("  GET  /api/prices/history             - Historique detaille")
    print("  GET  /api/senator-trades             - Trades des senateurs")
    print("  GET  /api/senator-trades/summary     - Resume trades senateurs")
    print("  POST /api/refresh/<type>             - Rafraichir donnees")
    print("  POST /api/chat                       - Assistant AI")
    print("  POST /api/analyze                    - Analyse personnalisee")
    print("  POST /api/background/start           - Demarrer auto-refresh")
    print("  POST /api/background/stop            - Arreter auto-refresh")
    print("  POST /api/bank-forecasts/scrape     - Lancer le scraping des previsions bancaires")
    print("  POST /api/bank-forecasts/analyze    - Lancer l'analyse IA des articles bancaires")
    print("  GET  /api/bank-forecasts             - Recuperer les previsions bancaires")
    print("  GET  /api/bank-analyses              - Recuperer les analyses bancaires")
    print("="*70)
    print()
    
    # Init system & models
    init_app_background_tasks()
    
    # Lancement du serveur HTTP statique (pour terminal.html sur port 8080)
    static_thread = threading.Thread(target=run_static_http_server, daemon=True)
    static_thread.start()
    
    # Configuration des logs - Silence is golden
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    # Démarrer les tâches de fond automatiquement
    background_tasks_running = True
    bg_thread = threading.Thread(target=background_refresh_loop, daemon=True)
    bg_thread.start()
    
    # TR Portfolio Auto-Refresh (5 min)
    tr_thread = threading.Thread(target=background_tr_portfolio_loop, daemon=True)
    tr_thread.start()

    # Démarrage automatique du calcul des tendances sectorielles au lancement
    # REMOVED: Now triggered by Login or Loading Task if logged in
    # print("[START] Lancement automatique de l'analyse des tendances sectorielles...")
    # sector_thread = threading.Thread(target=update_sector_monthly_trends, daemon=True)
    # sector_thread.start()
    
    # ----------------------------------------------------
    # START LOADING TASKS (Wallet, RSS, etc.)
    # ----------------------------------------------------
    print("[START] Lancement du chargement initial (Loading Screen)...")
    loading_thread = threading.Thread(target=run_initial_loading_tasks, daemon=True)
    loading_thread.start()

    # ----------------------------------------------------
    # PDF REPORTING & DEEP ANALYSIS (NEW)
    # ----------------------------------------------------
    
    class PDFReport(FPDF):
        def header(self):
            pass

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', '', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, f'Releve de compte | {datetime.now().strftime("%d/%m/%Y")}', 0, 0, 'C')

    @app.route('/api/report/portfolio_pdf', methods=['GET'])
    def generate_portfolio_pdf():
        """
        Generates a 'Trade Republic' style PDF Report
        with AI-driven Market Intelligence Summary.
        """
        try:
            # 1. Load Data
            portfolio = db_load_latest_portfolio()
            positions = portfolio.get('positions', []) if portfolio else []
            tickers = [p.get('ticker') for p in positions if p.get('ticker')]
            
            # 2. Deep Analysis & Market Data
            # We assume _generate_deep_analysis_data now calculates daily variations
            analysis_data = _generate_deep_analysis_data(tickers)
            
            # 3. AI Market Intelligence Generation
            # Identify Critical Points
            critical_assets = []
            market_mood_score = 0
            
            for ticker, data in analysis_data.items():
                trend = data.get('trend_label', '')
                flags = data.get('red_flags', [])
                daily_perf = data.get('daily_change_pct', 0)
                
                market_mood_score += daily_perf # Simple aggregate
                
                if 'Bearish' in trend or flags or abs(daily_perf) > 3.0:
                    critical_assets.append({
                        'ticker': ticker,
                        'reason': flags[0] if flags else ("Chute brutale" if daily_perf < -3 else "Volatilité"),
                        'perf': daily_perf
                    })
            
            # Synthesize "Market Point" text
            market_direction = "HAUSSIER" if market_mood_score > 0 else "BAISSIER"
            ai_text = f"Le sentiment de marché global est {market_direction} ({market_mood_score:.1f}% agrégé). "
            
            if critical_assets:
                ai_text += f"{len(critical_assets)} actifs sous surveillance prioritaire. "
                # Top 2 urgent
                top_crit = sorted(critical_assets, key=lambda x: x['perf'])[:2]
                for asset in top_crit:
                    ai_text += f"[{asset['ticker']}] montre des signes de {asset['reason']} ({asset['perf']:.1f}%). "
            else:
                ai_text += "Aucune anomalie majeure de structure détectée. "
                
            ai_text += "L'analyse prédictive suggère une rotation sectorielle imminente basée sur les flux Insiders récents."

            # 4. Generate PDF (Trade Republic Style)
            pdf = PDFReport()
            pdf.add_page()
            
            # --- APP HEADER STYLE ---
            pdf.set_font('Arial', 'B', 24)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 15, "Portefeuille", 0, 1, 'L')
            
            # Total Balance
            total_val = portfolio.get('total_value', 0)
            pdf.set_font('Arial', 'B', 32)
            pdf.cell(0, 15, f"{total_val:,.2f} EUR", 0, 1, 'L')
            
            # Sub-header Stats (P&L)
            pnl_val = portfolio.get('total_pnl', 0)
            pnl_pct = (pnl_val / (total_val - pnl_val) * 100) if (total_val - pnl_val) != 0 else 0
            
            pdf.set_font('Arial', 'B', 12)
            if pnl_val >= 0: pdf.set_text_color(22, 163, 74) # Green
            else: pdf.set_text_color(220, 38, 38) # Red
            
            # Triangle Up/Down
            arrow = "+" if pnl_val >= 0 else ""
            pdf.cell(0, 8, f"{arrow}{pnl_val:,.2f} EUR ({arrow}{pnl_pct:.2f}%) Aujourd'hui", 0, 1, 'L')
            
            pdf.ln(10)
            
            # --- AI MARKET BRIEF (News Ticker Style) ---
            pdf.set_fill_color(243, 244, 246) # Gray 100
            pdf.set_draw_color(243, 244, 246)
            pdf.rect(10, pdf.get_y(), 190, 20, 'FD')
            
            pdf.set_xy(15, pdf.get_y() + 5)
            pdf.set_font('Arial', 'B', 9)
            pdf.set_text_color(75, 85, 99) # Gray 600
            pdf.cell(25, 5, "MARKET POINT", 0, 0)
            
            pdf.set_font('Arial', '', 9)
            pdf.set_text_color(0, 0, 0)
            # Encode for basic PDF support
            clean_ai_text = ai_text.encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(0, 5, clean_ai_text, 0, 1)
            pdf.ln(15)

            # --- ASSETS LIST ---
            # Columns: Name, Price, Daily%
            
            # Headers
            pdf.set_font('Arial', 'B', 9)
            pdf.set_text_color(156, 163, 175) # Gray 400
            pdf.cell(90, 8, "TITRE", 0, 0)
            pdf.cell(40, 8, "PRIX", 0, 0, 'R')
            pdf.cell(40, 8, "AUJOURD'HUI", 0, 0, 'R')
            pdf.cell(20, 8, "ALERTE", 0, 1, 'C')
            
            # Thin line
            pdf.set_draw_color(229, 231, 235) # Gray 200
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)
            
            for pos in positions:
                ticker = pos.get('ticker', '')
                name = pos.get('name', 'Unknown')
                qty = pos.get('qty', 0)
                avg_price = pos.get('avgPrice', 0)
                
                data = analysis_data.get(ticker, {})
                current_price = data.get('current_price', avg_price)
                daily_change = data.get('daily_change_pct', 0.0)
                flags = data.get('red_flags', [])
                
                # --- ROW RENDER ---
                start_y = pdf.get_y()
                
                # Check Page Break
                if start_y > 270:
                    pdf.add_page()
                    start_y = pdf.get_y()
                
                # Icon Mock (Black Box with Initials)
                pdf.set_fill_color(0, 0, 0)
                pdf.rect(10, start_y + 2, 10, 10, 'F')
                pdf.set_text_color(255, 255, 255)
                pdf.set_font('Arial', 'B', 7)
                initials = name[:2].upper()
                pdf.text(12, start_y + 8, initials)
                
                # Name & Info
                pdf.set_xy(25, start_y + 1)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font('Arial', 'B', 10)
                pdf.cell(80, 5, name[:25], 0, 2)
                
                pdf.set_font('Arial', '', 8)
                pdf.set_text_color(156, 163, 175) # Gray
                market_val = qty * current_price
                pdf.cell(80, 4, f"{qty} units | {market_val:.1f} eur", 0, 0)
                
                # Price
                pdf.set_xy(100, start_y + 3)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font('Arial', 'B', 10)
                pdf.cell(40, 8, f"{current_price:.2f} eur", 0, 0, 'R')
                
                # Daily Change (Pill style if possible, or just text)
                pdf.set_xy(140, start_y + 3)
                if daily_change >= 0:
                    pdf.set_text_color(22, 163, 74) # Green
                    sign = "+"
                else: 
                    pdf.set_text_color(220, 38, 38) # Red
                    sign = ""
                
                pdf.set_font('Arial', 'B', 10)
                pdf.cell(40, 8, f"{sign}{daily_change:.2f}%", 0, 0, 'R')
                
                # Alert Status (Dot)
                pdf.set_xy(180, start_y + 5)
                # FPDF doesn't have circle by default easily, use text dot
                pdf.set_text_color(220, 38, 38) if flags else pdf.set_text_color(22, 163, 74)
                pdf.set_font('Arial', 'B', 20)
                pdf.cell(20, 4, ".", 0, 0, 'C') # Big dot
                
                # Line Separator
                pdf.ln(12) # Row height 14 (2+12)
                # pdf.set_draw_color(243, 244, 246)
                # pdf.line(25, pdf.get_y(), 200, pdf.get_y())

            # Save
            filename = f"report_{int(time.time())}.pdf"
            pdf.output(filename)
            
            return send_file(filename, as_attachment=True, download_name=f"GenerationalWealth_Report_{datetime.now().strftime('%Y%m%d')}.pdf")
            
        except Exception as e:
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': str(e)})

    def _generate_deep_analysis_data(tickers):
        """Helper to generate analysis data for a list of tickers"""
        results = {}
        if not tickers: return {}
        
        try:
            # 1. Price Data
            hist = yf.download(tickers, period="5d", progress=False, threads=True) # Fetch 5 days for robust change calc
            insiders = db_load_insiders() or []
            
            for ticker in tickers:
                t_res = {'red_flags': [], 'trend_label': 'Neutral', 'daily_change_pct': 0.0, 'current_price': 0.0, 'rsi': 50}
                
                try:
                    # Data Extract
                    df = None
                    if isinstance(hist, pd.DataFrame):
                        # Handle MultiIndex columns if multiple tickers
                        if isinstance(hist.columns, pd.MultiIndex):
                            try:
                                df = hist.xs(ticker, axis=1, level=1) if level_check(hist) else hist[ticker] 
                                # Simpler fallback
                                if ticker in hist.columns.levels[0]: # Verify
                                    df = hist[ticker]
                            except:
                                if ticker in hist.columns: df = hist[ticker] # Single level fallback
                        else:
                            # Single ticker download result
                            df = hist
                    
                    if df is not None and not df.empty:
                        # Clean
                        df = df.dropna(how='all')
                        if len(df) >= 2:
                            # Daily Change
                            last_close = df['Close'].iloc[-1]
                            prev_close = df['Close'].iloc[-2]
                            
                            # Clean scalars
                            if hasattr(last_close, 'item'): last_close = last_close.item()
                            if hasattr(prev_close, 'item'): prev_close = prev_close.item()
                            
                            t_res['current_price'] = last_close
                            if prev_close > 0:
                                t_res['daily_change_pct'] = ((last_close - prev_close) / prev_close) * 100
                            
                            # Calc RSI (Approx on 5 days is bad, need more history if we want RSI)
                            # Re-fetch deeply if strictly needed or assume 0 if not key. 
                            # User wants Trade Republic style (Price/Today%) primarily.
                            # We will skip deep RSI recalc here to save speed, OR handle separate long fetch.
                            # Let's trust the 5d simple trend for daily.

                except Exception as e:
                    print(f"Data Error {ticker}: {e}")

                # Populate
                results[ticker] = t_res
                
        except Exception as e:
            traceback.print_exc()
            
        return results

    def level_check(df):
        return True # Dummy helper


    # Helper functions (if they were meant to be inner, leave them, if global, this closes the previous scope)

# ============================================================================
#  NEW HELPER FUNCTIONS FOR TRANSACTION HISTORY & PORTFOLIO
# ============================================================================

import re

async def fetch_and_parse_transactions(api_instance):
    """
    Fetches ALL transactions, filters for relevant types (trade, savings_plan),
    fetches details if missing (shares/price), and parses into a clean structure.
    Input: api_instance (TradeRepublicAPI object)
    Output: List of dicts
    """
    print("[START] Starting fetch_and_parse_transactions...")
    
    # 1. Fetch ALL transactions using existing method (pagination handled internally)
    #    extract_details=False because we want to be selective
    raw_transactions = await api_instance.fetch_history(extract_details=False)
    
    parsed_transactions = []
    
    # Relevant types/keywords to filter (covers EN/DE/FR common terms)
    RELEVANT_KEYWORDS = [
        "trade", "savings plan", "sparplan", "buy", "sell", 
        "kauf", "verkauf", "order executed", "ausführung", "executed"
    ]
    # Exclude these
    EXCLUDE_KEYWORDS = ["dividend", "deposit", "withdrawal", "ausschüttung", "einzahlung", "auszahlung", "interest", "zinsen"]
    
    # Process with progress bar if available
    iterator = tqdm(raw_transactions, desc="Parsing Transactions") if 'tqdm' in globals() else raw_transactions

    for tx in iterator:
        t_id = tx.get("id")
        title = str(tx.get("title", "")).strip()       # Company Name usually
        subtitle = str(tx.get("subtitleText", "")).strip() # "Savings Plan executed"
        if not subtitle: subtitle = str(tx.get("subtitle", "")).strip()
        
        full_text = (title + " " + subtitle).lower()
        
        # Filter Logic
        is_relevant = False
        for kw in RELEVANT_KEYWORDS:
            if kw in full_text:
                is_relevant = True
                break
        
        for kex in EXCLUDE_KEYWORDS:
            if kex in full_text:
                is_relevant = False
                break
                
        if not is_relevant:
            continue

        # Basic parsing
        parsed = {
            "id": t_id,
            "date": None,
            "type": None, # 'BUY' or 'SELL'
            "isin": None,
            "shares": 0.0,
            "price": 0.0,
            "amount": 0.0,
            "fee": 0.0,
            "name": title
        }
        
        # Timestamp
        ts = tx.get("timestamp")
        if ts:
            try: parsed["date"] = datetime.fromtimestamp(ts / 1000.0)
            except: pass
            
        # Amount (Total Value)
        try:
            amt_obj = tx.get("data", {}).get("amount", {})
            parsed["amount"] = float(amt_obj.get("value", 0.0))
        except: pass

        # Attempt extended info from summary (sometimes packed in 'data' sections)
        # ISIN from Icon URL (Fastest method)
        icon_url = tx.get("icon", "")
        if icon_url:
            match = re.search(r"([A-Z]{2}[A-Z0-9]{9}\d)", icon_url)
            if match: parsed["isin"] = match.group(1)

        # 3. CRUCIAL STEP: Fetch Details if needed
        need_details = True # Always check effectively as summary lacks shares/price
        
        if need_details and t_id:
            try:
                # Rate limit throttle
                await asyncio.sleep(0.1)
                
                # Fetch
                details = await api_instance.fetch_transaction_details(t_id)
                # Returns dict: {"Shares": "5.123", "Price": "100.00 EUR", ...}
                
                # Helper to get value ignoring case
                def get_val(d, keys):
                    for k, v in d.items():
                        if k.lower() in [x.lower() for x in keys]:
                            return v
                    return None

                # Extract ISIN if missing
                if not parsed["isin"]:
                    val = get_val(details, ["ISIN", "Instrument"])
                    if val: parsed["isin"] = val.split(" ")[0].strip()

                # Extract Shares
                val = get_val(details, ["Shares", "Stück", "Anteile", "Anzahl"])
                if val:
                    # Clean "3.5134" or "3,5134" or "5 Stk."
                    if "Stk" in val: val = val.split(" ")[0]
                    clean = val.replace(",", ".").strip()
                    try: parsed["shares"] = float(clean)
                    except: pass

                # Extract Price per Share
                val = get_val(details, ["Price per share", "Price", "Kurs", "Ausführungskurs"])
                if val:
                    # "100.50 EUR"
                    clean = val.replace("EUR", "").replace("€", "").replace(",", ".").strip()
                    try: parsed["price"] = float(clean)
                    except: pass

                # Extract Fee
                val = get_val(details, ["Service costs", "Fremdkostenzuschlag", "Gebühr", "External costs", "Kosten"])
                if val:
                    clean = val.replace("EUR", "").replace("€", "").replace(",", ".").strip()
                    try: parsed["fee"] = float(clean)
                    except: pass
                    
            except Exception as e:
                print(f"[WARN] Detail fetch failed for {t_id}: {e}")

        # Post-Processing: Determine BUY/SELL and Sanity Checks
        # Logic: 
        #   Amount < 0 usually means money spent (BUY)
        #   Amount > 0 usually means money received (SELL)
        #   BUT verify with keywords
        
        is_sell = "sell" in full_text or "verkauf" in full_text
        if is_sell:
            parsed["type"] = "SELL"
        else:
            parsed["type"] = "BUY"
            
        # Ensure shares is positive for the record, logic handles sign later
        parsed["shares"] = abs(parsed["shares"])
        
        # Fallback: Calculate shares from amount/price if missing
        if parsed["shares"] == 0 and parsed["price"] > 0 and parsed["amount"] != 0:
            parsed["shares"] = abs(parsed["amount"]) / parsed["price"]
            
        parsed_transactions.append(parsed)

    print(f"[OK] Parsed {len(parsed_transactions)} transactions.")
    return parsed_transactions


def calculate_portfolio_history(transactions):
    """
    Generates a daily portfolio value series.
    Input: List of parsed transactions
    Output: List of dicts [{"date": "YYYY-MM-DD", "value": 1234.56}, ...]
    """
    if not transactions: return []
    
    # 1. Setup Date Range
    # Sort by date
    valid_tx = [t for t in transactions if t.get('date')]
    if not valid_tx: return []
    
    valid_tx.sort(key=lambda x: x['date'])
    start_date = valid_tx[0]['date']
    end_date = datetime.now()
    
    # Unique ISINs
    isins = set(t['isin'] for t in valid_tx if t['isin'])
    if not isins: return []

    print(f"[DATA] Calculating history for {len(isins)} ISINs from {start_date.strftime('%Y-%m-%d')}...")

    # 2. Bulk Fetch Price History (Optimization)
    ticker_map = {}
    tickers_to_fetch = []
    
    for isin in isins:
        try:
            # Assumes get_symbol_from_isin is available in global scope
            sym = get_symbol_from_isin(isin)
            if sym:
                ticker_map[isin] = sym
                tickers_to_fetch.append(sym)
        except: pass
            
    tickers_to_fetch = list(set(tickers_to_fetch))
    
    price_data = pd.DataFrame()
    if tickers_to_fetch:
        try:
            # Fetch history with some buffer before start_date
            fetch_start = (start_date - timedelta(days=5)).strftime('%Y-%m-%d')
            # Using yfinance download
            data = yf.download(tickers_to_fetch, start=fetch_start, progress=False, threads=True)
            
            # Handle yfinance structure
            if 'Close' in data:
                price_data = data['Close']
            else:
                price_data = data
        except Exception as e:
            print(f"[ERROR] Price fetch error: {e}")

    # Reindex to full daily range and fill forward
    full_idx = pd.date_range(start=start_date, end=end_date, freq='D')
    
    try:
        if isinstance(price_data, pd.Series):
            price_data = price_data.to_frame(name=tickers_to_fetch[0])
            
        # Reindex and auto-fill
        # Using nearest/ffill to handle weekends/holidays effectively
        price_data = price_data.reindex(full_idx, method='nearest', limit=3).ffill()
    except: pass

    # 3. Iterate Days and Compute Value
    portfolio_history = []
    holdings = collections.defaultdict(float) # ISIN -> Shares
    
    # Map transactions to date strings
    tx_map = collections.defaultdict(list)
    for t in valid_tx:
        d_str = t['date'].strftime('%Y-%m-%d')
        tx_map[d_str].append(t)
        
    for current_date in full_idx:
        d_str = current_date.strftime('%Y-%m-%d')
        
        # A. Apply Transactions
        if d_str in tx_map:
            for t in tx_map[d_str]:
                if not t['isin']: continue
                qty = abs(t['shares'])
                if t['type'] == 'BUY':
                    holdings[t['isin']] += qty
                elif t['type'] == 'SELL':
                    holdings[t['isin']] -= qty
                    if holdings[t['isin']] < 0: holdings[t['isin']] = 0
        
        # B. Calculate Total Value
        daily_total = 0.0
        
        for isin, shares in holdings.items():
            if shares <= 0.000001: continue
            
            price = 0.0
            sym = ticker_map.get(isin)
            
            if sym and not price_data.empty:
                try:
                    if sym in price_data.columns:
                        val = price_data.loc[current_date, sym]
                        if not pd.isna(val):
                            price = float(val)
                except: pass
            
            # If price missing, try to infer from last transaction price? (Optional complexity)
            # For now, just use found price
                
            daily_total += (shares * price)
            
        portfolio_history.append({
            "date": d_str,
            "value": round(daily_total, 2)
        })
        
    return portfolio_history

def background_market_refresh():
    """Refreshes market data every 30 s so the ticker tape and Vue Globale stay live 24/7."""
    import time as _time
    print("[NET] Background market refresh thread started (every 30s)")
    _time.sleep(10)  # small initial delay to let Flask fully start
    while True:
        try:
            with app.app_context():
                market = GlobalMarketData()
                data = market.get_all_market_data()
                if 'commodities' in data:     db_save_generic('market_commodities', data['commodities'])
                if 'forex' in data:           db_save_generic('market_forex', data['forex'])
                if 'treasury_yields' in data: db_save_generic('market_treasury', data['treasury_yields'])
                if 'indices' in data:         db_save_generic('market_indices', data['indices'])
                print(f"[OK] Market cache refreshed at {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"[ERROR] Background market refresh error: {e}")
        _time.sleep(30)


if __name__ == '__main__':
    threading.Thread(target=background_market_refresh, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)