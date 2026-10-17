"""Allocate cash using the withdrawal forecast and news-derived risk points."""


MINIMUM_RESERVE = 1_000_000.0
BASE_RESERVE_MULTIPLIER = 1.25
MINIMUM_EQUITY_WEIGHT = 0.05


def _normalise(weights):
    """Turn non-negative tier scores into weights that add up to one."""
    weights = {name: max(0.0, value) for name, value in weights.items()}
    total = sum(weights.values())
    return {name: value / total for name, value in weights.items()}


def _keep_minimum_equity_weight(weights):
    """Keep a small diversified equity holding even during bearish news."""
    weights = _normalise(weights)
    if weights["equities"] >= MINIMUM_EQUITY_WEIGHT:
        return weights

    other_tiers = [name for name in weights if name != "equities"]
    other_total = sum(weights[name] for name in other_tiers)
    weights["equities"] = MINIMUM_EQUITY_WEIGHT
    remaining_weight = 1 - MINIMUM_EQUITY_WEIGHT
    for name in other_tiers:
        weights[name] = weights[name] / other_total * remaining_weight
    return weights


def suggest_points_allocation(
    available_cash,
    predicted_withdrawals,
    repo_window_open,
    points,
):
    """Return an explainable four-tier allocation.

    ``points`` is the dictionary returned by ``news_to_points``. A high risk
    score increases the Reserve requirement and shifts the investable surplus
    away from Equities toward Repo and Bonds.
    """
    available_cash = max(0.0, float(available_cash))
    predicted_withdrawals = max(0.0, float(predicted_withdrawals))
    risk_points = max(0.0, min(100.0, float(points.get("risk_points", 0))))
    equity_points = max(-100.0, min(100.0, float(points.get("equity_points", 0))))
    bond_points = max(-50.0, min(50.0, float(points.get("bond_points", 0))))
    repo_points = max(-50.0, min(50.0, float(points.get("repo_points", 0))))

    # Risk can raise the withdrawal safety buffer from 1.25x to 1.50x.
    reserve_multiplier = BASE_RESERVE_MULTIPLIER + (risk_points / 400)
    reserve = max(MINIMUM_RESERVE, predicted_withdrawals * reserve_multiplier)
    reserve = min(available_cash, reserve)
    surplus = available_cash - reserve

    # Always calculate the desired Repo target. When the sweep window is
    # closed, the caller can queue this amount for the next available window.
    weights = _keep_minimum_equity_weight(
        {
            "repo": 0.35 + (repo_points / 500) + (risk_points / 500),
            "bonds": 0.30 + (bond_points / 500) + (risk_points / 1000),
            "equities": 0.35 + (equity_points / 300) - (risk_points / 250),
        }
    )

    return {
        "reserve": reserve,
        "repo": surplus * weights["repo"],
        "bonds": surplus * weights["bonds"],
        "equities": surplus * weights["equities"],
        "allocation_weights": weights,
        "reserve_multiplier": reserve_multiplier,
        "repo_execution_status": (
            "execute_now" if repo_window_open else "queue_for_next_sweep"
        ),
        "points_used": {
            "equity_points": equity_points,
            "bond_points": bond_points,
            "repo_points": repo_points,
            "risk_points": risk_points,
        },
    }
