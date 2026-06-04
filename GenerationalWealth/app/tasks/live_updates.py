import threading
import time
from datetime import datetime
from ..utils.db import db_load_latest_portfolio, db_save_portfolio
from ..services.trade_republic import TradeRepublicAPI

def run_live_updates(app):
    """Background thread for live portfolio updates"""
    with app.app_context():
        print("[LIVE] Live updates thread started")

        while True:
            try:
                # Sleep for 5 seconds between updates
                time.sleep(5)

                # Load latest portfolio to see if we need to update
                portfolio = db_load_latest_portfolio()

                # Initialize TR API
                tr_api = TradeRepublicAPI()

                # Try to get phone from config
                try:
                    tr_api.config.read(tr_api.config_path)
                    phone = tr_api.config.get("secret", "phone_number", fallback=None)
                except Exception:
                    phone = None

                if phone:
                    # Fetch fresh data
                    fresh_data = tr_api.fetch_portfolio()
                    if fresh_data:
                        # Save to database
                        db_save_portfolio(fresh_data, user_phone=phone)
                        print(f"[LIVE] Portfolio updated at {datetime.now().strftime('%H:%M:%S')}")
                    else:
                        print("[LIVE] Warning: Could not fetch fresh portfolio data")
                else:
                    print("[LIVE] No phone configured for live updates")

            except Exception as e:
                print(f"[LIVE] Error in live updates: {e}")
                # Continue the loop despite errors
                time.sleep(10)  # Wait longer before retrying after error


def start_live_updates_thread(app):
    """Start the live updates thread"""
    thread = threading.Thread(target=run_live_updates, args=(app,), daemon=True)
    thread.start()
    print("[OK] Live updates thread started")
    return thread