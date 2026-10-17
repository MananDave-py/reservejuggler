"""Fetch Marketaux financial news and convert it into portfolio risk points."""

import json
import os
from pathlib import Path
from statistics import mean
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


MARKETAUX_URL = "https://api.marketaux.com/v1/news/all"


def _local_api_token():
    """Read the local .env token when it is not already in the environment."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "MARKETAUX_API_TOKEN":
            return value.strip().strip('"').strip("'")
    return None


def _article_sentiment(article):
    """Average Marketaux sentiment across entities identified in one article."""
    entity_scores = [
        float(entity["sentiment_score"])
        for entity in article.get("entities", [])
        if entity.get("sentiment_score") is not None
    ]
    return mean(entity_scores) if entity_scores else 0.0


def _sentiment_label(score):
    if score >= 0.15:
        return "Bullish"
    if score <= -0.15:
        return "Bearish"
    return "Neutral"


def fetch_market_news(api_token=None, limit=3):
    """Return recent English financial news from Marketaux.

    ``MARKETAUX_API_TOKEN`` must be set in the environment unless ``api_token``
    is supplied directly. The function returns only the fields needed by the
    points system, keeping the view/template payload small.
    """
    api_token = api_token or os.environ.get("MARKETAUX_API_TOKEN") or _local_api_token()
    if not api_token:
        raise ValueError("Set MARKETAUX_API_TOKEN before fetching news.")

    query = urlencode(
        {
            "api_token": api_token,
            "entity_types": "equity,index,etf",
            "must_have_entities": "true",
            "group_similar": "true",
            "language": "en",
            "limit": max(1, min(int(limit), 3)),
        }
    )

    try:
        request = Request(
            f"{MARKETAUX_URL}?{query}",
            headers={"User-Agent": "ReserveJuggler/1.0"},
        )
        with urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except HTTPError as error:
        try:
            error_payload = json.loads(error.read().decode("utf-8"))
            message = error_payload.get("error", {}).get("message", "Access denied.")
        except (json.JSONDecodeError, UnicodeDecodeError):
            message = "Access denied."
        raise RuntimeError(
            f"Marketaux request failed ({error.code}): {message}"
        ) from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError("Could not fetch news from Marketaux.") from error

    error = payload.get("error")
    if error:
        message = error.get("message", "Unknown Marketaux error.")
        raise RuntimeError(f"Marketaux response: {message}")

    articles = []
    for article in payload.get("data", []):
        sentiment = _article_sentiment(article)
        articles.append(
            {
                "title": article.get("title", "Untitled article"),
                "url": article.get("url", ""),
                "published_at": article.get("published_at", ""),
                "source": article.get("source", ""),
                "sentiment": sentiment,
                "label": _sentiment_label(sentiment),
            }
        )
    return articles


def news_to_points(articles):
    """Convert article sentiment into transparent, bounded allocation points.

    Positive sentiment favours equities. Negative sentiment increases the
    preference for liquid repo and bonds, and increases the reserve buffer.
    """
    if not articles:
        return {
            "equity_points": 0,
            "bond_points": 0,
            "repo_points": 0,
            "risk_points": 0,
            "article_count": 0,
            "average_sentiment": 0.0,
        }

    sentiments = [max(-1.0, min(1.0, article["sentiment"])) for article in articles]
    average_sentiment = mean(sentiments)
    # Small values near zero are neutral. Only clearly bearish news adds risk.
    negative_share = sum(score <= -0.15 for score in sentiments) / len(sentiments)

    equity_points = round(max(-100, min(100, average_sentiment * 100)))
    # Safe assets receive points when the news sentiment is negative.
    bond_points = round(max(-50, min(50, -average_sentiment * 55)))
    repo_points = round(max(-50, min(50, -average_sentiment * 35)))
    risk_points = round(max(0, min(100, negative_share * 70 - average_sentiment * 30)))

    return {
        "equity_points": equity_points,
        "bond_points": bond_points,
        "repo_points": repo_points,
        "risk_points": risk_points,
        "article_count": len(articles),
        "average_sentiment": round(average_sentiment, 4),
    }
