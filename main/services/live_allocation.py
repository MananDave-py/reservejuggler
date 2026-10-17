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


def get_live_allocation(available_cash=DEFAULT_AVAILABLE_CASH, repo_window_open=None):
    """Return all data needed by the live allocation API response."""
    if repo_window_open is None:
        repo_window_open = datetime.now(timezone.utc).hour == 17

    forecast_result = _withdrawal_forecast()
    forecast = forecast_result["next_hour_forecast"]
    articles = fetch_market_news()
    points = news_to_points(articles)
    allocation = suggest_points_allocation(
        available_cash=available_cash,
        predicted_withdrawals=forecast["withdrawals_usd"],
        repo_window_open=repo_window_open,
        points=points,
    )

    return {
        "forecast": forecast,
        "model_metrics": forecast_result["model_metrics"],
        "market_news": articles,
        "market_points": points,
        "repo_window_open": repo_window_open,
        "available_cash_usd": available_cash,
        "suggested_allocation": allocation,
    }
