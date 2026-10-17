"""Turn a predicted withdrawal amount into a suggested tier allocation."""


MINIMUM_CASH_BUFFER = 1_000_000.0
CASH_SAFETY_MULTIPLIER = 1.25


def suggest_allocation(available_cash, predicted_withdrawals, repo_window_open):
    """Suggest reserve, repo, bond, and equity amounts for the current hour.

    The ML model supplies ``predicted_withdrawals``. This function holds back
    enough cash for that predicted payout and divides the remaining surplus
    between the three investment tiers.
    """
    available_cash = max(0.0, float(available_cash))
    predicted_withdrawals = max(0.0, float(predicted_withdrawals))

    suggested_cash = max(
        MINIMUM_CASH_BUFFER,
        predicted_withdrawals * CASH_SAFETY_MULTIPLIER,
    )
    suggested_cash = min(available_cash, suggested_cash)
    surplus = available_cash - suggested_cash

    if repo_window_open:
        repo = surplus * 0.50
        bonds = surplus * 0.30
        equities = surplus * 0.20
    else:
        # Repo cannot be opened outside its daily sweep window.
        repo = 0.0
        bonds = surplus * 0.60
        equities = surplus * 0.40

    return {
        "reserve": suggested_cash,
        "repo": repo,
        "bonds": bonds,
        "equities": equities,
        "predicted_withdrawals": predicted_withdrawals,
    }
