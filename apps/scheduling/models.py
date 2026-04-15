from django.db import models

from apps.accounts.models import User
from apps.core.models import TimestampedModel
from apps.employees.models import Department, Employee, ShiftTemplate


class ShiftRotationRule(TimestampedModel):
    class HolidayStrategy(models.TextChoices):
        SKIP = "SKIP", "Skip"
        MARK_CONFLICT = "MARK_CONFLICT", "Mark Conflict"
        ASSIGN_ANYWAY = "ASSIGN_ANYWAY", "Assign Anyway"

    name = models.CharField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        related_name="shift_rotation_rules",
        null=True,
        blank=True,
    )
    rotation_pattern = models.JSONField(default=list, blank=True, help_text="Ordered list of shift template ids.")
    holiday_strategy = models.CharField(max_length=20, choices=HolidayStrategy.choices, default=HolidayStrategy.MARK_CONFLICT)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ShiftRosterEntry(TimestampedModel):
    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        BULK = "BULK", "Bulk"
        ROTATION = "ROTATION", "Rotation"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="roster_entries")
    roster_date = models.DateField(db_index=True)
    shift_template = models.ForeignKey(ShiftTemplate, on_delete=models.CASCADE, related_name="roster_entries")
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    is_holiday = models.BooleanField(default=False)
    is_conflicted = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["roster_date", "employee__employee_id"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "roster_date"], name="unique_roster_entry_employee_date")
        ]
        indexes = [
            models.Index(fields=["roster_date", "is_conflicted"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.roster_date.isoformat()}"


class ScheduleConflict(TimestampedModel):
    class ConflictType(models.TextChoices):
        HOLIDAY = "HOLIDAY", "Holiday"
        DUPLICATE = "DUPLICATE", "Duplicate"
        OFFBOARDING = "OFFBOARDING", "Offboarding"
        INACTIVE_EMPLOYEE = "INACTIVE_EMPLOYEE", "Inactive Employee"

    roster_entry = models.ForeignKey(ShiftRosterEntry, on_delete=models.CASCADE, related_name="conflicts")
    conflict_type = models.CharField(max_length=30, choices=ConflictType.choices)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    reported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="reported_schedule_conflicts",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["conflict_type", "is_resolved"]),
        ]

    def __str__(self):
        return f"{self.roster_entry_id} - {self.conflict_type}"

