from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# db will be initialized via application factory
db = SQLAlchemy()


class IsinTicker(db.Model):
    __tablename__ = 'isin_ticker'

    isin = db.Column(db.String(20), primary_key=True)
    ticker = db.Column(db.String(20))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class PortfolioSnapshot(db.Model):
    __tablename__ = 'portfolio_snapshot'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Link to User
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    cash = db.Column(db.Float)
    total_value = db.Column(db.Float)
    positions_count = db.Column(db.Integer)
    # Storing the full complex JSON structure for frontend compatibility
    raw_data = db.Column(db.JSON)


class NewsItem(db.Model):
    __tablename__ = 'news_item'

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(50))  # 'Bloomberg', 'RSS', etc.
    title = db.Column(db.String(500))
    url = db.Column(db.String(500), unique=True)
    summary = db.Column(db.Text)
    published_at = db.Column(db.DateTime)
    sentiment = db.Column(db.String(20))  # 'Positive', 'Negative'
    sentiment_score = db.Column(db.Float)
    related_tickers = db.Column(db.JSON)  # List of tickers


class InsiderTransaction(db.Model):
    __tablename__ = 'insider_transaction'

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
    __tablename__ = 'bank_forecast'

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
    __tablename__ = 'sector_trend'

    id = db.Column(db.Integer, primary_key=True)
    sector_name = db.Column(db.String(100), unique=True)
    monthly_trend = db.Column(db.Float)
    stocks_count = db.Column(db.Integer)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.JSON)  # Full list of stocks in sector


class CachedData(db.Model):
    __tablename__ = 'cached_data'

    key = db.Column(db.String(100), primary_key=True)
    data = db.Column(db.JSON)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class TechnicalWarning(db.Model):
    __tablename__ = 'technical_warning'

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20), unique=True)
    rsi = db.Column(db.Float)
    signal_type = db.Column(db.String(50))  # 'Overbought', 'Oversold', 'Trend Reversal'
    level = db.Column(db.String(20))  # 'Warning', 'Critical'
    message = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class BankAnalysis(db.Model):
    __tablename__ = 'bank_analysis'

    id = db.Column(db.Integer, primary_key=True)
    bank = db.Column(db.String(50))
    title = db.Column(db.String(500))
    url = db.Column(db.String(500))  # Not unique as multiple banks might link same generic page? but usually unique
    analysis = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class WalletInvestment(db.Model):
    __tablename__ = 'wallet_investment'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Link to User
    isin = db.Column(db.String(20), nullable=False)  # Not unique globally anymore
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
    __tablename__ = 'wallet_cash'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Link to User
    amount = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(10), default='EUR')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class MacroData(db.Model):
    __tablename__ = 'macro_data'

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), unique=True)  # e.g., 'interest_rates', 'inflation'
    data = db.Column(db.JSON)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class IpSession(db.Model):
    """Maps a client IP to its Trade Republic session token."""
    __tablename__ = 'ip_session'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(64), unique=True, nullable=False)
    tr_session_token = db.Column(db.Text, default='')
    tr_phone = db.Column(db.String(50), default='')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)