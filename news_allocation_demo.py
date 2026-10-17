"""Run the Marketaux news-to-allocation flow from the project root.

PowerShell:
    $env:MARKETAUX_API_TOKEN = "your_token"
    .\\.venv\\Scripts\\python.exe news_allocation_demo.py
"""

from main.services.news_service import fetch_market_news, news_to_points
from main.services.points_allocator import suggest_points_allocation


AVAILABLE_CASH = 10_000_000
PREDICTED_WITHDRAWALS = 5_000_000
REPO_WINDOW_OPEN = True


def main():
    articles = fetch_market_news()
    points = news_to_points(articles)
    allocation = suggest_points_allocation(
        AVAILABLE_CASH,
        PREDICTED_WITHDRAWALS,
        REPO_WINDOW_OPEN,
        points,
    )

    print("News points:", points)
    print("\nArticles used for the score:")
    for article in articles:
        print(
            f"- [{article['label']}] sentiment {article['sentiment']:+.2f}: "
            f"{article['title']}"
        )
    print("\nSuggested allocation:")
    for tier in ("reserve", "repo", "bonds", "equities"):
        print(f"{tier.title()}: ${allocation[tier]:,.2f}")
    print("Weights:", allocation["allocation_weights"])
    print("\nLatest headlines:")
    for article in articles[:5]:
        print(f"- [{article['label']}] {article['title']}")


if __name__ == "__main__":
    main()
