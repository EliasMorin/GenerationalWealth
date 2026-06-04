from flask import Blueprint, request, jsonify
from ..utils.auth import _get_github_token_for_request, GROQ_API_KEY, GROQ_MODEL
from ..utils.token_bucket import call_groq_api
from ..utils.db import db_load_generic
import json
import traceback
from datetime import datetime, timedelta

# Create blueprint
ai_bp = Blueprint('ai', __name__)


@ai_bp.route('/news-recommendations', methods=['GET'])
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
                except Exception:
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
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# Helper function to fetch Bloomberg RSS (would normally be implemented)
def fetch_bloomberg_rss_api():
    """Fetch Bloomberg RSS data"""
    # This would normally fetch from Bloomberg RSS feed
    # For now, return empty structure
    return {
        'items': [],
        'fetched_at': datetime.now().isoformat()
    }