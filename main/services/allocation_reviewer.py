"""Use Gemini to explain the strengths and risks of a live allocation."""

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


def _local_gemini_key():
    """Read GEMINI_API_KEY from the ignored project .env file."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "GEMINI_API_KEY":
            return value.strip().strip('"').strip("'")
    return None


def _review_prompt(allocation_data):
    """Build a bounded prompt from the calculated allocation, not raw secrets."""
    forecast = allocation_data["forecast"]
    points = allocation_data["market_points"]
    allocation = allocation_data["suggested_allocation"]
    articles = [
        {
            "title": article["title"],
            "sentiment": article["sentiment"],
            "label": article["label"],
        }
        for article in allocation_data["market_news"]
    ]
    facts = {
        "available_cash_usd": allocation_data["available_cash_usd"],
        "repo_window_open": allocation_data["repo_window_open"],
        "withdrawal_forecast": forecast,
        "market_points": points,
        "suggested_allocation": {
            tier: allocation[tier]
            for tier in ("reserve", "repo", "bonds", "equities")
        },
        "reserve_multiplier": allocation["reserve_multiplier"],
        "news_articles": articles,
    }
    required_shape = {
        "summary": "short explanation",
        "strengths": ["..."],
        "weaknesses": ["..."],
        "risk_breakdown": {
            "risk_level": "low, medium, or high",
            "risk_points_explained": "...",
            "reserve_effect": "...",
            "investment_effect": "...",
        },
        "tier_analysis": {
            "tier_0_reserve": "...",
            "tier_1_repo": "...",
            "tier_2_bonds": "...",
            "tier_3_equities": "...",
        },
        "signals_used": ["..."],
        "recommended_checks": ["..."],
    }
    return (
        "You are reviewing an educational treasury allocation result. Use only "
        "the provided facts. Explain the calculation clearly and do not invent "
        "prices, news events, returns, or data that is absent. Return JSON only "
        "using this exact shape:\\n"
        + json.dumps(required_shape, indent=2)
        + "\\n\\nFacts to review:\\n"
        + json.dumps(facts, indent=2)
    )


def review_allocation(allocation_data, api_key=None, model=None):
    """Return Gemini's structured review of a result from get_live_allocation.

    Set GEMINI_API_KEY in .env. GEMINI_MODEL can optionally override the model
    name when a different Gemini model is enabled for the API key.
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY") or _local_gemini_key()
    if not api_key:
        raise ValueError("Set GEMINI_API_KEY before requesting an AI review.")

    model = model or os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    request_body = {
        "contents": [{"parts": [{"text": _review_prompt(allocation_data)}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    request = Request(
        f"{GEMINI_API_URL}/{model}:generateContent",
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
            "User-Agent": "ReserveJuggler/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as error:
        try:
            error_payload = json.loads(error.read().decode("utf-8"))
            message = error_payload.get("error", {}).get("message", "Request failed.")
        except (json.JSONDecodeError, UnicodeDecodeError):
            message = "Request failed."
        raise RuntimeError(f"Gemini request failed ({error.code}): {message}") from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError("Could not reach the Gemini API.") from error

    try:
        review_text = payload["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(review_text)
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("Gemini did not return a valid JSON review.") from error


def review_live_allocation(available_cash=10_000_000.0, repo_window_open=None):
    """Build a live allocation and its Gemini explanation in one call."""
    from .live_allocation import get_live_allocation

    allocation_data = get_live_allocation(available_cash, repo_window_open)
    return {
        "allocation_data": allocation_data,
        "ai_review": review_allocation(allocation_data),
    }
