import os
from datetime import datetime
from decimal import Decimal
from tempfile import NamedTemporaryFile

from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .services.dataloader import load_hourly_data
from .services.live_allocation import get_allocation_from_records
from .services.allocation_reviewer import check_gemini_api_key, review_allocation
from .services.news_service import fetch_market_news
from .services.points_allocator import suggest_points_allocation
from .models import AllocationRun, CsvUpload


def login_or_register(request):
    """Sign an existing user in or create a new account from the landing page."""
    next_url = request.POST.get("next") or request.GET.get("next") or "/dashboard/"
    if request.user.is_authenticated:
        return redirect(next_url)

    initial_form = "register" if request.GET.get("mode") == "register" else "login"
    context = {"next_url": next_url, "error_message": None, "active_form": initial_form}
    if request.method != "POST":
        return render(request, "main/login.html", context)

    action = request.POST.get("action")
    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")
    context["active_form"] = action

    if action == "register":
        if len(username) < 3:
            context["error_message"] = "Choose a username with at least 3 characters."
        elif User.objects.filter(username__iexact=username).exists():
            context["error_message"] = "That username is already registered. Please sign in."
        elif len(password) < 6:
            context["error_message"] = "Choose a password with at least 6 characters."
        else:
            User.objects.create_user(username=username, password=password)
            context["active_form"] = "login"
            context["success_message"] = (
                "Your account was created. Please sign in to continue."
            )
    else:
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(next_url)
        context["error_message"] = "Username or password is incorrect."

    return render(request, "main/login.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def dashboard(request):
    """Render sample data or calculate an allocation from an uploaded CSV."""
    allocation_history = AllocationRun.objects.filter(
        upload__user=request.user
    ).select_related("upload")
    latest_run = allocation_history.first()
    uploads = CsvUpload.objects.filter(user=request.user).order_by("-uploaded_at")
    history_items = [_history_chart_item(run) for run in allocation_history]
    context = {
        "allocation_data": _allocation_data_from_run(latest_run) if latest_run else None,
        "uploaded_csv_name": latest_run.upload.original_filename if latest_run else None,
        "is_historical": bool(latest_run),
        "saved_at": latest_run.calculated_at if latest_run else None,
        "error_message": None,
        "review_error": None,
        "ai_review": None,
        "allocation_history": history_items,
        "history_tier_charts": _history_tier_charts(history_items),
        "comparison_results": [],
        "uploaded_file_count": 0,
        "csv_uploads": uploads,
        "api_status": request.session.get("api_status", {
            "marketaux": {"ok": False, "message": "Marketaux key has not been checked."},
            "gemini": {"ok": False, "message": "Gemini key has not been checked."},
        }),
    }
    context["api_setup_required"] = bool(latest_run) and not all(
        status.get("ok") for status in context["api_status"].values()
    )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_api_keys":
            api_status = request.session.get("api_status", {
                "marketaux": {"ok": False, "message": "Marketaux key has not been checked."},
                "gemini": {"ok": False, "message": "Gemini key has not been checked."},
            })
            marketaux_key = request.POST.get("marketaux_api_token", "").strip()
            gemini_key = request.POST.get("gemini_api_key", "").strip()
            errors = []
            if marketaux_key:
                try:
                    fetch_market_news(api_token=marketaux_key, limit=1)
                    request.session["marketaux_api_token"] = marketaux_key
                    api_status["marketaux"] = {
                        "ok": True,
                        "message": "Marketaux API key is working.",
                    }
                except (RuntimeError, ValueError) as error:
                    api_status["marketaux"] = {"ok": False, "message": str(error)}
                    errors.append("Marketaux")
            if gemini_key:
                gemini_status = check_gemini_api_key(gemini_key)
                api_status["gemini"] = gemini_status
                if gemini_status["ok"]:
                    request.session["gemini_api_key"] = gemini_key
                else:
                    errors.append("Gemini")
            request.session["api_status"] = api_status
            if errors:
                messages.error(request, f"Could not validate {', '.join(errors)}. Check the key and try again.")
            elif marketaux_key or gemini_key:
                messages.success(request, "Entered API key checked. If you added Marketaux, upload the CSV again to apply news to its allocation.")
            return redirect("main:dashboard")
        if action == "review":
            if not latest_run:
                context["review_error"] = "Upload a CSV and calculate an allocation first."
            else:
                context["allocation_data"] = _allocation_data_from_run(latest_run)
                context["uploaded_csv_name"] = latest_run.upload.original_filename
                context["is_historical"] = True
                context["saved_at"] = latest_run.calculated_at
                try:
                    context["ai_review"] = review_allocation(
                        context["allocation_data"],
                        api_key=request.session.get("gemini_api_key"),
                    )
                except (RuntimeError, ValueError) as error:
                    context["review_error"] = str(error)
        else:
            uploaded_csvs = request.FILES.getlist("csv_file")
            if not uploaded_csvs:
                context["error_message"] = "Choose a CSV file before running the dashboard."
            elif len(uploaded_csvs) > 2:
                context["error_message"] = "Choose no more than two CSV files at a time."
            else:
                comparison_results = []
                upload_errors = []
                gemini_status = check_gemini_api_key(
                    request.session.get("gemini_api_key")
                )

                for uploaded_csv in uploaded_csvs:
                    if not uploaded_csv.name.lower().endswith(".csv"):
                        upload_errors.append(f"{uploaded_csv.name}: choose a .csv file.")
                        continue

                    temporary_path = None
                    try:
                        with NamedTemporaryFile(suffix=".csv", delete=False) as temporary_file:
                            for chunk in uploaded_csv.chunks():
                                temporary_file.write(chunk)
                            temporary_path = temporary_file.name

                        records = load_hourly_data(temporary_path)
                        allocation_data = get_allocation_from_records(
                            records,
                            api_token=request.session.get("marketaux_api_token"),
                        )
                        api_status = {
                            "marketaux": allocation_data["market_news_status"],
                            "gemini": gemini_status,
                        }
                        request.session["api_status"] = api_status
                        context["api_status"] = api_status
                        context["api_setup_required"] = not all(
                            status.get("ok") for status in api_status.values()
                        )
                        _store_upload_result(
                            request.user, uploaded_csv.name, records, allocation_data
                        )
                        comparison_results.append(
                            _comparison_result(uploaded_csv.name, allocation_data)
                        )
                        context["allocation_data"] = allocation_data
                        context["uploaded_csv_name"] = uploaded_csv.name
                        context["is_historical"] = False
                        context["saved_at"] = None
                    except (OSError, RuntimeError, ValueError) as error:
                        upload_errors.append(f"{uploaded_csv.name}: {error}")
                    finally:
                        if temporary_path:
                            os.unlink(temporary_path)

                if len(comparison_results) == 2:
                    context["comparison_results"] = comparison_results
                context["uploaded_file_count"] = len(comparison_results)
                if upload_errors:
                    context["error_message"] = "Some CSVs could not be processed: " + " ".join(upload_errors)
                elif comparison_results:
                    count = len(comparison_results)
                    context["error_message"] = (
                        f"Calculated {count} CSV file{'s' if count != 1 else ''}. "
                        "Their results are shown side by side below."
                        if count == 2
                        else "CSV allocation calculated and saved."
                    )

    return render(request, "main/dashboard.html", context)


@require_POST
@login_required
def delete_csv_upload(request, upload_id):
    """Delete one of the signed-in user's uploads and its allocation history."""
    upload = get_object_or_404(CsvUpload, id=upload_id, user=request.user)
    upload.delete()
    return redirect("main:dashboard")


@require_POST
@login_required
def delete_all_csv_uploads(request):
    """Delete all CSV uploads and associated allocation history for this user."""
    CsvUpload.objects.filter(user=request.user).delete()
    return redirect("main:dashboard")


def _money(value):
    """Store floating-point service results as fixed two-decimal database values."""
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _store_upload_result(user, filename, records, allocation_data):
    """Create the upload and its associated tier allocation in one transaction."""
    forecast = allocation_data["forecast"]
    allocation = allocation_data["suggested_allocation"]
    points = allocation_data["market_points"]

    with transaction.atomic():
        upload = CsvUpload.objects.create(
            user=user,
            original_filename=filename,
            total_rows=len(records),
        )
        allocation_time = datetime.fromisoformat(forecast["timestamp"])
        if timezone.is_naive(allocation_time):
            allocation_time = timezone.make_aware(allocation_time)

        AllocationRun.objects.create(
            upload=upload,
            allocation_for_time=allocation_time,
            available_cash_usd=_money(allocation_data["available_cash_usd"]),
            predicted_withdrawals_usd=_money(forecast["withdrawals_usd"]),
            reserve_usd=_money(allocation["reserve"]),
            repo_usd=_money(allocation["repo"]),
            bonds_usd=_money(allocation["bonds"]),
            equities_usd=_money(allocation["equities"]),
            reserve_multiplier=_money(allocation["reserve_multiplier"]),
            equity_points=points["equity_points"],
            bond_points=points["bond_points"],
            repo_points=points["repo_points"],
            risk_points=points["risk_points"],
            repo_execution_status=allocation["repo_execution_status"],
        )


def _comparison_result(filename, allocation_data):
    """Format the calculated figures for the two-file comparison panel."""
    allocation = allocation_data["suggested_allocation"]
    available_cash = float(allocation_data["available_cash_usd"])
    tiers = [
        ("Cash buffer", "reserve"),
        ("Overnight repo", "repo"),
        ("Government bonds", "bonds"),
        ("Growth equities", "equities"),
    ]
    return {
        "filename": filename,
        "available_cash_usd": available_cash,
        "withdrawals_usd": float(allocation_data["forecast"]["withdrawals_usd"]),
        "forecast_timestamp": allocation_data["forecast"]["timestamp"],
        "repo_window_open": allocation_data["repo_window_open"],
        "tiers": [
            {
                "name": name,
                "amount": float(allocation[key]),
                "percentage": float(allocation[key]) / available_cash * 100 if available_cash else 0,
            }
            for name, key in tiers
        ],
    }


def _allocation_data_from_run(run):
    """Recalculate the saved forecast using the current allocation rules."""
    available_cash = float(run.available_cash_usd)
    market_points = {
        "equity_points": run.equity_points,
        "bond_points": run.bond_points,
        "repo_points": run.repo_points,
        "risk_points": run.risk_points,
    }
    allocation = suggest_points_allocation(
        available_cash=available_cash,
        predicted_withdrawals=float(run.predicted_withdrawals_usd),
        repo_window_open=run.repo_execution_status == "execute_now",
        points=market_points,
    )
    # Keep saved database history intact while displaying today's allocation rule.
    run.reserve_multiplier = _money(allocation["reserve_multiplier"])
    run.reserve_usd = _money(allocation["reserve"])
    run.repo_usd = _money(allocation["repo"])
    run.bonds_usd = _money(allocation["bonds"])
    run.equities_usd = _money(allocation["equities"])
    percentages = {
        tier: allocation[tier] / available_cash * 100 if available_cash else 0
        for tier in ("reserve", "repo", "bonds", "equities")
    }
    return {
        "forecast": {
            "timestamp": run.allocation_for_time.isoformat(sep=" "),
            "withdrawals_usd": float(run.predicted_withdrawals_usd),
        },
        "market_points": market_points,
        "suggested_allocation": allocation,
        "allocation_percentages": percentages,
        "available_cash_usd": available_cash,
        "repo_window_open": run.repo_execution_status == "execute_now",
        "market_news": [],
    }


def _history_chart_item(run):
    """Build one chart column from one CSV upload using current allocation rules."""
    allocation = _allocation_data_from_run(run)["suggested_allocation"]
    available_cash = float(run.available_cash_usd)
    tiers = [
        ("Cash buffer", allocation["reserve"], "cash-cell"),
        ("Overnight repo", allocation["repo"], "repo-cell"),
        ("Government bonds", allocation["bonds"], "bonds-cell"),
        ("Growth equities", allocation["equities"], "equity-cell"),
    ]
    return {
        "name": run.upload.original_filename,
        "uploaded_at": run.calculated_at,
        "chart_tiers": [
            (
                name,
                amount,
                color,
                amount / available_cash * 100 if available_cash else 0,
            )
            for name, amount, color in tiers
        ],
    }


def _history_tier_charts(history):
    """Transpose CSV history into four independent per-tier charts."""
    distinct_history = []
    seen_allocations = set()
    for run in history:
        signature = tuple(
            round(float(amount), 2) if amount is not None else None
            for _, amount, _, _ in run["chart_tiers"]
        )
        if signature in seen_allocations:
            continue
        seen_allocations.add(signature)
        distinct_history.append(run)

    tiers = [
        ("Cash buffer", "reserve", "cash-chart"),
        ("Overnight repo", "repo", "repo-chart"),
        ("Government bonds", "bonds", "bonds-chart"),
        ("Growth equities", "equities", "equity-chart"),
    ]
    charts = []
    for title, key, color in tiers:
        values = []
        for run in distinct_history:
            _, amount, _, _ = next(
                item for item in run["chart_tiers"]
                if item[0] == title
            )
            if amount is not None:
                values.append({
                    "name": run["name"],
                    "uploaded_at": run["uploaded_at"],
                    "amount": amount,
                })
        maximum = max((item["amount"] for item in values), default=0)
        for item in values:
            item["width"] = item["amount"] / maximum * 100 if maximum else 0
        charts.append({
            "title": title,
            "key": key,
            "color": color,
            "values": values,
            "run_count": len(distinct_history),
        })
    return charts

def intro(request):
    """Render the landing page that introduces the MoneyMaxxer sandbox."""
    return render(request, "main/intro.html")
