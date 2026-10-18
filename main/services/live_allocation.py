"""Combine the withdrawal forecast, Marketaux news, and points allocator."""

from datetime import datetime, timezone
from functools import lru_cache

from .mlengine import train_and_evaluate
from .news_service import fetch_market_news, news_to_points
from .points_allocator import suggest_points_allocation


DEFAULT_AVAILABLE_CASH = 10_000_000.0


@lru_cache(maxsize=1)
def _withdrawal_forecast():
    """Train once per Django process and reuse the forecast for requests."""
    return train_and_evaluate()


def _build_allocation(forecast_result, available_cash, repo_window_open, api_token=None):
    """Combine one withdrawal forecast with fresh news and allocation points."""
    forecast = forecast_result["next_hour_forecast"]
    try:
        articles = fetch_market_news(api_token=api_token)
        news_status = {"ok": True, "message": "Market news API is working."}
    except (RuntimeError, ValueError) as error:
        # Keep the core allocation demo usable without external API credentials.
        articles = []
        message = str(error)
        if "Set MARKETAUX_API_TOKEN" in message:
            message = "No Marketaux key is configured; neutral news points were used."
        news_status = {"ok": False, "message": message}
    points = news_to_points(articles)
    allocation = suggest_points_allocation(
        available_cash=available_cash,
        predicted_withdrawals=forecast["withdrawals_usd"],
        repo_window_open=repo_window_open,
        points=points,
    )
    allocation_percentages = {
        tier: (allocation[tier] / available_cash * 100) if available_cash else 0
        for tier in ("reserve", "repo", "bonds", "equities")
    }
    return {
        "forecast": forecast,
        "model_metrics": forecast_result["model_metrics"],
        "market_news": articles,
        "market_news_status": news_status,
        "market_points": points,
        "repo_window_open": repo_window_open,
        "available_cash_usd": available_cash,
        "suggested_allocation": allocation,
        "allocation_percentages": allocation_percentages,
    }


def get_allocation_from_records(records, available_cash=DEFAULT_AVAILABLE_CASH,
                                repo_window_open=None, api_token=None):
    """Train from uploaded CSV records and return the resulting allocation."""
    if repo_window_open is None:
        repo_window_open = datetime.now(timezone.utc).hour == 17

    return _build_allocation(
        train_and_evaluate(records), available_cash, repo_window_open, api_token
    )


def get_live_allocation(available_cash=DEFAULT_AVAILABLE_CASH, repo_window_open=None):
    """Return an allocation trained from the project's default CSV file."""
    if repo_window_open is None:
        repo_window_open = datetime.now(timezone.utc).hour == 17

    return _build_allocation(
        _withdrawal_forecast(), available_cash, repo_window_open
    )
