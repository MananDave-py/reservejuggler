"""Show how sentiment and risk points change the suggested tier allocation.

Run:
    .\\.venv\\Scripts\\python.exe points_system_demo.py
"""

from main.services.news_service import news_to_points
from main.services.points_allocator import suggest_points_allocation


AVAILABLE_CASH = 10_000_000
PREDICTED_WITHDRAWALS = 5_000_000

SCENARIOS = {
    "Bullish market news": [0.7, 0.5, 0.3],
    "Neutral market news": [0.05, -0.05, 0.0],
    "Bearish market news": [-0.7, -0.5, -0.3],
}


def print_money(label, value):
    print(f"  {label:<10} ${value:>12,.2f}")


def main():
    print("Cash available: $10,000,000 | Predicted withdrawals: $5,000,000\n")

    for name, sentiments in SCENARIOS.items():
        articles = [{"sentiment": value} for value in sentiments]
        points = news_to_points(articles)
        allocation = suggest_points_allocation(
            AVAILABLE_CASH,
            PREDICTED_WITHDRAWALS,
            repo_window_open=True,
            points=points,
        )

        print(name)
        print(
            "  Points: "
            f"equity {points['equity_points']:+}, "
            f"bonds {points['bond_points']:+}, "
            f"repo {points['repo_points']:+}, "
            f"risk {points['risk_points']}"
        )
        print(f"  Reserve multiplier: {allocation['reserve_multiplier']:.2f}x")
        print_money("Reserve", allocation["reserve"])
        print_money("Repo", allocation["repo"])
        print_money("Bonds", allocation["bonds"])
        print_money("Equities", allocation["equities"])
        print()


if __name__ == "__main__":
    main()
