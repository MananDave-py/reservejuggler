"""Replay hourly cash flows and investments under an allocation policy."""

from datetime import datetime, timedelta

from .allocator import suggest_allocation
from .dataloader import load_hourly_data


HOURS_PER_YEAR = 365 * 24
DEFAULT_STARTING_CASH = 20_000_000.0


def _forecast_lookup(forecasts):
    """Accept model output or a mapping keyed by forecast timestamp."""
    if forecasts is None:
        return {}
    model_result = forecasts if isinstance(forecasts, dict) else None
    if model_result is not None and "predictions" not in model_result:
        lookup = {}
        for timestamp, value in model_result.items():
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            lookup[timestamp] = max(0.0, float(value))
        return lookup

    prediction_rows = (
        model_result.get("predictions", [])
        if model_result is not None
        else forecasts
    )

    lookup = {}
    for item in prediction_rows:
        timestamp = item["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        value = item.get(
            "predicted_withdrawals_usd",
            item.get("withdrawals_usd"),
        )
        if value is not None:
            lookup[timestamp] = max(0.0, float(value))

    if model_result and "next_hour_forecast" in model_result:
        item = model_result["next_hour_forecast"]
        timestamp = datetime.fromisoformat(item["timestamp"])
        lookup[timestamp] = max(0.0, float(item["withdrawals_usd"]))
    return lookup


def _sell_position(units, unit_price, cash_needed, haircut_pct):
    """Sell only enough units to cover the shortfall after the haircut."""
    if units <= 0 or unit_price <= 0 or cash_needed <= 0:
        return units, 0.0, 0.0

    haircut_rate = min(max(float(haircut_pct) / 100.0, 0.0), 0.999999)
    gross_needed = cash_needed / (1.0 - haircut_rate)
    gross_sold = min(units * unit_price, gross_needed)
    net_cash = gross_sold * (1.0 - haircut_rate)
    units_sold = gross_sold / unit_price
    return units - units_sold, net_cash, gross_sold - net_cash


