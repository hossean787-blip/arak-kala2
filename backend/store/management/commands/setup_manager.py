from getpass import getpass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Set or change the password of the sole Arak Kala manager."

    def handle(self, *args, **options):
        email = settings.STORE_MANAGER_EMAIL
        account, _ = get_user_model().objects.get_or_create(
            username=email, defaults={"email": email, "is_active": False}
        )
        password = getpass(f"New password for {email}: ")
        if password != getpass("Repeat password: "):
            raise CommandError("Passwords do not match.")
        try:
            validate_password(password, account)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        account.email = email
        account.is_active = True
        account.set_password(password)
        account.save()
        self.stdout.write(self.style.SUCCESS("Manager password configured."))
