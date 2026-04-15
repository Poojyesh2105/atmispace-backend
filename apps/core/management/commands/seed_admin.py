from datetime import date, time
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.employees.models import Department, Employee, ShiftTemplate


class Command(BaseCommand):
    help = "Create or update a test admin user."

    def handle(self, *args, **options):
        hr_department, _ = Department.objects.get_or_create(
            code="HR",
            defaults={
                "name": "Human Resources",
                "description": "People operations team",
            },
        )

        morning_shift, _ = ShiftTemplate.objects.get_or_create(
            name="Morning",
            defaults={
                "start_time": time(hour=9),
                "end_time": time(hour=18),
                "description": "Standard day shift",
            },
        )

        record = {
            "email": "admin@atmispace.com",
            "password": "Atmi@123",
            "first_name": "Poojyesh",
            "last_name": "S",
            "role": User.Role.ADMIN,
            "employee_id": "EMP001",
            "designation": "HR Director",
            "department": hr_department,
            "hire_date": date(2022, 1, 10),
            "shift_template": morning_shift,
            "ctc_per_annum": Decimal("1800000.00"),
            "monthly_fixed_deductions": Decimal("18000.00"),
        }

        user, created = User.objects.get_or_create(
            email=record["email"],
            defaults={
                "first_name": record["first_name"],
                "last_name": record["last_name"],
                "role": record["role"],
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        if created or not user.check_password(record["password"]):
            user.set_password(record["password"])

        user.first_name = record["first_name"]
        user.last_name = record["last_name"]
        user.role = record["role"]
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()

        employee, _ = Employee.objects.update_or_create(
            user=user,
            defaults={
                "employee_id": record["employee_id"],
                "designation": record["designation"],
                "department": record["department"],
                "hire_date": record["hire_date"],
                "employment_type": Employee.EmploymentType.FULL_TIME,
                "department_role": Employee.DepartmentRole.MEMBER,
                "shift_template": record["shift_template"],
                "shift_name": record["shift_template"].name,
                "shift_start_time": record["shift_template"].start_time,
                "shift_end_time": record["shift_template"].end_time,
                "ctc_per_annum": record["ctc_per_annum"],
                "monthly_fixed_deductions": record["monthly_fixed_deductions"],
                "phone_number": "+91-9999999999",
                "address": "Bengaluru, India",
                "emergency_contact_name": "Primary Contact",
                "emergency_contact_phone": "+91-8888888888",
                "is_active": True,
            },
        )

        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} admin user: {user.email}"))
        self.stdout.write(self.style.SUCCESS(f"Employee profile ready: {employee.employee_id}"))
