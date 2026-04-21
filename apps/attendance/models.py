from django.db import models

from apps.core.models import TimestampedModel
from apps.employees.models import Employee


class Attendance(TimestampedModel):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        HALF_DAY = "HALF_DAY", "Half Day"
        REMOTE = "REMOTE", "Remote"
        ABSENT = "ABSENT", "Absent"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendances")
    attendance_date = models.DateField(db_index=True)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    current_session_check_in = models.DateTimeField(null=True, blank=True)
    break_started_at = models.DateTimeField(null=True, blank=True)
    break_minutes = models.PositiveIntegerField(default=0)
    current_session_break_minutes = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PRESENT, db_index=True)
    notes = models.TextField(blank=True)
    total_work_minutes = models.PositiveIntegerField(default=0)
    check_in_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_in_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_in_accuracy_meters = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["-attendance_date", "-check_in"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "attendance_date"], name="unique_daily_attendance")
        ]
        indexes = [
            models.Index(fields=["employee", "attendance_date", "status"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.attendance_date}"


class AttendanceRegularization(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance_regularizations")
    date = models.DateField(db_index=True)
    requested_check_in = models.DateTimeField()
    requested_check_out = models.DateTimeField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    approver = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_regularization_reviews",
    )
    approver_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["employee", "date", "status"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.date} - {self.status}"
