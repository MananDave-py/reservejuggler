import os
from tempfile import NamedTemporaryFile

from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .services.dataloader import load_hourly_data
from .services.live_allocation import get_allocation_from_records


@require_http_methods(["GET", "POST"])
def dashboard(request):
    """Render sample data or calculate an allocation from an uploaded CSV."""
    context = {
        "allocation_data": None,
        "uploaded_csv_name": None,
        "error_message": None,
    }

    if request.method == "POST":
        uploaded_csv = request.FILES.get("csv_file")
        if not uploaded_csv:
            context["error_message"] = "Choose a CSV file before running the dashboard."
        elif not uploaded_csv.name.lower().endswith(".csv"):
            context["error_message"] = "Upload a file with the .csv extension."
        else:
            temporary_path = None
            try:
                with NamedTemporaryFile(suffix=".csv", delete=False) as temporary_file:
                    for chunk in uploaded_csv.chunks():
                        temporary_file.write(chunk)
                    temporary_path = temporary_file.name

                records = load_hourly_data(temporary_path)
                context["allocation_data"] = get_allocation_from_records(records)
                context["uploaded_csv_name"] = uploaded_csv.name
            except (OSError, RuntimeError, ValueError) as error:
                context["error_message"] = f"Could not process the CSV: {error}"
            finally:
                if temporary_path:
                    os.unlink(temporary_path)

    return render(request, "main/dashboard.html", context)


def intro(request):
    """Render the landing page that introduces the Reserve Juggler sandbox."""
    return render(request, "main/intro.html")
