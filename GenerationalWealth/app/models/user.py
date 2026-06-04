from flask_sqlalchemy import SQLAlchemy
import hashlib
from datetime import datetime

# db will be initialized via application factory
db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(50), unique=True, nullable=False)
    # In production, hash this PIN!
    pin = db.Column(db.String(10), nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AppUser(db.Model):
    """Web-app authentication — separate from Trade Republic credentials."""
    __tablename__ = 'app_user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    # Per-user GitHub token for AI analysis
    github_token = db.Column(db.String(200), default='')
    # Optional link to TR credentials (phone stored, pin hashed)
    tr_phone = db.Column(db.String(50), default='')
    tr_pin_hash = db.Column(db.String(128), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password: str) -> bool:
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()