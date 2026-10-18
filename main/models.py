from django.conf import settings
from django.db import models


class CsvUpload(models.Model):
    """Metadata for one CSV file processed by an authenticated user."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    total_rows = models.PositiveIntegerField()

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.user.username}: {self.original_filename}"


class AllocationRun(models.Model):
    """The calculated allocation produced from one uploaded CSV file."""

    upload = models.OneToOneField(
        CsvUpload,
        on_delete=models.CASCADE,
        related_name="allocation_run",
    )
    allocation_for_time = models.DateTimeField()
    calculated_at = models.DateTimeField(auto_now_add=True)
    available_cash_usd = models.DecimalField(max_digits=18, decimal_places=2)
    predicted_withdrawals_usd = models.DecimalField(max_digits=18, decimal_places=2)
    reserve_usd = models.DecimalField(max_digits=18, decimal_places=2)
    repo_usd = models.DecimalField(max_digits=18, decimal_places=2)
    bonds_usd = models.DecimalField(max_digits=18, decimal_places=2)
    equities_usd = models.DecimalField(max_digits=18, decimal_places=2)
    reserve_multiplier = models.DecimalField(max_digits=5, decimal_places=2)
    equity_points = models.IntegerField()
    bond_points = models.IntegerField()
    repo_points = models.IntegerField()
    risk_points = models.IntegerField()
    repo_execution_status = models.CharField(max_length=32)

    class Meta:
        ordering = ["-calculated_at"]

    def __str__(self):
        return f"Allocation for {self.upload.original_filename}"

# Create your models here.
