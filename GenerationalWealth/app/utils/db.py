from datetime import datetime
import threading
from typing import Any, Optional, Dict, List

# These will be initialized properly when using application factory
# For now, we'll use placeholder imports or define stubs
_db = None
_app = None

def init_db(app, db_instance):
    """Initialize the database utility with app and db instances."""
    global _app, _db
    _app = app
    _db = db_instance

# Import models - will be available after models are created
def _get_models():
    """Lazy load models to avoid circular imports."""
    try:
        from ..models import (
            User, AppUser, IsinTicker, PortfolioSnapshot, NewsItem,
            InsiderTransaction, BankForecast, SectorTrend, WalletInvestment,
            WalletCash, MacroData, IpSession, CachedData, TechnicalWarning,
            BankAnalysis, WalletInvestment, WalletCash
        )
        return {
            'User': User,
            'AppUser': AppUser,
            'IsinTicker': IsinTicker,
            'PortfolioSnapshot': PortfolioSnapshot,
            'NewsItem': NewsItem,
            'InsiderTransaction': InsiderTransaction,
            'BankForecast': BankForecast,
            'SectorTrend': SectorTrend,
            'WalletInvestment': WalletInvestment,
            'WalletCash': WalletCash,
            'MacroData': MacroData,
            'IpSession': IpSession,
            'CachedData': CachedData,
            'TechnicalWarning': TechnicalWarning,
            'BankAnalysis': BankAnalysis
        }
    except Exception as e:
        print(f"Error loading models: {e}")
        return {}


def db_save_generic(key: str, data: Any):
    """Save generic cached data to database."""
    try:
        if _app is None or _db is None:
            print("[WARN] DB not initialized for db_save_generic")
            return

        with _app.app_context():
            models = _get_models()
            CachedData = models.get('CachedData')
            if not CachedData:
                print("[ERROR] CachedData model not available")
                return

            cache = CachedData.query.get(key)
            if not cache:
                cache = CachedData(key=key, data=data)
                _db.session.add(cache)
            else:
                cache.data = data
                cache.updated_at = datetime.utcnow()
            _db.session.commit()
    except Exception as e:
        print(f"DB Error save generic {key}: {e}")


def db_load_generic(key: str, default=None):
    """Load generic cached data from database."""
    try:
        if _app is None:
            print("[WARN] DB not initialized for db_load_generic")
            return default

        with _app.app_context():
            models = _get_models()
            CachedData = models.get('CachedData')
            if not CachedData:
                print("[ERROR] CachedData model not available")
                return default

            cache = CachedData.query.get(key)
            if cache and cache.data is not None:
                # If data is empty, return it anyway to avoid crashing frontend
                # that expects an object or list
                return cache.data
            return default
    except Exception as e:
        print(f"Error loading generic key {key}: {e}")
        return default


def db_save_portfolio(data, user_phone=None):
    """Save portfolio data to database."""
    try:
        if _app is None or _db is None:
            print("[WARN] DB not initialized for db_save_portfolio")
            return

        with _app.app_context():
            models = _get_models()
            User = models.get('User')
            WalletCash = models.get('WalletCash')
            WalletInvestment = models.get('WalletInvestment')
            PortfolioSnapshot = models.get('PortfolioSnapshot')

            if not all([User, WalletCash, WalletInvestment, PortfolioSnapshot]):
                print("[ERROR] Required models not available for portfolio save")
                return

            # Identify User from Active TradeRepublic Session (Config)
            user_id = None
            try:
                # Priority 1: Use provided phone number
                if user_phone:
                    u = User.query.filter_by(phone=user_phone).first()
                    if u: user_id = u.id

                # Priority 2: Fallback to config if not provided
                # Note: This assumes tr_api is available in globals - not ideal
                # Will need to be refactored to pass TR API instance or config
                if not user_id:
                    # This is a simplified version - in practice, we'd need
                    # access to the TR API instance or config
                    print("[INFO] User identification via TR API fallback not implemented in utils")
            except Exception as e:
                print(f"Error identifying user for save: {e}")

            if user_id is None:
                print("[WARN] Could not identify user for portfolio save")
                return

            # Update detailed Wallet Tables
            # 1. Update Cash
            cash_obj = data.get('availableCash', data.get('available_cash', {}))
            cash_val = 0.0
            if isinstance(cash_obj, dict):
                cash_val = float(cash_obj.get('amount', 0))
            elif isinstance(cash_obj, (int, float)):
                cash_val = float(cash_obj)

            cash_db = WalletCash.query.filter_by(user_id=user_id).first()
            if not cash_db:
                _db.session.add(WalletCash(amount=cash_val, user_id=user_id))
            else:
                cash_db.amount = cash_val
                cash_db.updated_at = datetime.utcnow()

            # 2. Update Investments
            investments = data.get('my_investments', data.get('positions', data.get('positions_detailed', [])))
            for item in investments:
                if not item.get('isin'):
                    continue
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
                    _db.session.add(inv)
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
            total_investments = sum(
                float(i.get('total_value', i.get('totalValue', 0)))
                for i in investments
            )
            snap = PortfolioSnapshot(
                user_id=user_id,
                cash=cash_val,
                total_value=total_investments + cash_val,
                positions_count=len(investments),
                raw_data=data
            )
            _db.session.add(snap)
            _db.session.commit()
    except Exception as e:
        print(f"DB Error save portfolio: {e}")


