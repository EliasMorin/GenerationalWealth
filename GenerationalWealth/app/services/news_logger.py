import os
import json
from typing import Dict, Any

# Assuming these will be imported from utils or defined locally if not available
try:
    from ..services.youtube_live import db_get_news_segments
except ImportError:
    def db_get_news_segments(limit=50):
        return []


class NewsLogger:
    def __init__(self, json_file="bloomberg_news.json"):
        self.json_file = json_file
        # No load from file needed

    def load_data(self) -> Dict[str, Any]:
        # Fetch from DB for compatibility
        return {"news_segments": db_get_news_segments()}

    def save_data(self):
        pass

    def add_news_segment(self, title: str, ticker_fragments: list, ai_summary: str):
        # Import here to avoid circular imports
        from ..services.youtube_live import db_save_news_segment
        db_save_news_segment(title, ticker_fragments, ai_summary)