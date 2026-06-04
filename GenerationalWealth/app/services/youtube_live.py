import cv2
import queue
import threading
import time
import yt_dlp
from typing import Optional

# Assuming these will be imported from utils or defined locally if not available
try:
    from ..utils.http import create_retry_session
except ImportError:
    def create_retry_session(retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 504)):
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
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


# News-related functions (moved from backend.py)
def db_save_news_segment(title, ticker_fragments, ai_summary):
    try:
        # Import here to avoid circular imports
        from .. import db
        from ..models.news import NewsItem
        from datetime import datetime

        with db.session.begin():
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
        # Import here to avoid circular imports
        from .. import db
        from ..models.news import NewsItem

        with db.session.begin():
            items = NewsItem.query.filter_by(source="Bloomberg Live").order_by(NewsItem.published_at.desc()).limit(limit).all()
            return [{
                "timestamp": i.published_at.isoformat() if i.published_at else "",
                "main_title": i.title,
                "ticker_fragments": i.related_tickers,
                "ai_summary": i.summary,
                "fragment_count": len(i.related_tickers or [])
            } for i in items]
    except Exception as e:
        print(f"DB Error get news: {e}")
        return []