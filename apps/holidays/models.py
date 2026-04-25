from django.db import models

from apps.core.models import OrganizationScopedModel
from apps.employees.models import Employee


class HolidayCalendar(OrganizationScopedModel):
    name = models.CharField(max_length=160)
    country_code = models.CharField(max_length=10, db_index=True)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.country_code})"


class Holiday(OrganizationScopedModel):
    calendar = models.ForeignKey(HolidayCalendar, on_delete=models.CASCADE, related_name="holidays")
    name = models.CharField(max_length=160)
    date = models.DateField(db_index=True)
    is_optional = models.BooleanField(default=False)

    class Meta:
        ordering = ["date", "name"]
        constraints = [
            models.UniqueConstraint(fields=["calendar", "date", "name"], name="unique_holiday_calendar_date_name"),
        ]
        indexes = [
            models.Index(fields=["calendar", "date"]),
            models.Index(fields=["organization", "date"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.date}"


class EmployeeHolidayAssignment(OrganizationScopedModel):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name="holiday_assignment")
    calendar = models.ForeignKey(HolidayCalendar, on_delete=models.CASCADE, related_name="employee_assignments")

    class Meta:
        ordering = ["employee__employee_id"]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.calendar.name}"