def simulate_reserves(
    records=None,
    forecasts=None,
    starting_cash=DEFAULT_STARTING_CASH,
):
    """Run an hourly portfolio simulation and return summary plus ledger.

    ``forecasts`` may be the dict returned by ``train_and_evaluate``. Missing
    forecast timestamps use the average withdrawals in the prior 24 hours.
    """
    records = load_hourly_data() if records is None else records
    if not records:
        raise ValueError("At least one hourly record is required.")
    if starting_cash < 0:
        raise ValueError("starting_cash cannot be negative")

    forecast_by_time = _forecast_lookup(forecasts)

    cash = float(starting_cash)
    repo_balance = 0.0
    bond_units = 0.0
    equity_units = 0.0
    previous_bond_value = 0.0
    total_deposits = 0.0
    total_withdrawals = 0.0
    total_interest = 0.0
    total_liquidation_fees = 0.0
    total_overdraft_interest = 0.0
    peak_overdraft = 0.0
    ledger = []

    for index, row in enumerate(records):
        # Charge one hour of interest on any overdraft carried into this hour.
        if cash < 0:
            charge = (
                -cash
                * row["emergency_overdraft_penalty_apr_pct"]
                / 100.0
                / HOURS_PER_YEAR
            )
            cash -= charge
            total_overdraft_interest += charge

        # Accrue repo interest on the position held over the prior hour.
        if repo_balance > 0:
            repo_interest = (
                repo_balance * row["tier1_repo_rate_apy"] / 100.0 / HOURS_PER_YEAR
            )
            repo_balance += repo_interest
            total_interest += repo_interest

        # Accrue the bond coupon as cash using the prior hour's bond value.
        bond_coupon = (
            previous_bond_value
            * row["tier2_bond_yield_pct"]
            / 100.0
            / HOURS_PER_YEAR
        )
        cash += bond_coupon
        total_interest += bond_coupon

        # Repo principal and earned interest become liquid at the 08:00 release.
        if row["repo_sweep_mature"]:
            cash += repo_balance
            repo_balance = 0.0

        # Apply customer deposits and withdrawals for this hour.
        cash += row["deposits_usd"] - row["withdrawals_usd"]
        total_deposits += row["deposits_usd"]
        total_withdrawals += row["withdrawals_usd"]

        bond_price = row["tier2_bond_price_index"]
        equity_price = row["tier3_stock_index_price"]

        # Cover a cash shortfall by breaking repo, then selling bonds, then equities.
        if cash < 0 and repo_balance > 0:
            haircut = row["tier1_early_redemption_haircut_pct"] / 100.0
            gross_needed = -cash / (1.0 - haircut)
            gross_sold = min(repo_balance, gross_needed)
            net_cash = gross_sold * (1.0 - haircut)
            repo_balance -= gross_sold
            cash += net_cash
            total_liquidation_fees += gross_sold - net_cash

        if cash < 0:
            bond_units, proceeds, fee = _sell_position(
                bond_units,
                bond_price,
                -cash,
                row["tier2_bond_liquidation_haircut_pct"],
            )
            cash += proceeds
            total_liquidation_fees += fee

        if cash < 0:
            equity_units, proceeds, fee = _sell_position(
                equity_units,
                equity_price,
                -cash,
                row["tier3_stock_liquidation_haircut_pct"],
            )
            cash += proceeds
            total_liquidation_fees += fee

        # Any remaining deficit is treated as an emergency overdraft facility.
        peak_overdraft = max(peak_overdraft, -cash)

        # Predict the following hourly row; fall back to the trailing 24-hour mean.
        target_time = (
            records[index + 1]["timestamp"]
            if index + 1 < len(records)
            else row["timestamp"] + timedelta(hours=1)
        )
        prior_rows = records[max(0, index - 23):index + 1]
        fallback_forecast = sum(
            item["withdrawals_usd"] for item in prior_rows
        ) / len(prior_rows)
        forecast = forecast_by_time.get(target_time, fallback_forecast)

        # The allocator converts the ML withdrawal forecast into suggested amounts.
        suggestion = suggest_allocation(
            max(cash, 0.0),
            forecast,
            row["repo_sweep_window_open"],
        )
        repo_balance += suggestion["repo"]
        if bond_price > 0:
            bond_units += suggestion["bonds"] / bond_price
        if equity_price > 0:
            equity_units += suggestion["equities"] / equity_price
        cash = suggestion["reserve"]

        bond_value = bond_units * bond_price
        equity_value = equity_units * equity_price
        portfolio_value = cash + repo_balance + bond_value + equity_value
        previous_bond_value = bond_value

        ledger.append({
            "timestamp": row["timestamp"].isoformat(sep=" "),
            "predicted_next_hour_withdrawals_usd": forecast,
            "cash_usd": cash,
            "repo_usd": repo_balance,
            "bonds_usd": bond_value,
            "equities_usd": equity_value,
            "portfolio_value_usd": portfolio_value,
            "suggested_reserve_usd": suggestion["reserve"],
            "suggested_repo_usd": suggestion["repo"],
            "suggested_bonds_usd": suggestion["bonds"],
            "suggested_equities_usd": suggestion["equities"],
            "overdraft_usd": max(0.0, -cash),
        })

    ending_value = ledger[-1]["portfolio_value_usd"]
    net_external_flow = total_deposits - total_withdrawals
    net_profit = ending_value - starting_cash - net_external_flow

    return {
        "hours_simulated": len(records),
        "starting_cash_usd": float(starting_cash),
        "ending_portfolio_value_usd": ending_value,
        "net_external_flow_usd": net_external_flow,
        "net_profit_usd": net_profit,
        "net_return_on_starting_cash_pct": (
            net_profit / starting_cash * 100.0 if starting_cash else None
        ),
        "interest_earned_usd": total_interest,
        "liquidation_fees_usd": total_liquidation_fees,
        "overdraft_interest_usd": total_overdraft_interest,
        "peak_overdraft_usd": peak_overdraft,
        "ending_balances_usd": {
            "cash": ledger[-1]["cash_usd"],
            "repo": ledger[-1]["repo_usd"],
            "bonds": ledger[-1]["bonds_usd"],
            "equities": ledger[-1]["equities_usd"],
        },
        "ledger": ledger,
    }
