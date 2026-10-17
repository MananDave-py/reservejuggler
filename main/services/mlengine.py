"""Train a one-hour-ahead withdrawal forecast from the treasury dataset.

The forecast is an input to a later tier allocator; it does not choose tier
allocations itself.  This dataset contains no allocation labels, so the model
learns to forecast withdrawals rather than imitate a portfolio decision.
"""

from datetime import timedelta
from math import cos, pi, sin, sqrt

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from .dataloader import load_hourly_data


FLOW_FIELDS = ("deposits_usd", "withdrawals_usd", "net_flow_usd")
MARKET_FIELDS = (
    "tier1_repo_rate_apy",
    "tier2_bond_yield_pct",
    "tier2_bond_price_index",
    "tier2_bond_mod_duration",
    "tier3_stock_index_price",
    "tier3_stock_volatility_pct",
)
LAGS = (0, 1, 2, 3, 6, 12, 24, 48, 168)
ROLLING_WINDOWS = (6, 24, 168)
MAX_LOOKBACK = max(max(LAGS), max(ROLLING_WINDOWS) - 1)


def _features_at(records, index):
    """Build features using only records available through ``index``."""
    current = records[index]
    features = []

    for field in FLOW_FIELDS:
        for lag in LAGS:
            features.append(records[index - lag][field])

    for field in FLOW_FIELDS:
        for window in ROLLING_WINDOWS:
            values = [row[field] for row in records[index - window + 1:index + 1]]
            features.extend((sum(values) / window, max(values), min(values)))

    for field in MARKET_FIELDS:
        features.append(current[field])

    hour_angle = 2 * pi * current["timestamp"].hour / 24
    weekday_angle = 2 * pi * current["timestamp"].weekday() / 7
    year_position = current["timestamp"].timetuple().tm_yday
    year_angle = 2 * pi * year_position / 366
    features.extend((
        sin(hour_angle), cos(hour_angle),
        sin(weekday_angle), cos(weekday_angle),
        sin(year_angle), cos(year_angle),
        float(current["repo_sweep_window_open"]),
        float(current["repo_sweep_mature"]),
    ))
    return features


def _new_model():
    return HistGradientBoostingRegressor(
        learning_rate=0.08,
        max_iter=200,
        max_leaf_nodes=15,
        l2_regularization=1.0,
        random_state=42,
    )


def _metrics(actual, predicted):
    return {
        "mae_usd": float(mean_absolute_error(actual, predicted)),
        "rmse_usd": float(sqrt(mean_squared_error(actual, predicted))),
    }


def train_and_evaluate(records=None, test_fraction=0.2):
    """Train/evaluate chronologically, then fit a final model on all history.

    Returns a dict containing test metrics, timestamped holdout predictions, a
    fitted scikit-learn model, and a next-hour forecast after the last CSV row.
    The model object itself is not JSON serializable and should not be sent
    directly to a template or API response.
    """
    if not 0 < test_fraction < 0.5:
        raise ValueError("test_fraction must be greater than 0 and less than 0.5")

    records = load_hourly_data() if records is None else records
    if len(records) <= MAX_LOOKBACK + 2:
        raise ValueError(
            f"At least {MAX_LOOKBACK + 3} hourly records are required."
        )

    feature_rows = []
    targets = []
    target_timestamps = []
    persistence_baseline = []
    rolling_baseline = []

    # Features end at hour t; the target is the withdrawal at hour t+1.
    for index in range(MAX_LOOKBACK, len(records) - 1):
        feature_rows.append(_features_at(records, index))
        targets.append(records[index + 1]["withdrawals_usd"])
        target_timestamps.append(records[index + 1]["timestamp"])
        persistence_baseline.append(records[index]["withdrawals_usd"])
        prior_24_hours = records[index - 23:index + 1]
        rolling_baseline.append(
            sum(row["withdrawals_usd"] for row in prior_24_hours) / 24
        )

    split_at = int(len(feature_rows) * (1 - test_fraction))
    if split_at == 0 or split_at >= len(feature_rows):
        raise ValueError("Not enough rows for the requested chronological split.")

    train_x, test_x = feature_rows[:split_at], feature_rows[split_at:]
    train_y, test_y = targets[:split_at], targets[split_at:]

    evaluation_model = _new_model()
    evaluation_model.fit(train_x, train_y)
    test_predictions = evaluation_model.predict(test_x)
    test_actual = targets[split_at:]

    baseline_metrics = {
        "previous_hour": _metrics(
            test_actual, persistence_baseline[split_at:]
        ),
        "previous_24_hour_average": _metrics(
            test_actual, rolling_baseline[split_at:]
        ),
    }

    final_model = _new_model()
    final_model.fit(feature_rows, targets)
    next_hour_value = float(final_model.predict([_features_at(records, len(records) - 1)])[0])

    predictions = [
        {
            "timestamp": target_timestamps[index].isoformat(sep=" "),
            "actual_withdrawals_usd": float(test_actual[offset]),
            "predicted_withdrawals_usd": float(test_predictions[offset]),
            "previous_hour_baseline_usd": float(persistence_baseline[index]),
            "previous_24_hour_average_usd": float(rolling_baseline[index]),
        }
        for offset, index in enumerate(range(split_at, len(feature_rows)))
    ]

    last_timestamp = records[-1]["timestamp"]
    return {
        "target": "withdrawals_usd for the next hourly row",
        "training_rows": split_at,
        "test_rows": len(feature_rows) - split_at,
        "test_period_start": target_timestamps[split_at].isoformat(sep=" "),
        "test_period_end": target_timestamps[-1].isoformat(sep=" "),
        "baseline_metrics": baseline_metrics,
        "model_metrics": _metrics(test_actual, test_predictions),
        "predictions": predictions,
        "next_hour_forecast": {
            "timestamp": (last_timestamp + timedelta(hours=1)).isoformat(sep=" "),
            "withdrawals_usd": next_hour_value,
        },
        "model": final_model,
    }
