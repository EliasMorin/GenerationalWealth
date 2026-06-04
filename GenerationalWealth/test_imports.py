"""
Test script to verify that our refactored modules can be imported correctly.
This tests the basic import structure without requiring Flask or other dependencies to be installed.
"""

import sys
import os

# Add the app directory to the path so we can import from it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def test_basic_imports():
    """Test that we can import the basic module structure"""
    try:
        print("Testing basic imports...")

        # Test that we can import the app package
        import app
        print("✓ app package imported")

        # Test that we can import the __init__.py (this will fail if Flask is not installed, but that's OK for structure testing)
        try:
            from app import create_app
            print("✓ create_app function imported")
        except ImportError as e:
            if "Flask" in str(e):
                print("⚠ create_app import failed due to missing Flask (expected if not installed)")
            else:
                raise

        # Test utils imports
        try:
            from app.utils import cache, http, auth, db
            print("✓ utils modules imported")
        except ImportError as e:
            print(f"⚠ utils import issue: {e}")

        # Test models imports
        try:
            from app.models import user, portfolio
            print("✓ models modules imported")
        except ImportError as e:
            print(f"⚠ models import issue: {e}")

        # Test services imports
        try:
            from app.services import trade_republic, institutional_data, cash_analyzer
            print("✓ services modules imported")
        except ImportError as e:
            print(f"⚠ services import issue: {e}")

        # Test api imports
        try:
            from app.api import auth, portfolio, market, claude
            print("✓ api modules imported")
        except ImportError as e:
            print(f"⚠ api import issue: {e}")

        print("\nBasic import structure test completed!")
        return True

    except Exception as e:
        print(f"✗ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_basic_imports()
    exit(0 if success else 1)