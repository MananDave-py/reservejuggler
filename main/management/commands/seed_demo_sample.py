"""Preload the README's synthetic CSV into the Alex demo account once."""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from main.services.dataloader import load_hourly_data
from main.services.live_allocation import get_allocation_from_records
from main.views import _store_upload_result


class Command(BaseCommand):
    help = "Add the README sample allocation to Alex's demo account if empty."

    def handle(self, *args, **options):
        user_model = get_user_model()
        user = user_model.objects.filter(username="alex").first()
        if user is None:
            self.stderr.write("Demo account alex does not exist; skipping sample.")
            return

        from main.models import CsvUpload

        if CsvUpload.objects.filter(user=user).exists():
            self.stdout.write("Alex already has CSV data; leaving it unchanged.")
            return

        sample_path = Path(__file__).resolve().parents[3] / "data" / "treasury_4tier_dataset_2027.csv"
        records = load_hourly_data(sample_path)
        allocation_data = get_allocation_from_records(records, api_token="")
        _store_upload_result(user, sample_path.name, records, allocation_data)
        self.stdout.write(f"Loaded {sample_path.name} ({len(records)} rows) for alex.")