def db_load_latest_portfolio():
    """Load latest portfolio data from database."""
    try:
        if _app is None:
            print("[WARN] DB not initialized for db_load_latest_portfolio")
            return {}

        with _app.app_context():
            # Trigger background tasks if data is missing
            # Note: These imports would need to be adjusted in the refactored version
            if not db_load_generic('seasonality'):
                print("Missing seasonality: triggering background fetch...")
                # In a real implementation, we'd have a proper task queue
                # For now, just print the message

            if not db_load_generic('options_GOOG'):
                print("Missing options data: triggering GOOG fetch...")

            # Determine User ID - simplified version
            # In the refactored app, this would come from request/context
            user_id = None
            try:
                # This would normally come from request.headers.get('X-User-Phone')
                # For now, we'll try to get the first user or use a default
                models = _get_models()
                User = models.get('User')
                if User:
                    u = User.query.first()
                    if u:
                        user_id = u.id
            except Exception as e:
                print(f"Error determining user ID: {e}")

            if user_id is not None:
                models = _get_models()
                PortfolioSnapshot = models.get('PortfolioSnapshot')
                if PortfolioSnapshot:
                    snap = PortfolioSnapshot.query.filter_by(user_id=user_id).order_by(PortfolioSnapshot.id.desc()).first()
                    if snap and snap.raw_data:
                        return snap.raw_data

            # Fallback to load_portfolio_data function if needed
            # This would need to be imported or defined
            return {}
    except Exception as e:
        print(f"Error loading portfolio from DB: {e}")
        return {}


def db_save_insiders(data_dict):
    """Save dictionary of insiders {ticker: { 'all': [...] }} to DB"""
    if not data_dict or len(data_dict) == 0:
        print("[WARN] db_save_insiders: No data provided, skipping update to avoid clearing DB")
        return

    try:
        if _app is None or _db is None:
            print("[WARN] DB not initialized for db_save_insiders")
            return

        with _app.app_context():
            models = _get_models()
            InsiderTransaction = models.get('InsiderTransaction')
            if not InsiderTransaction:
                print("[ERROR] InsiderTransaction model not available")
                return

            _db.session.query(InsiderTransaction).delete()

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
                    _db.session.add(txn)
            _db.session.commit()
    except Exception as e:
        print(f"DB Error save insiders: {e}")


def db_load_insiders():
    """Load insider transactions from database."""
    try:
        if _app is None:
            print("[WARN] DB not initialized for db_load_insiders")
            return {}

        with _app.app_context():
            def parse_date(date_str):
                try:
                    # Handle "May 15 '24" format
                    d = date_str.strip().replace("'", "20")
                    return datetime.strptime(d, "%b %d %Y")
                except:
                    return None

            models = _get_models()
            InsiderTransaction = models.get('InsiderTransaction')
            if not InsiderTransaction:
                print("[ERROR] InsiderTransaction model not available")
                return {}

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
    """Save bank forecasts to database."""
    try:
        if _app is None or _db is None:
            print("[WARN] DB not initialized for db_save_bank_forecasts")
            return

        with _app.app_context():
            models = _get_models()
            BankForecast = models.get('BankForecast')
            if not BankForecast:
                print("[ERROR] BankForecast model not available")
                return

            # Check existing entries to decide update vs insert
            for f in forecasts:
                url = f.get('url')
                if not url:
                    continue

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
                    _db.session.add(db_item)
            _db.session.commit()
    except Exception as e:
        print(f"DB Error save forecasts: {e}")


def db_load_bank_forecasts():
    """Load bank forecasts from database."""
    try:
        if _app is None:
            print("[WARN] DB not initialized for db_load_bank_forecasts")
            return []

        with _app.app_context():
            def format_date(d):
                if not d:
                    return ""
                if isinstance(d, datetime):
                    return d.isoformat()
                return str(d)

            models = _get_models()
            BankForecast = models.get('BankForecast')
            if not BankForecast:
                print("[ERROR] BankForecast model not available")
                return []

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


# Additional helper functions that might be needed

def db_save_sector_trends(trends_data):
    """Save sector trends data."""
    try:
        if _app is None or _db is None:
            print("[WARN] DB not initialized for db_save_sector_trends")
            return

        with _app.app_context():
            models = _get_models()
            SectorTrend = models.get('SectorTrend')
            if not SectorTrend:
                print("[ERROR] SectorTrend model not available")
                return

            # Clear existing trends
            _db.session.query(SectorTrend).delete()

            # Save new trends
            for sector, trend_info in trends_data.items():
                trend = SectorTrend(
                    sector=sector,
                    trend=trend_info.get('trend', ''),
                    strength=trend_info.get('strength', 0),
                    confidence=trend_info.get('confidence', 0),
                    data=trend_info.get('data', {})
                )
                _db.session.add(trend)
            _db.session.commit()
    except Exception as e:
        print(f"DB Error save sector trends: {e}")


def db_load_sector_trends():
    """Load sector trends from database."""
    try:
        if _app is None:
            print("[WARN] DB not initialized for db_load_sector_trends")
            return {}

        with _app.app_context():
            models = _get_models()
            SectorTrend = models.get('SectorTrend')
            if not SectorTrend:
                print("[ERROR] SectorTrend model not available")
                return {}

            trends = SectorTrend.query.all()
            result = {}
            for trend in trends:
                result[trend.sector] = {
                    'trend': trend.trend,
                    'strength': trend.strength,
                    'confidence': trend.confidence,
                    'data': trend.data or {},
                    'updated_at': trend.updated_at.isoformat() if trend.updated_at else None
                }
            return result
    except Exception as e:
        print(f"Error loading sector trends: {e}")
        return {}