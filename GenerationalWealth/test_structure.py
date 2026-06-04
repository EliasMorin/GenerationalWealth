"""
Test script to verify the module structure works correctly.
"""

def test_imports():
    """Test that we can import our modules without errors."""
    try:
        print("Testing app package imports...")

        # Test app package
        from app import create_app
        print("✓ app package imported")

        # Test utils
        from app.utils.cache import ensure_isin_cache, get_sector_reference_index
        from app.utils.http import create_retry_session
        from app.utils.auth import _load_groq_key, _load_github_tokens
        from app.utils.db import db_save_generic, db_load_generic
        print("✓ utils package imported")

        # Test models
        from app.models.user import User, AppUser
        from app.models.portfolio import WalletInvestment, WalletCash, PortfolioSnapshot
        print("✓ models package imported")

        # Test services
        from app.services.trade_republic import TradeRepublicAPI
        from app.services.institutional_data import RealInstitutionalDataScraper
        from app.services.cash_analyzer import CashAnalyzer
        print("✓ services package imported")

        # Test api
        from app.api.auth import auth_bp
        print("✓ api package imported")

        print("\nAll imports successful! ✓")
        return True

    except Exception as e:
        print(f"✗ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    exit(0 if success else 1)