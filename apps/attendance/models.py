from django.db.models import Q
from django.db import models

from apps.core.models import OrganizationScopedModel
from apps.employees.models import Employee


class Attendance(OrganizationScopedModel):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        HALF_DAY = "HALF_DAY", "Half Day"
        REMOTE = "REMOTE", "Remote"
        ABSENT = "ABSENT", "Absent"

    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        BIOMETRIC = "BIOMETRIC", "Biometric"
        REGULARIZATION = "REGULARIZATION", "Regularization"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendances")
    attendance_date = models.DateField(db_index=True)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    current_session_check_in = models.DateTimeField(null=True, blank=True)
    break_started_at = models.DateTimeField(null=True, blank=True)
    break_minutes = models.PositiveIntegerField(default=0)
    break_count = models.PositiveIntegerField(default=0)
    current_session_break_minutes = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PRESENT, db_index=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL, db_index=True)
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
            models.Index(fields=["organization", "attendance_date", "status"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.attendance_date}"


class BiometricDevice(OrganizationScopedModel):
    name = models.CharField(max_length=140)
    device_code = models.CharField(max_length=80, unique=True)
    secret_key = models.CharField(max_length=160)
    location_name = models.CharField(max_length=140, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name", "device_code"]

    def __str__(self):
        return f"{self.name} ({self.device_code})"


class BiometricAttendanceEvent(OrganizationScopedModel):
    class EventType(models.TextChoices):
        CHECK_IN = "CHECK_IN", "Check In"
        CHECK_OUT = "CHECK_OUT", "Check Out"
        BREAK_START = "BREAK_START", "Break Start"
        BREAK_END = "BREAK_END", "Break End"
        AUTO = "AUTO", "Auto"

    class Status(models.TextChoices):
        PROCESSED = "PROCESSED", "Processed"
        IGNORED = "IGNORED", "Ignored"
        FAILED = "FAILED", "Failed"

    device = models.ForeignKey(BiometricDevice, on_delete=models.PROTECT, related_name="attendance_events")
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="biometric_events")
    attendance = models.ForeignKey(Attendance, on_delete=models.SET_NULL, null=True, blank=True, related_name="biometric_events")
    device_user_id = models.CharField(max_length=80)
    external_event_id = models.CharField(max_length=120, null=True, blank=True)
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    occurred_at = models.DateTimeField(db_index=True)
    raw_payload = models.JSONField(blank=True, default=dict)
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSED, db_index=True)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ["-occurred_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["device", "external_event_id"],
                name="unique_biometric_device_external_event",
            )
        ]
        indexes = [
            models.Index(fields=["device", "device_user_id", "occurred_at"]),
            models.Index(fields=["employee", "occurred_at"]),
            models.Index(fields=["organization", "occurred_at", "status"]),
        ]

    def __str__(self):
        return f"{self.device.device_code} - {self.device_user_id} - {self.event_type}"


class AttendanceRegularization(OrganizationScopedModel):
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
            models.Index(fields=["organization", "date", "status"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.date} - {self.status}"
