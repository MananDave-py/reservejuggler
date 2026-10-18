"""Create the demonstration user accounts for MoneyMaxxer."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


DUMMY_USERS = [
    ("alex", "alex123", "alex@example.test"),
    ("bella", "bella123", "bella@example.test"),
    ("carlos", "carlos123", "carlos@example.test"),
    ("diana", "diana123", "diana@example.test"),
]


class Command(BaseCommand):
    help = "Create or reset the four demonstration user accounts."

    def handle(self, *args, **options):
        user_model = get_user_model()
        for username, password, email in DUMMY_USERS:
            user, created = user_model.objects.get_or_create(
                username=username,
                defaults={"email": email},
            )
            user.email = email
            user.set_password(password)
            user.save()
            action = "Created" if created else "Reset"
            self.stdout.write(f"{action} {username}")
