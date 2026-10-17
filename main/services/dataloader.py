import csv
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = PROJECT_ROOT / "data" / "treasury_4tier_dataset.csv"

REQUIRED_COLUMNS = {
    "timestamp",
    "deposits_usd",
    "withdrawals_usd",
    "net_flow_usd",
    "repo_sweep_window_open",
    "repo_sweep_mature",
    "tier1_repo_rate_apy",
    "tier2_bond_yield_pct",
    "tier2_bond_price_index",
    "tier2_bond_mod_duration",
    "tier3_stock_index_price",
    "tier3_stock_volatility_pct",
    "tier1_early_redemption_haircut_pct",
    "tier2_bond_liquidation_haircut_pct",
    "tier3_stock_liquidation_haircut_pct",
    "emergency_overdraft_penalty_apr_pct",
}


def load_hourly_data(path=CSV_PATH):
    records = []

    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing columns: {sorted(missing)}")

        for line_number, row in enumerate(reader, start=2):
            try:
                deposits = Decimal(row["deposits_usd"])
                withdrawals = Decimal(row["withdrawals_usd"])
                net_flow = Decimal(row["net_flow_usd"])
                record = {
                    "timestamp": datetime.fromisoformat(row["timestamp"]),
                    "deposits_usd": float(deposits),
                    "withdrawals_usd": float(withdrawals),
                    "net_flow_usd": float(net_flow),
                    "repo_sweep_window_open":
                        row["repo_sweep_window_open"].lower() == "true",
                    "repo_sweep_mature":
                        row["repo_sweep_mature"].lower() == "true",
                    "tier1_repo_rate_apy": float(row["tier1_repo_rate_apy"]),
                    "tier2_bond_yield_pct":
                        float(row["tier2_bond_yield_pct"]),
                    "tier2_bond_price_index":
                        float(row["tier2_bond_price_index"]),
                    "tier2_bond_mod_duration":
                        float(row["tier2_bond_mod_duration"]),
                    "tier3_stock_index_price":
                        float(row["tier3_stock_index_price"]),
                    "tier3_stock_volatility_pct":
                        float(row["tier3_stock_volatility_pct"]),
                    "tier1_early_redemption_haircut_pct":
                        float(row["tier1_early_redemption_haircut_pct"]),
                    "tier2_bond_liquidation_haircut_pct":
                        float(row["tier2_bond_liquidation_haircut_pct"]),
                    "tier3_stock_liquidation_haircut_pct":
                        float(row["tier3_stock_liquidation_haircut_pct"]),
                    "emergency_overdraft_penalty_apr_pct": float(
                        row["emergency_overdraft_penalty_apr_pct"]
                    ),
                }
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Invalid value on CSV line {line_number}"
                ) from error

            if abs(net_flow - (deposits - withdrawals)) > Decimal("0.01"):
                raise ValueError(
                    f"net_flow_usd does not match deposits minus withdrawals "
                    f"on line {line_number}"
                )

            if records and record["timestamp"] != (
                records[-1]["timestamp"] + timedelta(hours=1)
            ):
                raise ValueError(
                    f"Timestamp is not hourly on line {line_number}"
                )

            records.append(record)

    if not records:
        raise ValueError("The CSV contains no data rows.")

    return records
