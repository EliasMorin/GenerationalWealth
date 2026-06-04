"""
Test script to verify the module structure without requiring external dependencies.
Just checks that files exist and have the expected content structure.
"""

import os

def test_file_structure():
    """Test that our expected files exist"""
    base_dir = "/Users/elias/Downloads/GenerationalWealth (1)/GenerationalWealth"

    # Expected files and directories
    expected_paths = [
        "app/__init__.py",
        "app/config.py",
        "app/models/user.py",
        "app/models/portfolio.py",
        "app/services/trade_republic.py",
        "app/services/institutional_data.py",
        "app/services/cash_analyzer.py",
        "app/services/truth_social.py",
        "app/services/global_market_data.py",
        "app/services/market_correlator.py",
        "app/services/technical_analyzer.py",
        "app/services/youtube_live.py",
        "app/services/news_logger.py",
        "app/services/capitol_trades.py",
        "app/services/macro_economic.py",
        "app/services/bank_forecast.py",
        "app/services/polymarket.py",
        "app/services/token_bucket.py",
        "app/utils/cache.py",
        "app/utils/http.py",
        "app/utils/auth.py",
        "app/utils/db.py",
        "app/api/auth.py",
        "app/api/portfolio.py",
        "app/api/market.py",
        "app/api/claude.py",
        "app/api/institutional.py",
        "app/api/cash.py",
        "app/api/ai.py",
        "app/api/refresh.py",
        "app/tasks/live_updates.py",
        "app/tasks/session_watchdog.py",
        "run.py"
    ]

    missing_files = []
    existing_files = []

    for path in expected_paths:
        full_path = os.path.join(base_dir, path)
        if os.path.exists(full_path):
            existing_files.append(path)
        else:
            missing_files.append(path)

    print(f"Found {len(existing_files)} expected files")
    print(f"Missing {len(missing_files)} expected files")

    if missing_files:
        print("\nMissing files:")
        for f in missing_files[:10]:  # Show first 10 missing
            print(f"  - {f}")
        if len(missing_files) > 10:
            print(f"  ... and {len(missing_files) - 10} more")

    # Check that run.py exists
    run_py_path = os.path.join(base_dir, "run.py")
    if os.path.exists(run_py_path):
        print("\n✓ run.py entry point exists")
        # Check its content
        with open(run_py_path, 'r') as f:
            content = f.read()
            if "from app import create_app" in content:
                print("✓ run.py has correct import")
            else:
                print("⚠ run.py may have incorrect import")
    else:
        print("\n✗ run.py entry point missing")

    return len(missing_files) == 0

def test_directory_structure():
    """Test that our expected directories exist"""
    base_dir = "/Users/elias/Downloads/GenerationalWealth (1)/GenerationalWealth"

    expected_dirs = [
        "app",
        "app/models",
        "app/services",
        "app/utils",
        "app/api",
        "app/tasks"
    ]

    missing_dirs = []
    existing_dirs = []

    for dir_path in expected_dirs:
        full_path = os.path.join(base_dir, dir_path)
        if os.path.isdir(full_path):
            existing_dirs.append(dir_path)
        else:
            missing_dirs.append(dir_path)

    print(f"\nFound {len(existing_dirs)} expected directories")
    print(f"Missing {len(missing_dirs)} expected directories")

    if missing_dirs:
        print("\nMissing directories:")
        for d in missing_dirs:
            print(f"  - {d}")

    return len(missing_dirs) == 0

if __name__ == "__main__":
    print("Testing file and directory structure...")
    files_ok = test_file_structure()
    dirs_ok = test_directory_structure()

    if files_ok and dirs_ok:
        print("\n✓ All structure tests passed!")
        exit(0)
    else:
        print("\n✗ Some structure tests failed!")
        exit(1)