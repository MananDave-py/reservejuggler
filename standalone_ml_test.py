"""Standalone test for the hourly withdrawal prediction model.

Run from the project folder:
    .\\.venv\\Scripts\\python.exe standalone_ml_test.py

This script reads the CSV directly.  It does not import Django, the allocator,
or the simulator.
"""

import csv
from datetime import datetime
from math import cos, pi, sin, sqrt
from pathlib import Path

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


CSV_PATH = Path(__file__).resolve().parent / "data" / "treasury_4tier_dataset.csv"
LAGS = (0, 1, 2, 3, 6, 12, 24, 48, 168)
ROLLING_WINDOWS = (6, 24, 168)
MAX_LOOKBACK = max(max(LAGS), max(ROLLING_WINDOWS) - 1)


def load_csv():
    """Read just the fields used by this standalone prediction test."""
    records = []
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            records.append(
                {
                    "timestamp": row["timestamp"],
                    "hour": int(row["timestamp"][11:13]),
                    "weekday": datetime.fromisoformat(row["timestamp"]).weekday(),
                    "deposits": float(row["deposits_usd"]),
                    "withdrawals": float(row["withdrawals_usd"]),
                    "net_flow": float(row["net_flow_usd"]),
                    "repo_rate": float(row["tier1_repo_rate_apy"]),
                    "bond_yield": float(row["tier2_bond_yield_pct"]),
                    "bond_price": float(row["tier2_bond_price_index"]),
                    "stock_price": float(row["tier3_stock_index_price"]),
                    "stock_volatility": float(row["tier3_stock_volatility_pct"]),
                }
            )
    return records


def build_features(records, index):
    """Use data through hour index to predict withdrawals at index + 1."""
    current = records[index]
    features = []

    for field in ("deposits", "withdrawals", "net_flow"):
        features.extend(records[index - lag][field] for lag in LAGS)
        for window in ROLLING_WINDOWS:
            values = [row[field] for row in records[index - window + 1 : index + 1]]
            features.extend((sum(values) / window, max(values), min(values)))

    features.extend(
        (
            current["repo_rate"],
            current["bond_yield"],
            current["bond_price"],
            current["stock_price"],
            current["stock_volatility"],
            sin(2 * pi * current["hour"] / 24),
            cos(2 * pi * current["hour"] / 24),
            sin(2 * pi * current["weekday"] / 7),
            cos(2 * pi * current["weekday"] / 7),
        )
    )
    return features


def main():
    records = load_csv()
    if len(records) <= MAX_LOOKBACK + 2:
        raise ValueError("The CSV does not contain enough hourly rows.")

    features = []
    targets = []
    for index in range(MAX_LOOKBACK, len(records) - 1):
        features.append(build_features(records, index))
        targets.append(records[index + 1]["withdrawals"])

    # Keep the newest 20% of hours unseen during evaluation.
    split_at = int(len(features) * 0.8)
    train_x, test_x = features[:split_at], features[split_at:]
    train_y, test_y = targets[:split_at], targets[split_at:]

    model = HistGradientBoostingRegressor(
        learning_rate=0.08,
        max_iter=200,
        max_leaf_nodes=15,
        l2_regularization=1.0,
        random_state=42,
    )
    model.fit(train_x, train_y)
    predictions = model.predict(test_x)
    test_start_index = MAX_LOOKBACK + split_at + 1

    # Refit on all historical data before predicting the hour after the CSV.
    model.fit(features, targets)
    next_hour_forecast = model.predict([build_features(records, len(records) - 1)])[0]

    print(f"CSV: {CSV_PATH}")
    print(f"Training rows: {len(train_x):,}")
    print(f"Test rows: {len(test_x):,}")
    print(f"Test MAE: ${mean_absolute_error(test_y, predictions):,.2f}")
    print(f"Test RMSE: ${sqrt(mean_squared_error(test_y, predictions)):,.2f}")
    wape = sum(abs(actual - predicted) for actual, predicted in zip(test_y, predictions))
    wape /= sum(test_y)
    print(f"Test accuracy (1 - WAPE): {(1 - wape) * 100:.2f}%")
    print("\nLatest held-out next-hour comparisons:")
    for offset in range(len(predictions) - 5, len(predictions)):
        record = records[test_start_index + offset]
        actual = test_y[offset]
        predicted = predictions[offset]
        print(
            f"{record['timestamp']}: actual ${actual:,.2f} | "
            f"predicted ${predicted:,.2f} | error ${abs(actual - predicted):,.2f}"
        )
    print(f"Next-hour withdrawal forecast: ${next_hour_forecast:,.2f}")


if __name__ == "__main__":
    main()
