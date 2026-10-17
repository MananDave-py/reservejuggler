# Views, URLs, and Template Guide

The allocation logic is already available in:

```python
from .services.live_allocation import get_live_allocation
```

`get_live_allocation()` does all of this:

1. Uses the ML model to predict the next hour's withdrawals.
2. Fetches current Marketaux financial news.
3. Converts the news sentiment into equity, bond, repo, and risk points.
4. Calculates the suggested Tier 0–3 allocation.

The view only needs to call that one function and pass its result to the
template.

## 1. Write this in `main/views.py`

```python
from django.shortcuts import render

from .services.live_allocation import get_live_allocation


def dashboard(request):
    # Later, this can come from a form, database, or user input.
    available_cash = 10_000_000

    try:
        allocation_data = get_live_allocation(available_cash=available_cash)
        error_message = None
    except (RuntimeError, ValueError) as error:
        allocation_data = None
        error_message = str(error)

    return render(
        request,
        "main/dashboard.html",
        {
            "allocation_data": allocation_data,
            "error_message": error_message,
        },
    )
```

`get_live_allocation()` automatically checks whether the repo sweep window is
open. It uses the current UTC hour and opens the repo tier only at 17:00 UTC.

## 2. Write this in `main/urls.py`

```python
from django.urls import path

from . import views

app_name = "main"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
]
```

The project-level `rjug/urls.py` already includes `main.urls`, so no change is
needed there.

## 3. Create this template file

```text
main/templates/main/dashboard.html
```

## 4. Values available in the template

The view sends two top-level values:

```text
allocation_data
error_message
```

When there is no error, use these values in `dashboard.html`:

| Template expression | Meaning |
|---|---|
| `{{ allocation_data.available_cash_usd }}` | Current cash used for the calculation |
| `{{ allocation_data.forecast.timestamp }}` | Hour being predicted |
| `{{ allocation_data.forecast.withdrawals_usd }}` | ML predicted withdrawals |
| `{{ allocation_data.model_metrics.mae_usd }}` | Average model error during testing |
| `{{ allocation_data.market_points.equity_points }}` | News score for equities |
| `{{ allocation_data.market_points.bond_points }}` | News score for bonds |
| `{{ allocation_data.market_points.repo_points }}` | News score for repo |
| `{{ allocation_data.market_points.risk_points }}` | Overall market risk score |
| `{{ allocation_data.suggested_allocation.reserve }}` | Tier 0 suggested reserve |
| `{{ allocation_data.suggested_allocation.repo }}` | Tier 1 suggested repo amount |
| `{{ allocation_data.suggested_allocation.bonds }}` | Tier 2 suggested bond amount |
| `{{ allocation_data.suggested_allocation.equities }}` | Tier 3 suggested equity amount |
| `{{ allocation_data.suggested_allocation.reserve_multiplier }}` | Reserve safety multiplier |
| `{{ allocation_data.repo_window_open }}` | Whether new repo investment is allowed now |

## 5. Basic template structure

```django
{% if error_message %}
  <p>{{ error_message }}</p>
{% else %}
  <h1>Reserve Juggler Dashboard</h1>

  <p>Predicted withdrawals: ${{ allocation_data.forecast.withdrawals_usd|floatformat:2 }}</p>
  <p>Market risk points: {{ allocation_data.market_points.risk_points }}</p>

  <h2>Suggested allocation</h2>
  <p>Tier 0 — Reserve: ${{ allocation_data.suggested_allocation.reserve|floatformat:2 }}</p>
  <p>Tier 1 — Repo: ${{ allocation_data.suggested_allocation.repo|floatformat:2 }}</p>
  <p>Tier 2 — Bonds: ${{ allocation_data.suggested_allocation.bonds|floatformat:2 }}</p>
  <p>Tier 3 — Equities: ${{ allocation_data.suggested_allocation.equities|floatformat:2 }}</p>

  <h2>Latest financial news</h2>
  {% for article in allocation_data.market_news %}
    <p>
      <a href="{{ article.url }}">{{ article.title }}</a>
      — {{ article.label }} ({{ article.sentiment|floatformat:2 }})
    </p>
  {% endfor %}
{% endif %}
```

## 6. Template layout to design

Build the dashboard in these sections:

1. **Top summary cards:** predicted withdrawals, reserve, and risk points.
2. **Tier allocation cards or chart:** Tier 0 through Tier 3 amounts.
3. **Market sentiment section:** equity, bond, repo, and risk points.
4. **Latest news section:** the Marketaux headlines, source, and sentiment label.
5. **Explanation panel:** state that Reserve is allocated first, then the
   remaining money is divided among Repo, Bonds, and Equities according to the
   points.
