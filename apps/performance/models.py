from django.db import models

from apps.core.models import OrganizationScopedModel
from apps.employees.models import Employee


class RatingScale(OrganizationScopedModel):
    name = models.CharField(max_length=120, unique=True)
    min_rating = models.DecimalField(max_digits=4, decimal_places=1, default=1)
    max_rating = models.DecimalField(max_digits=4, decimal_places=1, default=5)
    labels = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PerformanceCycle(OrganizationScopedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        CLOSED = "CLOSED", "Closed"

    name = models.CharField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    self_review_due_date = models.DateField()
    manager_review_due_date = models.DateField()
    hr_review_due_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    rating_scale = models.ForeignKey(
        RatingScale,
        on_delete=models.SET_NULL,
        related_name="performance_cycles",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-start_date", "name"]
        indexes = [
            models.Index(fields=["status", "start_date"]),
            models.Index(fields=["organization", "status", "start_date"]),
        ]

    def __str__(self):
        return self.name


class PerformanceGoal(OrganizationScopedModel):
    class Category(models.TextChoices):
        GOAL = "GOAL", "Goal"
        KRA = "KRA", "KRA"
        KPI = "KPI", "KPI"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"

    cycle = models.ForeignKey(PerformanceCycle, on_delete=models.CASCADE, related_name="goals")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="performance_goals")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.GOAL)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    target_value = models.CharField(max_length=160, blank=True)
    progress_value = models.CharField(max_length=160, blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)

    class Meta:
        ordering = ["cycle__start_date", "employee__employee_id", "title"]
        indexes = [
            models.Index(fields=["cycle", "employee", "status"]),
            models.Index(fields=["organization", "status", "cycle"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.title}"


class PerformanceReview(OrganizationScopedModel):
    class Status(models.TextChoices):
        SELF_PENDING = "SELF_PENDING", "Self Review Pending"
        MANAGER_PENDING = "MANAGER_PENDING", "Manager Review Pending"
        HR_PENDING = "HR_PENDING", "HR Review Pending"
        COMPLETED = "COMPLETED", "Completed"
        REJECTED = "REJECTED", "Rejected"

    cycle = models.ForeignKey(PerformanceCycle, on_delete=models.CASCADE, related_name="reviews")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="performance_reviews")
    manager = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        related_name="managed_performance_reviews",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SELF_PENDING, db_index=True)
    self_summary = models.TextField(blank=True)
    self_rating = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    manager_summary = models.TextField(blank=True)
    manager_rating = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    hr_summary = models.TextField(blank=True)
    final_rating = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    manager_reviewed_at = models.DateTimeField(null=True, blank=True)
    hr_reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-cycle__start_date", "employee__employee_id"]
        constraints = [
            models.UniqueConstraint(fields=["cycle", "employee"], name="unique_performance_review_cycle_employee")
        ]
        indexes = [
            models.Index(fields=["status", "cycle"]),
            models.Index(fields=["employee", "cycle"]),
            models.Index(fields=["organization", "status", "cycle"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.cycle.name}"
