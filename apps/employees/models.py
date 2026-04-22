from decimal import Decimal
from datetime import time

from django.db import models

from apps.accounts.models import User
from apps.core.models import TimestampedModel


class Department(TimestampedModel):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OrganizationSettings(TimestampedModel):
    organization_name = models.CharField(max_length=180, default="Organization")
    company_policies = models.TextField(blank=True)
    office_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Office GPS latitude for geo-fencing attendance"
    )
    office_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Office GPS longitude for geo-fencing attendance"
    )
    office_radius_meters = models.PositiveIntegerField(
        default=200,
        help_text="Radius in metres within which check-in counts as PRESENT (on-site)"
    )

    class Meta:
        verbose_name_plural = "Organization settings"

    def __str__(self):
        return self.organization_name


class ShiftTemplate(TimestampedModel):
    name = models.CharField(max_length=80, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(TimestampedModel):
    class EmploymentType(models.TextChoices):
        FULL_TIME = "FULL_TIME", "Full Time"
        CONTRACT = "CONTRACT", "Contract"
        INTERN = "INTERN", "Intern"

    class DepartmentRole(models.TextChoices):
        MEMBER = "MEMBER", "Member"
        TEAM_LEAD = "TEAM_LEAD", "Team Lead"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employee_profile")
    employee_id = models.CharField(max_length=30, unique=True)
    biometric_id = models.CharField(max_length=80, unique=True, null=True, blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        related_name="employees",
        null=True,
        blank=True,
    )
    manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="team_members",
        null=True,
        blank=True,
    )
    secondary_manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="secondary_team_members",
        null=True,
        blank=True,
    )
    designation = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    hire_date = models.DateField()
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
    )
    department_role = models.CharField(
        max_length=20,
        choices=DepartmentRole.choices,
        default=DepartmentRole.MEMBER,
    )
    shift_template = models.ForeignKey(
        ShiftTemplate,
        on_delete=models.SET_NULL,
        related_name="assigned_employees",
        null=True,
        blank=True,
    )
    shift_name = models.CharField(max_length=80, default="General")
    shift_start_time = models.TimeField(default=time(hour=9, minute=0))
    shift_end_time = models.TimeField(default=time(hour=18, minute=0))
    ctc_per_annum = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    personal_email = models.EmailField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["employee_id"]

    def __str__(self):
        return f"{self.employee_id} - {self.user.full_name}"

    @property
    def monthly_gross_salary(self):
        return (self.ctc_per_annum or Decimal("0")) / Decimal("12")
