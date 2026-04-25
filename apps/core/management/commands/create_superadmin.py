"""
Management command to create (or update) the platform SUPER_ADMIN user.

A SUPER_ADMIN:
  - Has role = SUPER_ADMIN on the User model
  - Is a Django staff + superuser (for /admin/ access)
  - Does NOT need an Employee profile or an Organization
  - Is NOT scoped to any single org — they see everything

Usage:
    python manage.py create_superadmin
    python manage.py create_superadmin --email owner@example.com --password s3cr3t
    python manage.py create_superadmin --email owner@example.com --no-input
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create or update the platform SUPER_ADMIN (platform owner) user."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default="superadmin@atmispace.com",
            help="Email address for the SUPER_ADMIN user (default: superadmin@atmispace.com)",
        )
        parser.add_argument(
            "--password",
            default=None,
            help="Password (prompted interactively if omitted)",
        )
        parser.add_argument(
            "--first-name",
            default="Platform",
            dest="first_name",
        )
        parser.add_argument(
            "--last-name",
            default="Admin",
            dest="last_name",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            dest="no_input",
            help="Use default password 'Atmi@SuperAdmin1' without prompting (dev/CI only)",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        email = options["email"].strip().lower()
        password = options["password"]
        first_name = options["first_name"]
        last_name = options["last_name"]
        no_input = options["no_input"]

        # ── Resolve password ───────────────────────────────────────────────
        if not password:
            if no_input:
                password = "Atmi@SuperAdmin1"
                self.stdout.write(
                    self.style.WARNING(
                        "  Using default password 'Atmi@SuperAdmin1'. "
                        "Change this immediately in production."
                    )
                )
            else:
                import getpass
                password = getpass.getpass(f"Password for {email}: ")
                confirm = getpass.getpass("Confirm password: ")
                if password != confirm:
                    raise CommandError("Passwords do not match.")
                if len(password) < 8:
                    raise CommandError("Password must be at least 8 characters.")

        # ── Create / update user ───────────────────────────────────────────
        with transaction.atomic():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": User.Role.SUPER_ADMIN,
                    "is_staff": True,
                    "is_superuser": True,
                    "is_active": True,
                },
            )

            if not created:
                # Ensure existing user is promoted correctly
                user.first_name = first_name
                user.last_name = last_name
                user.role = User.Role.SUPER_ADMIN
                user.is_staff = True
                user.is_superuser = True
                user.is_active = True

            user.set_password(password)
            user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"\n  ✓ {action} SUPER_ADMIN: {user.email}"))
        self.stdout.write(f"    Role     : {user.role}")
        self.stdout.write(f"    is_staff : {user.is_staff}")
        self.stdout.write(f"    Django admin (/admin/) : yes")
        self.stdout.write(f"    Platform API (/api/v1/platform/) : yes")
        self.stdout.write(f"    Org scoping : none (cross-org access)\n")
