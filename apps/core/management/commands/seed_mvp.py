from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.employees.models import Department, Employee, ShiftTemplate
from apps.leave_management.models import LeaveBalance, LeaveRequest


class Command(BaseCommand):
    help = "Seed the HRMS MVP with demo users, employees, leave balances, and attendance."

    def handle(self, *args, **options):
        hr_department, _ = Department.objects.get_or_create(
            code="HR",
            defaults={"name": "Human Resources", "description": "People operations team"},
        )
        eng_department, _ = Department.objects.get_or_create(
            code="ENG",
            defaults={"name": "Engineering", "description": "Engineering and product delivery"},
        )
        ops_department, _ = Department.objects.get_or_create(
            code="OPS",
            defaults={"name": "Operations", "description": "Business operations team"},
        )
        finance_department, _ = Department.objects.get_or_create(
            code="FIN",
            defaults={"name": "Finance", "description": "Payroll, salary processing, and payslip operations"},
        )
        morning_shift, _ = ShiftTemplate.objects.get_or_create(
            name="Morning",
            defaults={"start_time": time(hour=9), "end_time": time(hour=18), "description": "Standard day shift"},
        )
        night_shift, _ = ShiftTemplate.objects.get_or_create(
            name="Night",
            defaults={"start_time": time(hour=21), "end_time": time(hour=6), "description": "Overnight shift"},
        )

        users = [
            {
                "email": "admin@atmispace.com",
                "password": "Atmi@123",
                "first_name": "Poojyesh",
                "last_name": "S",
                "role": User.Role.ADMIN,
                "employee_id": "EMP001",
                "designation": "HR Director",
                "department": hr_department,
                "hire_date": "2022-01-10",
                "shift_template": morning_shift,
                "ctc_per_annum": Decimal("1800000.00"),
                "monthly_fixed_deductions": Decimal("18000.00"),
            },
            {
                "email": "hr@atmispace.com",
                "password": "Hr@12345",
                "first_name": "Pravalika",
                "last_name": "T",
                "role": User.Role.HR,
                "employee_id": "EMP002",
                "designation": "HR Business Partner",
                "department": hr_department,
                "hire_date": "2022-03-04",
                "shift_template": morning_shift,
                "ctc_per_annum": Decimal("1200000.00"),
                "monthly_fixed_deductions": Decimal("12000.00"),
            },
            {
                "email": "manager@atmispace.com",
                "password": "Manager@123",
                "first_name": "Kaushik",
                "last_name": "V",
                "role": User.Role.MANAGER,
                "employee_id": "EMP003",
                "designation": "Engineering Manager",
                "department": eng_department,
                "hire_date": "2021-11-15",
                "shift_template": morning_shift,
                "ctc_per_annum": Decimal("1560000.00"),
                "monthly_fixed_deductions": Decimal("14500.00"),
            },
            {
                "email": "employee@atmispace.com",
                "password": "Employee@123",
                "first_name": "Abhijit",
                "last_name": "Burla",
                "role": User.Role.EMPLOYEE,
                "employee_id": "EMP004",
                "designation": "Software Engineer",
                "department": eng_department,
                "hire_date": "2023-06-12",
                "shift_template": morning_shift,
                "ctc_per_annum": Decimal("840000.00"),
                "monthly_fixed_deductions": Decimal("6500.00"),
            },
            {
                "email": "ops@atmispace.com",
                "password": "Ops@12345",
                "first_name": "Poojyesh",
                "last_name": "S",
                "role": User.Role.EMPLOYEE,
                "employee_id": "EMP005",
                "designation": "Operations Executive",
                "department": ops_department,
                "hire_date": "2024-01-08",
                "shift_template": night_shift,
                "ctc_per_annum": Decimal("600000.00"),
                "monthly_fixed_deductions": Decimal("4200.00"),
            },
            {
                "email": "accounts@atmispace.com",
                "password": "Accounts@123",
                "first_name": "Ananya",
                "last_name": "R",
                "role": User.Role.ACCOUNTS,
                "employee_id": "EMP006",
                "designation": "Payroll Accountant",
                "department": finance_department,
                "hire_date": "2023-09-01",
                "shift_template": morning_shift,
                "ctc_per_annum": Decimal("900000.00"),
                "monthly_fixed_deductions": Decimal("7000.00"),
            },
        ]

        employee_records = {}
        manager_employee = None

        for record in users:
            user, created = User.objects.get_or_create(
                email=record["email"],
                defaults={
                    "first_name": record["first_name"],
                    "last_name": record["last_name"],
                    "role": record["role"],
                    "is_staff": record["role"] == User.Role.ADMIN,
                },
            )
            if created or not user.check_password(record["password"]):
                user.set_password(record["password"])
            user.first_name = record["first_name"]
            user.last_name = record["last_name"]
            user.role = record["role"]
            user.is_staff = record["role"] == User.Role.ADMIN
            user.save()

            employee, _ = Employee.objects.update_or_create(
                user=user,
                defaults={
                    "employee_id": record["employee_id"],
                    "designation": record["designation"],
                    "department": record["department"],
                    "hire_date": record["hire_date"],
                    "employment_type": Employee.EmploymentType.FULL_TIME,
                    "department_role": (
                        Employee.DepartmentRole.TEAM_LEAD if record["role"] == User.Role.MANAGER else Employee.DepartmentRole.MEMBER
                    ),
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
            employee_records[record["email"]] = employee
            if record["role"] == User.Role.MANAGER:
                manager_employee = employee

        for email in ["employee@atmispace.com", "ops@atmispace.com"]:
            employee = employee_records[email]
            employee.manager = manager_employee
            employee.save(update_fields=["manager"])

        leave_allocations = {
            LeaveBalance.LeaveType.CASUAL: Decimal("12.0"),
            LeaveBalance.LeaveType.SICK: Decimal("10.0"),
            LeaveBalance.LeaveType.EARNED: Decimal("15.0"),
            LeaveBalance.LeaveType.LOP: Decimal("0.0"),
        }

        for employee in employee_records.values():
            for leave_type, allocated in leave_allocations.items():
                LeaveBalance.objects.update_or_create(
                    employee=employee,
                    leave_type=leave_type,
                    defaults={"allocated_days": allocated, "used_days": Decimal("0.0")},
                )

        requester = employee_records["employee@atmispace.com"]
        approver = employee_records["manager@atmispace.com"].user

        LeaveRequest.objects.get_or_create(
            employee=requester,
            leave_type=LeaveBalance.LeaveType.CASUAL,
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
            defaults={
                "reason": "Family function",
                "status": LeaveRequest.Status.PENDING,
                "total_days": Decimal("1.0"),
            },
        )

        LeaveRequest.objects.get_or_create(
            employee=employee_records["ops@atmispace.com"],
            leave_type=LeaveBalance.LeaveType.SICK,
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
            defaults={
                "reason": "Medical consultation",
                "status": LeaveRequest.Status.APPROVED,
                "total_days": Decimal("1.0"),
                "approver": approver,
                "approver_note": "Approved for recovery time.",
                "reviewed_at": timezone.now(),
            },
        )

        LeaveBalance.objects.filter(
            employee=employee_records["ops@atmispace.com"],
            leave_type=LeaveBalance.LeaveType.SICK,
        ).update(used_days=Decimal("1.0"))

        today = timezone.localdate()
        for employee in employee_records.values():
            for offset in range(1, 4):
                attendance_date = today - timedelta(days=offset)
                shift_start = employee.shift_start_time
                shift_end = employee.shift_end_time
                check_in = timezone.make_aware(datetime.combine(attendance_date, shift_start))
                check_out = timezone.make_aware(datetime.combine(attendance_date, shift_end))
                if check_out <= check_in:
                    check_out += timedelta(days=1)
                check_out -= timedelta(minutes=30)

                Attendance.objects.update_or_create(
                    employee=employee,
                    attendance_date=attendance_date,
                    defaults={
                        "check_in": check_in,
                        "check_out": check_out,
                        "status": Attendance.Status.PRESENT,
                        "notes": f"Seeded historical attendance for {attendance_date.isoformat()}",
                        "break_minutes": 30,
                        "break_started_at": None,
                        "total_work_minutes": int((check_out - check_in).total_seconds() // 60) - 30,
                    },
                )

        self.stdout.write(self.style.SUCCESS("HRMS MVP demo data seeded successfully."))
        self.stdout.write("Login credentials:")
        for record in users:
            self.stdout.write(f"  {record['email']} / {record['password']}")
