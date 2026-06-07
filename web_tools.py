"""
web_tools.py — JARVIS v3 Web Search (DuckDuckGo, no API key needed)
"""
from __future__ import annotations
import logging, urllib.parse
import requests

logger = logging.getLogger(__name__)


def search_web(query: str, max_results: int = 5) -> str:
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote_plus(query)}&format=json&no_redirect=1&no_html=1"
        r = requests.get(url, timeout=10, headers={"User-Agent": "JARVIS/3.0"})
        r.raise_for_status()
        data = r.json()
        results = []
        if data.get("AbstractText"):
            results.append(f"📌 {data['AbstractText']}\n   Source: {data.get('AbstractSource','')}")
        if data.get("Answer"):
            results.append(f"💡 {data['Answer']}")
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"• {topic['Text'][:200]}\n  {topic.get('FirstURL','')}")
        if not results:
            return f"No results for: {query}"
        return f"🔍 '{query}'\n{'─'*40}\n" + "\n\n".join(results[:max_results])
    except Exception as e:
        return f"Search error: {e}"


def fetch_url(url: str, max_chars: int = 5000) -> str:
    try:
        import re
        r = requests.get(url, timeout=15, headers={"User-Agent": "JARVIS/3.0"})
        r.raise_for_status()
        text = re.sub(r"<script[^>]*>.*?</script>", "", r.text, flags=re.DOTALL|re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL|re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()[:max_chars]
    except Exception as e:
        return f"Fetch error: {e}"
